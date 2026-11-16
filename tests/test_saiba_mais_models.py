"""Model das seções do "Saiba mais" (PRD Saiba mais: seções por subgrupo).

Cada teste corresponde a um item da seção "Testes" do PRD. A migration
`0007_conteudo_inicial_saiba_mais` já deixa três seções no banco de teste, então
os testes de ordenação filtram só as seções que eles mesmos criam.
"""
import re

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction

from rede.models import SecaoSaibaMais
from rede.models.secao_saiba_mais import caminho_da_imagem

pytestmark = pytest.mark.django_db

Subgrupo = SecaoSaibaMais.Subgrupo


def _secao(slug, subgrupo=Subgrupo.CASA_AZUL, **campos):
    return SecaoSaibaMais.objects.create(
        slug=slug, subgrupo=subgrupo, titulo=campos.pop("titulo", slug),
        texto=campos.pop("texto", "Texto."), **campos,
    )


def test_slug_unico_mesmo_em_subgrupos_diferentes():
    """(1) O slug é único no projeto: o detalhe da API busca só por ele."""
    _secao("historia", Subgrupo.CASA_AZUL)
    with pytest.raises(IntegrityError), transaction.atomic():
        _secao("historia", Subgrupo.ITES_IFRJ)


def test_secao_nasce_despublicada():
    """(2) A equipe escreve e revisa antes de a seção ir para o site."""
    assert _secao("rascunho").publicado is False


def test_ordenacao_por_subgrupo_e_ordem():
    """(3) Subgrupo na ordem do menu e, dentro dele, a `ordem` da equipe."""
    _secao("ites-2", Subgrupo.ITES_IFRJ, ordem=2)
    _secao("casa-2", Subgrupo.CASA_AZUL, ordem=2)
    _secao("es-1", Subgrupo.ECONOMIA_SOLIDARIA, ordem=1)
    _secao("casa-1", Subgrupo.CASA_AZUL, ordem=1)

    slugs = SecaoSaibaMais.objects.filter(
        slug__in=["ites-2", "casa-2", "es-1", "casa-1"]
    ).values_list("slug", flat=True)

    assert list(slugs) == ["casa-1", "casa-2", "es-1", "ites-2"]


def test_mesma_ordem_desempata_pela_mais_antiga():
    """(4) Sem unicidade em (subgrupo, ordem), o `id` decide o empate."""
    _secao("primeira", ordem=5)
    _secao("segunda", ordem=5)

    slugs = SecaoSaibaMais.objects.filter(
        slug__in=["primeira", "segunda"]
    ).values_list("slug", flat=True)

    assert list(slugs) == ["primeira", "segunda"]


def test_subgrupo_fora_das_opcoes_e_recusado():
    """(5) Só os três subgrupos que têm rota no frontend."""
    secao = SecaoSaibaMais(
        subgrupo="parceiros", titulo="Parceiros", slug="parceiros", texto="Texto.",
    )
    with pytest.raises(ValidationError) as erro:
        secao.full_clean()
    assert "subgrupo" in erro.value.message_dict


def test_imagem_exige_descricao():
    """(6) Sem descrição, quem usa leitor de tela não sabe o que a imagem mostra."""
    secao = SecaoSaibaMais(
        subgrupo=Subgrupo.CASA_AZUL, titulo="Fachada", slug="fachada", texto="Texto.",
        imagem=SimpleUploadedFile("fachada.jpg", b"conteudo", content_type="image/jpeg"),
    )
    with pytest.raises(ValidationError) as erro:
        secao.clean()
    assert "imagem_descricao" in erro.value.message_dict

    secao.imagem_descricao = "Fachada azul da Casa Paul Singer."
    secao.clean()


def test_caminho_da_imagem_e_unico_por_envio():
    """(7) Dois envios de `foto.JPG` não podem gravar a mesma chave no bucket."""
    primeiro = caminho_da_imagem(None, "foto.JPG")
    segundo = caminho_da_imagem(None, "foto.JPG")

    assert primeiro != segundo
    for caminho in (primeiro, segundo):
        assert re.fullmatch(r"saiba-mais/[0-9a-f]{32}\.jpg", caminho)


def test_carga_inicial_publica_uma_secao_por_subgrupo():
    """(8) A migration de dados deixa o site com conteúdo no dia da troca."""
    carga = {
        secao.slug: secao
        for secao in SecaoSaibaMais.objects.filter(
            slug__in=["quem-somos", "rede-de-economia-solidaria", "a-ites"]
        )
    }

    assert {slug: secao.subgrupo for slug, secao in carga.items()} == {
        "quem-somos": Subgrupo.CASA_AZUL,
        "rede-de-economia-solidaria": Subgrupo.ECONOMIA_SOLIDARIA,
        "a-ites": Subgrupo.ITES_IFRJ,
    }
    assert all(secao.publicado for secao in carga.values())
    assert all(secao.texto.strip() for secao in carga.values())
