from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from support.models import SupportTicket, SupportTicketResponse
from support.serializers import (SupportTicketCreateSerializer,
                                 SupportTicketResponseCreateSerializer,
                                 SupportTicketResponseSerializer,
                                 SupportTicketSerializer)

# Create your views here.

class SupportTicketViewSet(viewsets.ModelViewSet):

    def get_serializer_class(self):
        if self.action == 'create':
            return SupportTicketCreateSerializer

        return SupportTicketSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.validation_error',
            }, status=400)

        data = serializer.validated_data
        ticket = SupportTicket.objects.create(
            user=request.user,
            title=data['title'],
            content=data['content']
        )

        return Response(SupportTicketSerializer(ticket).data, status=201)

    def get_queryset(self):
        return SupportTicket.objects.filter(user=self.request.user).order_by('-created_at')

    def destroy(self, request, *args, **kwargs):
        return Response({ 'is_success': False, 'reason': 'fz.method_not_allowed' }, status=405)

    @action(detail=True, methods=['get'], url_path='responses', url_name='responses')
    def responses(self, request, pk=None):
        ticket = self.get_object()
        responses = ticket.responses.all().order_by('created_at')
        serializer = SupportTicketResponseSerializer(responses, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='responses', url_name='response')
    def add_response(self, request, pk=None):
        ticket = self.get_object()
        serializer = SupportTicketResponseCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.validation_error',
            }, status=400)

        data = serializer.validated_data
        response = SupportTicketResponse.objects.create(
            ticket=ticket,
            responder='__USER__',
            content=data['content']
        )

        return Response(SupportTicketResponseSerializer(response).data, status=201)



