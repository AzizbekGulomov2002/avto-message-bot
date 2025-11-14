"""Users app configuration."""
from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Users app config."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    
    def ready(self):
        """Import signals and models when app is ready."""
        import users.payments  # Register UserPayment admin

