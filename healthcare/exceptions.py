from rest_framework.views import exception_handler

def api_exception_handler(exc,context):
    response=exception_handler(exc,context)
    if response is None:return response
    if isinstance(response.data,dict) and 'detail' in response.data:return response
    response.data={'detail':'请求数据校验失败。','errors':response.data}
    return response
