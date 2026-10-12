"""Núcleo de teste de models (PRD Seção 8.1).

Cobre models e constraints — NÃO serialização (fatia seguinte). Cada teste
corresponde a um item da lista da Seção 8.1.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from rede.models import (
    Categoria,
    Coletivo,
    Evento,
    ImagemEvento,
    Pessoa,
    PontoDeInteresse,
)
from rede.models.coletivo import caminho_da_foto, validar_tamanho_da_foto

pytestmark = pytest.mark.django_db


def test_coletivo_slug_unico():
    """(1) Coletivo com slug; slug duplicado levanta erro de integridade."""
    Coletivo.objects.create(nome="Sementes do Vale", slug="sementes-do-vale")
    with pytest.raises(IntegrityError), transaction.atomic():
        Coletivo.objects.create(nome="Outro", slug="sementes-do-vale")


def test_coletivo_ativo_default_true():
    """(2) Default de `ativo` é True."""
    coletivo = Coletivo.objects.create(nome="Horta Comunitária", slug="horta")
    assert coletivo.ativo is True


def test_situacao_independe_de_ativo():
    """(3) `situacao` é ortogonal a `ativo`: em transição e ainda ativo."""
    coletivo = Coletivo.objects.create(
        nome="Rede em Transição",
        slug="rede-transicao",
        situacao=Coletivo.Situacao.EM_TRANSICAO,
    )
    assert coletivo.situacao == "em_transicao"
    assert coletivo.ativo is True


def test_pessoa_exige_coletivo():
    """(4) Pessoa exige coletivo (FK obrigatória)."""
    with pytest.raises(IntegrityError), transaction.atomic():
        Pessoa.objects.create(nome="Maria")


def test_pessoa_pertence_ao_coletivo():
    """(4b) Pessoa criada com coletivo aparece na relação reversa."""
    coletivo = Coletivo.objects.create(nome="Coletivo A", slug="coletivo-a")
    pessoa = Pessoa.objects.create(nome="João", coletivo=coletivo)
    assert pessoa.coletivo == coletivo
    assert list(coletivo.pessoas.all()) == [pessoa]


def test_coletivo_categorias_m2m():
    """(5) M2M Coletivo.categorias: associar duas categorias e contar."""
    coletivo = Coletivo.objects.create(nome="Feira Central", slug="feira-central")
    artesanato = Categoria.objects.create(nome="Artesanato", slug="artesanato")
    alimentacao = Categoria.objects.create(nome="Alimentação", slug="alimentacao")
    coletivo.categorias.add(artesanato, alimentacao)
    assert coletivo.categorias.count() == 2
    # Relação reversa a partir da categoria.
    assert coletivo in artesanato.coletivos.all()


def test_evento_imagens_ordenadas():
    """(6) Evento aceita zero ou mais ImagemEvento, ordenadas por `ordem`."""
    evento = Evento.objects.create(
        titulo="Feira de Verão",
        slug="feira-verao",
        data_inicio="2026-01-10T09:00:00Z",
    )
    assert evento.imagens.count() == 0  # zero imagens é válido
    segunda = ImagemEvento.objects.create(evento=evento, imagem="eventos/b.jpg", ordem=2)
    primeira = ImagemEvento.objects.create(evento=evento, imagem="eventos/a.jpg", ordem=1)
    assert list(evento.imagens.all()) == [primeira, segunda]


def test_ponto_de_interesse_coletivo_opcional_e_tipo_por_choices():
    """(7) PontoDeInteresse aceita coletivo=None; `tipo` restrito às choices."""
    ponto = PontoDeInteresse.objects.create(
        nome="Feira do Arariboia",
        tipo=PontoDeInteresse.TipoPonto.FEIRA_ARARIBOIA,
        latitude=Decimal("-22.883000"),
        longitude=Decimal("-43.103000"),
        coletivo=None,
    )
    assert ponto.coletivo is None
    assert ponto.tipo == "feira_arariboia"
    # `tipo` fora das choices falha na validação do model.
    ponto.tipo = "inexistente"
    with pytest.raises(ValidationError):
        ponto.full_clean()


# --- Foto do coletivo -------------------------------------------------------


def test_caminho_da_foto_e_unico_por_envio():
    """Dois envios de `foto.JPG` não podem gravar a mesma chave no bucket.

    Com `AWS_S3_FILE_OVERWRITE=True`, a mesma chave faria um coletivo mostrar
    a foto de outro, sem erro nenhum.
    """
    primeiro = caminho_da_foto(None, "foto.JPG")
    segundo = caminho_da_foto(None, "foto.JPG")

    assert primeiro != segundo
    for caminho in (primeiro, segundo):
        assert caminho.startswith("coletivos/")
        assert caminho.endswith(".jpg")
        assert "foto" not in caminho


class _ArquivoFalso:
    """Só o `size` que o validador lê: dispensa montar uma imagem válida."""

    def __init__(self, size):
        self.size = size


def test_foto_acima_de_5_mb_e_recusada_com_o_tamanho_na_mensagem():
    with pytest.raises(ValidationError) as erro:
        validar_tamanho_da_foto(_ArquivoFalso(int(7.2 * 1024 * 1024)))

    assert erro.value.messages == ["A foto tem 7,2 MB. O limite é 5 MB."]


def test_foto_com_5_mb_exatos_passa():
    validar_tamanho_da_foto(_ArquivoFalso(5 * 1024 * 1024))
