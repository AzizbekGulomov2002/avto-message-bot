# Python Messenger Bot

Bu loyiha Go tilida yozilgan messenger botining Python versiyasidir. Telegram bot va Django admin panelini o'z ichiga oladi.

## Xususiyatlar

- ✅ Telegram bot orqali xabar yuborish
- ✅ Xabarlarni rejalashtirish (cron job)
- ✅ Guruhlarni tanlash va boshqarish
- ✅ Har bir guruhni alohida to'xtatish/davom ettirish
- ✅ Video qo'llanma yuborish
- ✅ Django admin panel orqali foydalanuvchilarni boshqarish
- ✅ PostgreSQL ma'lumotlar bazasi

## O'rnatish

### 1. Kerakli paketlarni o'rnatish

```bash
pip install -r requirements.txt
```

### 2. Ma'lumotlar bazasini sozlash

PostgreSQL ma'lumotlar bazasini yarating va `.env` faylini sozlang:

```bash
cp .env.example .env
```

`.env` faylini tahrirlang va quyidagilarni to'ldiring:

```env
BOT_TOKEN=your_bot_token_here
APP_ID=your_app_id_here
APP_HASH=your_app_hash_here

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=godb
POSTGRES_PASSWORD=0208
POSTGRES_DB=tgbot
```

### 3. Ma'lumotlar bazasi jadvallarini yaratish

Go bot loyihasidagi migration fayllaridan foydalaning yoki quyidagi SQL so'rovlarni bajaring:

```sql
CREATE TABLE users (
    id BIGINT NOT NULL PRIMARY KEY,
    auth INT DEFAULT 0,
    status INT DEFAULT 0,
    full_name VARCHAR(200),
    active_until TIMESTAMPTZ
);

CREATE TABLE groups (
    user_id BIGINT REFERENCES users(id),
    id VARCHAR(100),
    user_name VARCHAR(100),
    name VARCHAR(100)
);

CREATE TABLE scheduled_messages (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    interval_minutes INT NOT NULL,
    paused BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE scheduled_message_groups (
    scheduled_id INT NOT NULL REFERENCES scheduled_messages(id) ON DELETE CASCADE,
    group_id BIGINT NOT NULL,
    PRIMARY KEY (scheduled_id, group_id)
);

CREATE TABLE admins (
    id BIGINT NOT NULL PRIMARY KEY
);
```

## Ishga tushirish

### Botni ishga tushirish

```bash
cd bot
python main.py
```

### Django admin panelni ishga tushirish

```bash
cd django_admin/admin_panel
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Keyin brauzerda `http://localhost:8000/admin` ga kiring.

## Struktura

```
python-messanger-bot/
├── bot/                    # Telegram bot kodi
│   ├── config.py          # Konfiguratsiya
│   ├── main.py            # Asosiy bot fayli
│   ├── handlers/          # Bot handlerlari
│   ├── models/            # Ma'lumotlar modellari
│   └── storage/           # Ma'lumotlar bazasi operatsiyalari
├── django_admin/          # Django admin panel
│   └── admin_panel/
│       ├── users/         # Foydalanuvchilar modellari
│       ├── groups/        # Guruhlar modellari
│       └── messages/      # Xabarlar modellari
├── requirements.txt       # Python paketlari
├── .env.example           # Konfiguratsiya namunasi
└── README.md              # Hujjatlar
```

## Foydalanish

1. Botni ishga tushiring
2. Telegramda botga `/start` buyrug'ini yuboring
3. Telefon raqamingizni kiriting
4. Kodni kiriting (agar kerak bo'lsa, parolni ham)
5. Asosiy menyudan kerakli funksiyani tanlang

## Admin panel

Django admin panel orqali:
- Foydalanuvchilarni ko'rish va boshqarish
- Guruhlarni ko'rish
- Rejalashtirilgan xabarlarni ko'rish va boshqarish

## Eslatmalar

- Bot ishlashi uchun `APP_ID` va `APP_HASH` kerak. Bularni [my.telegram.org](https://my.telegram.org) dan olishingiz mumkin.
- Video qo'llanma uchun `VIDEO_TUTORIAL_FILE_ID` yoki `VIDEO_TUTORIAL_PATH` ni `.env` faylida belgilang.

## Muammolarni hal qilish

### Bot ishlamayapti

- `.env` faylini tekshiring
- Ma'lumotlar bazasi ulanishini tekshiring
- Bot token to'g'riligini tekshiring

### Django admin ishlamayapti

- Ma'lumotlar bazasi ulanishini tekshiring
- `python manage.py migrate` ni bajaring
- Superuser yaratganingizni tekshiring

## Yordam

Muammo bo'lsa, issue oching yoki administrator bilan bog'laning.

