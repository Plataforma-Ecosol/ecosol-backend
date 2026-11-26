"""Relatório: distribuição dos coletivos para os gráficos (backend#57).

`GET /api/equipe/relatorio/distribuicao/` devolve só contagens: por bairro, por
categoria (o segmento) e por mês de cadastro. Os filtros opcionais são o
período do cadastro (`de`, `ate`) e a situação (`situacao`).

Quem acessa (só a equipe, só por sessão, sem cache) é a `VisaoDaEquipe`; aqui
fica um teste de fumaça do 403, e a cobrança completa é a da suíte de acesso
da API da equipe.

A rede da fixture `rede` foi montada para cada regra ter um caso que a
quebraria: duas grafias do mesmo bairro, coletivo sem bairro, coletivo em duas
categorias, coletivo sem categoria, um mês vazio no meio da série, um cadastro
às 23h30 do último dia do mês (já é o mês seguinte em UTC) e um coletivo
inativo e encerrado.
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.text import slugify

from rede.models import Categoria, Coletivo

pytestmark = pytest.mark.django_db

URL = "/api/equipe/relatorio/distribuicao/"
FUSO = ZoneInfo("America/Sao_Paulo")
CHAVES = {"total", "por_bairro", "por_categoria", "por_mes"}


def no_fuso(ano, mes, dia, hora=12, minuto=0):
    return datetime(ano, mes, dia, hora, minuto, tzinfo=FUSO)


def cadastrar(nome, em, *, bairro="", categorias=(), situacao="regular", ativo=True):
    """Coletivo com `criado_em` escolhido.

    `criado_em` é `auto_now_add`: o `create` grava o agora, e só o `update`
    do queryset, que não passa pelo `save`, consegue pôr a data do cenário.
    """
    coletivo = Coletivo.objects.create(
        nome=nome, slug=slugify(nome), bairro=bairro, situacao=situacao, ativo=ativo,
    )
    coletivo.categorias.add(*categorias)
    Coletivo.objects.filter(pk=coletivo.pk).update(criado_em=em)
    return coletivo


@pytest.fixture
def equipe(api):
    """O cliente da API já logado pela sessão, como a Área da equipe chega."""
    pessoa = get_user_model().objects.create_user(
        username="coordenacao", password="senha-de-teste-123", is_staff=True,
    )
    api.force_login(pessoa)
    return api


@pytest.fixture
def categorias():
    return {
        slug: Categoria.objects.create(nome=nome, slug=slug)
        for slug, nome in [
            ("alimentacao", "Alimentação"),
            ("artesanato", "Artesanato"),
            ("agroecologia", "Agroecologia"),
        ]
    }


@pytest.fixture
def rede(categorias):
    """Seis coletivos de janeiro a abril de 2026, sem nenhum em fevereiro."""
    alimentacao, artesanato, agroecologia = (
        categorias["alimentacao"], categorias["artesanato"], categorias["agroecologia"],
    )
    cadastrar("Padaria do Morro", no_fuso(2026, 1, 15), bairro="Centro",
              categorias=[alimentacao])
    cadastrar("Horta Viva", no_fuso(2026, 1, 20), bairro="centro",
              categorias=[agroecologia, alimentacao], situacao="em_transicao")
    cadastrar("Mãos de Barro", no_fuso(2026, 3, 5), bairro="Centro",
              categorias=[artesanato])
    # 23h30 de 31/03 em Niterói, 02h30 de 01/04 em UTC: é de março.
    cadastrar("Ateliê Fonseca", no_fuso(2026, 3, 31, 23, 30), bairro="Fonseca",
              categorias=[artesanato], situacao="encerrado", ativo=False)
    cadastrar("Sem Endereço", no_fuso(2026, 4, 2))
    cadastrar("Rede Icaraí", no_fuso(2026, 4, 10), bairro="Icaraí",
              categorias=[alimentacao])


def _totais(linhas, chave):
    return [(linha[chave], linha["total"]) for linha in linhas]


# --- Rota e acesso -----------------------------------------------------------


def test_rota_tem_nome():
    assert reverse("equipe-relatorio-distribuicao") == URL


def test_anonimo_recebe_403(api, rede):
    assert api.get(URL).status_code == 403


# --- Contrato --------------------------------------------------------------------


def test_resposta_tem_exatamente_as_chaves_do_contrato(equipe, rede):
    dados = equipe.get(URL).json()

    assert set(dados) == CHAVES
    assert {chave for linha in dados["por_bairro"] for chave in linha} == {"bairro", "total"}
    assert {chave for linha in dados["por_categoria"] for chave in linha} == {
        "id", "nome", "slug", "total",
    }
    assert {chave for linha in dados["por_mes"] for chave in linha} == {"mes", "total"}


def test_resposta_so_tem_contagens_e_nenhum_coletivo(equipe, rede):
    """O Relatório agrega: nome ou slug de coletivo não aparece em lugar nenhum."""
    texto = json.dumps(equipe.get(URL).json(), ensure_ascii=False)

    for coletivo in Coletivo.objects.all():
        assert coletivo.nome not in texto
        assert coletivo.slug not in texto


def test_sem_cadastro_vem_zero_e_listas_vazias(equipe):
    assert equipe.get(URL).json() == {
        "total": 0, "por_bairro": [], "por_categoria": [], "por_mes": [],
    }


# --- Cada distribuição -----------------------------------------------------------


def test_total_conta_todo_cadastro_inclusive_o_inativo(equipe, rede):
    """O Relatório mede a rede cadastrada, não o que está no ar no site."""
    assert equipe.get(URL).json()["total"] == 6


def test_por_bairro_junta_as_grafias_e_poe_o_sem_bairro_no_fim(equipe, rede):
    """ "Centro" (2) e "centro" (1) são um bairro só, com a grafia mais usada.

    Empate em total vai por ordem alfabética; o sem bairro vem por último,
    qualquer que seja o total dele.
    """
    por_bairro = equipe.get(URL).json()["por_bairro"]

    assert _totais(por_bairro, "bairro") == [
        ("Centro", 3), ("Fonseca", 1), ("Icaraí", 1), (None, 1),
    ]


def test_empate_criado_ao_juntar_grafias_vai_em_ordem_alfabetica(equipe):
    """O banco ordena as linhas antes de as grafias se juntarem.

    "Zona Sul" (2) chega antes de "Barreto" (1) e "barreto" (1); juntas, as
    duas grafias empatam com Zona Sul, e quem desempata é a ordem alfabética.
    """
    for indice, bairro in enumerate(["Zona Sul", "Zona Sul", "Barreto", "barreto"]):
        cadastrar(f"Coletivo {indice}", no_fuso(2026, 5, 1 + indice), bairro=bairro)

    por_bairro = equipe.get(URL).json()["por_bairro"]

    assert _totais(por_bairro, "bairro") == [("Barreto", 2), ("Zona Sul", 2)]


def test_por_bairro_soma_o_total(equipe, rede):
    dados = equipe.get(URL).json()

    assert sum(linha["total"] for linha in dados["por_bairro"]) == dados["total"]


def test_por_categoria_conta_o_coletivo_em_cada_categoria(equipe, rede, categorias):
    """A Horta Viva está em duas categorias e conta nas duas.

    Por isso a soma (7) passa do total (6). O coletivo sem categoria entra na
    última linha, com `id`, `nome` e `slug` nulos.
    """
    por_categoria = equipe.get(URL).json()["por_categoria"]

    assert _totais(por_categoria, "nome") == [
        ("Alimentação", 3), ("Artesanato", 2), ("Agroecologia", 1), (None, 1),
    ]
    assert por_categoria[0] == {
        "id": categorias["alimentacao"].id,
        "nome": "Alimentação",
        "slug": "alimentacao",
        "total": 3,
    }
    assert por_categoria[-1] == {"id": None, "nome": None, "slug": None, "total": 1}


def test_categoria_sem_coletivo_nao_aparece(equipe, rede):
    Categoria.objects.create(nome="Serviços", slug="servicos")

    nomes = [linha["nome"] for linha in equipe.get(URL).json()["por_categoria"]]

    assert "Serviços" not in nomes


def test_por_mes_e_serie_continua_com_zero_no_mes_vazio(equipe, rede):
    """Fevereiro não tem cadastro e aparece com zero, entre janeiro e março."""
    por_mes = equipe.get(URL).json()["por_mes"]

    assert _totais(por_mes, "mes") == [
        ("2026-01", 2), ("2026-02", 0), ("2026-03", 2), ("2026-04", 2),
    ]


def test_por_mes_atravessa_a_virada_do_ano(equipe):
    cadastrar("Coletivo de Dezembro", no_fuso(2025, 12, 10))
    cadastrar("Coletivo de Fevereiro", no_fuso(2026, 2, 10))

    por_mes = equipe.get(URL).json()["por_mes"]

    assert _totais(por_mes, "mes") == [("2025-12", 1), ("2026-01", 0), ("2026-02", 1)]


def test_mes_e_data_seguem_o_fuso_de_sao_paulo(equipe):
    """23h30 de 31/03 em Niterói já é 01/04 em UTC; para o Relatório, é março."""
    cadastrar("Coletivo da Meia-Noite", no_fuso(2026, 3, 31, 23, 30))

    assert equipe.get(URL).json()["por_mes"] == [{"mes": "2026-03", "total": 1}]
    assert equipe.get(URL, {"ate": "2026-03-31"}).json()["total"] == 1
    assert equipe.get(URL, {"de": "2026-04-01"}).json()["total"] == 0


# --- Filtros ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("parametros", "total"),
    [
        ({"de": "2026-03-01"}, 4),
        # O dia do `ate` entra inteiro, inclusive o cadastro das 23h30.
        ({"ate": "2026-03-31"}, 4),
        ({"de": "2026-01-20", "ate": "2026-01-20"}, 1),
        ({"situacao": "regular"}, 4),
        ({"situacao": "em_transicao"}, 1),
        # O encerrado também está inativo, e conta mesmo assim.
        ({"situacao": "encerrado"}, 1),
        ({"de": "2026-03-01", "situacao": "regular"}, 3),
        ({"de": "2027-01-01"}, 0),
    ],
    ids=[
        "de", "ate-inclusivo", "um-dia-so", "regular", "em-transicao", "encerrado",
        "periodo-e-situacao", "nada-no-periodo",
    ],
)
def test_filtros_recortam_o_total(equipe, rede, parametros, total):
    assert equipe.get(URL, parametros).json()["total"] == total


def test_filtros_valem_para_todas_as_distribuicoes(equipe, rede):
    """Um recorte só, aplicado às três listas: os gráficos contam a mesma rede."""
    dados = equipe.get(URL, {"de": "2026-03-01", "situacao": "regular"}).json()

    # Mãos de Barro (Centro, março), Sem Endereço e Rede Icaraí (abril).
    assert dados["total"] == 3
    assert _totais(dados["por_bairro"], "bairro") == [("Centro", 1), ("Icaraí", 1), (None, 1)]
    assert _totais(dados["por_categoria"], "nome") == [
        ("Alimentação", 1), ("Artesanato", 1), (None, 1),
    ]
    assert _totais(dados["por_mes"], "mes") == [("2026-03", 1), ("2026-04", 2)]


def test_recorte_vazio_devolve_listas_vazias(equipe, rede):
    assert equipe.get(URL, {"de": "2027-01-01"}).json() == {
        "total": 0, "por_bairro": [], "por_categoria": [], "por_mes": [],
    }


@pytest.mark.parametrize(
    ("parametro", "valor"),
    [
        # Só AAAA-MM-DD, como na API pública: o formato brasileiro é 400.
        ("de", "15/03/2026"),
        ("ate", "2026-02-30"),
        ("situacao", "ativo"),
        ("situacao", "Regular"),
    ],
    ids=["data-brasileira", "dia-que-nao-existe", "situacao-inexistente", "maiuscula"],
)
def test_parametro_invalido_responde_400_dizendo_qual(equipe, rede, parametro, valor):
    resposta = equipe.get(URL, {parametro: valor})

    assert resposta.status_code == 400
    assert list(resposta.json()) == [parametro]


# --- Desempenho ------------------------------------------------------------------


def test_numero_de_consultas_nao_cresce_com_a_rede(equipe, categorias, django_assert_num_queries):
    """Seis consultas com 30 coletivos, as mesmas seis com um só.

    Duas são da sessão (a sessão e o usuário) e quatro são do Relatório: o
    total, o bairro, a categoria e o mês. É este teste que segura um laço
    que consultasse coletivo por coletivo.
    """
    for indice in range(30):
        cadastrar(
            f"Coletivo {indice:02d}",
            no_fuso(2025 + indice // 12, indice % 12 + 1, 10),
            bairro=f"Bairro {indice % 5}",
            categorias=list(categorias.values())[: indice % 3 + 1],
        )

    with django_assert_num_queries(6):
        resposta = equipe.get(URL)

    assert resposta.json()["total"] == 30
