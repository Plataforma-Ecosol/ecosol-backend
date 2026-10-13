"""Rotas da API pública do app `rede`.

Incluídas em `config/urls.py` sob o prefixo `/api/`. As três entidades
públicas do sistema — Coletivo, Evento e Ponto de Interesse — entram no mesmo
router, com o mesmo contrato de paginação, busca e filtros.

As opções dos painéis de filtro (`/api/filtros/...`) ficam fora do router:
não são recurso com lista e detalhe, são uma resposta só por listagem.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from rede.views import (
    ColetivoViewSet,
    EventoViewSet,
    FiltrosDeColetivosView,
    FiltrosDeEventosView,
    PontoDeInteresseViewSet,
)

router = DefaultRouter()
router.register("coletivos", ColetivoViewSet, basename="coletivo")
router.register("eventos", EventoViewSet, basename="evento")
router.register(
    "pontos-de-interesse", PontoDeInteresseViewSet, basename="ponto-de-interesse",
)

urlpatterns = [
    path("filtros/coletivos/", FiltrosDeColetivosView.as_view(), name="filtros-coletivos"),
    path("filtros/eventos/", FiltrosDeEventosView.as_view(), name="filtros-eventos"),
    *router.urls,
]
