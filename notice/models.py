from django.db import models
from django.utils import timezone

from flitz.models import BaseModel


class Notice(BaseModel):
    """
    공지사항 모델
    """
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['deleted_at']),
        ]

    title = models.CharField(max_length=255, help_text="공지사항 제목")
    content = models.TextField(help_text="공지사항 내용")
    
    deleted_at = models.DateTimeField(null=True, blank=True, default=None, help_text="삭제 일시")

    def __str__(self):
        return self.title
    
    @property
    def is_deleted(self):
        """공지사항이 삭제되었는지 여부"""
        return self.deleted_at is not None
    
    def soft_delete(self):
        """Soft Delete 수행"""
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at', 'updated_at'])
