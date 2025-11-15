"""User models for Django admin."""
from django.db import models
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django import forms
from django.utils.html import format_html


class User(models.Model):
    """User model matching database schema."""
    id = models.BigIntegerField(primary_key=True)
    auth = models.IntegerField(default=0)
    status = models.IntegerField(default=0)
    full_name = models.CharField(max_length=200, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
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
    
    @property
    def is_authenticated(self):
        """Return auth as boolean."""
        return bool(self.auth)
    
    @is_authenticated.setter
    def is_authenticated(self, value):
        """Set auth from boolean."""
        self.auth = 1 if value else 0
    
    def get_status_display(self):
        """Get status display with icon."""
        if self.is_active:
            return format_html('<span style="color: green;">✓ Faol</span>')
        return format_html('<span style="color: red;">✗ Nofaol</span>')
    
    def get_auth_display(self):
        """Get auth display with icon."""
        if self.is_authenticated:
            return format_html('<span style="color: green;">✓ Faol</span>')
        return format_html('<span style="color: red;">✗ Nofaol</span>')
    
    def get_active_until_display(self):
        """Get active_until display."""
        if self.active_until:
            from django.utils import timezone
            from django.utils.formats import date_format
            return date_format(self.active_until, "SHORT_DATETIME_FORMAT")
        return "-"


class IsActiveFilter(SimpleListFilter):
    """Custom filter for is_active status."""
    title = 'Status (Faol/Nofaol)'
    parameter_name = 'is_active'
    
    def lookups(self, request, model_admin):
        return (
            ('1', '✓ Faol'),
            ('0', '✗ Nofaol'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(status=1)
        elif self.value() == '0':
            return queryset.filter(status=0)
        return queryset


class IsAuthenticatedFilter(SimpleListFilter):
    """Custom filter for is_authenticated status."""
    title = 'Auth (Faol/Nofaol)'
    parameter_name = 'is_authenticated'
    
    def lookups(self, request, model_admin):
        return (
            ('1', '✓ Faol'),
            ('0', '✗ Nofaol'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(auth=1)
        elif self.value() == '0':
            return queryset.filter(auth=0)
        return queryset


class UserAdminForm(forms.ModelForm):
    """Custom form for User admin with is_active and is_authenticated as BooleanFields."""
    is_active = forms.BooleanField(
        label='Is Active',
        required=False,
        help_text='Check to activate user (status=1), uncheck to deactivate (status=0)'
    )
    is_authenticated = forms.BooleanField(
        label='Is Authenticated',
        required=False,
        help_text='Check if user is authenticated (auth=1), uncheck if not authenticated (auth=0)'
    )
    
    class Meta:
        model = User
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['is_active'].initial = bool(self.instance.status)
            self.fields['is_authenticated'].initial = bool(self.instance.auth)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if 'is_active' in self.cleaned_data:
            instance.status = 1 if self.cleaned_data['is_active'] else 0
        if 'is_authenticated' in self.cleaned_data:
            instance.auth = 1 if self.cleaned_data['is_authenticated'] else 0
        if commit:
            instance.save()
        return instance


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """User admin interface."""
    form = UserAdminForm
    list_display = ('id', 'full_name', 'get_status_display', 'get_auth_display', 'get_active_until_display')
    list_filter = (IsActiveFilter, IsAuthenticatedFilter)
    search_fields = ('id', 'full_name')
    readonly_fields = ('id', 'get_status_display', 'get_auth_display', 'get_active_until_display')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'full_name', 'phone', 'is_active', 'is_authenticated')
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
    
    def get_auth_display(self, obj):
        """Display auth in admin."""
        return obj.get_auth_display()
    get_auth_display.short_description = 'Auth'
    get_auth_display.admin_order_field = 'auth'
    
    def get_active_until_display(self, obj):
        """Display active_until in admin."""
        return obj.get_active_until_display()
    get_active_until_display.short_description = 'Active Until'
    get_active_until_display.admin_order_field = 'active_until'
    
    def save_model(self, request, obj, form, change):
        """Override save to send notification when status is changed."""
        # Get old status if this is an update
        old_status = None
        if change and obj.pk:
            try:
                old_user = User.objects.get(pk=obj.pk)
                old_status = old_user.status
            except User.DoesNotExist:
                pass
        
        # Save the user
        super().save_model(request, obj, form, change)
        
        # Send notification if status changed
        if old_status is not None and old_status != obj.status:
            from .signals import send_telegram_message
            if old_status == 0 and obj.status == 1:
                # Status changed from inactive to active
                message = "✅ Akkauntingiz aktiv qilindi, ishlatishingiz mumkin"
                send_telegram_message(obj.id, message, show_menu=True)
            elif old_status == 1 and obj.status == 0:
                # Status changed from active to inactive
                message = "❌ Sizning akkauntingiz no faol bo'ldi, admin bilan bog'laning: @system24admin"
                send_telegram_message(obj.id, message)
    
    def delete_model(self, request, obj):
        """Override delete to handle foreign key constraints and delete session."""
        from django.db import connection
        import os
        
        # Delete user's session files
        user_id = obj.id
        session_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'bot', 'sessions')
        session_patterns = [
            os.path.join(session_dir, f'session_{user_id}.json'),
            os.path.join(session_dir, f'tg_session_{user_id}.session'),
            os.path.join(session_dir, f'tg_session_{user_id}.session-journal'),
        ]
        
        for pattern in session_patterns:
            try:
                if os.path.exists(pattern):
                    os.remove(pattern)
            except Exception as e:
                print(f"Error deleting session file {pattern}: {e}")
        
        # Delete related data first (only if tables exist)
        with connection.cursor() as cursor:
            # Check if groups table exists and delete related groups
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'groups'
                );
            """)
            groups_exists = cursor.fetchone()[0]
            if groups_exists:
                try:
                    cursor.execute("DELETE FROM groups WHERE user_id = %s", [obj.id])
                except Exception as e:
                    print(f"Error deleting from groups table: {e}")
            
            # Check if messages table exists and delete related messages
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'messages'
                );
            """)
            messages_exists = cursor.fetchone()[0]
            if messages_exists:
                try:
                    cursor.execute("DELETE FROM messages WHERE user_id = %s", [obj.id])
                except Exception as e:
                    print(f"Error deleting from messages table: {e}")
            
            # Delete from scheduled_messages and related tables if they exist
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'scheduled_messages'
                );
            """)
            scheduled_messages_exists = cursor.fetchone()[0]
            if scheduled_messages_exists:
                try:
                    # Delete from scheduled_message_groups first (foreign key constraint)
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'scheduled_message_groups'
                        );
                    """)
                    scheduled_groups_exists = cursor.fetchone()[0]
                    if scheduled_groups_exists:
                        cursor.execute("""
                            DELETE FROM scheduled_message_groups 
                            WHERE scheduled_id IN (
                                SELECT id FROM scheduled_messages WHERE user_id = %s
                            )
                        """, [obj.id])
                    # Delete from scheduled_messages
                    cursor.execute("DELETE FROM scheduled_messages WHERE user_id = %s", [obj.id])
                except Exception as e:
                    print(f"Error deleting from scheduled_messages table: {e}")
        
        # Then delete the user
        super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """Override bulk delete to handle foreign key constraints and delete sessions."""
        from django.db import connection
        import os
        
        # Delete sessions for all users being deleted
        user_ids = list(queryset.values_list('id', flat=True))
        if user_ids:
            session_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'bot', 'sessions')
            for user_id in user_ids:
                session_patterns = [
                    os.path.join(session_dir, f'session_{user_id}.json'),
                    os.path.join(session_dir, f'tg_session_{user_id}.session'),
                    os.path.join(session_dir, f'tg_session_{user_id}.session-journal'),
                ]
                for pattern in session_patterns:
                    try:
                        if os.path.exists(pattern):
                            os.remove(pattern)
                    except Exception as e:
                        print(f"Error deleting session file {pattern}: {e}")
            
            # Delete related data first (only if tables exist)
            with connection.cursor() as cursor:
                # Check if groups table exists and delete related groups
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'groups'
                    );
                """)
                groups_exists = cursor.fetchone()[0]
                if groups_exists:
                    try:
                        cursor.execute("DELETE FROM groups WHERE user_id = ANY(%s)", [user_ids])
                    except Exception as e:
                        print(f"Error deleting from groups table: {e}")
                
                # Check if messages table exists and delete related messages
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'messages'
                    );
                """)
                messages_exists = cursor.fetchone()[0]
                if messages_exists:
                    try:
                        cursor.execute("DELETE FROM messages WHERE user_id = ANY(%s)", [user_ids])
                    except Exception as e:
                        print(f"Error deleting from messages table: {e}")
                
                # Delete from scheduled_messages and related tables if they exist
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'scheduled_messages'
                    );
                """)
                scheduled_messages_exists = cursor.fetchone()[0]
                if scheduled_messages_exists:
                    try:
                        # Delete from scheduled_message_groups first (foreign key constraint)
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = 'scheduled_message_groups'
                            );
                        """)
                        scheduled_groups_exists = cursor.fetchone()[0]
                        if scheduled_groups_exists:
                            cursor.execute("""
                                DELETE FROM scheduled_message_groups 
                                WHERE scheduled_id IN (
                                    SELECT id FROM scheduled_messages WHERE user_id = ANY(%s)
                                )
                            """, [user_ids])
                        # Delete from scheduled_messages
                        cursor.execute("DELETE FROM scheduled_messages WHERE user_id = ANY(%s)", [user_ids])
                    except Exception as e:
                        print(f"Error deleting from scheduled_messages table: {e}")
        # Then delete the users
        super().delete_queryset(request, queryset)

