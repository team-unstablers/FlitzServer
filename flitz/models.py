from uuid_v7.base import uuid7

from django.db import models

class UUIDv7Field(models.UUIDField):
    def __init__(self, *args, **kwargs):
        kwargs['default'] = uuid7
        super().__init__(*args, **kwargs)


class BaseModel(models.Model):
    id = UUIDv7Field(primary_key=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True