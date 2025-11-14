"""Management command to check expired payments."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from users.payments import UserPayment
from users.models import User
from telegram import Bot
import os
import sys
import asyncio

# Add bot directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../../../bot'))
from bot.config import Config


class Command(BaseCommand):
    help = 'Check expired payments and deactivate users, send notifications'

    def handle(self, *args, **options):
        """Handle the command."""
        try:
            today = timezone.now().date()
            
            # Find expired payments with active users
            expired_payments = UserPayment.objects.filter(
                deadline__lte=today,
                user__status=1
            ).select_related('user')
            
            if not expired_payments.exists():
                self.stdout.write(self.style.SUCCESS('No expired payments found.'))
                return
            
            self.stdout.write(f'Found {expired_payments.count()} expired payments.')
            
            # Get bot token and send notifications
            config = Config()
            bot = Bot(token=config.BOT_TOKEN)
            
            deactivated_count = 0
            for payment in expired_payments:
                user = payment.user
                if user.status == 1:  # Only deactivate if still active
                    # Deactivate user
                    user.status = 0
                    user.save(update_fields=['status'])
                    deactivated_count += 1
                    
                    # Send notification
                    try:
                        asyncio.run(bot.send_message(
                            chat_id=user.id,
                            text="⚠️ Sizning akkauntingiz muddati tugadi, iltimos admin bilan bog'laning"
                        ))
                        self.stdout.write(
                            self.style.SUCCESS(f'Deactivated user {user.id} and sent notification.')
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'Error sending notification to user {user.id}: {e}')
                        )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deactivated {deactivated_count} users.')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error checking expired payments: {e}')
            )

