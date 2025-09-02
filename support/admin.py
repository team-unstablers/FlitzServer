from django.contrib import admin
from django.utils.html import format_html

from support.models import SupportTicket, SupportTicketResponse


class SupportTicketResponseInline(admin.TabularInline):
    model = SupportTicketResponse
    extra = 1
    fields = ['responder', 'content', 'created_at']
    readonly_fields = ['created_at']


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'is_resolved', 'response_count', 'created_at']
    list_filter = ['is_resolved', 'created_at']
    search_fields = ['title', 'content', 'user__username', 'user__display_name']
    readonly_fields = ['created_at', 'updated_at']
    
    inlines = [SupportTicketResponseInline]
    
    fieldsets = (
        ('티켓 정보', {
            'fields': ('user', 'title', 'content')
        }),
        ('상태', {
            'fields': ('is_resolved',)
        }),
        ('시간 정보', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def response_count(self, obj):
        count = obj.responses.count()
        if count > 0:
            return format_html('<span style="color: green;">{}</span>', count)
        return format_html('<span style="color: gray;">{}</span>', count)
    response_count.short_description = '응답 수'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').prefetch_related('responses')


@admin.register(SupportTicketResponse)
class SupportTicketResponseAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'responder', 'created_at']
    list_filter = ['created_at', 'responder']
    search_fields = ['ticket__title', 'responder', 'content']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('응답 정보', {
            'fields': ('ticket', 'responder', 'content')
        }),
        ('시간 정보', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('ticket', 'ticket__user')