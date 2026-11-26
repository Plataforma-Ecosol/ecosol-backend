"""Só a equipe acessa a API da equipe e o Relatório (backend#58).

A restrição em si é a `VisaoDaEquipe` (`rede/views_equipe.py`, PR #67): só
sessão, só `is_staff`, sem cache. É o "padrão do backend#24" que o card pede.
`tests/test_api_equipe.py` prova essas promessas em `/api/equipe/eu/`; esta
suíte as cobra de **toda** rota da equipe, inclusive as que ainda não existem.

O risco é concreto: o padrão do DRF no projeto é `IsAuthenticatedOrReadOnly`.
Um endpoint do Relatório escrito sem a `VisaoDaEquipe` responderia GET a
qualquer anônimo, com os agregados do cadastro.

**Rotas da equipe** são descobertas no resolver do Django, sem lista à mão:

- tudo sob `/api/equipe/`;
- qualquer rota da API com "relatorio" no caminho ou no nome, onde quer que
  esteja. Um Relatório que nascesse fora do prefixo também é cobrado.

Hoje isso é só o `/api/equipe/eu/`; os endpoints do backend#56 e #57 entram
sozinhos. As variantes com sufixo de formato (`.json`) que o router do DRF cria
ficam de fora: são a mesma view da rota principal.

A segunda parte trava o outro critério do card: a API pública continua aberta
a anônimo e só leitura.
"""
import base64
import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import URLPattern, URLResolver, get_resolver

from rede.views_equipe import VisaoDaEquipe

pytestmark = pytest.mark.django_db

PREFIXO_DA_API = "api/"
PREFIXO_DA_EQUIPE = "api/equipe/"
SENHA = "senha-de-teste-123"

#: Argumentos para rotas da equipe com parâmetro na URL, usados no teste em que
#: a equipe recebe 200. Sem uma entrada aqui, esse teste falha em vez de pular a
#: rota. Os testes de 403 não precisam: a permissão é checada antes de a view
#: buscar qualquer objeto, então qualquer valor serve.
ARGUMENTOS_DAS_ROTAS: dict[str, dict] = {}

RELATORIO = re.compile(r"relat[oó]rio", re.IGNORECASE)
SUFIXO_DE_FORMATO = re.compile(r"\(\?P<format>|<(?:\w+:)?format>")
PARAMETRO = re.compile(r"<(?:(\w+):)?(\w+)>|\(\?P<(\w+)>[^)]*\)")
#: Valor qualquer, mas que a URL aceite, para cada conversor do Django.
VALOR_QUALQUER = {"uuid": "00000000-0000-0000-0000-000000000000"}


# --- Descoberta das rotas ----------------------------------------------------


def _caminho(padrao) -> str:
    """Trecho de URL de um padrão, sem as âncoras de `re_path`."""
    return str(padrao.pattern).removeprefix("^").removesuffix("$")


def _rotas(padroes, prefixo=""):
    for padrao in padroes:
        caminho = prefixo + _caminho(padrao)
        if isinstance(padrao, URLResolver):
            yield from _rotas(padrao.url_patterns, caminho)
        elif isinstance(padrao, URLPattern):
            yield caminho, padrao


def _tem_parametro(caminho: str) -> bool:
    return "<" in caminho or "(" in caminho


def _e_da_equipe(caminho: str, padrao: URLPattern) -> bool:
    return caminho.startswith(PREFIXO_DA_EQUIPE) or bool(
        RELATORIO.search(caminho) or RELATORIO.search(padrao.name or "")
    )


ROTAS_DA_API = sorted(
    (
        (caminho, padrao)
        for caminho, padrao in _rotas(get_resolver().url_patterns)
        if caminho.startswith(PREFIXO_DA_API) and not SUFIXO_DE_FORMATO.search(caminho)
    ),
    key=lambda rota: rota[0],
)
ROTAS_DA_EQUIPE = [rota for rota in ROTAS_DA_API if _e_da_equipe(*rota)]
CAMINHOS_DA_EQUIPE = [caminho for caminho, _ in ROTAS_DA_EQUIPE]
#: Só as rotas públicas sem parâmetro: listagens, filtros e a raiz da API.
CAMINHOS_PUBLICOS = [
    caminho
    for caminho, padrao in ROTAS_DA_API
    if not _e_da_equipe(caminho, padrao) and not _tem_parametro(caminho)
]


def _url(caminho: str, argumentos: dict | None = None) -> str:
    """URL do GET. Sem `argumentos`, preenche cada parâmetro com um valor qualquer."""

    def preencher(achado):
        conversor, nome = achado.group(1), achado.group(2) or achado.group(3)
        if argumentos is None:
            return VALOR_QUALQUER.get(conversor, "1")
        return str(argumentos[nome])

    return "/" + PARAMETRO.sub(preencher, caminho)


def _url_para_a_equipe(caminho: str) -> str:
    if not _tem_parametro(caminho):
        return "/" + caminho
    if caminho not in ARGUMENTOS_DAS_ROTAS:
        pytest.fail(
            f"A rota {caminho!r} tem parâmetro: inclua os argumentos dela em "
            "ARGUMENTOS_DAS_ROTAS para o teste da equipe saber o que pedir."
        )
    return _url(caminho, ARGUMENTOS_DAS_ROTAS[caminho])


