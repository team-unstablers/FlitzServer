from rest_framework import pagination, status
from rest_framework.response import Response


class CursorPagination(pagination.CursorPagination):
    ordering = '-created_at'
    max_page_size = 50