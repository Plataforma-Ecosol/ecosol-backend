"""Identidade da Casa Paul Singer na área administrativa (card 71).

Tudo sai do bloco `UNFOLD` do settings.py e de `config/identidade.py`. Estes
testes provam as promessas da fatia: as cores são as do frontend, o tema é um
só, a marca aparece no login e no menu, o link do site público funciona, e o
menu montado à mão não esquece nenhum model registrado, e os textos do
próprio Unfold saem em português.
"""
import re
from pathlib import Path

import pytest
import unfold
from django.conf import settings as django_settings
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.staticfiles import finders
from django.test import RequestFactory
from django.urls import reverse
from django.utils import translation

from config.identidade import AZUL, DEGRAUS, PRIMARIO, escala_oklch, hex_para_oklch

ARQUIVOS_DA_MARCA = ("logo.png", "icon.png", "apple-icon.png", "favicon.ico", "login.png")


def _itens_do_menu():
    return [
        item
        for grupo in django_settings.UNFOLD["SIDEBAR"]["navigation"]
        for item in grupo["items"]
    ]


@pytest.fixture
def admin_logado(client, db):
    usuario = get_user_model().objects.create_superuser(
        username="coordenacao",
        email="coordenacao@exemplo.org",
        password="senha-de-teste-123",
    )
    client.force_login(usuario)
    return client


# --- Cores ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cor", "esperado"),
    [
        ("#FFFFFF", "oklch(100.0% 0.000 0.0)"),
        ("#33469B", "oklch(42.9% 0.140 270.0)"),
        # Hex em minúsculas, como às vezes chega copiado de outra ferramenta.
        ("#33469b", "oklch(42.9% 0.140 270.0)"),
        ("#78716C", "oklch(55.3% 0.012 58.1)"),
    ],
)
def test_conversao_de_hex_para_oklch(cor, esperado):
    assert hex_para_oklch(cor) == esperado


def test_escalas_completas_e_iguais_ao_frontend():
    assert tuple(AZUL) == DEGRAUS
    assert tuple(PRIMARIO) == DEGRAUS
    # O azul da marca, no mesmo degrau do `globals.css`.
    assert AZUL["800"] == "#33469B"
    # O primário só reordena os degraus: nenhum hex fora da escala do site.
    assert set(PRIMARIO.values()) <= set(AZUL.values())


def test_botao_e_item_ativo_usam_o_azul_da_marca():
    """O Unfold pinta botão, link e item ativo com o 600 do `primary`."""
    assert PRIMARIO["600"] == AZUL["800"] == "#33469B"


def test_cores_do_tema_saem_das_escalas():
    cores = django_settings.UNFOLD["COLORS"]

    assert cores["base"] == escala_oklch(AZUL)
    assert cores["primary"] == escala_oklch(PRIMARIO)


def test_texto_nos_degraus_escuros_da_base():
    """Nos degraus padrão do Unfold (500/600/900) o texto azul ficaria claro demais."""
    fonte = django_settings.UNFOLD["COLORS"]["font"]

    assert fonte["subtle-light"] == "var(--color-base-700)"
    assert fonte["default-light"] == "var(--color-base-900)"
    assert fonte["important-light"] == "var(--color-base-950)"


def test_tema_claro_fixo():
    """Um tema só, como o site. Sem a chave, o Unfold mostra o seletor de tema."""
    assert django_settings.UNFOLD["THEME"] == "light"


# --- Marca --------------------------------------------------------------------


@pytest.mark.parametrize("arquivo", ARQUIVOS_DA_MARCA)
def test_arquivos_da_marca_existem(arquivo):
    assert finders.find(f"rede/marca/{arquivo}") is not None


def test_login_mostra_a_marca(client, db):
    """No login a marca entra pela imagem lateral (o círculo sobre o bege).

    O login do Unfold não desenha o `SITE_ICON`: o ícone só aparece no topo do
    menu, conferido no teste seguinte.
    """
    resposta = client.get(reverse("admin:login"))

    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "rede/marca/login.png" in html
    assert "rede/marca/favicon.ico" in html
    assert "Área da equipe" in html


def test_inicio_tem_a_logo_e_o_link_do_site_publico(admin_logado):
    resposta = admin_logado.get(reverse("admin:index"))

    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "rede/marca/logo.png" in html
    assert django_settings.URL_SITE_PUBLICO in html
    assert "Ver site público" in html


