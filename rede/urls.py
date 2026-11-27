"""Rotas da API pública do app `rede`.

Incluídas em `config/urls.py` sob o prefixo `/api/`. As três entidades
públicas do sistema — Coletivo, Evento e Ponto de Interesse — entram no mesmo
router, com o mesmo contrato de paginação, busca e filtros.

As seções do Saiba mais também estão no router, por terem lista e detalhe,
mas fogem desse contrato: a listagem vem agrupada por subgrupo, sem
paginação nem parâmetros (ver `SecaoSaibaMaisViewSet`).

As opções dos painéis de filtro (`/api/filtros/...`) ficam fora do router:
não são recurso com lista e detalhe, são uma resposta só por listagem.

A API da equipe (`/api/equipe/...`) também mora aqui, mas em views separadas
(`rede/views_equipe.py`): exige sessão de equipe do Admin, sem cache.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from rede.views import (
    ColetivoViewSet,
    EventoViewSet,
    FiltrosDeColetivosView,
    FiltrosDeEventosView,
    PontoDeInteresseViewSet,
    SecaoSaibaMaisViewSet,
)
from rede.views_equipe import DistribuicaoDosColetivosView, EuView, IndicadoresGeraisView

router = DefaultRouter()
router.register("coletivos", ColetivoViewSet, basename="coletivo")
router.register("eventos", EventoViewSet, basename="evento")
router.register(
    "pontos-de-interesse", PontoDeInteresseViewSet, basename="ponto-de-interesse",
)
router.register("saiba-mais", SecaoSaibaMaisViewSet, basename="secao-saiba-mais")

urlpatterns = [
    path("filtros/coletivos/", FiltrosDeColetivosView.as_view(), name="filtros-coletivos"),
    path("filtros/eventos/", FiltrosDeEventosView.as_view(), name="filtros-eventos"),
    path("equipe/eu/", EuView.as_view(), name="equipe-eu"),
    path(
        "equipe/relatorio/distribuicao/",
        DistribuicaoDosColetivosView.as_view(),
        name="equipe-relatorio-distribuicao",
    ),
    path(
        "equipe/relatorio/indicadores/",
        IndicadoresGeraisView.as_view(),
        name="equipe-relatorio-indicadores",
    ),
    *router.urls,
]
