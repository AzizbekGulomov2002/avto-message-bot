"""User models for Django admin."""
from django.db import models
from django.contrib import admin
from django import forms
from django.utils.html import format_html


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
    
    @property
    def is_active(self):
        """Return status as boolean."""
        return bool(self.status)
    
    @is_active.setter
    def is_active(self, value):
        """Set status from boolean."""
        self.status = 1 if value else 0
    
    def get_status_display(self):
        """Get status display with icon."""
        if self.is_active:
            return format_html('<span style="color: green;">✓ Faol</span>')
        return format_html('<span style="color: red;">✗ Nofaol</span>')


class UserAdminForm(forms.ModelForm):
    """Custom form for User admin with is_active as BooleanField."""
    is_active = forms.BooleanField(
        label='Is Active',
        required=False,
        help_text='Check to activate user (status=1), uncheck to deactivate (status=0)'
    )
    
    class Meta:
        model = User
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['is_active'].initial = bool(self.instance.status)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if 'is_active' in self.cleaned_data:
            instance.status = 1 if self.cleaned_data['is_active'] else 0
        if commit:
            instance.save()
        return instance


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """User admin interface."""
    form = UserAdminForm
    list_display = ('id', 'full_name', 'get_status_display', 'auth', 'active_until')
    list_filter = ('status', 'auth')
    search_fields = ('id', 'full_name')
    readonly_fields = ('id', 'get_status_display')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'full_name', 'is_active', 'auth')
        }),
        ('Subscription', {
            'fields': ('active_until',)
        }),
    )
    
    def get_status_display(self, obj):
        """Display status in admin."""
        return obj.get_status_display()
    get_status_display.short_description = 'Status'
    get_status_display.admin_order_field = 'status'

