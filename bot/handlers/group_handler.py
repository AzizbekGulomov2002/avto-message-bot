"""Group handling utilities."""
from typing import List, Dict, Optional
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from telethon.errors import AuthKeyUnregisteredError, SessionPasswordNeededError
from bot.storage.user_storage import UserStorage


async def fetch_user_groups(client: TelegramClient, user_id: int, user_storage: UserStorage = None) -> List[Dict]:
    """Fetch groups/channels for a user. Optimized for speed - no database saving."""
    groups = []
    
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[GROUPS] Fetching groups for user {user_id}")
        print(f"[GROUPS] Fetching groups for user {user_id}")
        
        # Check if client is connected and authenticated
        if not client.is_connected():
            logger.info(f"[GROUPS] Connecting client for user {user_id}")
            print(f"[GROUPS] Connecting client for user {user_id}")
            await client.connect()
        
        # Verify authentication by checking if we can get user info
        try:
            me = await client.get_me()
            if me is None:
                logger.error(f"[GROUPS] ❌ Session expired for user {user_id}. get_me() returned None. User needs to re-authenticate.")
                print(f"[GROUPS] ❌ Session expired for user {user_id}. get_me() returned None. User needs to re-authenticate.")
                raise AuthKeyUnregisteredError("Session expired. Please re-authenticate.")
            logger.info(f"[GROUPS] Client authenticated for user {user_id}, Telegram ID: {me.id}")
            print(f"[GROUPS] Client authenticated for user {user_id}, Telegram ID: {me.id}")
        except AuthKeyUnregisteredError:
            logger.error(f"[GROUPS] ❌ Session expired for user {user_id}. User needs to re-authenticate.")
            print(f"[GROUPS] ❌ Session expired for user {user_id}. User needs to re-authenticate.")
            raise
        except Exception as e:
            logger.error(f"[GROUPS] ❌ Error verifying authentication for user {user_id}: {e}")
            print(f"[GROUPS] ❌ Error verifying authentication for user {user_id}: {e}")
            # If get_me() fails, treat it as session expired
            raise AuthKeyUnregisteredError("Session expired. Please re-authenticate.")
        
        # Get dialogs with limit to speed up - only get first 500 dialogs (usually enough for groups)
        # This significantly speeds up the process and avoids flood wait
        logger.info(f"[GROUPS] Getting dialogs for user {user_id} (limited to 500 for speed)")
        print(f"[GROUPS] Getting dialogs for user {user_id} (limited to 500 for speed)")
        dialogs = await client.get_dialogs(limit=500)
        
        logger.info(f"[GROUPS] Found {len(dialogs)} dialogs for user {user_id}")
        print(f"[GROUPS] Found {len(dialogs)} dialogs for user {user_id}")
        
        # Process dialogs in batch for better performance
        for dialog in dialogs:
            try:
                entity = dialog.entity
                
                # Check if it's a channel or supergroup
                if isinstance(entity, Channel):
                    # Supergroup (megagroup=True) or regular group (broadcast=False)
                    if entity.megagroup or not entity.broadcast:
                        group_id = entity.id
                        group_name = entity.title or "Noma'lum guruh"
                        username = getattr(entity, 'username', None)
                        
                        groups.append({
                            'id': group_id,
                            'name': group_name,
                            'username': username
                        })
                # Also check for regular chats (Chat type)
                elif isinstance(entity, Chat):
                    group_id = entity.id
                    group_name = entity.title or "Noma'lum guruh"
                    
                    groups.append({
                        'id': group_id,
                        'name': group_name,
                        'username': None
                    })
            except Exception as e:
                logger.warning(f"[GROUPS] Error processing dialog: {e}")
                print(f"[GROUPS] Error processing dialog: {e}")
                continue
        
        logger.info(f"[GROUPS] ✅ Total groups found: {len(groups)} for user {user_id}")
        print(f"[GROUPS] ✅ Total groups found: {len(groups)} for user {user_id}")
        
    except AuthKeyUnregisteredError:
        # Re-raise AuthKeyUnregisteredError so it can be handled by caller
        raise
    except Exception as e:
        logger.error(f"[GROUPS] ❌ Error fetching groups for user {user_id}: {e}", exc_info=True)
        print(f"[GROUPS] ❌ Error fetching groups for user {user_id}: {e}")
        import traceback
        traceback.print_exc()
    
    return groups


async def get_group_name(client: TelegramClient, group_id: int) -> str:
    """Get group name by ID."""
    try:
        if not client.is_connected():
            await client.connect()
        
        entity = await client.get_entity(group_id)
        if hasattr(entity, 'title'):
            return entity.title
        return f"Guruh {group_id}"
    except Exception:
        return f"Guruh {group_id}"

