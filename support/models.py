from django.db import models

from flitz.models import BaseModel

from user.models import User


# Create your models here.
class SupportTicket(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')

    title = models.CharField(max_length=255)
    content = models.TextField()

    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class SupportTicketResponse(BaseModel):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='responses')
    responder = models.CharField(max_length=64)

    content = models.TextField()

    def __str__(self):
        return f"Response by {self.responder} on {self.ticket}"

