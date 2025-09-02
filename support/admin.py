from django.contrib import admin

# Register your models here.

from support.models import SupportTicket, SupportTicketResponse

admin.site.register(SupportTicket)
admin.site.register(SupportTicketResponse)