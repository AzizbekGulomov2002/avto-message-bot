"""User models for Django admin."""
from django.db import models
from django.contrib import admin


class User(models.Model):
    """User model matching database schema."""
    id = models.BigIntegerField(primary_key=True)
    auth = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    full_name = models.CharField(max_length=200, null=True, blank=True)
    active_until = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'users'
        managed = False  # Use existing table
    
    def __str__(self):
        return f"{self.id} - {self.full_name or 'No name'}"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """User admin interface."""
    list_display = ('id', 'full_name', 'status', 'auth', 'active_until')
    list_filter = ('status', 'auth')
    search_fields = ('id', 'full_name')
    readonly_fields = ('id',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'full_name', 'status', 'auth')
        }),
        ('Subscription', {
            'fields': ('active_until',)
        }),
    )

