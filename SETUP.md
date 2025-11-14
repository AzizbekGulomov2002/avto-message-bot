# O'rnatish Qo'llanmasi

## Talablar

- Python 3.8 yoki yuqori versiya
- PostgreSQL ma'lumotlar bazasi
- Telegram Bot Token
- Telegram API credentials (APP_ID va APP_HASH)

## Qadam-baqadam o'rnatish

### 1. Loyihani klonlash yoki yuklab olish

```bash
cd /path/to/python-messanger-bot
```

### 2. Virtual environment yaratish

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# yoki
venv\Scripts\activate  # Windows
```

### 3. Paketlarni o'rnatish

```bash
pip install -r requirements.txt
```

### 4. Ma'lumotlar bazasini sozlash

PostgreSQL ma'lumotlar bazasini yarating:

```sql
CREATE DATABASE tgbot;
```

### 5. Environment variables sozlash

`.env.example` faylini `.env` ga nusxalang va to'ldiring:

```bash
cp .env.example .env
```

`.env` faylini tahrirlang:

```env
BOT_TOKEN=your_bot_token_from_botfather
APP_ID=your_app_id_from_my_telegram_org
APP_HASH=your_app_hash_from_my_telegram_org

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=tgbot
```

### 6. Ma'lumotlar bazasi jadvallarini yaratish

Go bot loyihasidagi migration fayllaridan foydalaning yoki quyidagi SQL so'rovlarni bajaring:

```sql
-- users jadvali
CREATE TABLE users (
    id BIGINT NOT NULL PRIMARY KEY,
    auth INT DEFAULT 0,
    status INT DEFAULT 0,
    full_name VARCHAR(200),
    active_until TIMESTAMPTZ
);

-- groups jadvali
CREATE TABLE groups (
    user_id BIGINT REFERENCES users(id),
    id VARCHAR(100),
    user_name VARCHAR(100),
    name VARCHAR(100)
);

-- scheduled_messages jadvali
CREATE TABLE scheduled_messages (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    interval_minutes INT NOT NULL,
    paused BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- scheduled_message_groups jadvali
CREATE TABLE scheduled_message_groups (
    scheduled_id INT NOT NULL REFERENCES scheduled_messages(id) ON DELETE CASCADE,
    group_id BIGINT NOT NULL,
    PRIMARY KEY (scheduled_id, group_id)
);

-- admins jadvali
CREATE TABLE admins (
    id BIGINT NOT NULL PRIMARY KEY
);
```

### 7. Botni ishga tushirish

```bash
./run_bot.sh
# yoki
cd bot && python main.py
```

### 8. Django admin panelni ishga tushirish

Yangi terminal oynasida:

```bash
cd src/config
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Keyin brauzerda `http://localhost:8000/admin` ga kiring.

## Telegram API credentials olish

1. [my.telegram.org](https://my.telegram.org) ga kiring
2. Telefon raqamingizni kiriting
3. Kodni kiriting
4. "API development tools" bo'limiga kiring
5. `api_id` va `api_hash` ni oling

## Bot token olish

1. Telegramda [@BotFather](https://t.me/BotFather) ga kiring
2. `/newbot` buyrug'ini yuboring
3. Bot nomini va username ni kiriting
4. Bot token ni oling

## Muammolarni hal qilish

### Bot ishlamayapti

- `.env` faylini tekshiring
- Ma'lumotlar bazasi ulanishini tekshiring: `psql -U your_user -d tgbot`
- Bot token to'g'riligini tekshiring

### Django admin ishlamayapti

- Ma'lumotlar bazasi ulanishini tekshiring
- `python manage.py migrate` ni bajaring
- Superuser yaratganingizni tekshiring: `python manage.py createsuperuser`

### Guruhlar ko'rinmayapti

- Foydalanuvchi autentifikatsiya qilganini tekshiring
- Telegram client to'g'ri ishlayotganini tekshiring
- Session fayllarini tekshiring (`tg_session_*.session`)

## Qo'shimcha ma'lumot

Batafsil ma'lumot uchun `README.md` faylini ko'ring.

