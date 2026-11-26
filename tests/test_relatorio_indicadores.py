"""Relatório: indicadores gerais da rede (backend#56).

`GET /api/equipe/relatorio/indicadores/` devolve os totais dos cartões do
Relatório: coletivos cadastrados, coletivos por situação, aptos x não aptos e
membros. Só números, sem filtro: é a rede inteira.

"Apto" é o coletivo com ao menos 3 pessoas cadastradas, calculado a cada
consulta. É a única parte calculável da regra do PRD Técnico 4.1; o caráter
interfamiliar continua verificação humana.

A fixture `rede` tem um caso para cada fronteira: um coletivo com exatamente 3
pessoas (apto), um com 2 (não apto), um sem ninguém e um inativo e encerrado,
que conta como qualquer outro.
"""
import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.text import slugify

from rede.models import Coletivo, Pessoa
from rede.relatorio import MINIMO_DE_PESSOAS_PARA_APTIDAO

pytestmark = pytest.mark.django_db

URL = "/api/equipe/relatorio/indicadores/"
CHAVES = {"total_coletivos", "por_situacao", "aptidao", "total_membros"}


def coletivo_com(nome, pessoas, *, situacao="regular", ativo=True):
    """Coletivo com `pessoas` integrantes cadastrados."""
    coletivo = Coletivo.objects.create(
        nome=nome, slug=slugify(nome), situacao=situacao, ativo=ativo,
    )
    Pessoa.objects.bulk_create(
        Pessoa(coletivo=coletivo, nome=f"Integrante {indice} de {nome}")
        for indice in range(pessoas)
    )
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
def rede():
    """Cinco coletivos e onze pessoas; dois coletivos aptos."""
    coletivo_com("Padaria do Morro", 3)
    coletivo_com("Horta Viva", 5, situacao="em_transicao")
    coletivo_com("Ateliê Fonseca", 2, situacao="encerrado", ativo=False)
    coletivo_com("Recém-Chegado", 0)
    coletivo_com("Feira da Praça", 1)


# --- Rota e acesso -----------------------------------------------------------


def test_rota_tem_nome():
    assert reverse("equipe-relatorio-indicadores") == URL


def test_anonimo_recebe_403(api, rede):
    assert api.get(URL).status_code == 403


# --- Cada número -----------------------------------------------------------------


def test_cada_numero_confere_com_a_rede(equipe, rede):
    """A resposta inteira, número por número, contra a fixture."""
    assert equipe.get(URL).json() == {
        "total_coletivos": 5,
        "por_situacao": [
            {"slug": "regular", "nome": "Regular", "total": 3},
            {"slug": "em_transicao", "nome": "Em transição", "total": 1},
            {"slug": "encerrado", "nome": "Encerrado", "total": 1},
        ],
        "aptidao": {"minimo_de_pessoas": 3, "aptos": 2, "nao_aptos": 3},
        "total_membros": 11,
    }


def test_resposta_tem_exatamente_as_chaves_do_contrato(equipe, rede):
    dados = equipe.get(URL).json()

    assert set(dados) == CHAVES
    assert set(dados["aptidao"]) == {"minimo_de_pessoas", "aptos", "nao_aptos"}
    assert all(set(linha) == {"slug", "nome", "total"} for linha in dados["por_situacao"])


def test_inativo_conta_em_todos_os_totais(equipe, rede):
    """O Relatório mede a rede cadastrada, não o que está no ar no site."""
    Coletivo.objects.update(ativo=False)

    dados = equipe.get(URL).json()

    assert dados["total_coletivos"] == 5
    assert dados["total_membros"] == 11
    assert dados["aptidao"]["aptos"] == 2


# --- Situação ----------------------------------------------------------------------


def test_por_situacao_tem_todas_as_situacoes_do_model_na_ordem(equipe, rede):
    """Situação nova no model aparece sozinha, sem mexer no endpoint."""
    slugs = [linha["slug"] for linha in equipe.get(URL).json()["por_situacao"]]

    assert slugs == [valor for valor, _ in Coletivo.Situacao.choices]


