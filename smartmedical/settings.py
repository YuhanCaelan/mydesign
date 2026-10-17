import os
from datetime import timedelta
from pathlib import Path

BASE_DIR=Path(__file__).resolve().parent.parent
SECRET_KEY=os.environ.get('SMARTMEDICAL_SECRET_KEY','django-insecure-smartmedical-local-development-only')
DEBUG=os.environ.get('SMARTMEDICAL_DEBUG','1')=='1'
ALLOWED_HOSTS=[item.strip() for item in os.environ.get('SMARTMEDICAL_ALLOWED_HOSTS','127.0.0.1,localhost').split(',') if item.strip()]

INSTALLED_APPS=[
    'django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions',
    'django.contrib.messages','django.contrib.staticfiles','rest_framework','healthcare',
]
MIDDLEWARE=[
    'django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF='smartmedical.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='smartmedical.wsgi.application'
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'smartmedical.sqlite3'}}
AUTH_PASSWORD_VALIDATORS=[
    {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE='zh-hans';TIME_ZONE='Asia/Shanghai';USE_I18N=True;USE_TZ=True
STATIC_URL='/static/';STATIC_ROOT=BASE_DIR/'smartmedical_static'
MEDIA_URL='/protected-media/';MEDIA_ROOT=BASE_DIR/'smartmedical_media'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
AUTH_USER_MODEL='healthcare.User'
REST_FRAMEWORK={
    'DEFAULT_AUTHENTICATION_CLASSES':('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES':('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_PAGINATION_CLASS':'healthcare.pagination.StandardPagination','PAGE_SIZE':20,
    'DEFAULT_FILTER_BACKENDS':('rest_framework.filters.SearchFilter','rest_framework.filters.OrderingFilter'),
    'DEFAULT_RENDERER_CLASSES':('rest_framework.renderers.JSONRenderer',),
    'EXCEPTION_HANDLER':'healthcare.exceptions.api_exception_handler',
}
SIMPLE_JWT={'ACCESS_TOKEN_LIFETIME':timedelta(minutes=60),'REFRESH_TOKEN_LIFETIME':timedelta(days=7),'ROTATE_REFRESH_TOKENS':True,'BLACKLIST_AFTER_ROTATION':False}
FILE_UPLOAD_MAX_MEMORY_SIZE=10*1024*1024
DATA_UPLOAD_MAX_MEMORY_SIZE=12*1024*1024
