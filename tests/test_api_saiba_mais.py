"""Contrato do endpoint público das seções do Saiba mais (card 63).

O que se prova aqui:

1. **Só o publicado sai**, e a seção despublicada responde como inexistente.
2. **A ordem é a do Admin**: nenhum parâmetro da URL a desfaz.
3. **A resposta não tem nada além do contrato**: lista branca de chaves, como
   nos outros endpoints públicos.

A carga inicial (migration 0007) já cria três seções publicadas, uma por
subgrupo, e o pytest-django aplica as migrations. Os testes que precisam de um
cenário limpo apagam essas seções no começo e dizem isso; os demais contam com
elas.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from rede.models import SecaoSaibaMais
from tests.helpers import PNG_MINIMO

pytestmark = pytest.mark.django_db

LISTAGEM = "/api/saiba-mais/"

#: Conjunto exato de chaves de uma seção, na listagem e no detalhe.
CHAVES_DA_SECAO = {
    "id",
    "slug",
    "subgrupo",
    "titulo",
    "texto",
    "imagem",
    "imagem_descricao",
    "atualizado_em",
}

#: Os subgrupos na ordem do menu do site, que é a dos `choices` do model.
ORDEM_DOS_SUBGRUPOS = ["casa-azul", "economia-solidaria", "ites-ifrj"]


def secao(titulo, subgrupo="casa-azul", **campos):
    """Cria uma seção publicada, com slug derivado do título."""
    campos.setdefault("publicado", True)
    return SecaoSaibaMais.objects.create(
        titulo=titulo,
        slug=titulo.lower().replace(" ", "-"),
        subgrupo=subgrupo,
        texto=f"Texto de {titulo}.",
        **campos,
    )


def secoes_do(resposta, subgrupo):
    """As seções de um subgrupo na resposta da listagem."""
    grupo = next(g for g in resposta.json()["subgrupos"] if g["slug"] == subgrupo)
    return grupo["secoes"]


def slugs_do(resposta, subgrupo):
    return [s["slug"] for s in secoes_do(resposta, subgrupo)]


# --- Listagem ---------------------------------------------------------------


def test_listagem_traz_os_tres_subgrupos_na_ordem_do_menu(api):
    """O envelope é `subgrupos`, e não o da paginação do DRF."""
    resposta = api.get(LISTAGEM)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert set(corpo) == {"subgrupos"}
    assert [g["slug"] for g in corpo["subgrupos"]] == ORDEM_DOS_SUBGRUPOS
    assert [g["nome"] for g in corpo["subgrupos"]] == [
        "Casa Azul", "Economia Solidária", "ITES/IFRJ",
    ]
    for grupo in corpo["subgrupos"]:
        assert set(grupo) == {"slug", "nome", "secoes"}


def test_carga_inicial_aparece_cada_secao_no_seu_subgrupo(api):
    resposta = api.get(LISTAGEM)

    assert slugs_do(resposta, "casa-azul") == ["quem-somos"]
    assert slugs_do(resposta, "economia-solidaria") == ["rede-de-economia-solidaria"]
    assert slugs_do(resposta, "ites-ifrj") == ["a-ites"]


def test_secao_despublicada_some_da_listagem_e_o_detalhe_da_404(api):
    oculta = secao("Rascunho", publicado=False)

    assert "rascunho" not in slugs_do(api.get(LISTAGEM), "casa-azul")
    assert api.get(f"{LISTAGEM}{oculta.slug}/").status_code == 404


def test_despublicar_pelo_admin_tira_a_secao_do_ar(api):
    """O caminho real: a seção estava no ar e a equipe desmarcou `publicado`."""
    SecaoSaibaMais.objects.filter(slug="quem-somos").update(publicado=False)

    assert slugs_do(api.get(LISTAGEM), "casa-azul") == []
    assert api.get(f"{LISTAGEM}quem-somos/").status_code == 404


def test_subgrupo_sem_secao_publicada_vem_com_lista_vazia(api):
    """O contrato não muda conforme o conteúdo: os três subgrupos vêm sempre."""
    SecaoSaibaMais.objects.filter(subgrupo="ites-ifrj").update(publicado=False)

    resposta = api.get(LISTAGEM)

    assert [g["slug"] for g in resposta.json()["subgrupos"]] == ORDEM_DOS_SUBGRUPOS
    assert secoes_do(resposta, "ites-ifrj") == []


def test_ordem_do_admin_por_ordem_e_desempate_por_id(api):
    """Apaga a carga inicial para o subgrupo ter só as seções deste teste."""
    SecaoSaibaMais.objects.all().delete()
    terceira = secao("Terceira", ordem=5)
    primeira = secao("Primeira", ordem=1)
    # Mesma `ordem` da primeira, criada depois: o `id` maior a põe em seguida.
    segunda = secao("Segunda", ordem=1)

    assert slugs_do(api.get(LISTAGEM), "casa-azul") == [
        primeira.slug, segunda.slug, terceira.slug,
    ]


def test_parametros_da_url_nao_mudam_a_resposta(api):
    """Sem busca nem `ordering`: a ordem é da equipe, e não de quem consulta."""
    secao("Nossa história", ordem=0)
    padrao = api.get(LISTAGEM).json()

    assert api.get(f"{LISTAGEM}?ordering=-ordem").json() == padrao
    assert api.get(f"{LISTAGEM}?ordering=titulo").json() == padrao
    assert api.get(f"{LISTAGEM}?q=autogestionária").json() == padrao
    assert api.get(f"{LISTAGEM}?subgrupo=ites-ifrj").json() == padrao


def test_listagem_nao_pagina(api):
    """Todas as seções vêm de uma vez, acima do `page_size` padrão de 20."""
    for indice in range(25):
        secao(f"Seção {indice:02d}", subgrupo="economia-solidaria", ordem=indice + 10)

    resposta = api.get(f"{LISTAGEM}?page_size=5&page=2")

    assert resposta.status_code == 200
    assert "count" not in resposta.json()
    # As 25 novas e a seção da carga inicial.
    assert len(secoes_do(resposta, "economia-solidaria")) == 26


def test_listagem_faz_uma_query_so(api, django_assert_num_queries):
    for subgrupo in ORDEM_DOS_SUBGRUPOS:
        for indice in range(3):
            secao(f"{subgrupo} {indice}", subgrupo=subgrupo)

    with django_assert_num_queries(1):
        resposta = api.get(LISTAGEM)

    assert sum(len(g["secoes"]) for g in resposta.json()["subgrupos"]) == 12


# --- Contrato da seção ------------------------------------------------------


def test_secao_tem_exatamente_as_chaves_do_contrato(api):
    """Lista branca: `publicado`, `ordem` e `criado_em` não saem por nenhuma rota."""
    item_da_lista = secoes_do(api.get(LISTAGEM), "casa-azul")[0]
    detalhe = api.get(f"{LISTAGEM}quem-somos/").json()

    assert set(item_da_lista) == CHAVES_DA_SECAO
    assert set(detalhe) == CHAVES_DA_SECAO
    for campo in ("publicado", "ordem", "criado_em"):
        assert campo not in item_da_lista
        assert campo not in detalhe


def test_detalhe_por_slug(api):
    resposta = api.get(f"{LISTAGEM}quem-somos/")

    assert resposta.status_code == 200
    assert resposta.json()["slug"] == "quem-somos"
    assert resposta.json()["subgrupo"] == "casa-azul"
    assert resposta.json()["titulo"] == "Quem somos"

    assert api.get(f"{LISTAGEM}nao-existe/").status_code == 404


def test_imagem_ausente_vem_null_e_presente_vem_url_absoluta(api):
    secao(
        "Com imagem",
        imagem=SimpleUploadedFile("foto.png", PNG_MINIMO, "image/png"),
        imagem_descricao="Fachada da Casa Azul.",
    )

    sem_imagem = api.get(f"{LISTAGEM}quem-somos/").json()
    com_imagem = api.get(f"{LISTAGEM}com-imagem/").json()

    assert sem_imagem["imagem"] is None
    assert sem_imagem["imagem_descricao"] == ""
    # Absoluta, com o nome único da pasta `saiba-mais/`, e não o original.
    assert com_imagem["imagem"].startswith("http://testserver/media/saiba-mais/")
    assert com_imagem["imagem"].endswith(".png")
    assert "foto.png" not in com_imagem["imagem"]
    assert com_imagem["imagem_descricao"] == "Fachada da Casa Azul."


def test_api_e_somente_leitura(api):
    detalhe = f"{LISTAGEM}quem-somos/"

    assert api.post(LISTAGEM, {"titulo": "X"}).status_code == 405
    assert api.put(detalhe, {"titulo": "X"}).status_code == 405
    assert api.patch(detalhe, {"titulo": "X"}).status_code == 405
    assert api.delete(detalhe).status_code == 405