def test_descoberta_acha_a_api_da_equipe_e_a_publica():
    """Sem isto, uma descoberta quebrada esvaziaria a suíte sem ninguém notar."""
    assert "api/equipe/eu/" in CAMINHOS_DA_EQUIPE
    assert "api/coletivos/" in CAMINHOS_PUBLICOS
    assert not set(CAMINHOS_DA_EQUIPE) & set(CAMINHOS_PUBLICOS)


# --- Toda rota da equipe ---------------------------------------------------------


@pytest.fixture
def da_equipe():
    return get_user_model().objects.create_user(
        username="coordenacao", password=SENHA, is_staff=True,
    )


@pytest.mark.parametrize("caminho,padrao", ROTAS_DA_EQUIPE, ids=CAMINHOS_DA_EQUIPE)
def test_rota_da_equipe_herda_a_visao_da_equipe(caminho, padrao):
    """A regra do README: todo endpoint da equipe herda de `VisaoDaEquipe`."""
    classe = getattr(padrao.callback, "cls", None) or getattr(
        padrao.callback, "view_class", None
    )

    assert classe is not None and issubclass(classe, VisaoDaEquipe), (
        f"/{caminho} precisa herdar de VisaoDaEquipe (rede/views_equipe.py)."
    )
    # Herdar e depois sobrescrever afrouxaria a regra em silêncio. Permissão
    # pode ganhar classes (no DRF elas se somam, então fica mais restrito);
    # autenticação não pode mudar, porque cada classe a mais é uma porta a mais.
    assert classe.authentication_classes == VisaoDaEquipe.authentication_classes, (
        f"/{caminho} não pode mudar as authentication_classes da VisaoDaEquipe."
    )
    assert set(VisaoDaEquipe.permission_classes) <= set(classe.permission_classes), (
        f"/{caminho} não pode tirar as permission_classes da VisaoDaEquipe."
    )


@pytest.mark.parametrize("perfil", ["anonimo", "sem-is-staff", "equipe-desativada"])
@pytest.mark.parametrize("caminho", CAMINHOS_DA_EQUIPE)
def test_quem_nao_e_da_equipe_recebe_403(api, perfil, caminho):
    """403, e não 401: só com sessão, o DRF não manda `WWW-Authenticate`.

    O card aceita os dois; o frontend trata os dois da mesma forma.
    """
    usuarios = get_user_model().objects
    if perfil == "sem-is-staff":
        api.force_login(usuarios.create_user(username="comum", password=SENHA))
    elif perfil == "equipe-desativada":
        api.force_login(
            usuarios.create_user(
                username="ex-equipe", password=SENHA, is_staff=True, is_active=False,
            )
        )

    assert api.get(_url(caminho)).status_code == 403


@pytest.mark.parametrize("caminho", CAMINHOS_DA_EQUIPE)
def test_equipe_logada_pela_sessao_recebe_200(api, da_equipe, caminho):
    # `force_login`, e não `force_authenticate`: passa pela sessão de verdade.
    api.force_login(da_equipe)

    assert api.get(_url_para_a_equipe(caminho)).status_code == 200


@pytest.mark.parametrize("caminho", CAMINHOS_DA_EQUIPE)
def test_basic_auth_e_recusado(api, da_equipe, caminho):
    """Usuário e senha certos no cabeçalho não bastam: só a sessão vale."""
    credenciais = base64.b64encode(f"coordenacao:{SENHA}".encode()).decode()

    resposta = api.get(_url(caminho), HTTP_AUTHORIZATION=f"Basic {credenciais}")

    assert resposta.status_code == 403


@pytest.mark.parametrize("caminho", CAMINHOS_DA_EQUIPE)
def test_resposta_da_equipe_sem_cache(api, da_equipe, caminho):
    """Proxy ou CDN não podem guardar a resposta de quem está logado."""
    api.force_login(da_equipe)

    cache_control = api.get(_url_para_a_equipe(caminho))["Cache-Control"]

    assert "no-store" in cache_control
    assert "private" in cache_control


# --- A API pública continua igual ----------------------------------------------


@pytest.mark.parametrize("caminho", CAMINHOS_PUBLICOS)
def test_api_publica_continua_aberta_a_anonimo(api, caminho):
    assert api.get("/" + caminho).status_code == 200


@pytest.mark.parametrize("caminho", CAMINHOS_PUBLICOS)
def test_api_publica_continua_so_leitura(api, da_equipe, caminho):
    """Nem a equipe logada escreve pela API pública: o método não existe.

    Logado, e não anônimo, de propósito. Para anônimo, a raiz `/api/` responde
    403 antes de chegar ao método (ela segue o `IsAuthenticatedOrReadOnly`
    global), e um 403 não distingue "sem método" de "sem permissão". Com
    `force_login` o APIClient não cobra CSRF, então o 405 prova que não há
    escrita nem para quem está logado.
    """
    api.force_login(da_equipe)

    assert api.post("/" + caminho, {}).status_code == 405
