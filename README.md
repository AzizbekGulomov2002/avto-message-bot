# Avto Message Bot

Python implementation of a Telegram messenger bot with a Django admin panel. Users authenticate with their Telegram account, schedule recurring messages to selected groups, and are managed through the admin interface.

## Features

- Send messages through Telegram
- Schedule recurring messages with configurable intervals and duration
- Select and manage target groups
- Pause or resume scheduled messages per group
- Video tutorial delivery
- User management through the Django admin panel
- PostgreSQL database
- Superuser approval flow with an access end date after user authentication

## Requirements

- Python 3.8 or newer
- PostgreSQL
- Telegram bot token
- Telegram API credentials (`APP_ID` and `APP_HASH`)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/AzizbekGulomov2002/avto-message-bot.git
cd avto-message-bot
```

### 2. Create a virtual environment

```bash
python3 -m venv env
source env/bin/activate
```

On Windows:

```bash
env\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```env
BOT_TOKEN=your_bot_token_here
APP_ID=your_app_id_here
APP_HASH=your_app_hash_here

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_DB=your_db_name

DJANGO_SECRET_KEY=your-secret-key-here-change-in-production
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
```

Optional:

- `VIDEO_TUTORIAL_FILE_ID` or `VIDEO_TUTORIAL_PATH` for the tutorial video
- `SUPERUSER_IDS` as a comma-separated list of Telegram user IDs allowed to approve access
- `LOG_LEVEL` for logging verbosity

### 5. Prepare the database

Create a PostgreSQL database, then run Django migrations:

```bash
cd src/config
python manage.py migrate
python manage.py createsuperuser
cd ../..
```

The bot also creates required runtime tables on startup when needed.

## Running the project

### Start the bot

From the project root:

```bash
source env/bin/activate
python -m bot.main
```

Or:

```bash
./run_bot.sh
```

### Start the Django admin panel

```bash
source env/bin/activate
cd src/config
python manage.py runserver
```

Or:

```bash
./run_django.sh
```

Open `http://localhost:8000/admin` in your browser.

## Project structure

```text
avto-message-bot/
├── bot/                    # Telegram bot
│   ├── config.py           # Configuration
│   ├── main.py             # Main bot entry point
│   ├── handlers/           # Bot handlers
│   ├── models/             # Data models
│   └── storage/            # Database operations
├── src/                    # Django admin panel
│   └── config/
│       ├── users/          # User models and admin
│       └── messages/       # Message models and admin
├── requirements.txt
├── .env.example
├── run_bot.sh
├── run_django.sh
└── README.md
```

## Usage

1. Start the bot and the Django admin panel.
2. In Telegram, send `/start` to the bot.
3. Submit your phone number and complete authentication.
4. Wait for superuser approval if your account is not active yet.
5. Use the main menu to send or schedule messages.

## Admin panel

Through Django admin you can:

- View and manage users, including phone numbers and access status
- Review scheduled messages
- Activate or deactivate users and set access end dates

If `SUPERUSER_IDS` is not set, Telegram IDs from the `admins` table are used for approval notifications.

## Notes

- `APP_ID` and `APP_HASH` are available from [my.telegram.org](https://my.telegram.org).
- The bot token is created through [@BotFather](https://t.me/BotFather).
- Do not commit `.env` or session files to version control.

## Troubleshooting

### Bot does not start

- Verify `.env` values
- Check the PostgreSQL connection
- Confirm the bot token is valid

### Django admin does not work

- Verify database credentials
- Run `python manage.py migrate`
- Ensure a superuser account exists

## Support

Open an issue on GitHub or contact the project administrator if you need help.
