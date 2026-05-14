"""Main bot application."""
import sys
from pathlib import Path

# Add project root to Python path to allow imports from any directory
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
import calendar
import logging
import threading
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError, AuthKeyUnregisteredError

from bot.config import Config
from bot.storage.database import Database
from bot.storage.user_storage import UserStorage
from bot.storage.scheduled_storage import ScheduledStorage
from bot.handlers.user_state import UserState, UserStateManager
from bot.handlers.group_handler import fetch_user_groups, get_group_name

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Tashkent timezone
TASHKENT_TZ = pytz.timezone('Asia/Tashkent')
GROUP_STAGGER_SECONDS = 5


class MessengerBot:
    """Main bot handler."""
    
    def __init__(self, config: Config):
        """Initialize bot."""
        self.config = config
        self.db = Database(config)
        self.user_storage = UserStorage(self.db)
        self.scheduled_storage = ScheduledStorage(self.db)
        self.state_manager = UserStateManager()
        self.clients: Dict[int, TelegramClient] = {}
        self.clients_lock = threading.Lock()
        self.scheduler = AsyncIOScheduler(timezone=TASHKENT_TZ)
        self.last_sent_times: Dict[int, datetime] = {}  # Track last sent time for each scheduled message
        self.last_sent_lock = threading.Lock()
        self.group_send_lock = threading.Lock()
        self.active_group_cycles: Set[tuple[int, int, int]] = set()
        self.send_batches: Dict[str, Dict] = {}
        self.activation_request_sent: Set[int] = set()
        self.scheduler.start()
        
        # Validate APP_ID and APP_HASH
        self._validate_telegram_credentials()
        
        # Initialize bot application
        self.application = Application.builder().token(config.BOT_TOKEN).build()
        
        # Register handlers
        self._register_handlers()
        
        # Connect to database
        self.db.connect()
        
        # Ensure required tables exist
        self._ensure_tables_exist()
        
        # Start periodic deactivation check
        self.scheduler.add_job(
            self._check_expired_users,
            'interval',
            minutes=1,
            id='check_expired_users'
        )
        
        # Start periodic payment deadline check
        self.scheduler.add_job(
            self._check_expired_payments,
            'interval',
            minutes=1,
            id='check_expired_payments'
        )
        
        # Start periodic scheduled messages sending
        self.scheduler.add_job(
            self._send_scheduled_messages,
            'interval',
            seconds=GROUP_STAGGER_SECONDS,
            id='send_scheduled_messages'
        )
    
    def _ensure_tables_exist(self):
        """Ensure required database tables exist."""
        try:
            conn = self.db.get_connection()
            try:
                with conn.cursor() as cur:
                    # Check and create scheduled_messages table
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'scheduled_messages'
                        );
                    """)
                    exists = cur.fetchone()[0]
                    
                    if not exists:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS scheduled_messages (
                                id SERIAL PRIMARY KEY,
                                user_id BIGINT NOT NULL,
                                message TEXT NOT NULL,
                                interval_minutes INTEGER NOT NULL,
                                paused BOOLEAN NOT NULL DEFAULT FALSE,
                                expires_at TIMESTAMPTZ,
                                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                            );
                        """)
                        logger.info("✅ Created scheduled_messages table")
                        print("✅ Created scheduled_messages table")
                    
                    # Check and create scheduled_message_groups table
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'scheduled_message_groups'
                        );
                    """)
                    exists = cur.fetchone()[0]
                    
                    if not exists:
                        # Create table without foreign key first
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS scheduled_message_groups (
                                scheduled_id INTEGER NOT NULL,
                                group_id BIGINT NOT NULL,
                                PRIMARY KEY (scheduled_id, group_id)
                            );
                        """)
                        logger.info("✅ Created scheduled_message_groups table")
                        print("✅ Created scheduled_message_groups table")
                        
                        # Add foreign key constraint if scheduled_messages exists
                        cur.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = 'scheduled_messages'
                            );
                        """)
                        if cur.fetchone()[0]:
                            cur.execute("""
                                DO $$
                                BEGIN
                                    IF NOT EXISTS (
                                        SELECT 1 FROM information_schema.table_constraints 
                                        WHERE constraint_name = 'scheduled_message_groups_scheduled_id_fkey'
                                    ) THEN
                                        ALTER TABLE scheduled_message_groups 
                                        ADD CONSTRAINT scheduled_message_groups_scheduled_id_fkey 
                                        FOREIGN KEY (scheduled_id) REFERENCES scheduled_messages(id) ON DELETE CASCADE;
                                    END IF;
                                END $$;
                            """)

                    cur.execute("""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns
                                WHERE table_name = 'scheduled_message_groups'
                                  AND column_name = 'send_offset_seconds'
                            ) THEN
                                ALTER TABLE scheduled_message_groups
                                ADD COLUMN send_offset_seconds INTEGER NOT NULL DEFAULT 0;
                            END IF;

                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns
                                WHERE table_name = 'scheduled_message_groups'
                                  AND column_name = 'last_sent_at'
                            ) THEN
                                ALTER TABLE scheduled_message_groups
                                ADD COLUMN last_sent_at TIMESTAMPTZ;
                            END IF;
                        END $$;
                    """)
                    
                    # Check and create user_last_groups table
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'user_last_groups'
                        );
                    """)
                    table_exists = cur.fetchone()[0]

                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns
                            WHERE table_name = 'user_last_groups' AND column_name = 'group_id'
                        );
                    """)
                    has_group_id_column = cur.fetchone()[0]

                    if table_exists and not has_group_id_column:
                        cur.execute("DROP TABLE user_last_groups")
                        table_exists = False
                        logger.info("Recreated user_last_groups table with updated schema")
                        print("Recreated user_last_groups table with updated schema")

                    if not table_exists:
                        cur.execute("""
                            CREATE TABLE user_last_groups (
                                user_id BIGINT NOT NULL,
                                group_id BIGINT NOT NULL,
                                PRIMARY KEY (user_id, group_id)
                            );
                        """)
                        logger.info("✅ Created user_last_groups table")
                        print("✅ Created user_last_groups table")

                    cur.execute("""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns
                                WHERE table_name = 'users' AND column_name = 'is_superuser'
                            ) THEN
                                ALTER TABLE users ADD COLUMN is_superuser BOOLEAN NOT NULL DEFAULT FALSE;
                            END IF;
                        END $$;
                    """)
                    
                    conn.commit()
            finally:
                self.db.put_connection(conn)
        except Exception as e:
            logger.error(f"Error ensuring tables exist: {e}")
            print(f"Error ensuring tables exist: {e}")
    
    def _validate_telegram_credentials(self):
        """Validate APP_ID and APP_HASH credentials."""
        logger.info("=" * 60)
        logger.info("Validating Telegram API credentials...")
        logger.info(f"APP_ID: {self.config.APP_ID}")
        logger.info(f"APP_HASH: {'*' * (len(self.config.APP_HASH) - 4) + self.config.APP_HASH[-4:] if len(self.config.APP_HASH) > 4 else '****'}")
        print("=" * 60)
        print("Validating Telegram API credentials...")
        print(f"APP_ID: {self.config.APP_ID}")
        print(f"APP_HASH: {'*' * (len(self.config.APP_HASH) - 4) + self.config.APP_HASH[-4:] if len(self.config.APP_HASH) > 4 else '****'}")
        
        if not self.config.APP_ID or self.config.APP_ID == 0:
            logger.error("❌ APP_ID is missing or invalid!")
            print("❌ APP_ID is missing or invalid!")
            return False
        
        if not self.config.APP_HASH or len(self.config.APP_HASH) < 10:
            logger.error("❌ APP_HASH is missing or invalid!")
            print("❌ APP_HASH is missing or invalid!")
            return False
        
        logger.info("✅ APP_ID and APP_HASH format validation passed")
        logger.info("Note: Full validation will occur when user authenticates")
        print("✅ APP_ID and APP_HASH format validation passed")
        print("Note: Full validation will occur when user authenticates")
        logger.info("=" * 60)
        print("=" * 60)
        return True

    def _is_superuser(self, user_id: int) -> bool:
        """Return whether the Telegram user can approve access."""
        return self.user_storage.is_admin(user_id)

    def _awaiting_activation_message(self) -> str:
        """Message shown to users waiting for admin approval."""
        return (
            "✅ Akkauntingiz tasdiqlandi.\n\n"
            "Admin kirish huquqini ko'rib chiqmoqda. Tasdiqlangandan keyin sizga xabar beriladi."
        )

    def _shift_access_calendar_month(self, year: int, month: int, offset: int) -> tuple[int, int]:
        """Move calendar month by offset."""
        month += offset
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        return year, month

    def _build_access_calendar_keyboard(self, target_user_id: int, year: int, month: int) -> InlineKeyboardMarkup:
        """Build inline calendar for superuser access approval."""
        prev_year, prev_month = self._shift_access_calendar_month(year, month, -1)
        next_year, next_month = self._shift_access_calendar_month(year, month, 1)
        month_name = calendar.month_name[month]

        keyboard = [[
            InlineKeyboardButton("◀️", callback_data=f"access_cal_{target_user_id}_{prev_year}_{prev_month}"),
            InlineKeyboardButton(f"{month_name} {year}", callback_data="access_ignore"),
            InlineKeyboardButton("▶️", callback_data=f"access_cal_{target_user_id}_{next_year}_{next_month}"),
        ]]

        for week in calendar.monthcalendar(year, month):
            row = []
            for day in week:
                if day == 0:
                    continue
                date_value = f"{year}-{month:02d}-{day:02d}"
                row.append(
                    InlineKeyboardButton(
                        str(day),
                        callback_data=f"access_day_{target_user_id}_{date_value}"
                    )
                )
            if row:
                keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton("❌ Rad etish", callback_data=f"access_reject_{target_user_id}")
        ])
        return InlineKeyboardMarkup(keyboard)

    async def _notify_superusers_about_activation_request(self, user_id: int):
        """Send activation request with calendar to superusers."""
        if user_id in self.activation_request_sent:
            return

        user = self.user_storage.get_user(user_id)
        if not user or user.auth != 1 or user.status != 0:
            return

        superusers = self.user_storage.get_superuser_ids()
        if not superusers:
            logger.warning(f"No superusers configured for activation request of user {user_id}")
            return

        now = datetime.now(TASHKENT_TZ)
        text = (
            "🆕 Yangi foydalanuvchi aktivatsiya kutmoqda\n\n"
            f"ID: {user.id}\n"
            f"Ism: {user.full_name or '—'}\n"
            f"Telefon: {user.phone or '—'}\n\n"
            "Qaysi sanagacha aktiv qilasiz?"
        )
        reply_markup = self._build_access_calendar_keyboard(user.id, now.year, now.month)

        sent_any = False
        for superuser_id in superusers:
            if superuser_id == user_id:
                continue
            try:
                await self.application.bot.send_message(superuser_id, text, reply_markup=reply_markup)
                sent_any = True
            except Exception as e:
                logger.error(f"Failed to notify superuser {superuser_id} about user {user_id}: {e}")

        if sent_any:
            self.activation_request_sent.add(user_id)

    async def _maybe_request_activation_review(self, user_id: int):
        """Notify superusers once the user finished authentication."""
        user = self.user_storage.get_user(user_id)
        if not user or user.auth != 1 or user.status != 0:
            return
        if not user.full_name:
            return
        await self._notify_superusers_about_activation_request(user_id)

    async def _activate_user_access(self, target_user_id: int, active_until: datetime, admin_chat_id: int):
        """Activate user until selected date and notify both sides."""
        active_until = active_until.astimezone(TASHKENT_TZ)
        if not self.user_storage.activate_user_until(target_user_id, active_until):
            await self.application.bot.send_message(admin_chat_id, "⚠️ Foydalanuvchini aktivlashtirib bo'lmadi.")
            return

        active_until_text = active_until.strftime("%d.%m.%Y")
        await self.application.bot.send_message(
            admin_chat_id,
            f"✅ Foydalanuvchi {target_user_id} {active_until_text} gacha aktiv qilindi."
        )
        await self.application.bot.send_message(
            target_user_id,
            f"✅ Akkauntingiz aktiv qilindi. Kirish muddati: {active_until_text} gacha.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📤 Xabar yuborish", callback_data="action_send_message"),
                InlineKeyboardButton("📋 Xabarlar jadvali", callback_data="action_messages_table"),
            ], [
                InlineKeyboardButton("📹 Video qo'llanma", callback_data="action_video_tutorial"),
            ]])
        )

    async def _reject_user_access(self, target_user_id: int, admin_chat_id: int):
        """Reject pending user activation."""
        await self.application.bot.send_message(
            admin_chat_id,
            f"❌ Foydalanuvchi {target_user_id} uchun aktivatsiya rad etildi."
        )
        await self.application.bot.send_message(
            target_user_id,
            "❌ Akkauntingiz aktivatsiyasi rad etildi. Qo'shimcha ma'lumot uchun @system24admin bilan bog'laning."
        )

    async def _handle_access_approval_callback(self, query, data: str):
        """Handle superuser activation calendar callbacks."""
        admin_id = query.from_user.id
        if not self._is_superuser(admin_id):
            await query.answer("Bu amal faqat superuser uchun.", show_alert=True)
            return

        if data == "access_ignore":
            await query.answer()
            return

        if data.startswith("access_cal_"):
            parts = data.split("_")
            target_user_id = int(parts[2])
            year = int(parts[3])
            month = int(parts[4])
            await query.edit_message_reply_markup(
                reply_markup=self._build_access_calendar_keyboard(target_user_id, year, month)
            )
            return

        if data.startswith("access_day_"):
            parts = data.split("_")
            target_user_id = int(parts[2])
            date_value = parts[3]
            selected_date = datetime.strptime(date_value, "%Y-%m-%d").date()
            active_until = TASHKENT_TZ.localize(
                datetime.combine(selected_date, datetime.max.time().replace(microsecond=0))
            )
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Tasdiqlash",
                        callback_data=f"access_confirm_{target_user_id}_{date_value}"
                    ),
                    InlineKeyboardButton(
                        "⬅️ Orqaga",
                        callback_data=f"access_back_cal_{target_user_id}_{selected_date.year}_{selected_date.month}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "❌ Rad etish",
                        callback_data=f"access_reject_{target_user_id}"
                    )
                ],
            ])
            await query.edit_message_text(
                f"📅 Foydalanuvchi {target_user_id} {selected_date.strftime('%d.%m.%Y')} gacha aktiv qilinsinmi?",
                reply_markup=keyboard
            )
            return

        if data.startswith("access_back_cal_"):
            parts = data.split("_")
            target_user_id = int(parts[3])
            year = int(parts[4])
            month = int(parts[5])
            user = self.user_storage.get_user(target_user_id)
            text = (
                "🆕 Yangi foydalanuvchi aktivatsiya kutmoqda\n\n"
                f"ID: {target_user_id}\n"
                f"Ism: {user.full_name if user and user.full_name else '—'}\n"
                f"Telefon: {user.phone if user and user.phone else '—'}\n\n"
                "Qaysi sanagacha aktiv qilasiz?"
            )
            await query.edit_message_text(
                text,
                reply_markup=self._build_access_calendar_keyboard(target_user_id, year, month)
            )
            return

        if data.startswith("access_confirm_"):
            parts = data.split("_")
            target_user_id = int(parts[2])
            date_value = parts[3]
            selected_date = datetime.strptime(date_value, "%Y-%m-%d").date()
            active_until = TASHKENT_TZ.localize(
                datetime.combine(selected_date, datetime.max.time().replace(microsecond=0))
            )
            await self._activate_user_access(target_user_id, active_until, query.message.chat_id)
            return

        if data.startswith("access_reject_"):
            target_user_id = int(data.split("_")[2])
            await self._reject_user_access(target_user_id, query.message.chat_id)
            return
    
    def _register_handlers(self):
        """Register bot handlers."""
        self.application.add_handler(CommandHandler("start", self.handle_start))
        self.application.add_handler(CommandHandler("admin", self.handle_admin))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        # Handle contact messages (phone number sharing)
        self.application.add_handler(MessageHandler(filters.CONTACT, self.handle_contact))
        # Handle video messages (for getting file_id)
        self.application.add_handler(MessageHandler(filters.VIDEO, self.handle_video_message))
        self.application.add_handler(MessageHandler(filters.Document.VIDEO, self.handle_video_document))
        # Handle text messages (but not commands)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        # Handle user leaving/blocking the bot
        self.application.add_handler(ChatMemberHandler(self.handle_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    
    async def _get_or_create_client(self, user_id: int) -> Optional[TelegramClient]:
        """Get or create Telegram client for user. Sessions are preserved and restored automatically."""
        with self.clients_lock:
            if user_id in self.clients:
                client = self.clients[user_id]
                # Verify client is still valid
                try:
                    if not client.is_connected():
                        await client.connect()
                    # Quick check if session is valid
                    try:
                        await client.get_me()
                        return client
                    except (AuthKeyUnregisteredError, Exception):
                        # Session might be expired, but keep it and try to reconnect
                        logger.warning(f"[CLIENT] Session check failed for user {user_id}, but keeping session file")
                        pass
                except Exception as e:
                    logger.warning(f"[CLIENT] Error checking client for user {user_id}: {e}")
                return client
            
            # Validate APP_ID and APP_HASH before creating client
            logger.info(f"[CLIENT] Creating/restoring Telegram client for user {user_id}")
            logger.info(f"[CLIENT] APP_ID: {self.config.APP_ID}, APP_HASH: {'*' * (len(self.config.APP_HASH) - 4) + self.config.APP_HASH[-4:] if len(self.config.APP_HASH) > 4 else '****'}")
            print(f"[CLIENT] Creating/restoring Telegram client for user {user_id}")
            print(f"[CLIENT] APP_ID: {self.config.APP_ID}")
            print(f"[CLIENT] APP_HASH: {'*' * (len(self.config.APP_HASH) - 4) + self.config.APP_HASH[-4:] if len(self.config.APP_HASH) > 4 else '****'}")
            
            # Create sessions directory if it doesn't exist (inside bot folder)
            import os
            from pathlib import Path
            bot_dir = Path(__file__).resolve().parent
            sessions_dir = bot_dir / "sessions"
            if not sessions_dir.exists():
                sessions_dir.mkdir(exist_ok=True)
                logger.info(f"[CLIENT] Created sessions directory: {sessions_dir}")
                print(f"[CLIENT] Created sessions directory: {sessions_dir}")
            
            # Create new client with session file in sessions directory
            # Session file will be loaded if it exists, or created if it doesn't
            session_file = str(sessions_dir / f"tg_session_{user_id}.session")
            session_exists = os.path.exists(session_file)
            logger.info(f"[CLIENT] Session file path: {session_file} (exists: {session_exists})")
            print(f"[CLIENT] Session file path: {session_file} (exists: {session_exists})")
            
            client = TelegramClient(session_file, self.config.APP_ID, self.config.APP_HASH)
            self.clients[user_id] = client
            
            if session_exists:
                logger.info(f"[CLIENT] ✅ Telegram client restored from existing session for user {user_id}")
                print(f"[CLIENT] ✅ Telegram client restored from existing session for user {user_id}")
            else:
                logger.info(f"[CLIENT] ✅ Telegram client created successfully for user {user_id}")
                print(f"[CLIENT] ✅ Telegram client created successfully for user {user_id}")
            
            return client
    
    async def _reset_telegram_session(self, user_id: int):
        """Remove stale Telethon session before a fresh login attempt."""
        client = self.clients.pop(user_id, None)
        if client:
            try:
                if client.is_connected():
                    await client.disconnect()
            except Exception as e:
                logger.warning(f"[CLIENT] Could not disconnect stale client for user {user_id}: {e}")

        sessions_dir = Path(__file__).resolve().parent / "sessions"
        for suffix in ("", "-journal"):
            session_path = sessions_dir / f"tg_session_{user_id}.session{suffix}"
            if session_path.exists():
                session_path.unlink()
                logger.info(f"[CLIENT] Removed stale session file: {session_path}")

    def _code_request_prompt(self, code_length: int = 5) -> str:
        """User-facing instructions after Telegram sends a login code."""
        formatted_code_hint = " ".join(["X"] * code_length)
        return (
            "📝 Telegram akkauntingizga yangi kod yuborildi.\n\n"
            f"Faqat oxirgi kelgan kodni kiriting (masalan: {formatted_code_hint}).\n"
            "Raqamlar orasini ochib kiriting"
        )

    async def _send_code_request(self, user_id: int, phone: str) -> bool:
        """Send code request to user's phone number."""
        try:
            await self._reset_telegram_session(user_id)
            logger.info(f"[CODE REQUEST] Sending code request to phone {phone} for user {user_id}")
            print(f"[CODE REQUEST] Sending code request to phone {phone} for user {user_id}")
            
            client = await self._get_or_create_client(user_id)
            if not client.is_connected():
                logger.info(f"[CODE REQUEST] Connecting Telegram client for user {user_id}")
                print(f"[CODE REQUEST] Connecting Telegram client for user {user_id}")
                await client.connect()
            
            # Send code request
            logger.info(f"[CODE REQUEST] Requesting code for phone {phone}")
            print(f"[CODE REQUEST] Requesting code for phone {phone}")
            result = await client.send_code_request(phone)
            
            logger.info(f"[CODE REQUEST] ✅ Code request sent successfully. Phone hash: {result.phone_code_hash[:10]}...")
            print(f"[CODE REQUEST] ✅ Code request sent successfully. Phone hash: {result.phone_code_hash[:10]}...")
            
            # Store phone code hash for later use
            state = self.state_manager.get_state(user_id)
            state.phone_code_hash = result.phone_code_hash
            
            # Format code display message (e.g., "7 3 4 6 8")
            code_length = result.type.length if hasattr(result.type, 'length') else 5
            formatted_code_hint = " ".join(["X"] * code_length)
            logger.info(f"[CODE REQUEST] Code format hint: {formatted_code_hint} (length: {code_length})")
            print(f"[CODE REQUEST] Code format hint: {formatted_code_hint} (length: {code_length})")
            
            return True
        except Exception as e:
            logger.error(f"[CODE REQUEST] ❌ Error sending code request for user {user_id}: {e}", exc_info=True)
            print(f"[CODE REQUEST] ❌ Error sending code request for user {user_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _save_session_json(self, user_id: int, client: TelegramClient):
        """Save session information to JSON file."""
        try:
            import os
            import json
            from datetime import datetime
            
            # Ensure client is connected
            if not client.is_connected():
                await client.connect()
            
            # Get user's own entity
            me = await client.get_me()
            
            # Prepare session data
            session_data = {
                "user_id": user_id,
                "telegram_id": me.id,
                "username": me.username if me.username else None,
                "first_name": me.first_name if me.first_name else None,
                "last_name": me.last_name if me.last_name else None,
                "phone": me.phone if me.phone else None,
                "authenticated_at": datetime.now().isoformat(),
                "session_file": client.session.filename if hasattr(client.session, 'filename') else None
            }
            
            # Save to JSON file in sessions directory (inside bot folder)
            from pathlib import Path
            bot_dir = Path(__file__).resolve().parent
            sessions_dir = bot_dir / "sessions"
            if not sessions_dir.exists():
                sessions_dir.mkdir(exist_ok=True)
            
            json_file = str(sessions_dir / f"session_{user_id}.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[SESSION JSON] ✅ Session data saved to {json_file}")
            print(f"[SESSION JSON] ✅ Session data saved to {json_file}")
            
        except Exception as e:
            logger.error(f"[SESSION JSON] ❌ Error saving session JSON for user {user_id}: {e}", exc_info=True)
            print(f"[SESSION JSON] ❌ Error saving session JSON for user {user_id}: {e}")
            # Don't raise exception, just log the error
    
    async def _send_login_message(self, user_id: int, client: TelegramClient):
        """Send login message to user's Telegram account."""
        try:
            logger.info(f"[LOGIN MESSAGE] Preparing to send login message to user {user_id}")
            print(f"[LOGIN MESSAGE] Preparing to send login message to user {user_id}")
            
            # Ensure client is connected
            if not client.is_connected():
                logger.info(f"[LOGIN MESSAGE] Connecting client for user {user_id}")
                print(f"[LOGIN MESSAGE] Connecting client for user {user_id}")
                await client.connect()
            
            # Get user's own entity (Saved Messages)
            me = await client.get_me()
            logger.info(f"[LOGIN MESSAGE] User {user_id} authenticated as Telegram ID: {me.id}, Username: @{me.username if me.username else 'N/A'}")
            print(f"[LOGIN MESSAGE] User {user_id} authenticated as Telegram ID: {me.id}, Username: @{me.username if me.username else 'N/A'}")
            
            # Save session to JSON
            await self._save_session_json(user_id, client)
            
            # Message to send
            login_message = "✅ Sizning Telegram akkauntingizga muvaffaqiyatli kirildi!\n\nBot orqali xabarlarni yuborish tizimi faollashtirildi."
            
            logger.info(f"[LOGIN MESSAGE] Sending message to Saved Messages for user {user_id}")
            print(f"[LOGIN MESSAGE] Sending message to Saved Messages for user {user_id}")
            
            # Send message to user's Saved Messages
            sent_message = await client.send_message('me', login_message)
            
            logger.info(f"[LOGIN MESSAGE] ✅ Login message successfully sent to user {user_id} (Telegram ID: {me.id}, Message ID: {sent_message.id})")
            print(f"[LOGIN MESSAGE] ✅ Login message successfully sent to user {user_id} (Telegram ID: {me.id}, Message ID: {sent_message.id})")
            
        except Exception as e:
            logger.error(f"[LOGIN MESSAGE] ❌ Error sending login message to user {user_id}: {e}", exc_info=True)
            print(f"[LOGIN MESSAGE] ❌ Error sending login message to user {user_id}: {e}")
            import traceback
            traceback.print_exc()
            # Don't raise exception, just log the error
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        user = self.user_storage.get_user(user_id)
        if not user:
            # New user - create in database with status=0 and auth=0
            logger.info(f"[START] New user detected: {user_id}")
            print(f"[START] New user detected: {user_id}")
            self.user_storage.insert_user(user_id)
            user = self.user_storage.get_user(user_id)
        
        # Check if user was retrieved successfully
        if not user:
            logger.error(f"[START] Failed to retrieve user {user_id} after insertion")
            print(f"[START] Failed to retrieve user {user_id} after insertion")
            await update.message.reply_text("⚠️ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
            return
        
        # Check if user is waiting for name input
        state = self.state_manager.get_state(user_id)
        if state.step == "waiting_for_name":
            await update.message.reply_text("Ism Familiyangiz:", reply_markup=None)
            return
        
        # Check authentication first (regardless of status)
        if user.auth == 0:
            # Need authentication - this is required for all users
            logger.info(f"[START] User {user_id} needs authentication (auth=0)")
            print(f"[START] User {user_id} needs authentication (auth=0)")
            state.step = "waiting_for_phone"
            # Create keyboard with contact button
            keyboard = [[KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text(
                "👋 Xush kelibsiz!\n\n"
                "📱 Avval Telegram akkauntingizga kirish uchun telefon raqamingizni yuboring yoki kiriting (masalan: +998901234567):",
                reply_markup=reply_markup
            )
            return
        
        # User is authenticated, check status
        if user.status == 0:
            # User authenticated but not activated by admin
            logger.info(f"[START] User {user_id} is authenticated but not activated (status=0)")
            print(f"[START] User {user_id} is authenticated but not activated (status=0)")
            await update.message.reply_text(self._awaiting_activation_message())
            await self._maybe_request_activation_review(user_id)
            return
        logger.info(f"[START] User {user_id} is authenticated and activated, showing main menu")
        print(f"[START] User {user_id} is authenticated and activated, showing main menu")
        await self._show_main_menu(chat_id)
    
    async def handle_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Check if user is waiting for name input
        state = self.state_manager.get_state(user_id)
        if state.step == "waiting_for_name":
            await update.message.reply_text("Ism Familiyangiz:", reply_markup=None)
            return
        
        # Check if user is active
        user = self.user_storage.get_user(user_id)
        if user and user.status == 0:
            await update.message.reply_text(self._awaiting_activation_message())
            return
        
        # For all users, show contact message
        await update.message.reply_text("admin bilan bog'lanish: @system24admin")
    
    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle contact (phone number) sharing."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        state = self.state_manager.get_state(user_id)
        
        # Only process contact if we're waiting for phone
        if state.step != "waiting_for_phone":
            return
        
        contact = update.message.contact
        if not contact or not contact.phone_number:
            await update.message.reply_text(
                "❌ Telefon raqam olinmadi. Iltimos, qayta urinib ko'ring."
            )
            return
        
        # Get phone number from contact
        phone = contact.phone_number
        
        # Ensure phone starts with + (Telegram usually provides it)
        if not phone.startswith('+'):
            phone = '+' + phone
        
        # Validate phone number format: +998 followed by 9 digits (total 12 digits after +998)
        if not phone.startswith('+998'):
            await update.message.reply_text(
                "❌ Telefon raqam noto'g'ri formatda.\n\n"
                "Iltimos, +998 bilan boshlanadigan 12 xonali raqam kiriting (masalan: +998901234567):"
            )
            return
        
        # Remove +998 and check if remaining is 9 digits
        remaining = phone[4:].replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not remaining.isdigit() or len(remaining) != 9:
            await update.message.reply_text(
                "❌ Telefon raqam noto'g'ri formatda.\n\n"
                "Iltimos, +998 bilan boshlanadigan 12 xonali raqam kiriting (masalan: +998901234567):"
            )
            return
        
        # Format phone number properly: +998 + 9 digits
        formatted_phone = f"+998{remaining}"
        state.phone = formatted_phone
        # Save phone number to database
        self.user_storage.update_user_phone(user_id, formatted_phone)
        # Send code request to user's phone
        code_sent = await self._send_code_request(user_id, formatted_phone)
        if code_sent:
            state.step = "waiting_for_code"
            await update.message.reply_text(
                self._code_request_prompt(),
                reply_markup=None
            )
        else:
            await update.message.reply_text("❌ Kod yuborishda xatolik yuz berdi. Qayta urinib ko'ring.")
    
    def _update_env_file(self, file_id: str) -> bool:
        """Update .env file with new VIDEO_TUTORIAL_FILE_ID."""
        try:
            from pathlib import Path
            import re
            
            # Get project root directory
            project_root = Path(__file__).resolve().parent.parent
            env_file = project_root / ".env"
            
            if not env_file.exists():
                logger.warning(f".env file not found at {env_file}")
                return False
            
            # Read .env file
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update or add VIDEO_TUTORIAL_FILE_ID
            pattern = r'^VIDEO_TUTORIAL_FILE_ID=.*$'
            replacement = f'VIDEO_TUTORIAL_FILE_ID={file_id}'
            
            if re.search(pattern, content, re.MULTILINE):
                # Update existing line
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            else:
                # Add new line
                content += f'\n{replacement}\n'
            
            # Write back to .env file
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Reload config
            from dotenv import load_dotenv
            load_dotenv(override=True)
            self.config.VIDEO_TUTORIAL_FILE_ID = file_id
            
            logger.info(f"✅ Updated .env file with new VIDEO_TUTORIAL_FILE_ID: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating .env file: {e}", exc_info=True)
            return False
    
    async def handle_video_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video messages to get file_id."""
        user_id = update.effective_user.id
        video = update.message.video
        
        if video:
            file_id = video.file_id
            file_unique_id = video.file_unique_id
            
            # Get video info
            file_size = video.file_size
            duration = video.duration
            width = video.width
            height = video.height
            
            # Update .env file automatically
            env_updated = self._update_env_file(file_id)
            
            if env_updated:
                message = (
                    f"✅ Video qabul qilindi va .env fayli yangilandi!\n\n"
                    f"📹 File ID:\n<code>{file_id}</code>\n\n"
                    f"🆔 File Unique ID: {file_unique_id}\n"
                    f"📊 O'lcham: {width}x{height}\n"
                    f"⏱️ Davomiyligi: {duration} soniya\n"
                    f"💾 Hajmi: {file_size} bytes\n\n"
                    f"✅ .env fayli avtomatik yangilandi!\n"
                    f"Endi 'Video qo'llanma' tugmasi ishlaydi."
                )
            else:
                message = (
                    f"✅ Video qabul qilindi!\n\n"
                    f"📹 File ID:\n<code>{file_id}</code>\n\n"
                    f"🆔 File Unique ID: {file_unique_id}\n"
                    f"📊 O'lcham: {width}x{height}\n"
                    f"⏱️ Davomiyligi: {duration} soniya\n"
                    f"💾 Hajmi: {file_size} bytes\n\n"
                    f"⚠️ .env faylini avtomatik yangilab bo'lmadi.\n"
                    f"Quyidagi file_id ni .env fayliga qo'shing:\n"
                    f"<code>VIDEO_TUTORIAL_FILE_ID={file_id}</code>"
                )
            
            await update.message.reply_text(message, parse_mode='HTML')
            
            # Also print to console
            print("\n" + "=" * 60)
            print("VIDEO FILE_ID TOPILDI!")
            print("=" * 60)
            print(f"File ID: {file_id}")
            print(f"File Unique ID: {file_unique_id}")
            if env_updated:
                print("✅ .env fayli avtomatik yangilandi!")
            else:
                print(f"\n.env fayliga quyidagini qo'shing:")
                print(f"VIDEO_TUTORIAL_FILE_ID={file_id}")
            print("=" * 60 + "\n")
            
            logger.info(f"Video file_id received: {file_id}")
    
    async def handle_video_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video documents to get file_id."""
        user_id = update.effective_user.id
        document = update.message.document
        
        if document and document.mime_type and 'video' in document.mime_type:
            file_id = document.file_id
            file_unique_id = document.file_unique_id
            
            # Update .env file automatically
            env_updated = self._update_env_file(file_id)
            
            if env_updated:
                message = (
                    f"✅ Video fayl (document sifatida) qabul qilindi va .env fayli yangilandi!\n\n"
                    f"📹 File ID:\n<code>{file_id}</code>\n\n"
                    f"🆔 File Unique ID: {file_unique_id}\n"
                    f"📄 Fayl nomi: {document.file_name or 'Noma\'lum'}\n"
                    f"💾 Hajmi: {document.file_size} bytes\n\n"
                    f"✅ .env fayli avtomatik yangilandi!\n"
                    f"Endi 'Video qo'llanma' tugmasi ishlaydi."
                )
            else:
                message = (
                    f"✅ Video fayl (document sifatida) qabul qilindi!\n\n"
                    f"📹 File ID:\n<code>{file_id}</code>\n\n"
                    f"🆔 File Unique ID: {file_unique_id}\n"
                    f"📄 Fayl nomi: {document.file_name or 'Noma\'lum'}\n"
                    f"💾 Hajmi: {document.file_size} bytes\n\n"
                    f"⚠️ .env faylini avtomatik yangilab bo'lmadi.\n"
                    f"Quyidagi file_id ni .env fayliga qo'shing:\n"
                    f"<code>VIDEO_TUTORIAL_FILE_ID={file_id}</code>"
                )
            
            await update.message.reply_text(message, parse_mode='HTML')
            
            # Also print to console
            print("\n" + "=" * 60)
            print("VIDEO FILE_ID TOPILDI (document sifatida)!")
            print("=" * 60)
            print(f"File ID: {file_id}")
            print(f"File Unique ID: {file_unique_id}")
            if env_updated:
                print("✅ .env fayli avtomatik yangilandi!")
            else:
                print(f"\n.env fayliga quyidagini qo'shing:")
                print(f"VIDEO_TUTORIAL_FILE_ID={file_id}")
            print("=" * 60 + "\n")
            
            logger.info(f"Video file_id received (as document): {file_id}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        text = update.message.text
        
        state = self.state_manager.get_state(user_id)
        
        # Handle authentication flow
        if state.step == "waiting_for_phone":
            # Validate phone number format: +998 followed by 9 digits (total 12 digits after +998)
            phone = text.strip()
            if not phone.startswith('+998'):
                await update.message.reply_text(
                    "❌ Telefon raqam noto'g'ri formatda.\n\n"
                    "Iltimos, +998 bilan boshlanadigan 12 xonali raqam kiriting (masalan: +998901234567):"
                )
                return
            
            # Remove +998 and check if remaining is 9 digits
            remaining = phone[4:].replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            if not remaining.isdigit() or len(remaining) != 9:
                await update.message.reply_text(
                    "❌ Telefon raqam noto'g'ri formatda.\n\n"
                    "Iltimos, +998 bilan boshlanadigan 12 xonali raqam kiriting (masalan: +998901234567):"
                )
                return
            
            # Format phone number properly: +998 + 9 digits
            formatted_phone = f"+998{remaining}"
            state.phone = formatted_phone
            # Save phone number to database
            self.user_storage.update_user_phone(user_id, formatted_phone)
            # Send code request to user's phone
            code_sent = await self._send_code_request(user_id, formatted_phone)
            if code_sent:
                state.step = "waiting_for_code"
                await update.message.reply_text(
                    self._code_request_prompt(),
                    reply_markup=None
                )
            else:
                await update.message.reply_text("❌ Kod yuborishda xatolik yuz berdi. Qayta urinib ko'ring.")
            return
        
        if state.step == "waiting_for_code":
            # Clean code: remove all spaces and non-digit characters, keep only digits
            cleaned_code = ''.join(filter(str.isdigit, text))
            state.code = cleaned_code
            
            logger.info(f"[CODE INPUT] User {user_id} entered a login code ({len(cleaned_code)} digits)")
            
            if not cleaned_code or len(cleaned_code) < 4:
                await update.message.reply_text("❌ Kod noto'g'ri formatda. Iltimos, faqat raqamlarni kiriting:")
                return
            
            # Authenticate user
            result = await self._authenticate_user(user_id, state.phone, cleaned_code, state.phone_code_hash, chat_id)
            if result == "success":
                # Update auth status to 1
                self.user_storage.update_auth_status(user_id)
                
                # Check if user needs to provide full name
                user = self.user_storage.get_user(user_id)
                if user and not user.full_name:
                    # New user - ask for full name
                    state.step = "waiting_for_name"
                    await update.message.reply_text("Ism Familiyangiz:", reply_markup=None)
                    return
                
                state.step = ""
                
                # Check if user is activated
                if user and user.status == 1:
                    # User is activated, show main menu
                    await update.message.reply_text("✅ Autentifikatsiya muvaffaqiyatli!")
                    await self._show_main_menu(chat_id)
                else:
                    await update.message.reply_text(self._awaiting_activation_message())
                    await self._maybe_request_activation_review(user_id)
            elif result == "code_expired":
                code_sent = await self._send_code_request(user_id, state.phone)
                if code_sent:
                    state.step = "waiting_for_code"
                    await update.message.reply_text(
                        "⏰ Kod eskirib qolgan yoki allaqachon ishlatilgan.\n\n"
                        f"{self._code_request_prompt()}"
                    )
                else:
                    keyboard = [[KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)]]
                    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                    await update.message.reply_text(
                        "⏰ Kod eskirib qolgan. Yangi kod yuborish uchun telefon raqamingizni qayta yuboring yoki kiriting:",
                        reply_markup=reply_markup
                    )
                    state.step = "waiting_for_phone"
                    state.phone_code_hash = None
            elif result == "code_shared":
                code_sent = await self._send_code_request(user_id, state.phone)
                if code_sent:
                    state.step = "waiting_for_code"
                    await update.message.reply_text(
                        "🔒 Telegram bu kodni xavfsizlik sababli rad etdi, chunki u allaqachon boshqa joyda ishlatilgan.\n\n"
                        f"{self._code_request_prompt()}"
                    )
                else:
                    await update.message.reply_text(
                        "🔒 Telegram kirishni blokladi. Bir necha daqiqa kutib, telefon raqamingizni qayta yuboring."
                    )
                    state.step = "waiting_for_phone"
                    state.phone_code_hash = None
            elif result == "code_invalid":
                code_format = " ".join(["X"] * len(cleaned_code)) if cleaned_code else "X X X X X"
                await update.message.reply_text(
                    f"❌ Kod noto'g'ri. Iltimos, to'g'ri kodni kiriting:\n"
                    f"Masalan: {code_format}"
                )
            elif result == "password_needed":
                # Password required - state already set in _authenticate_user
                await update.message.reply_text(
                    "🔐 Sizning akkauntingizda ikki bosqichli autentifikatsiya (2FA) yoqilgan.\n"
                    "Iltimos, parolingizni kiriting:"
                )
            else:
                logger.error(f"[AUTH] Unknown result: {result}")
                print(f"[AUTH] Unknown result: {result}")
                await update.message.reply_text("❌ Autentifikatsiya muvaffaqiyatsiz. Qayta urinib ko'ring.")
            return
        
        if state.step == "waiting_for_password":
            state.password = text
            logger.info(f"[PASSWORD INPUT] User {user_id} entered password")
            print(f"[PASSWORD INPUT] User {user_id} entered password")
            # Handle password authentication
            success = await self._authenticate_user_password(user_id, state.password)
            if success:
                # Update auth status to 1
                self.user_storage.update_auth_status(user_id)
                state.password = None  # Clear password from state
                
                # Check if user needs to provide full name
                user = self.user_storage.get_user(user_id)
                if user and not user.full_name:
                    # New user - ask for full name
                    state.step = "waiting_for_name"
                    await update.message.reply_text("Ism Familiyangiz:", reply_markup=None)
                    return
                
                state.step = ""
                
                # Check if user is activated
                if user and user.status == 1:
                    # User is activated, show main menu
                    await update.message.reply_text("✅ Autentifikatsiya muvaffaqiyatli!")
                    await self._show_main_menu(chat_id)
                else:
                    await update.message.reply_text(self._awaiting_activation_message())
                    await self._maybe_request_activation_review(user_id)
            else:
                await update.message.reply_text(
                    "❌ Parol noto'g'ri. Iltimos, to'g'ri parolni kiriting:"
                )
            return
        
        # Handle full name input
        if state.step == "waiting_for_name":
            # Check if user sent a command - ignore it and ask again
            if text.startswith('/'):
                await update.message.reply_text("Ism Familiyangiz:", reply_markup=None)
                return
            
            full_name = text.strip()
            # Validate that it's a proper name (not empty, has at least 2 characters, not just numbers/symbols)
            if not full_name or len(full_name) < 2:
                await update.message.reply_text("❌ Ism bo'sh bo'lishi yoki juda qisqa bo'lishi mumkin emas. Iltimos, to'liq ism familiyangizni kiriting:")
                return
            
            # Check if it's mostly letters (allow spaces and some special characters)
            if not any(c.isalpha() for c in full_name):
                await update.message.reply_text("❌ Iltimos, to'g'ri ism familiyangizni kiriting (faqat raqamlar yoki belgilar emas):")
                return
            
            # Save full name to database
            self.user_storage.update_user_full_name(user_id, full_name)
            state.step = ""
            
            # Check if user is activated
            user = self.user_storage.get_user(user_id)
            if user and user.status == 1:
                # User is activated, show main menu
                await update.message.reply_text("✅ Autentifikatsiya muvaffaqiyatli!")
                await self._show_main_menu(chat_id)
            else:
                await update.message.reply_text(self._awaiting_activation_message())
                await self._maybe_request_activation_review(user_id)
            return
        if state.step == "waiting_for_message":
            state.pending_message = text
            state.step = ""
            await self._show_group_selection(chat_id, user_id)
            return
        
        # Handle unknown commands/text - check user status
        user = self.user_storage.get_user(user_id)
        if user:
            if user.auth == 0:
                # Not authenticated, show auth prompt
                state = self.state_manager.get_state(user_id)
                state.step = "waiting_for_phone"
                # Create keyboard with contact button
                keyboard = [[KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                await update.message.reply_text(
                    "👋 Xush kelibsiz!\n\n"
                    "📱 Avval Telegram akkauntingizga kirish uchun telefon raqamingizni yuboring yoki kiriting (masalan: +998901234567):",
                    reply_markup=reply_markup
                )
                return
            elif user.status == 0:
                await update.message.reply_text(self._awaiting_activation_message())
                return
            elif user.status == 1:
                # User is authenticated and activated, show main menu
                await self._show_main_menu(chat_id)
                return
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries."""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        chat_id = query.message.chat_id
        data = query.data
        
        state = self.state_manager.get_state(user_id)
        
        if data.startswith(("access_cal_", "access_day_", "access_confirm_", "access_reject_", "access_back_cal_")) or data == "access_ignore":
            await self._handle_access_approval_callback(query, data)
            return
        
        # Main menu actions
        if data == "action_send_message":
            state.step = "waiting_for_message"
            await query.message.reply_text("📝 Yubormoqchi bo'lgan xabaringizni kiriting:")
            return
        
        if data == "action_messages_table":
            await self._show_messages_table(chat_id, user_id)
            return
        
        if data == "action_pause_all_messages":
            await self._pause_all_messages(chat_id, user_id)
            return
        
        if data == "action_delete_all_messages":
            await self._delete_all_messages(chat_id, user_id)
            return
        
        if data == "action_video_tutorial":
            await self._send_video_tutorial(chat_id)
            return
        
        if data == "action_back_to_menu":
            await self._show_main_menu(chat_id)
            return
        
        # Group selection
        if data.startswith("toggle_group_"):
            parts = data.split("_")
            if len(parts) >= 3:
                group_id = int(parts[2])
                if group_id in state.selected_groups:
                    del state.selected_groups[group_id]
                else:
                    state.selected_groups[group_id] = True
                # Edit existing message instead of sending new one
                await self._show_group_selection(chat_id, user_id, edit_message=query.message)
            return
        
        if data == "confirm_groups":
            if not state.selected_groups:
                await query.message.reply_text("⚠️ Hech qanday guruh tanlanmadi!")
                return
            # After groups are selected, show schedule intervals first (Qancha vaqtda bir marta)
            await self._show_schedule_intervals(chat_id, user_id)
            return
        
        # Schedule interval selection
        if data.startswith("select_interval_"):
            interval_id = int(data.split("_")[2])
            state.selected_interval_id = interval_id
            # After interval is selected, show duration options (Qancha vaqt davomida)
            await self._show_duration_options(chat_id, user_id)
            return
        
        # Duration option selection
        if data.startswith("select_duration_"):
            duration_id = int(data.split("_")[2])
            state.selected_duration_id = duration_id
            # After duration is selected, save the scheduled message
            await self._save_scheduled_message(chat_id, user_id)
            return
        
        # Pagination
        if data.startswith("groups_page_"):
            page = int(data.split("_")[2])
            state.groups_page = page
            await self._show_group_selection(chat_id, user_id)
            return
    
    async def _show_main_menu(self, chat_id: int):
        """Show main menu."""
        keyboard = [
            [InlineKeyboardButton("📤 Xabar yuborish", callback_data="action_send_message")],
            [InlineKeyboardButton("📋 Xabarlar jadvali", callback_data="action_messages_table")],
            [InlineKeyboardButton("📹 Video qo'llanma", callback_data="action_video_tutorial")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await self.application.bot.send_message(
            chat_id,
            "🎯 Nima qilishni xohlaysiz? Quyidagi tugmalardan birini tanlang:",
            reply_markup=reply_markup
        )
    
    async def _show_schedule_intervals(self, chat_id: int, user_id: int):
        """Show schedule interval options (minutes - from duration_options table)."""
        try:
            # Use duration_options for minutes (1 daqiqa, 2 daqiqa, etc.)
            intervals = self.scheduled_storage.get_duration_options()
            
            if not intervals:
                await self.application.bot.send_message(
                    chat_id,
                    "⚠️ Interval variantlari topilmadi. Iltimos, admin bilan bog'laning."
                )
                return
            
            text = "⏰ Qancha vaqtda bir martadan yuborib turilsin?\n\nQuyidagilardan birini tanlang:"
            keyboard = []
            
            # Group intervals into rows of 3
            for i in range(0, len(intervals), 3):
                row = []
                for j in range(3):
                    if i + j < len(intervals):
                        interval = intervals[i + j]
                        row.append(
                            InlineKeyboardButton(
                                interval['display_text'],
                                callback_data=f"select_interval_{interval['id']}"
                            )
                        )
                if row:
                    keyboard.append(row)
            
            keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="action_back_to_menu")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await self.application.bot.send_message(chat_id, text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error showing schedule intervals: {e}", exc_info=True)
            await self.application.bot.send_message(
                chat_id,
                "⚠️ Interval variantlarini ko'rsatishda xatolik yuz berdi."
            )
    
    async def _show_duration_options(self, chat_id: int, user_id: int):
        """Show duration options (hours - from schedule_intervals table)."""
        try:
            # Use schedule_intervals for hours (1 soat, 2 soat, etc.)
            durations = self.scheduled_storage.get_schedule_intervals()
            
            if not durations:
                await self.application.bot.send_message(
                    chat_id,
                    "⚠️ Duration variantlari topilmadi. Iltimos, admin bilan bog'laning."
                )
                return
            
            text = "⏰ Qancha vaqt davomida yuborib turilsin?\n\nQuyidagilardan birini tanlang:"
            keyboard = []
            
            # Group durations into rows of 3
            for i in range(0, len(durations), 3):
                row = []
                for j in range(3):
                    if i + j < len(durations):
                        duration = durations[i + j]
                        row.append(
                            InlineKeyboardButton(
                                duration['display_text'],
                                callback_data=f"select_duration_{duration['id']}"
                            )
                        )
                if row:
                    keyboard.append(row)
            
            keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="action_back_to_menu")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await self.application.bot.send_message(chat_id, text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error showing duration options: {e}", exc_info=True)
            await self.application.bot.send_message(
                chat_id,
                "⚠️ Duration variantlarini ko'rsatishda xatolik yuz berdi."
            )
    
    async def _send_video_tutorial(self, chat_id: int):
        """Send video tutorial."""
        caption = "Video qo'llanma\nadmin: @system24admin"
        
        try:
            # Try sending by file_id first
            if self.config.VIDEO_TUTORIAL_FILE_ID:
                try:
                    await self.application.bot.send_video(
                        chat_id,
                        video=self.config.VIDEO_TUTORIAL_FILE_ID.strip(),
                        caption=caption
                    )
                    # Show main menu after sending video
                    await self._show_main_menu(chat_id)
                    return
                except Exception as file_id_error:
                    file_id_used = self.config.VIDEO_TUTORIAL_FILE_ID.strip()
                    logger.warning(f"Failed to send video by file_id: {file_id_error}")
                    logger.warning(f"File_id used: {file_id_used[:50]}... (length: {len(file_id_used)})")
                    logger.info("Trying to send video by file path as fallback...")
                    # If file_id fails, try file path
                    if self.config.VIDEO_TUTORIAL_PATH:
                        try:
                            with open(self.config.VIDEO_TUTORIAL_PATH, 'rb') as video:
                                await self.application.bot.send_video(
                                    chat_id,
                                    video=video,
                                    caption=caption
                                )
                                # Show main menu after sending video
                                await self._show_main_menu(chat_id)
                                return
                        except Exception as file_path_error:
                            logger.error(f"Failed to send video by file path: {file_path_error}")
                            await self.application.bot.send_message(
                                chat_id,
                                "⚠️ Videoni yuborishda xatolik yuz berdi.\n\n"
                                "Iltimos, video faylini botga yuboring va uning file_id sini oling."
                            )
                            return
                    else:
                        file_id_used = self.config.VIDEO_TUTORIAL_FILE_ID.strip()
                        await self.application.bot.send_message(
                            chat_id,
                            "⚠️ Video file_id noto'g'ri yoki eskirgan.\n\n"
                            "📹 To'g'ri file_id olish uchun:\n"
                            "1. Video faylini shu botga yuboring\n"
                            "2. Bot avtomatik ravishda file_id ni .env fayliga yozadi\n"
                            "3. Botni qayta ishga tushiring\n\n"
                            f"🔍 Hozirgi file_id: <code>{file_id_used[:30]}...</code>\n"
                            "❌ Bu file_id ishlamayapti.",
                            parse_mode='HTML'
                        )
                        return
            # Fallback to file path
            elif self.config.VIDEO_TUTORIAL_PATH:
                try:
                    with open(self.config.VIDEO_TUTORIAL_PATH, 'rb') as video:
                        await self.application.bot.send_video(
                            chat_id,
                            video=video,
                            caption=caption
                        )
                        # Show main menu after sending video
                        await self._show_main_menu(chat_id)
                        return
                except Exception as file_path_error:
                    logger.error(f"Failed to send video by file path: {file_path_error}")
                    await self.application.bot.send_message(
                        chat_id,
                        "⚠️ Video faylini topib bo'lmadi.\n\n"
                        "Iltimos, video faylini botga yuboring va uning file_id sini oling."
                    )
                    return
            else:
                await self.application.bot.send_message(
                    chat_id,
                    "⚠️ Video topilmadi.\n\n"
                    "Iltimos, video faylini botga yuboring va uning file_id sini oling."
                )
                return
        except Exception as e:
            logger.error(f"Video qo'llanmani yuborishda xato: {e}", exc_info=True)
            await self.application.bot.send_message(
                chat_id,
                "⚠️ Videoni yuborishda xatolik yuz berdi.\n\n"
                "Iltimos, video faylini botga yuboring va uning file_id sini oling."
            )
            return
    
    async def _show_messages_table(self, chat_id: int, user_id: int):
        """Show scheduled messages table for the user."""
        try:
            # Query scheduled messages for this user with group names
            query = """
                SELECT 
                    sm.id,
                    sm.message,
                    sm.interval_minutes,
                    sm.paused,
                    sm.expires_at,
                    sm.created_at,
                    COUNT(smg.group_id) as group_count,
                    ARRAY_AGG(smg.group_id) as group_ids
                FROM scheduled_messages sm
                LEFT JOIN scheduled_message_groups smg ON sm.id = smg.scheduled_id
                WHERE sm.user_id = %s
                GROUP BY sm.id, sm.message, sm.interval_minutes, sm.paused, sm.expires_at, sm.created_at
                ORDER BY sm.created_at DESC
            """
            
            messages = self.db.execute_query(query, (user_id,), fetch_all=True)
            
            if not messages:
                keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="action_back_to_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await self.application.bot.send_message(
                    chat_id,
                    "📋 Sizda rejalashtirilgan xabarlar mavjud emas.",
                    reply_markup=reply_markup
                )
                # Show main menu after showing empty message
                await self._show_main_menu(chat_id)
                return
            
            # Format messages for display
            text = "📋 Rejalashtirilgan xabarlar:\n\n"
            
            # Get client for fetching group names
            client = await self._get_or_create_client(user_id)
            
            for idx, msg in enumerate(messages, 1):
                message_id = msg['id']
                message_text = msg['message']
                interval = msg['interval_minutes']
                paused = msg['paused']
                expires_at = msg['expires_at']
                created_at = msg['created_at']
                group_count = msg['group_count'] or 0
                group_ids = msg.get('group_ids') or []
                
                # Filter out None values from group_ids array
                if group_ids and group_ids[0] is None:
                    group_ids = []
                
                # Get group names
                group_names = []
                if group_ids:
                    for group_id in group_ids[:5]:  # Limit to 5 groups to avoid long text
                        try:
                            group_name = await get_group_name(client, group_id)
                            group_names.append(group_name)
                        except Exception as e:
                            logger.warning(f"Error getting group name for {group_id}: {e}")
                            group_names.append(f"Guruh {group_id}")
                
                # Format group display
                if group_names:
                    if len(group_names) == 1:
                        groups_display = group_names[0]
                    elif len(group_names) <= 3:
                        groups_display = ", ".join(group_names)
                    else:
                        groups_display = ", ".join(group_names[:3]) + f" va yana {len(group_names) - 3} ta"
                else:
                    groups_display = f"{group_count} ta"
                
                # Truncate message if too long
                if len(message_text) > 50:
                    display_message = message_text[:47] + "..."
                else:
                    display_message = message_text
                
                # Format status with stickers
                status = "🛑 To'xtatilgan" if paused else "✅ Faol"
                
                # Format interval
                if interval < 60:
                    interval_text = f"{interval} daqiqa"
                else:
                    hours = interval // 60
                    minutes = interval % 60
                    if minutes > 0:
                        interval_text = f"{hours} soat {minutes} daqiqa"
                    else:
                        interval_text = f"{hours} soat"
                
                # Format dates - convert to Tashkent timezone
                if created_at:
                    # Ensure timezone is set to Tashkent
                    if created_at.tzinfo is None:
                        created_at_tz = created_at.replace(tzinfo=TASHKENT_TZ)
                    else:
                        created_at_tz = created_at.astimezone(TASHKENT_TZ)
                    created_str = created_at_tz.strftime("%Y-%m-%d %H:%M")
                else:
                    created_str = "Noma'lum"
                
                # Calculate correct expires_at based on interval if it seems wrong
                # If expires_at is too close to created_at, recalculate based on interval
                if expires_at and created_at:
                    # Ensure both are in Tashkent timezone
                    if expires_at.tzinfo is None:
                        expires_at_tz = expires_at.replace(tzinfo=TASHKENT_TZ)
                    else:
                        expires_at_tz = expires_at.astimezone(TASHKENT_TZ)
                    
                    if created_at.tzinfo is None:
                        created_at_tz = created_at.replace(tzinfo=TASHKENT_TZ)
                    else:
                        created_at_tz = created_at.astimezone(TASHKENT_TZ)
                    
                    time_diff = (expires_at_tz - created_at_tz).total_seconds() / 3600  # hours
                    interval_hours = interval / 60  # convert minutes to hours
                    # If the difference is less than interval, it's likely wrong
                    # Recalculate: expires_at should be at least created_at + interval
                    if time_diff < interval_hours:
                        # Recalculate based on duration (which should be >= interval)
                        # For now, use interval as minimum duration
                        from datetime import timedelta
                        expires_at_tz = created_at_tz + timedelta(hours=interval_hours)
                    
                    expires_str = expires_at_tz.strftime("%Y-%m-%d %H:%M")
                elif expires_at:
                    # Just convert to Tashkent timezone
                    if expires_at.tzinfo is None:
                        expires_at_tz = expires_at.replace(tzinfo=TASHKENT_TZ)
                    else:
                        expires_at_tz = expires_at.astimezone(TASHKENT_TZ)
                    expires_str = expires_at_tz.strftime("%Y-%m-%d %H:%M")
                else:
                    expires_str = "Cheklanmagan"
                
                text += f"📌 Xabar #{message_id}\n"
                text += f"💬 {display_message}\n"
                text += f"⏱️ Interval: {interval_text}\n"
                text += f"📊 Status: {status}\n"
                text += f"👥 Guruhlar: {groups_display}\n"
                text += f"📅 Yaratilgan: {created_str}\n"
                text += f"⏰ Tugaydi: {expires_str}\n"
                text += "\n" + "─" * 30 + "\n\n"
            
            # Add buttons for each message and control buttons
            keyboard = []
            
            # Add pause all and delete all buttons
            keyboard.append([
                InlineKeyboardButton("⏸️ Barchasini to'xtatish", callback_data="action_pause_all_messages"),
                InlineKeyboardButton("🗑️ Barchasini o'chirish", callback_data="action_delete_all_messages")
            ])
            
            # Add back button
            keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="action_back_to_menu")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Telegram message limit is 4096 characters
            if len(text) > 4000:
                text = text[:3900] + "\n\n... va yana bir nechta xabarlar"
            
            await self.application.bot.send_message(
                chat_id,
                text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error showing messages table: {e}", exc_info=True)
            keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="action_back_to_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await self.application.bot.send_message(
                chat_id,
                "⚠️ Xabarlar jadvalini ko'rsatishda xatolik yuz berdi.",
                reply_markup=reply_markup
            )
    
    async def _pause_all_messages(self, chat_id: int, user_id: int):
        """Pause all scheduled messages for the user."""
        try:
            # Get message IDs before updating
            get_ids_query = """
                SELECT id FROM scheduled_messages
                WHERE user_id = %s AND paused = FALSE
            """
            message_ids = self.db.execute_query(get_ids_query, (user_id,), fetch_all=True)
            
            # Update all messages to paused
            query = """
                UPDATE scheduled_messages
                SET paused = TRUE
                WHERE user_id = %s AND paused = FALSE
            """
            
            affected = self.db.execute_query(query, (user_id,))
            
            # Clean up tracking for paused messages
            if message_ids:
                with self.last_sent_lock:
                    for msg_row in message_ids:
                        self.last_sent_times.pop(msg_row['id'], None)
            
            if affected > 0:
                await self.application.bot.send_message(
                    chat_id,
                    f"✅ {affected} ta xabar to'xtatildi."
                )
            else:
                await self.application.bot.send_message(
                    chat_id,
                    "ℹ️ To'xtatiladigan faol xabarlar mavjud emas."
                )
            
            # Refresh messages table
            await self._show_messages_table(chat_id, user_id)
            
        except Exception as e:
            logger.error(f"Error pausing all messages: {e}", exc_info=True)
            await self.application.bot.send_message(
                chat_id,
                "⚠️ Xabarlarni to'xtatishda xatolik yuz berdi."
            )
    
    async def _delete_all_messages(self, chat_id: int, user_id: int):
        """Delete all scheduled messages for the user."""
        try:
            # Get message IDs before deleting
            get_ids_query = """
                SELECT id FROM scheduled_messages
                WHERE user_id = %s
            """
            message_ids = self.db.execute_query(get_ids_query, (user_id,), fetch_all=True)
            
            # Delete all messages for this user
            # Due to CASCADE, scheduled_message_groups will be deleted automatically
            query = """
                DELETE FROM scheduled_messages
                WHERE user_id = %s
            """
            
            affected = self.db.execute_query(query, (user_id,))
            
            # Clean up tracking for deleted messages
            if message_ids:
                with self.last_sent_lock:
                    for msg_row in message_ids:
                        self.last_sent_times.pop(msg_row['id'], None)
            
            if affected > 0:
                await self.application.bot.send_message(
                    chat_id,
                    f"✅ {affected} ta xabar o'chirildi."
                )
            else:
                await self.application.bot.send_message(
                    chat_id,
                    "ℹ️ O'chiriladigan xabarlar mavjud emas."
                )
            
            # Refresh messages table (will show empty message and main menu)
            await self._show_messages_table(chat_id, user_id)
            
        except Exception as e:
            logger.error(f"Error deleting all messages: {e}", exc_info=True)
            await self.application.bot.send_message(
                chat_id,
                "⚠️ Xabarlarni o'chirishda xatolik yuz berdi."
            )
    
    async def _authenticate_user(self, user_id: int, phone: str, code: str, phone_code_hash: Optional[str] = None, chat_id: Optional[int] = None) -> str:
        """Authenticate user with phone and code."""
        client = await self._get_or_create_client(user_id)
        code_str = str(code).strip()

        try:
            logger.info(f"[AUTH] Starting authentication for user {user_id} with phone {phone}")
            if not client.is_connected():
                await client.connect()

            if not phone_code_hash:
                logger.warning(f"[AUTH] Missing phone_code_hash for user {user_id}")
                return "code_expired"

            logger.info(
                f"[AUTH] Signing in user {user_id} with code length {len(code_str)} "
                f"(hash: {phone_code_hash[:10]}...)"
            )
            await client.sign_in(phone, code_str, phone_code_hash=phone_code_hash)

            logger.info(f"[AUTH] Authentication successful for user {user_id}")
            await self._send_login_message(user_id, client)
            return "success"
        except PhoneCodeExpiredError as e:
            logger.warning(f"[AUTH] Code expired for user {user_id}: {e}")
            return "code_expired"
        except PhoneCodeInvalidError as e:
            logger.warning(f"[AUTH] Invalid code for user {user_id}: {e}")
            return "code_invalid"
        except SessionPasswordNeededError:
            logger.info(f"[AUTH] Password required for user {user_id}")
            state = self.state_manager.get_state(user_id)
            state.step = "waiting_for_password"
            return "password_needed"
        except Exception as e:
            error_text = str(e).lower()
            if any(token in error_text for token in ("shared", "previously", "confirmation code has expired")):
                logger.warning(f"[AUTH] Login code rejected for user {user_id}: {e}")
                return "code_shared" if "shared" in error_text or "previously" in error_text else "code_expired"

            logger.error(f"[AUTH] Authentication error for user {user_id}: {e}", exc_info=True)
            return "error"
    
    async def _authenticate_user_password(self, user_id: int, password: str) -> bool:
        """Authenticate user with password."""
        try:
            logger.info(f"[AUTH] Starting password authentication for user {user_id}")
            print(f"[AUTH] Starting password authentication for user {user_id}")
            
            client = await self._get_or_create_client(user_id)
            if not client.is_connected():
                logger.info(f"[AUTH] Connecting Telegram client for user {user_id}")
                print(f"[AUTH] Connecting Telegram client for user {user_id}")
                await client.connect()
            
            logger.info(f"[AUTH] Signing in user {user_id} with password")
            print(f"[AUTH] Signing in user {user_id} with password")
            await client.sign_in(password=password)
            
            logger.info(f"[AUTH] ✅ Password authentication successful for user {user_id}")
            print(f"[AUTH] ✅ Password authentication successful for user {user_id}")
            
            # Send login message to user's Telegram account
            await self._send_login_message(user_id, client)
            
            return True
        except Exception as e:
            logger.error(f"[AUTH] ❌ Password authentication error for user {user_id}: {e}")
            print(f"[AUTH] ❌ Password authentication error for user {user_id}: {e}")
            return False
    
    async def _show_group_selection(self, chat_id: int, user_id: int, edit_message=None):
        """Show group selection interface."""
        state = self.state_manager.get_state(user_id)
        
        # Load previously selected groups from user_last_groups table if state is empty
        if not state.selected_groups:
            try:
                # First try to get from user_last_groups (most reliable)
                last_groups_result = self.db.execute_query(
                    "SELECT group_id FROM user_last_groups WHERE user_id = %s",
                    (user_id,),
                    fetch_all=True
                )
                
                if last_groups_result:
                    # Pre-select these groups
                    for group_row in last_groups_result:
                        state.selected_groups[group_row['group_id']] = True
                        logger.info(f"[GROUPS] Pre-selected group {group_row['group_id']} from user_last_groups")
                else:
                    # Fallback: Get from the most recent scheduled message if user_last_groups is empty
                    scheduled_query = """
                        SELECT id FROM scheduled_messages
                        WHERE user_id = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                    """
                    scheduled_result = self.db.execute_query(scheduled_query, (user_id,), fetch_one=True)
                    
                    if scheduled_result:
                        scheduled_id = scheduled_result['id']
                        # Get all groups from the most recent scheduled message
                        groups_result = self.db.execute_query(
                            "SELECT group_id FROM scheduled_message_groups WHERE scheduled_id = %s",
                            (scheduled_id,),
                            fetch_all=True
                        )
                        # Pre-select these groups and save to user_last_groups
                        for group_row in groups_result:
                            group_id = group_row['group_id']
                            state.selected_groups[group_id] = True
                            # Save to user_last_groups for future use
                            try:
                                self.db.execute_query(
                                    "INSERT INTO user_last_groups (user_id, group_id) VALUES (%s, %s) ON CONFLICT (user_id, group_id) DO NOTHING",
                                    (user_id, group_id)
                                )
                            except Exception:
                                pass  # Table might not exist yet, ignore
                            logger.info(f"[GROUPS] Pre-selected group {group_id} from last scheduled message")
            except Exception as e:
                logger.error(f"Error loading previous groups: {e}")
                # If user_last_groups table doesn't exist, try to create it
                try:
                    create_table_query = """
                        CREATE TABLE IF NOT EXISTS user_last_groups (
                            user_id BIGINT NOT NULL,
                            group_id BIGINT NOT NULL,
                            PRIMARY KEY (user_id, group_id)
                        )
                    """
                    self.db.execute_query(create_table_query)
                    logger.info("[GROUPS] Created user_last_groups table")
                except Exception as create_error:
                    logger.error(f"Error creating user_last_groups table: {create_error}")
        
        # If editing existing message, skip loading
        if edit_message is None:
            loading_msg = await self.application.bot.send_message(chat_id, "⏳ Guruhlar yuklanmoqda...")
        else:
            loading_msg = None
        
        try:
            # Get or create client
            client = await self._get_or_create_client(user_id)
            if not client:
                await self.application.bot.send_message(chat_id, "⚠️ Telegram klienti ishga tushmadi.")
                return
            
            # Fetch groups (no database saving)
            try:
                groups = await fetch_user_groups(client, user_id)
            except AuthKeyUnregisteredError:
                # Session expired - try to reconnect and restore session
                logger.warning(f"[GROUPS] Session expired for user {user_id}, attempting to restore...")
                try:
                    await loading_msg.delete()
                except:
                    pass
                
                # Try to restore session by reconnecting
                try:
                    with self.clients_lock:
                        if user_id in self.clients:
                            client = self.clients[user_id]
                            try:
                                if client.is_connected():
                                    await client.disconnect()
                            except:
                                pass
                            # Remove from memory but keep session files
                            del self.clients[user_id]
                    
                    # Try to reconnect with existing session file
                    client = await self._get_or_create_client(user_id)
                    if client:
                        try:
                            await client.connect()
                            # Verify session is still valid
                            me = await client.get_me()
                            if me:
                                logger.info(f"[GROUPS] ✅ Session restored for user {user_id}")
                                # Retry fetching groups
                                groups = await fetch_user_groups(client, user_id)
                                # Continue with group selection if successful
                            else:
                                raise AuthKeyUnregisteredError("Session invalid")
                        except Exception as restore_error:
                            logger.error(f"[GROUPS] Failed to restore session for user {user_id}: {restore_error}")
                            # Session cannot be restored, but don't delete it
                            # User can manually re-authenticate if needed
                            await self.application.bot.send_message(
                                chat_id,
                                "⚠️ Session bilan muammo bor. Iltimos, qayta urinib ko'ring yoki /start buyrug'ini yuboring."
                            )
                            return
                except Exception as e:
                    logger.error(f"[GROUPS] Error during session restore for user {user_id}: {e}")
                    await self.application.bot.send_message(
                        chat_id,
                        "⚠️ Session bilan muammo bor. Iltimos, qayta urinib ko'ring."
                    )
                    return
            
            if not groups:
                try:
                    await loading_msg.delete()
                except:
                    pass
                await self.application.bot.send_message(chat_id, "⚠️ Hech qanday guruh topilmadi.")
                return
            
            # Show groups with pagination
            page = state.groups_page
            items_per_page = 10
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_groups = groups[start_idx:end_idx]
            
            text = "📋 Guruhlarni tanlang:\n\n"
            keyboard = []
            
            for group in page_groups:
                group_id = group['id']
                group_name = group['name']
                is_selected = group_id in state.selected_groups
                
                # Show ✅ only for selected groups, no checkbox for unselected
                if is_selected:
                    text += f"✅ {group_name}\n"
                    keyboard.append([
                        InlineKeyboardButton(
                            f"✅ {group_name}",
                            callback_data=f"toggle_group_{group_id}"
                        )
                    ])
                else:
                    text += f"{group_name}\n"
                    keyboard.append([
                        InlineKeyboardButton(
                            group_name,
                            callback_data=f"toggle_group_{group_id}"
                        )
                    ])
            
            # Pagination buttons
            total_pages = (len(groups) + items_per_page - 1) // items_per_page
            nav_buttons = []
            
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"groups_page_{page - 1}"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"groups_page_{page + 1}"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            # Confirm button
            if state.selected_groups:
                keyboard.append([
                    InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_groups")
                ])
            
            keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="action_back_to_menu")])
            
            text += f"\n📄 Sahifa: {page}/{total_pages}\n"
            text += f"Tanlangan: {len(state.selected_groups)} guruh"
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # If editing existing message, edit it instead of sending new one
            if edit_message is not None:
                try:
                    await edit_message.edit_text(text, reply_markup=reply_markup)
                    return
                except Exception as e:
                    logger.error(f"Error editing message: {e}")
                    # Fall through to send new message if edit fails
            
            # Update loading message with group list when possible
            if loading_msg:
                try:
                    await loading_msg.edit_text(text, reply_markup=reply_markup)
                    return
                except Exception:
                    pass
            
            # Send new message
            await self.application.bot.send_message(chat_id, text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error showing groups: {e}")
            try:
                await loading_msg.delete()
            except:
                pass
            await self.application.bot.send_message(chat_id, "⚠️ Guruhlarni yuklashda xatolik yuz berdi.")

    def _create_send_batch(self, user_id: int, total_groups: int, notify_on_complete: bool) -> str:
        """Track a staggered group send batch for completion notification."""
        batch_id = str(uuid.uuid4())
        with self.group_send_lock:
            self.send_batches[batch_id] = {
                'user_id': user_id,
                'total': total_groups,
                'done': 0,
                'success': 0,
                'failed': 0,
                'notify': notify_on_complete,
            }
        return batch_id

    async def _record_send_batch_result(self, batch_id: Optional[str], success: bool):
        """Record one group result and notify the user when the batch is complete."""
        if not batch_id:
            return

        batch = None
        with self.group_send_lock:
            batch = self.send_batches.get(batch_id)
            if not batch:
                return

            batch['done'] += 1
            if success:
                batch['success'] += 1
            else:
                batch['failed'] += 1

            if batch['done'] < batch['total']:
                return

            self.send_batches.pop(batch_id, None)

        if batch['notify']:
            await self._notify_group_send_task_complete(
                batch['user_id'],
                batch['success'],
                batch['failed'],
                batch['total'],
            )

    async def _execute_group_send(
        self,
        user_id: int,
        group_id: int,
        message_text: str,
        scheduled_id: Optional[int] = None,
        cycle_key: Optional[tuple[int, int, int]] = None,
    ) -> bool:
        """Send one message to a single group."""
        if cycle_key is not None:
            with self.group_send_lock:
                if cycle_key in self.active_group_cycles:
                    return False
                self.active_group_cycles.add(cycle_key)

        try:
            client = await self._get_or_create_client(user_id)
            if not client:
                logger.warning(f"[GROUP SEND] No client for user {user_id}")
                return False

            if not client.is_connected():
                await client.connect()

            await client.send_message(group_id, message_text)
            logger.info(f"[GROUP SEND] Sent message to group {group_id} for user {user_id}")

            if scheduled_id is not None:
                self.db.execute_query(
                    """
                    UPDATE scheduled_message_groups
                    SET last_sent_at = %s
                    WHERE scheduled_id = %s AND group_id = %s
                    """,
                    (datetime.now(TASHKENT_TZ), scheduled_id, group_id),
                )
            return True
        except AuthKeyUnregisteredError:
            logger.warning(f"[GROUP SEND] Session expired for user {user_id} while sending to group {group_id}")
            with self.clients_lock:
                if user_id in self.clients:
                    client = self.clients[user_id]
                    try:
                        if client.is_connected():
                            await client.disconnect()
                    except Exception:
                        pass
                    del self.clients[user_id]
            return False
        except Exception as e:
            logger.error(f"[GROUP SEND] Error sending to group {group_id} for user {user_id}: {e}")
            return False
        finally:
            if cycle_key is not None:
                with self.group_send_lock:
                    self.active_group_cycles.discard(cycle_key)

    async def _send_group_after_delay(
        self,
        user_id: int,
        group_id: int,
        message_text: str,
        delay_seconds: float,
        batch_id: Optional[str],
        scheduled_id: Optional[int] = None,
        cycle_key: Optional[tuple[int, int, int]] = None,
    ):
        """Send to one group after a delay without blocking other groups."""
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        success = await self._execute_group_send(
            user_id,
            group_id,
            message_text,
            scheduled_id=scheduled_id,
            cycle_key=cycle_key,
        )
        await self._record_send_batch_result(batch_id, success)

    def _dispatch_staggered_group_send(
        self,
        user_id: int,
        group_offsets: list[tuple[int, int]],
        message_text: str,
        scheduled_id: Optional[int] = None,
        notify_on_complete: bool = True,
    ):
        """Schedule parallel staggered sends for a group batch."""
        if not group_offsets:
            return

        batch_id = self._create_send_batch(user_id, len(group_offsets), notify_on_complete)
        for group_id, offset_seconds in group_offsets:
            asyncio.create_task(
                self._send_group_after_delay(
                    user_id,
                    group_id,
                    message_text,
                    float(offset_seconds),
                    batch_id,
                    scheduled_id=scheduled_id,
                )
            )

    async def _notify_group_send_task_complete(
        self,
        user_id: int,
        success_count: int,
        failed_count: int,
        total_groups: int,
    ):
        """Notify the user after a sequential group send task finishes."""
        if success_count > 0 and failed_count == 0:
            text = f"✅ {success_count} ta guruhga yuborish vazifasi tugadi."
        elif success_count > 0:
            text = (
                f"✅ {success_count} ta guruhga yuborish vazifasi tugadi.\n"
                f"⚠️ {failed_count} ta guruhga yuborishda xatolik yuz berdi."
            )
        else:
            text = f"❌ {total_groups} ta guruhga yuborish vazifasi yakunlandi, lekin xabar yuborilmadi."

        try:
            await self.application.bot.send_message(user_id, text)
        except Exception as e:
            logger.error(f"[GROUP SEND] Failed to notify user {user_id}: {e}")

    async def _save_scheduled_message(self, chat_id: int, user_id: int):
        """Save scheduled message to database."""
        try:
            state = self.state_manager.get_state(user_id)
            
            if not state.pending_message or not state.selected_groups:
                await self.application.bot.send_message(chat_id, "⚠️ Xabar yoki guruhlar tanlanmagan!")
                return
            
            if not state.selected_interval_id or not state.selected_duration_id:
                await self.application.bot.send_message(chat_id, "⚠️ Interval yoki duration tanlanmagan!")
                return
            
            # Get interval and duration details
            # Note: selected_interval_id comes from duration_options (minutes)
            #       selected_duration_id comes from schedule_intervals (hours)
            duration_options = self.scheduled_storage.get_duration_options()  # has hours, but we need minutes
            schedule_intervals = self.scheduled_storage.get_schedule_intervals()  # has minutes, but we need hours
            
            selected_interval = next((d for d in duration_options if d['id'] == state.selected_interval_id), None)
            selected_duration = next((i for i in schedule_intervals if i['id'] == state.selected_duration_id), None)
            
            if not selected_interval or not selected_duration:
                await self.application.bot.send_message(chat_id, "⚠️ Interval yoki duration topilmadi!")
                return
            
            # Calculate interval_minutes from duration_options (which now has minutes)
            interval_minutes = int(selected_interval['minutes'])
            interval_hours = interval_minutes / 60.0  # Convert to hours for comparison
            
            # Calculate expires_at based on duration from schedule_intervals (which now has hours)
            duration_hours = float(selected_duration['hours'])
            
            # Ensure duration is at least equal to interval (in hours)
            # If duration is less than interval, use interval as minimum
            if duration_hours < interval_hours:
                duration_hours = interval_hours
            
            # Calculate expires_at with Tashkent timezone
            from datetime import datetime, timedelta
            now = datetime.now(TASHKENT_TZ)
            expires_at = now + timedelta(hours=duration_hours)
            
            # Insert scheduled message
            insert_query = """
                INSERT INTO scheduled_messages (user_id, message, interval_minutes, expires_at, paused, created_at)
                VALUES (%s, %s, %s, %s, FALSE, %s)
                RETURNING id
            """
            
            result = self.db.execute_query(
                insert_query,
                (user_id, state.pending_message, interval_minutes, expires_at, now),
                fetch_one=True
            )
            
            scheduled_id = result['id']
            
            # Store values before clearing
            message_text = state.pending_message
            groups_count = len(state.selected_groups)
            group_ids = list(state.selected_groups.keys())
            group_offsets = [
                (group_id, index * GROUP_STAGGER_SECONDS)
                for index, group_id in enumerate(group_ids)
            ]
            
            # Insert groups
            try:
                for group_id, offset_seconds in group_offsets:
                    group_insert_query = """
                        INSERT INTO scheduled_message_groups (scheduled_id, group_id, send_offset_seconds)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (scheduled_id, group_id) DO UPDATE
                        SET send_offset_seconds = EXCLUDED.send_offset_seconds
                    """
                    self.db.execute_query(group_insert_query, (scheduled_id, group_id, offset_seconds))
                
                # Save user's last selected groups for future use
                # First, delete old last groups for this user
                self.db.execute_query(
                    "DELETE FROM user_last_groups WHERE user_id = %s",
                    (user_id,)
                )
                # Then insert new last groups
                for group_id in state.selected_groups.keys():
                    self.db.execute_query(
                        "INSERT INTO user_last_groups (user_id, group_id) VALUES (%s, %s) ON CONFLICT (user_id, group_id) DO NOTHING",
                        (user_id, group_id)
                    )
            except Exception as e:
                # If group insertion fails, delete the scheduled message to maintain consistency
                logger.error(f"Error inserting groups for scheduled message {scheduled_id}: {e}")
                try:
                    delete_query = "DELETE FROM scheduled_messages WHERE id = %s"
                    self.db.execute_query(delete_query, (scheduled_id,))
                except Exception as delete_error:
                    logger.error(f"Error deleting scheduled message {scheduled_id} after group insert failure: {delete_error}")
                raise e
            
            asyncio.create_task(
                self._dispatch_staggered_group_send(
                    user_id,
                    group_offsets,
                    message_text,
                    scheduled_id=scheduled_id,
                )
            )
            
            # Format last message time
            expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M")
            
            # Show success message before clearing
            await self.application.bot.send_message(
                chat_id,
                f"✅ Xabar rejalashtirildi!\n\n"
                f"📝 Xabar: {message_text[:50]}{'...' if len(message_text) > 50 else ''}\n"
                f"⏱️ Interval: {selected_interval['display_text']}\n"
                f"⏰ Duration: {selected_duration['display_text']}\n"
                f"👥 Guruhlar: {groups_count} ta\n"
                f"📅 Oxirgi xabar: {expires_at_str}\n\n"
                f"📤 Guruhlarga xabar {GROUP_STAGGER_SECONDS} soniya oralig'ida ketma-ket yuboriladi. "
                f"Tugagach, sizga xabar beriladi."
            )
            
            # Clear pending data
            state.pending_message = ""
            state.selected_groups = {}
            state.selected_interval_id = None
            state.selected_duration_id = None
            state.step = ""
            
            # Show main menu
            await self._show_main_menu(chat_id)
            
        except Exception as e:
            logger.error(f"Error saving scheduled message: {e}", exc_info=True)
            await self.application.bot.send_message(
                chat_id,
                "⚠️ Xabarni saqlashda xatolik yuz berdi."
            )
    
    async def _send_message_to_groups(self, chat_id: int, user_id: int):
        """Send message to selected groups with a fixed stagger between them."""
        state = self.state_manager.get_state(user_id)
        
        if not state.pending_message or not state.selected_groups:
            await self.application.bot.send_message(chat_id, "⚠️ Xabar yoki guruhlar tanlanmagan!")
            return
        
        group_ids = list(state.selected_groups.keys())
        message_text = state.pending_message
        group_offsets = [
            (group_id, index * GROUP_STAGGER_SECONDS)
            for index, group_id in enumerate(group_ids)
        ]
        
        # Clear pending data before background send starts
        state.pending_message = ""
        state.selected_groups = {}
        
        asyncio.create_task(
            self._dispatch_staggered_group_send(
                user_id,
                group_offsets,
                message_text,
            )
        )
        
        await self.application.bot.send_message(
            chat_id,
            f"📤 Tanlangan guruhlarga xabar {GROUP_STAGGER_SECONDS} soniya oralig'ida yuborilmoqda. "
            f"Tugagach, sizga xabar beriladi."
        )
        
        # Show main menu
        await self._show_main_menu(chat_id)
    
    async def _check_expired_users(self):
        """Check and deactivate expired users."""
        try:
            user_ids = self.user_storage.list_users_to_deactivate()
            count = self.user_storage.deactivate_expired_users()
            
            if count > 0:
                logger.info(f"Auto-deactivated {count} expired users")
                # Notify users
                for user_id in user_ids:
                    try:
                        await self.application.bot.send_message(
                            user_id,
                            "⚠️ Sizning akkauntingiz muddati tugadi va deaktivatsiya qilindi."
                        )
                    except Exception:
                        pass  # Ignore errors when notifying
        except Exception as e:
            logger.error(f"Error checking expired users: {e}")
    
    async def _check_expired_payments(self):
        """Check expired payments and deactivate users, send notifications."""
        try:
            from datetime import date
            
            today = date.today()
            
            # Check for expired payments with active users
            query = """
                SELECT up.user_id, u.id
                FROM user_payments up
                INNER JOIN users u ON up.user_id = u.id
                WHERE up.deadline <= %s AND u.status = 1
                GROUP BY up.user_id, u.id
            """
            
            results = self.db.execute_query(query, (today,), fetch_all=True)
            
            if not results:
                return
            
            logger.info(f"[PAYMENTS] Found {len(results)} users with expired payments")
            print(f"[PAYMENTS] Found {len(results)} users with expired payments")
            
            deactivated_count = 0
            for row in results:
                user_id = row['user_id']
                try:
                    # Deactivate user
                    self.user_storage.set_user_status(user_id, 0)
                    deactivated_count += 1
                    
                    # Send notification
                    await self.application.bot.send_message(
                        user_id,
                        "⚠️ Sizning akkauntingiz muddati tugadi, iltimos admin bilan bog'laning"
                    )
                    
                    logger.info(f"[PAYMENTS] Deactivated user {user_id} and sent notification")
                    print(f"[PAYMENTS] Deactivated user {user_id} and sent notification")
                    
                except Exception as e:
                    logger.error(f"[PAYMENTS] Error processing user {user_id}: {e}")
                    print(f"[PAYMENTS] Error processing user {user_id}: {e}")
            
            if deactivated_count > 0:
                logger.info(f"[PAYMENTS] Successfully deactivated {deactivated_count} users")
                print(f"[PAYMENTS] Successfully deactivated {deactivated_count} users")
                
        except Exception as e:
            logger.error(f"[PAYMENTS] Error checking expired payments: {e}", exc_info=True)
            print(f"[PAYMENTS] Error checking expired payments: {e}")
    
    async def _send_scheduled_messages(self):
        """Send scheduled messages per group on its own interval without blocking others."""
        try:
            now = datetime.now(TASHKENT_TZ)
            
            query = """
                SELECT 
                    sm.id,
                    sm.user_id,
                    sm.message,
                    sm.interval_minutes,
                    sm.expires_at
                FROM scheduled_messages sm
                WHERE sm.paused = FALSE
                  AND (sm.expires_at IS NULL OR sm.expires_at > %s)
                  AND EXISTS (
                      SELECT 1 FROM scheduled_message_groups smg 
                      WHERE smg.scheduled_id = sm.id
                  )
            """
            
            messages = self.db.execute_query(query, (now,), fetch_all=True)
            
            if not messages:
                return
            
            for msg in messages:
                try:
                    scheduled_id = msg['id']
                    user_id = msg['user_id']
                    message_text = msg['message']
                    interval_minutes = int(msg['interval_minutes'])
                    expires_at = msg['expires_at']
                    
                    user = self.user_storage.get_user(user_id)
                    if not user or user.status != 1 or user.auth != 1:
                        continue
                    
                    if expires_at:
                        expires_at_tz = (
                            expires_at.replace(tzinfo=TASHKENT_TZ)
                            if expires_at.tzinfo is None
                            else expires_at
                        )
                        if now >= expires_at_tz:
                            continue
                    
                    groups_query = """
                        SELECT group_id, send_offset_seconds, last_sent_at
                        FROM scheduled_message_groups
                        WHERE scheduled_id = %s
                        ORDER BY send_offset_seconds, group_id
                    """
                    groups = self.db.execute_query(groups_query, (scheduled_id,), fetch_all=True)
                    
                    if not groups:
                        continue
                    
                    interval_delta = timedelta(minutes=interval_minutes)
                    
                    for group_row in groups:
                        group_id = group_row['group_id']
                        last_sent_at = group_row['last_sent_at']
                        
                        if last_sent_at is None:
                            continue
                        
                        if last_sent_at.tzinfo is None:
                            last_sent_at = last_sent_at.replace(tzinfo=TASHKENT_TZ)
                        
                        next_due_at = last_sent_at + interval_delta
                        if now < next_due_at:
                            continue
                        
                        cycle_key = (scheduled_id, group_id, int(next_due_at.timestamp()))
                        asyncio.create_task(
                            self._send_group_after_delay(
                                user_id,
                                group_id,
                                message_text,
                                0.0,
                                None,
                                scheduled_id=scheduled_id,
                                cycle_key=cycle_key,
                            )
                        )
                    
                except Exception as e:
                    logger.error(
                        f"[SCHEDULED] Error processing scheduled message {msg.get('id', 'unknown')}: {e}",
                        exc_info=True,
                    )
                    
        except Exception as e:
            logger.error(f"[SCHEDULED] Error in scheduled messages job: {e}", exc_info=True)
            print(f"[SCHEDULED] Error in scheduled messages job: {e}")
    
    async def start(self):
        """Start the bot."""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot started")
    
    async def handle_chat_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle chat member updates (when user leaves/blocks the bot)."""
        try:
            chat_member = update.my_chat_member
            if not chat_member:
                return
            
            user_id = chat_member.from_user.id
            new_status = chat_member.new_chat_member.status
            
            # Check if user left or blocked the bot
            # NOTE: We do NOT delete session here - sessions are only deleted when admin removes user from admin panel
            # This ensures sessions persist even if user temporarily leaves/returns
            if new_status in ['left', 'kicked']:
                logger.info(f"[CHAT MEMBER] User {user_id} left or blocked the bot. Session will be preserved.")
                print(f"[CHAT MEMBER] User {user_id} left or blocked the bot. Session will be preserved.")
                # Just disconnect client from memory, but keep session files
                with self.clients_lock:
                    if user_id in self.clients:
                        try:
                            client = self.clients[user_id]
                            if client.is_connected():
                                await client.disconnect()
                        except:
                            pass
                        # Remove from memory but keep session files on disk
                        del self.clients[user_id]
                        logger.info(f"[CHAT MEMBER] Client removed from memory for user {user_id}, but session files preserved")
        except Exception as e:
            logger.error(f"Error handling chat member update: {e}", exc_info=True)
    
    def _delete_user_session(self, user_id: int):
        """Delete user's session files."""
        import os
        from pathlib import Path
        
        try:
            bot_dir = Path(__file__).resolve().parent
            sessions_dir = bot_dir / "sessions"
            
            session_files = [
                sessions_dir / f"session_{user_id}.json",
                sessions_dir / f"tg_session_{user_id}.session",
                sessions_dir / f"tg_session_{user_id}.session-journal",
            ]
            
            for session_file in session_files:
                try:
                    if session_file.exists():
                        os.remove(str(session_file))
                        logger.info(f"[SESSION DELETE] Deleted {session_file}")
                        print(f"[SESSION DELETE] Deleted {session_file}")
                except Exception as e:
                    logger.error(f"Error deleting session file {session_file}: {e}")
                    print(f"Error deleting session file {session_file}: {e}")
            
            # Remove client from memory
            with self.clients_lock:
                if user_id in self.clients:
                    del self.clients[user_id]
                    logger.info(f"[SESSION DELETE] Removed client from memory for user {user_id}")
                    print(f"[SESSION DELETE] Removed client from memory for user {user_id}")
        except Exception as e:
            logger.error(f"Error deleting user session: {e}", exc_info=True)
            print(f"Error deleting user session: {e}")
    
    async def stop(self):
        """Stop the bot."""
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        self.scheduler.shutdown()
        self.db.close()
        logger.info("Bot stopped")


async def main():
    """Main entry point."""
    config = Config()
    if not config.validate():
        logger.error("Invalid configuration. Please check your .env file.")
        return
    
    bot = MessengerBot(config)
    
    try:
        await bot.start()
        # Keep running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())

