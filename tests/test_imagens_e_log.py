"""Duas falhas que só apareceram na homologação, no Render.

* **Imagem com 403.** Sem `AWS_S3_CUSTOM_DOMAIN`, o django-storages monta a URL
  da imagem a partir do endpoint S3 — que só aceita requisição assinada. A foto
  estava no bucket, pública, e mesmo assim o site a mostrava quebrada.
* **Erro 500 sem rastro.** Com DEBUG=False, o padrão do Django manda o erro por
  e-mail aos ADMINS e não escreve nada no console. No Render, uma senha errada
  no banco virou 500 sem uma linha no painel de Logs.
"""
import io
import logging

import pytest
from django.test import Client
from storages.backends.s3 import S3Storage

from config.ambiente import dominio_publico_supabase
from rede.views import ColetivoViewSet

REF = "abcdefghijklmnop"
PUBLICO = f"{REF}.supabase.co/storage/v1/object/public/divulgacao"


# --- Endereço público das imagens -------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    [
        f"https://{REF}.supabase.co/storage/v1/s3",
        # O painel às vezes mostra o endpoint neste subdomínio.
        f"https://{REF}.storage.supabase.co/storage/v1/s3",
        f"https://{REF}.supabase.co/storage/v1/s3/",
        f"  https://{REF}.supabase.co/storage/v1/s3\n",
    ],
)
def test_endpoint_do_supabase_vira_leitura_publica(endpoint):
    assert dominio_publico_supabase(endpoint, "divulgacao") == PUBLICO


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://s3.sa-east-1.amazonaws.com",
        "http://localhost:9000",
        f"https://{REF}.supabase.co/rest/v1",
        "",
    ],
)
def test_fora_do_supabase_nao_inventa_dominio(endpoint):
    assert dominio_publico_supabase(endpoint, "divulgacao") is None


def test_url_da_imagem_aponta_para_a_leitura_publica():
    """O mesmo caminho da API: o storage monta a URL a partir do domínio.

    Nenhuma requisição sai daqui — com domínio próprio, o django-storages só
    concatena. A URL errada (a do endpoint S3) respondia 403 no navegador.
    """
    storage = S3Storage(
        bucket_name="divulgacao",
        endpoint_url=f"https://{REF}.storage.supabase.co/storage/v1/s3",
        access_key="chave-de-teste",
        secret_key="segredo-de-teste",
        querystring_auth=False,
        custom_domain=dominio_publico_supabase(
            f"https://{REF}.storage.supabase.co/storage/v1/s3", "divulgacao"
        ),
    )

    assert storage.url("eventos/feira.png") == f"https://{PUBLICO}/eventos/feira.png"


# --- Erros no log ---------------------------------------------------------------------


@pytest.fixture
def console_do_django():
    """O texto que o handler de console do logger `django` escreveria.

    Troca o stream do handler, e não o `sys.stderr`: o handler guardou o stream
    ao ser configurado, então capturar o stderr depois não pegaria nada.
    """
    handler = next(
        h for h in logging.getLogger("django").handlers
        if isinstance(h, logging.StreamHandler)
    )
    saida = io.StringIO()
    original = handler.setStream(saida)
    yield saida
    handler.setStream(original)


def test_erro_500_aparece_no_console_com_traceback(monkeypatch, console_do_django):
    def quebrar(*args, **kwargs):
        raise RuntimeError("falha simulada para o teste de log")

    monkeypatch.setattr(ColetivoViewSet, "list", quebrar)

    resposta = Client(raise_request_exception=False).get("/api/coletivos/")

    assert resposta.status_code == 500
    log = console_do_django.getvalue()
    assert "Internal Server Error: /api/coletivos/" in log
    assert "RuntimeError: falha simulada para o teste de log" in log
