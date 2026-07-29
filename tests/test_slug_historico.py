"""Histórico de slugs do Coletivo (PRD Seção 5 e itens 17 a 23 da Seção 8.3).

A primeira metade cobre o model: quando a troca de slug vira registro e quando
NÃO vira. A segunda cobre o que o usuário final sente — o link publicado num
cartaz continua abrindo o perfil certo, com 301 para a URL canônica.
"""
import pytest
from rest_framework.test import APIClient

from rede.models import Coletivo, ColetivoSlugAnterior

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


def test_trocar_o_slug_registra_o_slug_antigo():
    """(17) Trocar o slug cria a entrada com o slug antigo apontando ao coletivo."""
    coletivo = Coletivo.objects.create(nome="Sementes do Vale", slug="sementes")
    coletivo.slug = "sementes-do-vale"
    coletivo.save()

    historico = ColetivoSlugAnterior.objects.get(slug="sementes")
    assert historico.coletivo == coletivo
    assert list(coletivo.slugs_anteriores.values_list("slug", flat=True)) == ["sementes"]


def test_vaivem_de_slug_limpa_o_historico():
    """(21) a → b → a: o histórico de `a` some, porque `a` voltou a ser o atual."""
    coletivo = Coletivo.objects.create(nome="Horta Comunitária", slug="a")
    coletivo.slug = "b"
    coletivo.save()
    assert ColetivoSlugAnterior.objects.filter(slug="a").exists()

    coletivo.slug = "a"
    coletivo.save()

    # `a` é o slug atual: não pode continuar no histórico apontando para si mesmo.
    assert not ColetivoSlugAnterior.objects.filter(slug="a").exists()
    assert ColetivoSlugAnterior.objects.filter(slug="b").exists()


def test_criar_ou_salvar_sem_trocar_o_slug_nao_cria_historico():
    """(23) Criação não gera histórico; salvar sem mexer no slug também não."""
    coletivo = Coletivo.objects.create(nome="Feira Central", slug="feira-central")
    assert ColetivoSlugAnterior.objects.count() == 0

    coletivo.nome = "Feira Central de Niterói"
    coletivo.save()
    assert ColetivoSlugAnterior.objects.count() == 0


def test_um_slug_nunca_aponta_para_dois_coletivos():
    """Invariante da Seção 5.2: o slug atual de um coletivo tira o do histórico de outro."""
    antigo = Coletivo.objects.create(nome="Coletivo A", slug="rede-solidaria")
    antigo.slug = "coletivo-a"
    antigo.save()
    assert ColetivoSlugAnterior.objects.filter(slug="rede-solidaria").exists()

    # Outro coletivo assume o slug que estava no histórico do primeiro.
    Coletivo.objects.create(nome="Rede Solidária", slug="rede-solidaria")

    assert not ColetivoSlugAnterior.objects.filter(slug="rede-solidaria").exists()


def test_apagar_o_coletivo_limpa_o_historico():
    """`on_delete=CASCADE`: sem coletivo, o histórico não faz sentido."""
    coletivo = Coletivo.objects.create(nome="Coletivo Temporário", slug="temp")
    coletivo.slug = "temporario"
    coletivo.save()
    assert ColetivoSlugAnterior.objects.count() == 1

    coletivo.delete()
    assert ColetivoSlugAnterior.objects.count() == 0


def test_str_do_historico_mostra_o_caminho_do_redirect():
    """`__str__` deixa legível, no Admin, para onde o slug antigo aponta."""
    coletivo = Coletivo.objects.create(nome="Ateliê Coletivo", slug="atelie")
    coletivo.slug = "atelie-coletivo"
    coletivo.save()

    historico = ColetivoSlugAnterior.objects.get(slug="atelie")
    assert str(historico) == "atelie → atelie-coletivo"


# --- Comportamento HTTP -----------------------------------------------------


def test_slug_antigo_responde_301_para_a_url_canonica(api):
    """(18) O endereço antigo responde 301, com `Location` na URL canônica.

    301, e não 302: é o que faz o buscador consolidar no endereço novo a
    autoridade do antigo, em vez de indexar duplicata.
    """
    coletivo = Coletivo.objects.create(nome="Sementes do Vale", slug="sementes")
    coletivo.slug = "sementes-do-vale"
    coletivo.save()

    resposta = api.get("/api/coletivos/sementes/")

    assert resposta.status_code == 301
    assert resposta.headers["Location"].endswith("/api/coletivos/sementes-do-vale/")


def test_seguir_o_redirect_chega_ao_coletivo_certo(api):
    """(19) Seguindo o 301 chega-se ao perfil, com 200 — o link publicado não quebra."""
    coletivo = Coletivo.objects.create(nome="Sementes do Vale", slug="sementes")
    coletivo.slug = "sementes-do-vale"
    coletivo.save()

    resposta = api.get("/api/coletivos/sementes/", follow=True)

    assert resposta.status_code == 200
    assert resposta.json()["slug"] == "sementes-do-vale"
    assert resposta.json()["nome"] == "Sementes do Vale"


def test_slug_antigo_de_coletivo_inativo_responde_404(api):
    """(20) O histórico NÃO fura a regra de visibilidade.

    Se a equipe tirou o coletivo do ar, nem o endereço atual nem o antigo
    podem servir de porta dos fundos.
    """
    coletivo = Coletivo.objects.create(nome="Fora do Ar", slug="antigo")
    coletivo.slug = "fora-do-ar"
    coletivo.ativo = False
    coletivo.save()

    assert api.get("/api/coletivos/antigo/").status_code == 404
    assert api.get("/api/coletivos/fora-do-ar/").status_code == 404


def test_vaivem_volta_a_responder_200_sem_redirect(api):
    """(21) a → b → a: `/api/coletivos/a/` volta a responder 200 direto, sem 301."""
    coletivo = Coletivo.objects.create(nome="Horta Comunitária", slug="horta")
    coletivo.slug = "horta-comunitaria"
    coletivo.save()
    assert api.get("/api/coletivos/horta/").status_code == 301

    coletivo.slug = "horta"
    coletivo.save()

    resposta = api.get("/api/coletivos/horta/")
    assert resposta.status_code == 200
    assert resposta.json()["slug"] == "horta"
    # E o endereço intermediário passa a ser o que redireciona.
    assert api.get("/api/coletivos/horta-comunitaria/").status_code == 301


def test_slug_nunca_usado_responde_404(api):
    """(22) Slug que nunca existiu é 404 — o histórico não inventa redirect."""
    Coletivo.objects.create(nome="Feira Central", slug="feira-central")

    assert api.get("/api/coletivos/nunca-existiu/").status_code == 404
