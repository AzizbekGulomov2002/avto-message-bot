"""User payments models for Django admin."""
from django.db import models
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import User


class UserPayment(models.Model):
    """User payment model."""
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    payed_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateField()
    sum = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'user_payments'
        ordering = ['-payed_at']
        verbose_name = 'User Payment'
        verbose_name_plural = 'User Payments'
        managed = True  # Allow Django to manage this table
    
    def __str__(self):
        return f"Payment {self.id} - User {self.user.id} - {self.sum}"
    
    def is_expired(self):
        """Check if payment deadline has expired."""
        if self.deadline is None:
            return False
        return timezone.now().date() >= self.deadline


@admin.register(UserPayment)
class UserPaymentAdmin(admin.ModelAdmin):
    """User payment admin interface."""
    list_display = ('id', 'user', 'sum', 'payed_at', 'deadline', 'is_expired_display')
    list_filter = ('deadline', 'payed_at')
    search_fields = ('user__id', 'user__full_name')
    readonly_fields = ('id', 'payed_at', 'is_expired_display')
    date_hierarchy = 'deadline'
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('id', 'user', 'sum', 'payed_at', 'deadline')
        }),
        ('Status', {
            'fields': ('is_expired_display',)
        }),
    )
    
    def is_expired_display(self, obj):
        """Display expired status."""
        if obj is None or obj.pk is None:
            return format_html('<span style="color: gray;">-</span>')
        if obj.is_expired():
            return format_html('<span style="color: red; font-weight: bold;">⚠️ Muddati tugagan</span>')
        return format_html('<span style="color: green;">✓ Faol</span>')
    is_expired_display.short_description = 'Holat'
    is_expired_display.admin_order_field = 'deadline'

