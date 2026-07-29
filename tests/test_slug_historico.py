"""Histórico de slugs do Coletivo (PRD Seção 5 e itens 17, 21 e 23 da 8.3).

Aqui só o comportamento de model: quando a troca de slug vira registro e
quando NÃO vira. O comportamento HTTP (301, 404 de inativo) é testado na
suíte de API, junto do restante do contrato.
"""
import pytest

from rede.models import Coletivo, ColetivoSlugAnterior

pytestmark = pytest.mark.django_db


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
