"""Rotas do projeto.

Django Admin, healthcheck e a API pública somente leitura sob `/api/`
(as rotas do app `rede` ficam em `rede/urls.py`).
"""
from django.conf import settings
from django.conf.urls.static import static
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

# O Django não serve arquivos de mídia sozinho. Em desenvolvimento (DEBUG=True)
# ele passa a servir os uploads do MEDIA_ROOT, para que as imagens enviadas
# pelo Admin apareçam no ambiente local. Em produção DEBUG=False e este trecho
# fica inerte — quem serve as imagens lá é o Supabase Storage.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
