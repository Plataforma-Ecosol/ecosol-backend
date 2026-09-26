"""Prontidão para deploy (PRD de homologação, Seção 5.5).

Fora do compose, com DEBUG=False e atrás do proxy HTTPS do Render, o Admin
abria sem CSS e o login dava 403. O ambiente local escondia os dois: o
`runserver` serve os estáticos sozinho em DEBUG, e em `http://localhost` a
checagem de origem do CSRF não se aplica.

Estes testes provam as promessas da fatia, não a mecânica: o CSS sai sem
DEBUG, a lista de origens confiáveis é respeitada (e não ignorada), o host do
Render entra sozinho, e sem as variáveis novas nada muda no compose e no CI.
"""
import pytest
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client

from config.ambiente import hosts_permitidos

ORIGEM_HOMOLOG = "https://homolog.exemplo"
SENHA = "senha-de-teste-123"


# --- Estáticos do Admin -------------------------------------------------------


def test_admin_serve_css_sem_debug(settings, tmp_path, client):
    """O mesmo caminho do Render: collectstatic no build, WhiteNoise em runtime.

    A suíte já roda com DEBUG=False, então nenhum `runserver` ou finder ajuda:
    o arquivo só chega se o WhiteNoise o encontrar no STATIC_ROOT.
    """
    settings.STATIC_ROOT = tmp_path / "staticfiles"
    call_command("collectstatic", interactive=False, verbosity=0)

    resposta = client.get("/static/admin/css/base.css")

    assert resposta.status_code == 200
    assert resposta["Content-Type"].startswith("text/css")


# --- Origem do CSRF no login do Admin -------------------------------------------


@pytest.fixture
def login_https(settings, db):
    """POST de login do Admin por HTTPS, com checagem de CSRF de verdade.

    O `client` padrão do Django pula o CSRF; aqui ele é ligado, e a requisição
    vai como `secure=True` — é em HTTPS que o Django confere o cabeçalho Origin.
    """
    settings.CSRF_TRUSTED_ORIGINS = [ORIGEM_HOMOLOG]
    get_user_model().objects.create_superuser(
        username="coordenacao", email="coordenacao@exemplo.org", password=SENHA
    )

    def postar(origem):
        cliente = Client(enforce_csrf_checks=True)
        cliente.get("/admin/login/", secure=True)
        token = cliente.cookies["csrftoken"].value
        return cliente.post(
            "/admin/login/",
            {"username": "coordenacao", "password": SENHA, "csrfmiddlewaretoken": token},
            secure=True,
            headers={"Origin": origem},
        )

    return postar


def test_login_aceita_origem_confiavel(login_https):
    resposta = login_https(ORIGEM_HOMOLOG)

    # 302 para o índice do Admin: passou pelo CSRF e autenticou.
    assert resposta.status_code == 302


def test_login_recusa_origem_fora_da_lista(login_https):
    """Sem este caso, uma lista ignorada passaria no teste anterior."""
    resposta = login_https("https://outro-site.exemplo")

    assert resposta.status_code == 403


# --- Host do Render -----------------------------------------------------------------


def test_host_do_render_entra_em_allowed_hosts():
    hosts = hosts_permitidos(["localhost"], "ecosol-backend-homolog.onrender.com")

    assert hosts == ["localhost", "ecosol-backend-homolog.onrender.com"]


@pytest.mark.parametrize("host_render", ["", "   "])
def test_sem_render_allowed_hosts_fica_como_declarado(host_render):
    assert hosts_permitidos(["localhost", "127.0.0.1"], host_render) == [
        "localhost",
        "127.0.0.1",
    ]


def test_host_do_render_nao_duplica_o_declarado():
    hosts = hosts_permitidos(["app.onrender.com"], "app.onrender.com")

    assert hosts == ["app.onrender.com"]


# --- Padrões do ambiente local ------------------------------------------------------
# Lê as settings como carregadas, sem override: são as do compose ou do CI, que
# não definem nenhuma das variáveis novas. Se um destes quebrar, o deploy mudou
# o comportamento de quem desenvolve.


def test_sem_variaveis_cookies_nao_exigem_https():
    assert django_settings.SESSION_COOKIE_SECURE is False
    assert django_settings.CSRF_COOKIE_SECURE is False


def test_sem_variaveis_nenhuma_origem_extra_e_confiavel():
    assert django_settings.CSRF_TRUSTED_ORIGINS == []


def test_sem_variaveis_cabecalho_do_proxy_nao_e_confiavel():
    # None é o padrão do Django: nenhum cabeçalho declara a requisição HTTPS.
    assert django_settings.SECURE_PROXY_SSL_HEADER is None


def test_whitenoise_logo_depois_do_security_middleware():
    """A ordem que a documentação do WhiteNoise exige."""
    assert django_settings.MIDDLEWARE[:2] == [
        "django.middleware.security.SecurityMiddleware",
        "whitenoise.middleware.WhiteNoiseMiddleware",
    ]
