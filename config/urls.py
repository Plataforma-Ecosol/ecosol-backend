"""Rotas do projeto.

As rotas da API pública (/api/coletivos/) entram no PR 5.
Por ora, temos o Django Admin e um healthcheck simples.
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def healthcheck(_request):
    """Confirma que o projeto está de pé (usado no smoke test e no deploy)."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", healthcheck, name="health"),
]
