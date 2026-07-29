"""Rotas da API pública do app `rede`.

Incluídas em `config/urls.py` sob o prefixo `/api/`. Eventos e Pontos de
Interesse entram aqui nas fatias seguintes, no mesmo router.
"""
from rest_framework.routers import DefaultRouter

from rede.views import ColetivoViewSet

router = DefaultRouter()
router.register("coletivos", ColetivoViewSet, basename="coletivo")

urlpatterns = router.urls
