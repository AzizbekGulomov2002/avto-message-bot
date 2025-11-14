"""Group models for Django admin."""
from django.db import models
from django.contrib import admin


class Group(models.Model):
    """Group model matching database schema."""
    # Note: id is not unique in DB (multiple users can have same group_id)
    # but Django requires a primary key. For unmanaged models, this works.
    id = models.CharField(max_length=100, primary_key=True)
    user_id = models.BigIntegerField()
    user_name = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    
    class Meta:
        db_table = 'groups'
        managed = False  # Use existing table
        # Note: Actual DB constraint is on (user_id, id), but Django needs a single PK field
        unique_together = [['user_id', 'id']]
    
    def __str__(self):
        return f"{self.name or self.id} (User: {self.user_id})"


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """Group admin interface."""
    list_display = ('id', 'name', 'user_name', 'user_id')
    list_filter = ('user_id',)
    search_fields = ('id', 'name', 'user_name', 'user_id')
    
    fieldsets = (
        ('Group Information', {
            'fields': ('id', 'name', 'user_name', 'user_id')
        }),
    )

