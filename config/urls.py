"""Rotas do projeto.

Django Admin, healthcheck e a API pública somente leitura sob `/api/`
(as rotas do app `rede` ficam em `rede/urls.py`).
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthcheck(_request):
    """Confirma que o projeto está de pé (usado no smoke test e no deploy)."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", healthcheck, name="health"),
    path("api/", include("rede.urls")),
]
