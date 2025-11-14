"""Message models for Django admin."""
from django.db import models
from django.contrib import admin


class ScheduledMessage(models.Model):
    """Scheduled message model."""
    id = models.AutoField(primary_key=True)
    user_id = models.BigIntegerField()
    message = models.TextField()
    interval_minutes = models.IntegerField()
    paused = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'scheduled_messages'
        managed = False  # Use existing table
    
    def __str__(self):
        return f"Message {self.id} (User: {self.user_id})"


class ScheduledMessageGroup(models.Model):
    """Scheduled message group relation."""
    scheduled_id = models.IntegerField()
    group_id = models.BigIntegerField()
    
    class Meta:
        db_table = 'scheduled_message_groups'
        managed = False  # Use existing table
        unique_together = [['scheduled_id', 'group_id']]
    
    def __str__(self):
        return f"Scheduled {self.scheduled_id} - Group {self.group_id}"


@admin.register(ScheduledMessage)
class ScheduledMessageAdmin(admin.ModelAdmin):
    """Scheduled message admin interface."""
    list_display = ('id', 'user_id', 'interval_minutes', 'paused', 'expires_at', 'created_at')
    list_filter = ('paused', 'created_at')
    search_fields = ('id', 'user_id', 'message')
    readonly_fields = ('id', 'created_at')
    
    fieldsets = (
        ('Message Information', {
            'fields': ('id', 'user_id', 'message', 'interval_minutes', 'paused', 'expires_at', 'created_at')
        }),
    )


@admin.register(ScheduledMessageGroup)
class ScheduledMessageGroupAdmin(admin.ModelAdmin):
    """Scheduled message group admin interface."""
    list_display = ('scheduled_id', 'group_id')
    list_filter = ('scheduled_id',)
    search_fields = ('scheduled_id', 'group_id')

