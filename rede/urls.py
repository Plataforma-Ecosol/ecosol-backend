"""Rotas da API pública do app `rede`.

Incluídas em `config/urls.py` sob o prefixo `/api/`. As três entidades
públicas do sistema — Coletivo, Evento e Ponto de Interesse — entram no mesmo
router, com o mesmo contrato de paginação, busca e filtros.
"""
from rest_framework.routers import DefaultRouter

from rede.views import ColetivoViewSet, EventoViewSet, PontoDeInteresseViewSet

router = DefaultRouter()
router.register("coletivos", ColetivoViewSet, basename="coletivo")
router.register("eventos", EventoViewSet, basename="evento")
router.register(
    "pontos-de-interesse", PontoDeInteresseViewSet, basename="ponto-de-interesse",
)

urlpatterns = router.urls
