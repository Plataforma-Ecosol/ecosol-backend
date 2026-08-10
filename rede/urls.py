"""Rotas da API pública do app `rede`.

Incluídas em `config/urls.py` sob o prefixo `/api/`. Pontos de Interesse
entram aqui na fatia seguinte, no mesmo router.
"""
from rest_framework.routers import DefaultRouter

from rede.views import ColetivoViewSet, EventoViewSet

router = DefaultRouter()
router.register("coletivos", ColetivoViewSet, basename="coletivo")
router.register("eventos", EventoViewSet, basename="evento")

urlpatterns = router.urls