# --- Menu lateral ---------------------------------------------------------------


def test_menu_cobre_todo_model_registrado():
    """Com `show_all_applications` desligado, model sem item some da navegação.

    Um model registrado numa fatia futura e esquecido no menu quebra aqui, em
    vez de ficar acessível só para quem souber a URL de cor.
    """
    links_do_menu = {str(item["link"]) for item in _itens_do_menu()}
    changelists = {
        reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
        for model in django_admin.site._registry
    }

    assert links_do_menu == changelists


@pytest.mark.parametrize("item", _itens_do_menu(), ids=lambda item: item["title"])
def test_itens_do_menu_abrem(admin_logado, item):
    assert admin_logado.get(str(item["link"])).status_code == 200


def test_menu_respeita_a_permissao_de_ver(db):
    """Quem só pode ver Coletivo não vê nem o item de Pessoa."""
    usuario = get_user_model().objects.create_user(
        username="voluntaria", password="senha-de-teste-123", is_staff=True
    )
    usuario.user_permissions.add(
        Permission.objects.get(codename="view_coletivo", content_type__app_label="rede")
    )
    request = RequestFactory().get("/admin/")
    request.user = get_user_model().objects.get(pk=usuario.pk)  # sem cache de permissão

    visiveis = {item["title"] for item in _itens_do_menu() if item["permission"](request)}

    assert visiveis == {"Coletivos"}


# --- Português ----------------------------------------------------------------------
PO = Path(django_settings.BASE_DIR) / "locale/pt_BR/LC_MESSAGES/django.po"
MARCADORES_DE_TEXTO = (
    re.compile(r"""{%\s*trans(?:late)?\s+(['"])(.+?)\1"""),
    re.compile(r"""\b_\((['"])(.+?)\1\)"""),
    re.compile(r"""gettext(?:_lazy)?\((['"])(.+?)\1\)"""),
)


def _textos_do_unfold():
    """Os textos marcados para tradução nos templates e módulos do Unfold.

    Fora o `unfold.contrib`, que este projeto não usa.
    """
    raiz = Path(unfold.__file__).parent
    textos = set()
    for arquivo in [*raiz.rglob("*.html"), *raiz.rglob("*.py")]:
        if "contrib" in arquivo.relative_to(raiz).parts:
            continue
        conteudo = arquivo.read_text(encoding="utf-8")
        for marcador in MARCADORES_DE_TEXTO:
            textos.update(m.group(2) for m in marcador.finditer(conteudo))
    return textos


def _entradas_do_po():
    """Pares msgid/msgstr do catálogo do projeto (uma linha cada, sem plural)."""
    texto = PO.read_text(encoding="utf-8")
    pares = re.findall(r'^msgid "(.+)"\nmsgstr "(.+)"$', texto, re.MULTILINE)
    return {msgid.replace('\\"', '"'): msgstr.replace('\\"', '"') for msgid, msgstr in pares}


def test_todo_texto_do_unfold_sai_em_portugues():
    """Ao atualizar o Unfold, texto novo sem tradução aparece aqui.

    Traduzir no `locale/pt_BR/LC_MESSAGES/django.po` e compilar o .mo (README).
    """
    with translation.override("pt-br"):
        sem_traducao = sorted(t for t in _textos_do_unfold() if translation.gettext(t) == t)

    assert sem_traducao == []


def test_traducao_compilada_bate_com_o_po():
    """O .mo versionado é o que vale em runtime; editar só o .po não traduz nada."""
    entradas = _entradas_do_po()
    assert entradas

    with translation.override("pt-br"):
        assert {msgid: translation.gettext(msgid) for msgid in entradas} == entradas


def test_buscas_em_portugues(admin_logado):
    html = admin_logado.get(reverse("admin:rede_evento_changelist")).content.decode()

    assert "Digite para buscar" in html
    assert "Type to search" not in html


def test_menu_sem_a_caixa_de_busca(admin_logado):
    """A busca do menu só filtrava 7 itens pelo nome; saiu."""
    html = admin_logado.get(reverse("admin:index")).content.decode()

    assert django_settings.UNFOLD["SIDEBAR"]["show_search"] is False
    assert "Buscar no menu" not in html


def test_login_em_portugues(client, db):
    html = client.get(reverse("admin:login")).content.decode()

    assert "Entrar na" in html
    assert "Welcome back to" not in html
