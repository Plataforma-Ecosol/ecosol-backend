"""Fixtures compartilhadas e guardas globais da suíte.

A guarda de storage é a razão de este arquivo existir. O `.env` da máquina de
desenvolvimento aponta para o Supabase real (`DJANGO_USE_S3=True`); sem ela,
todo upload de teste vai para o bucket `divulgacao` de produção — e com
`AWS_S3_FILE_OVERWRITE` no default `True`, sobrescreve o objeto de mesma chave,
sem renomear e sem log. Escrita em banco o pytest-django reverte; escrita em S3
não é revertida por nada.

Por isso a fixture é `autouse`: isolamento opt-in falha no primeiro teste que
esquecer de pedi-la, e o custo desse esquecimento é perda de dado em produção.
"""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture(autouse=True)
def media_temporaria(settings, tmp_path):
    """Manda os uploads do teste para uma pasta descartável.

    Sem isto, cada rodada de teste sujaria a `media/` da árvore do repositório
    com PNGs de um pixel — ou, com `DJANGO_USE_S3=True`, o bucket de produção.

    Trocar `MEDIA_ROOT` não basta: `MEDIA_ROOT` só é lido pelo
    `FileSystemStorage`, então com o backend S3 ativo a fixture viraria no-op e
    o `SimpleUploadedFile` subiria para o bucket real. É o backend que precisa
    ser trocado. O spread preserva o alias `staticfiles`: o `StorageHandler`
    copia `settings.STORAGES` sem mesclar os defaults, então substituir o dict
    inteiro derrubaria o outro backend.
    """
    settings.MEDIA_ROOT = tmp_path
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    }
    return tmp_path
