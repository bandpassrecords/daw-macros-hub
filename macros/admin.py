from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    CubaseVersion, KeyCommandsFile, MacroCategory, Macro, 
    MacroVote, MacroFavorite, MacroCollection, MacroDownload
)


@admin.register(CubaseVersion)
class CubaseVersionAdmin(admin.ModelAdmin):
    list_display = ['version', 'major_version', 'minor_version', 'patch_version', 'created_at']
    list_filter = ['major_version', 'created_at']
    search_fields = ['version']
    ordering = ['-major_version', '-minor_version', '-patch_version']


@admin.register(KeyCommandsFile)
class KeyCommandsFileAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'cubase_version', 'is_public', 'download_count', 'created_at']
    list_filter = ['is_public', 'cubase_version', 'created_at']
    search_fields = ['name', 'user__username', 'description']
    readonly_fields = ['id', 'download_count', 'created_at', 'updated_at']
    raw_id_fields = ['user']
    
    fieldsets = (
        (None, {
            'fields': ('id', 'user', 'name', 'description', 'file')
        }),
        ('Metadata', {
            'fields': ('cubase_version', 'is_public')
        }),
        ('Statistics', {
            'fields': ('download_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'cubase_version')


@admin.register(MacroCategory)
class MacroCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_macro_count', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']
    
    def get_macro_count(self, obj):
        return obj.macro_set.count()
    get_macro_count.short_description = 'Macros Count'


class MacroVoteInline(admin.TabularInline):
    model = MacroVote
    extra = 0
    readonly_fields = ['user', 'rating', 'comment', 'created_at']
    raw_id_fields = ['user']


@admin.register(Macro)
class MacroAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'category', 'get_user', 'is_public', 
        'get_average_rating', 'vote_count', 'view_count', 'download_count'
    ]
    list_filter = ['is_public', 'category', 'created_at', 'keycommands_file__cubase_version']
    search_fields = ['name', 'description', 'keycommands_file__user__username']
    readonly_fields = [
        'id', 'view_count', 'download_count', 'created_at', 'updated_at',
        'get_average_rating', 'vote_count'
    ]
    raw_id_fields = ['keycommands_file']
    inlines = [MacroVoteInline]
    
    fieldsets = (
        (None, {
            'fields': ('id', 'keycommands_file', 'category', 'name', 'description')
        }),
        ('Settings', {
            'fields': ('key_binding', 'is_public')
        }),
        ('Statistics', {
            'fields': ('get_average_rating', 'vote_count', 'view_count', 'download_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_user(self, obj):
        return obj.keycommands_file.user.username
    get_user.short_description = 'User'
    get_user.admin_order_field = 'keycommands_file__user__username'
    
    def get_average_rating(self, obj):
        avg = obj.average_rating
        if avg > 0:
            return f"{avg:.1f} ⭐"
        return "No ratings"
    get_average_rating.short_description = 'Avg Rating'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'keycommands_file__user', 'category'
        ).prefetch_related('votes')


@admin.register(MacroVote)
class MacroVoteAdmin(admin.ModelAdmin):
    list_display = ['macro', 'user', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['macro__name', 'user__username', 'comment']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['macro', 'user']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('macro', 'user')


@admin.register(MacroFavorite)
class MacroFavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'macro', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'macro__name']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'macro']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'macro')


@admin.register(MacroCollection)
class MacroCollectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'get_macro_count', 'is_public', 'created_at']
    list_filter = ['is_public', 'created_at']
    search_fields = ['name', 'user__username', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['user']
    filter_horizontal = ['macros']
    
    fieldsets = (
        (None, {
            'fields': ('id', 'user', 'name', 'description')
        }),
        ('Settings', {
            'fields': ('is_public',)
        }),
        ('Macros', {
            'fields': ('macros',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_macro_count(self, obj):
        return obj.macros.count()
    get_macro_count.short_description = 'Macros Count'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(MacroDownload)
class MacroDownloadAdmin(admin.ModelAdmin):
    list_display = ['macro', 'get_user_display', 'ip_address', 'downloaded_at']
    list_filter = ['downloaded_at']
    search_fields = ['macro__name', 'user__username', 'ip_address']
    readonly_fields = ['downloaded_at']
    raw_id_fields = ['macro', 'user']
    
    def get_user_display(self, obj):
        if obj.user:
            return obj.user.username
        return f"Anonymous ({obj.ip_address})"
    get_user_display.short_description = 'User'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('macro', 'user')


# Admin site customization
admin.site.site_header = "Cubase Macros Admin"
admin.site.site_title = "Cubase Macros Admin Portal"
admin.site.index_title = "Welcome to Cubase Macros Administration"
