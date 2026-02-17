from django.contrib import admin
from django.urls import path
from whatsapp_inbound.api import api

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", api.urls),
]
