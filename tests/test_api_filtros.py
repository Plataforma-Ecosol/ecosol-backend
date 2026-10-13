"""Opções dos painéis de filtro e a combinação de categorias.

`/api/filtros/coletivos/` e `/api/filtros/eventos/` alimentam o painel de
filtros do frontend (PRD de componentes do frontend, seção 3). A regra que
mais importa aqui é a de visibilidade: só entra opção em uso por registro
ATIVO — um bairro que só existe num coletivo tirado do ar denunciaria que ele
existe.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from rede.filters import MAXIMO_DE_CATEGORIAS
from rede.models import Categoria, Coletivo, Evento

pytestmark = pytest.mark.django_db


def coletivo(slug, bairro="", categorias=(), ativo=True):
    novo = Coletivo.objects.create(nome=slug, slug=slug, bairro=bairro, ativo=ativo)
    novo.categorias.add(*categorias)
    return novo


def evento(slug, bairro="", ativo=True):
    return Evento.objects.create(
        titulo=slug,
        slug=slug,
        bairro=bairro,
        ativo=ativo,
        data_inicio=timezone.now() + timedelta(days=1),
    )


# --- /api/filtros/coletivos/ -------------------------------------------------


def test_opcoes_de_coletivos_tem_categorias_e_bairros(api):
    moda = Categoria.objects.create(nome="Moda", slug="moda")
    alimentacao = Categoria.objects.create(nome="Alimentação", slug="alimentacao")
    coletivo("a", bairro="Icaraí", categorias=[moda, alimentacao])
    coletivo("b", bairro="Centro", categorias=[moda])

    resposta = api.get("/api/filtros/coletivos/")

    assert resposta.status_code == 200
    assert resposta.json() == {
        "categorias": [
            {"id": alimentacao.id, "nome": "Alimentação", "slug": "alimentacao"},
            {"id": moda.id, "nome": "Moda", "slug": "moda"},
        ],
        "bairros": ["Centro", "Icaraí"],
    }


def test_opcoes_ignoram_coletivo_inativo_e_categoria_sem_uso(api):
    """Só o que está em uso por coletivo ATIVO vira opção."""
    usada = Categoria.objects.create(nome="Usada", slug="usada")
    so_do_inativo = Categoria.objects.create(nome="Só do inativo", slug="so-do-inativo")
    Categoria.objects.create(nome="Sem coletivo", slug="sem-coletivo")
    coletivo("ativo", bairro="Centro", categorias=[usada])
    coletivo("inativo", bairro="Jurujuba", categorias=[so_do_inativo], ativo=False)

    dados = api.get("/api/filtros/coletivos/").json()

    assert [c["nome"] for c in dados["categorias"]] == ["Usada"]
    assert dados["bairros"] == ["Centro"]


def test_categoria_de_varios_coletivos_aparece_uma_vez(api):
    moda = Categoria.objects.create(nome="Moda", slug="moda")
    for slug in ("a", "b", "c"):
        coletivo(slug, categorias=[moda])

    assert len(api.get("/api/filtros/coletivos/").json()["categorias"]) == 1


def test_bairros_sem_repeticao_por_maiuscula_com_a_grafia_mais_usada(api):
    """"Centro" e "centro" são o mesmo filtro (`iexact`), então uma opção só."""
    coletivo("a", bairro="Centro")
    coletivo("b", bairro="Centro")
    coletivo("c", bairro="centro")
    coletivo("d", bairro="")

    assert api.get("/api/filtros/coletivos/").json()["bairros"] == ["Centro"]


def test_bairros_em_ordem_alfabetica_ignorando_acento(api):
    for slug, bairro in [("a", "Zona Sul"), ("b", "Ícaro"), ("c", "Barreto")]:
        coletivo(slug, bairro=bairro)

    assert api.get("/api/filtros/coletivos/").json()["bairros"] == [
        "Barreto",
        "Ícaro",
        "Zona Sul",
    ]


def test_opcoes_de_coletivos_em_numero_fixo_de_queries(api, django_assert_num_queries):
    """Uma query para as categorias e uma para os bairros, com qualquer volume."""
    moda = Categoria.objects.create(nome="Moda", slug="moda")
    for i in range(10):
        coletivo(f"c{i}", bairro=f"Bairro {i}", categorias=[moda])

    with django_assert_num_queries(2):
        api.get("/api/filtros/coletivos/")


# --- /api/filtros/eventos/ ---------------------------------------------------


def test_opcoes_de_eventos_tem_os_bairros_dos_eventos_ativos(api):
    evento("feira", bairro="Centro")
    evento("roda", bairro="Fonseca")
    evento("oculto", bairro="Jurujuba", ativo=False)

    resposta = api.get("/api/filtros/eventos/")

    assert resposta.status_code == 200
    assert resposta.json() == {"bairros": ["Centro", "Fonseca"]}


def test_opcoes_sao_somente_leitura(api):
    assert api.post("/api/filtros/coletivos/", {}).status_code == 405
    assert api.post("/api/filtros/eventos/", {}).status_code == 405


# --- ?categoria= repetida ----------------------------------------------------


@pytest.fixture
def categorias_e_coletivos():
    moda = Categoria.objects.create(nome="Moda", slug="moda")
    alimentacao = Categoria.objects.create(nome="Alimentação", slug="alimentacao")
    coletivo("so-moda", categorias=[moda])
    coletivo("so-alimentacao", categorias=[alimentacao])
    coletivo("as-duas", categorias=[moda, alimentacao])
    return moda, alimentacao


def slugs(resposta):
    return sorted(c["slug"] for c in resposta.json()["results"])


def test_categorias_repetidas_combinam_com_e(api, categorias_e_coletivos):
    moda, alimentacao = categorias_e_coletivos

    resposta = api.get(f"/api/coletivos/?categoria={moda.id}&categoria={alimentacao.id}")

    assert slugs(resposta) == ["as-duas"]


def test_uma_categoria_continua_como_antes(api, categorias_e_coletivos):
    moda, _ = categorias_e_coletivos

    assert slugs(api.get(f"/api/coletivos/?categoria={moda.id}")) == ["as-duas", "so-moda"]


def test_combinacao_nao_repete_coletivo(api, categorias_e_coletivos):
    """Um coletivo nas duas categorias aparece uma vez, e o `count` bate."""
    moda, alimentacao = categorias_e_coletivos

    dados = api.get(
        f"/api/coletivos/?categoria={moda.id}&categoria={alimentacao.id}&categoria={moda.id}"
    ).json()

    assert dados["count"] == 1
    assert len(dados["results"]) == 1


def test_categoria_inexistente_devolve_lista_vazia(api, categorias_e_coletivos):
    """Categoria que saiu do cadastro não derruba um link já compartilhado."""
    moda, _ = categorias_e_coletivos

    resposta = api.get(f"/api/coletivos/?categoria={moda.id}&categoria=99999")

    assert resposta.status_code == 200
    assert resposta.json()["count"] == 0


def test_categoria_em_texto_responde_400_mesmo_repetida(api, categorias_e_coletivos):
    moda, _ = categorias_e_coletivos

    assert api.get(f"/api/coletivos/?categoria={moda.id}&categoria=texto").status_code == 400


def test_teto_de_categorias_combinadas(api):
    """Cada categoria é uma junção a mais: o teto evita consulta pesada de graça."""
    no_limite = "&".join(f"categoria={i}" for i in range(1, MAXIMO_DE_CATEGORIAS + 1))
    acima = f"{no_limite}&categoria={MAXIMO_DE_CATEGORIAS + 1}"

    assert api.get(f"/api/coletivos/?{no_limite}").status_code == 200
    assert api.get(f"/api/coletivos/?{acima}").status_code == 400


def test_categorias_combinam_com_bairro_e_busca(api, categorias_e_coletivos):
    moda, alimentacao = categorias_e_coletivos
    coletivo("as-duas-no-centro", bairro="Centro", categorias=[moda, alimentacao])

    resposta = api.get(
        f"/api/coletivos/?categoria={moda.id}&categoria={alimentacao.id}"
        "&bairro=centro&q=centro"
    )

    assert slugs(resposta) == ["as-duas-no-centro"]
