from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """统一分页：默认 20 条，允许前端通过 page_size 指定每页条数。"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
