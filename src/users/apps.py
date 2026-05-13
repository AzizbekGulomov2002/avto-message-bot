"""Users app configuration."""
from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Users app config."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        """Register admin modules and cache invalidation when the app is ready."""
        import users.payments  # noqa: F401
        from django.db.models.signals import post_save

        from users.models import User
        from users.superusers import clear_superuser_cache

        post_save.connect(
            lambda **kwargs: clear_superuser_cache(),
            sender=User,
            dispatch_uid='users.clear_superuser_cache',
        )
