"""API da equipe (`/api/equipe/`): só sessão de equipe do Admin entra.

O `/api/equipe/eu/` é o endpoint do spike backend#24. A Área da equipe no Next
o chama repassando o `sessionid` e decide pela resposta se mostra a página ou
manda para o login. Estes testes provam as promessas da `VisaoDaEquipe`, que
os endpoints do Relatório (backend#56 a #58) herdam:

- só `is_staff` passa; anônimo e usuário comum recebem 403;
- só a sessão autentica (Basic Auth é recusado);
- a resposta nunca é guardada em cache;
- nenhum dado além do nome curto sai do Django.
"""
import base64

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db

URL = "/api/equipe/eu/"
SENHA = "senha-de-teste-123"
ORIGEM_DO_SITE = "https://site.exemplo"
HOST_DO_RENDER = "backend.exemplo"


@pytest.fixture
def da_equipe():
    return get_user_model().objects.create_user(
        username="coordenacao",
        password=SENHA,
        first_name="Ana",
        last_name="Souza",
        email="ana@exemplo.org",
        is_staff=True,
    )


def test_rota_tem_nome():
    assert reverse("equipe-eu") == URL


def test_anonimo_recebe_403(api):
    assert api.get(URL).status_code == 403


def test_usuario_sem_is_staff_recebe_403(api):
    comum = get_user_model().objects.create_user(username="comum", password=SENHA)
    api.force_login(comum)

    assert api.get(URL).status_code == 403


def test_equipe_logada_recebe_so_o_nome(api, da_equipe):
    api.force_login(da_equipe)

    resposta = api.get(URL)

    assert resposta.status_code == 200
    # Só a chave `nome`: e-mail, username e afins ficam no Django (LGPD).
    assert resposta.json() == {"nome": "Ana"}


def test_sem_primeiro_nome_usa_o_username(api):
    sem_nome = get_user_model().objects.create_user(
        username="voluntaria", password=SENHA, is_staff=True
    )
    api.force_login(sem_nome)

    assert api.get(URL).json() == {"nome": "voluntaria"}


def test_basic_auth_e_recusado(api, da_equipe):
    """Usuário e senha certos no cabeçalho não bastam: só a sessão vale."""
    credenciais = base64.b64encode(f"coordenacao:{SENHA}".encode()).decode()

    resposta = api.get(URL, HTTP_AUTHORIZATION=f"Basic {credenciais}")

    assert resposta.status_code == 403


def test_login_pelo_admin_abre_a_api(client, da_equipe):
    """O caminho real: login no formulário do Admin, depois a API com o cookie."""
    resposta = client.post(
        reverse("admin:login"), {"username": "coordenacao", "password": SENHA}
    )
    assert resposta.status_code == 302
    assert "sessionid" in client.cookies

    assert client.get(URL).status_code == 200


@pytest.mark.parametrize(
    ("confiaveis", "esperado"),
    [([ORIGEM_DO_SITE], 302), ([], 403)],
    ids=["site-na-lista", "site-fora-da-lista"],
)
def test_login_pelo_rewrite_do_site(settings, da_equipe, confiaveis, esperado):
    """O POST de login como chega pelo rewrite do Next.

    O `Origin` é o do site e o `Host` é o do Render. Sem o site em
    `CSRF_TRUSTED_ORIGINS`, o Django recusa com 403 (Parte 3 do PRD).
    """
    settings.ALLOWED_HOSTS = [HOST_DO_RENDER]
    settings.CSRF_TRUSTED_ORIGINS = confiaveis
    cliente = Client(enforce_csrf_checks=True, HTTP_HOST=HOST_DO_RENDER)
    cliente.get("/admin/login/", secure=True)
    token = cliente.cookies["csrftoken"].value

    resposta = cliente.post(
        "/admin/login/?next=/equipe/relatorio",
        {"username": "coordenacao", "password": SENHA, "csrfmiddlewaretoken": token},
        secure=True,
        headers={"Origin": ORIGEM_DO_SITE},
    )

    assert resposta.status_code == esperado
    if esperado == 302:
        # Relativo: o navegador continua no endereço do site, e não é levado
        # ao Render (onde o cookie da sessão não vale).
        assert resposta["Location"] == "/equipe/relatorio"


def test_logout_fecha_a_api(client, da_equipe):
    client.force_login(da_equipe)
    client.post(reverse("admin:logout"))

    assert client.get(URL).status_code == 403


@pytest.mark.parametrize("logado", [True, False], ids=["equipe", "anonimo"])
def test_resposta_sem_cache(api, da_equipe, logado):
    """Proxy ou CDN não podem guardar a resposta de quem está logado."""
    if logado:
        api.force_login(da_equipe)

    cache_control = api.get(URL)["Cache-Control"]

    assert "no-store" in cache_control
    assert "private" in cache_control


def test_api_da_equipe_so_leitura(api, da_equipe):
    api.force_login(da_equipe)

    # Sem token CSRF o DRF recusaria com 403; com `force_login` a checagem
    # CSRF da sessão do APIClient fica desligada, então o 405 prova que o
    # método não existe.
    assert api.post(URL, {}).status_code == 405
