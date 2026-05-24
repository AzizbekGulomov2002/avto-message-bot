"""Users app configuration."""
from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Users app config."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        """Register admin modules and user signals when the app is ready."""
        import users.payments  # noqa: F401
        from django.db.models.signals import post_save, pre_save

        from users.models import User
        from users.notifications import (
            notify_pending_activation_requests_for_superuser,
            notify_superuser_assigned,
        )
        from users.superusers import clear_superuser_cache

        def cache_previous_superuser(sender, instance, **kwargs):
            if not instance.pk:
                instance._was_superuser = False
                return
            try:
                previous = User.objects.get(pk=instance.pk)
                instance._was_superuser = previous.is_superuser
            except User.DoesNotExist:
                instance._was_superuser = False

        def handle_user_saved(sender, instance, **kwargs):
            try:
                clear_superuser_cache()
                was_superuser = getattr(instance, '_was_superuser', False)
                if instance.is_superuser and not was_superuser:
                    notify_superuser_assigned(instance.id)
                    notify_pending_activation_requests_for_superuser(instance.id)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Failed post-save superuser handling for user %s",
                    instance.id,
                )

        pre_save.connect(
            cache_previous_superuser,
            sender=User,
            dispatch_uid='users.cache_previous_superuser',
        )
        post_save.connect(
            handle_user_saved,
            sender=User,
            dispatch_uid='users.handle_user_saved',
        )
