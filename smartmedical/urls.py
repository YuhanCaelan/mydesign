from django.contrib import admin
from django.http import HttpResponse
from django.urls import include,path,re_path
from django.views.static import serve
from django.conf import settings

def vue_frontend(request):
    index=settings.BASE_DIR/'frontend'/'dist'/'index.html'
    if not index.exists(): return HttpResponse('请先在 frontend 执行 npm run build。',status=503)
    return HttpResponse(index.read_text(encoding='utf-8'),content_type='text/html; charset=utf-8')

urlpatterns=[
    path('admin/',admin.site.urls),path('api/v1/',include('healthcare.urls')),
    path('',vue_frontend),path('app/',vue_frontend),
    re_path(r'^app/assets/(?P<path>.+)$',serve,{'document_root':settings.BASE_DIR/'frontend'/'dist'/'assets'}),
    re_path(r'^app/.*$',vue_frontend),
]
