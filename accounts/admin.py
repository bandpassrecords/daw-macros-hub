from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = [
        'bio', 'location', 'website', 'avatar', 'preferred_cubase_version',
        'show_email', 'show_real_name', 'email_notifications', 'newsletter_subscription',
        'total_uploads', 'total_downloads'
    ]
    readonly_fields = ['total_uploads', 'total_downloads']


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = BaseUserAdmin.list_display + ('get_total_uploads', 'get_total_downloads', 'date_joined')
    
    def get_total_uploads(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.total_uploads
        return 0
    get_total_uploads.short_description = 'Total Uploads'
    
    def get_total_downloads(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.total_downloads
        return 0
    get_total_downloads.short_description = 'Total Downloads'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'get_display_name', 'location', 'preferred_cubase_version',
        'total_uploads', 'total_downloads', 'created_at'
    ]
    list_filter = ['show_email', 'show_real_name', 'email_notifications', 'newsletter_subscription', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'bio', 'location']
    readonly_fields = ['created_at', 'updated_at', 'total_uploads', 'total_downloads']
    raw_id_fields = ['user']
    
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'bio', 'location', 'website', 'avatar', 'preferred_cubase_version')
        }),
        ('Privacy Settings', {
            'fields': ('show_email', 'show_real_name'),
            'classes': ('collapse',)
        }),
        ('Notifications', {
            'fields': ('email_notifications', 'newsletter_subscription'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('total_uploads', 'total_downloads'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_display_name(self, obj):
        return obj.display_name
    get_display_name.short_description = 'Display Name'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
