"""Message models for Django admin."""
from django.db import models
from django.contrib import admin


# ScheduledMessage and ScheduledMessageGroup models removed
# These are managed through the bot application, not Django admin


class ScheduleInterval(models.Model):
    """Schedule interval options for message sending."""
    id = models.AutoField(primary_key=True)
    time = models.FloatField(help_text="Time value (e.g., 5, 10, 30)")
    time_type = models.CharField(
        max_length=20,
        choices=[
            ('sekund', 'Sekund'),
            ('minut', 'Minut'),
            ('soat', 'Soat'),
        ],
        default='minut',
        help_text="Time unit: sekund, minut, or soat"
    )
    display_order = models.IntegerField(default=0, help_text="Order in which to display this option")
    is_active = models.BooleanField(default=True, help_text="Whether this option is active")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'schedule_intervals'
        managed = False  # Table created manually via migration
        ordering = ['display_order', 'time']
        verbose_name = 'Schedule Interval'
        verbose_name_plural = 'Schedule Intervals'
    
    def __str__(self):
        time_unit = {
            'sekund': 'sekund',
            'minut': 'daqiqa',
            'soat': 'soat'
        }.get(self.time_type, self.time_type)
        return f"{int(self.time) if self.time.is_integer() else self.time} {time_unit}"
    
    def get_minutes(self):
        """Convert to minutes for internal use."""
        if self.time_type == 'sekund':
            return self.time / 60.0
        elif self.time_type == 'minut':
            return self.time
        elif self.time_type == 'soat':
            return self.time * 60.0
        return self.time


class DurationOption(models.Model):
    """Duration options for message sending."""
    id = models.AutoField(primary_key=True)
    time = models.FloatField(help_text="Time value (e.g., 1, 2, 3)")
    time_type = models.CharField(
        max_length=20,
        choices=[
            ('sekund', 'Sekund'),
            ('minut', 'Minut'),
            ('soat', 'Soat'),
        ],
        default='soat',
        help_text="Time unit: sekund, minut, or soat"
    )
    display_order = models.IntegerField(default=0, help_text="Order in which to display this option")
    is_active = models.BooleanField(default=True, help_text="Whether this option is active")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'duration_options'
        managed = False  # Table created manually via migration
        ordering = ['display_order', 'time']
        verbose_name = 'Duration Option'
        verbose_name_plural = 'Duration Options'
    
    def __str__(self):
        time_unit = {
            'sekund': 'sekund',
            'minut': 'daqiqa',
            'soat': 'soat'
        }.get(self.time_type, self.time_type)
        return f"{int(self.time) if self.time.is_integer() else self.time} {time_unit}"
    
    def get_hours(self):
        """Convert to hours for internal use."""
        if self.time_type == 'sekund':
            return self.time / 3600.0
        elif self.time_type == 'minut':
            return self.time / 60.0
        elif self.time_type == 'soat':
            return self.time
        return self.time


@admin.register(ScheduleInterval)
class ScheduleIntervalAdmin(admin.ModelAdmin):
    """Schedule interval admin interface."""
    list_display = ('id', 'time', 'time_type', 'display_order', 'is_active', 'created_at')
    list_filter = ('time_type', 'is_active', 'created_at')
    search_fields = ('time',)
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'time')


@admin.register(DurationOption)
class DurationOptionAdmin(admin.ModelAdmin):
    """Duration option admin interface."""
    list_display = ('id', 'time', 'time_type', 'display_order', 'is_active', 'created_at')
    list_filter = ('time_type', 'is_active', 'created_at')
    search_fields = ('time',)
    list_editable = ('display_order', 'is_active')
    ordering = ('display_order', 'time')

