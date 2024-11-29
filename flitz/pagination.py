from rest_framework import pagination

class CursorPagination(pagination.CursorPagination):
    ordering = '-created_at'
    max_page_size = 50