def test_situacao_sem_coletivo_aparece_com_zero(equipe):
    coletivo_com("Único Coletivo", 4, situacao="em_transicao")

    por_situacao = equipe.get(URL).json()["por_situacao"]

    assert [(linha["slug"], linha["total"]) for linha in por_situacao] == [
        ("regular", 0), ("em_transicao", 1), ("encerrado", 0),
    ]


def test_por_situacao_soma_o_total(equipe, rede):
    dados = equipe.get(URL).json()

    assert sum(linha["total"] for linha in dados["por_situacao"]) == dados["total_coletivos"]


# --- Aptidão -----------------------------------------------------------------------


def test_minimo_de_pessoas_e_tres():
    """A regra do PRD 4.1. Mudar este número é decisão de negócio, não refactor."""
    assert MINIMO_DE_PESSOAS_PARA_APTIDAO == 3


@pytest.mark.parametrize(
    ("pessoas", "apto"),
    [(0, False), (2, False), (3, True), (4, True)],
    ids=["sem-ninguem", "duas", "tres-exatas", "quatro"],
)
def test_apto_a_partir_de_tres_pessoas_cadastradas(equipe, pessoas, apto):
    coletivo_com("Coletivo da Fronteira", pessoas)

    aptidao = equipe.get(URL).json()["aptidao"]

    assert (aptidao["aptos"], aptidao["nao_aptos"]) == ((1, 0) if apto else (0, 1))


def test_aptidao_e_calculada_das_pessoas_cadastradas(equipe):
    """Não há campo marcado à mão: cadastrar ou remover pessoa muda a conta."""
    coletivo = coletivo_com("Coletivo em Formação", 2)
    assert equipe.get(URL).json()["aptidao"]["aptos"] == 0

    Pessoa.objects.create(coletivo=coletivo, nome="Terceira Integrante")
    assert equipe.get(URL).json()["aptidao"]["aptos"] == 1

    Pessoa.objects.filter(coletivo=coletivo).first().delete()
    assert equipe.get(URL).json()["aptidao"]["aptos"] == 0


def test_aptos_mais_nao_aptos_e_o_total(equipe, rede):
    dados = equipe.get(URL).json()

    assert dados["aptidao"]["aptos"] + dados["aptidao"]["nao_aptos"] == dados["total_coletivos"]


# --- Membros e vazio -----------------------------------------------------------------


def test_total_de_membros_conta_cada_pessoa_uma_vez(equipe, rede):
    assert equipe.get(URL).json()["total_membros"] == Pessoa.objects.count() == 11


def test_sem_cadastro_vem_tudo_zerado(equipe):
    assert equipe.get(URL).json() == {
        "total_coletivos": 0,
        "por_situacao": [
            {"slug": "regular", "nome": "Regular", "total": 0},
            {"slug": "em_transicao", "nome": "Em transição", "total": 0},
            {"slug": "encerrado", "nome": "Encerrado", "total": 0},
        ],
        "aptidao": {"minimo_de_pessoas": 3, "aptos": 0, "nao_aptos": 0},
        "total_membros": 0,
    }


def test_resposta_so_tem_numeros_e_nenhum_nome(equipe, rede):
    """Nem pessoa nem coletivo aparecem na resposta, só as contagens."""
    texto = json.dumps(equipe.get(URL).json(), ensure_ascii=False)

    for nome in [*Pessoa.objects.values_list("nome", flat=True),
                 *Coletivo.objects.values_list("nome", flat=True)]:
        assert nome not in texto


# --- Desempenho --------------------------------------------------------------------


def test_numero_de_consultas_nao_cresce_com_a_rede(equipe, django_assert_num_queries):
    """Seis consultas com 30 coletivos e 90 pessoas, as mesmas seis com um só.

    Duas são da sessão (a sessão e o usuário) e quatro são dos indicadores: o
    total, a situação, a aptidão e os membros. Contar as pessoas coletivo por
    coletivo, num laço, quebraria este teste.
    """
    for indice in range(30):
        coletivo_com(f"Coletivo {indice:02d}", indice % 6)

    with django_assert_num_queries(6):
        resposta = equipe.get(URL)

    assert resposta.json()["total_coletivos"] == 30
