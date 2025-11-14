"""Messages app configuration."""
from django.apps import AppConfig


class MessagesConfig(AppConfig):
    """Messages app config."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'messages'
    label = 'bot_messages'

