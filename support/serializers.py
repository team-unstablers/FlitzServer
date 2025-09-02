from rest_framework import serializers

from support.models import SupportTicket, SupportTicketResponse


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ['id', 'title', 'content', 'is_resolved', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class SupportTicketResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicketResponse
        fields = ['content', 'responder', 'created_at', 'updated_at']
        
class SupportTicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ['title', 'content']

class SupportTicketResponseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicketResponse
        fields = ['content']
