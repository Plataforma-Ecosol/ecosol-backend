"""Regressão de LGPD do Relatório de coletivos (backend#59, filho do #55).

O Relatório só pode devolver números agregados. Esta suíte prova que nenhum
endpoint dele expõe dado de membro (Pessoa) nem dado pessoal do cadastro do
coletivo. É bloqueante no CI, como o resto da regressão de LGPD.

**Cobertura automática.** As rotas não são listadas à mão: a suíte descobre
toda rota sob `PREFIXO_DO_RELATORIO` no resolver do Django. Um endpoint novo
do Relatório entra na regressão sem ninguém lembrar de incluí-lo. Enquanto
não houver nenhuma rota (backend#56 a #58 ainda não entraram), os testes
parametrizados aparecem como `skipped`, e não como verdes.

**Duas redes de proteção, de propósito:**

1. **Por chave.** Nenhuma chave de dado de membro (e-mail, telefone,
   documento...) pode existir na resposta, em qualquer nível do JSON.
2. **Por valor.** O cadastro do teste é preenchido com valores-sentinela
   únicos, e nenhum deles pode aparecer em lugar nenhum da resposta. É esta
   rede que pega o vazamento com nome de chave trocado (`"rotulo": "Fulana"`)
   ou embutido num texto.

A chave `nome` não está na lista proibida: num agregado ela nomeia categoria,
bairro ou coletivo, que são públicos. O nome de membro é barrado pela rede de
valor, com o sentinela de `Pessoa.nome`.
"""
import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import URLPattern, URLResolver, get_resolver

from rede.models import Categoria, Coletivo, Pessoa
from rede.views_equipe import VisaoDaEquipe

pytestmark = pytest.mark.django_db

#: Toda rota cujo caminho começa aqui é do Relatório e entra na regressão.
PREFIXO_DO_RELATORIO = "api/equipe/relatorio/"

#: Argumentos para rotas do Relatório com parâmetro na URL. Sem uma entrada
#: aqui, a rota parametrizada faz o teste falhar em vez de ficar de fora.
ARGUMENTOS_DAS_ROTAS: dict[str, dict] = {}

#: Chaves que, em qualquer nível da resposta, denunciam dado de membro ou
#: dado pessoal do cadastro. Comparação sem maiúsculas.
CHAVES_PROIBIDAS = frozenset({
    # Membro em si
    "pessoa", "pessoas", "membro", "membros", "integrante", "integrantes",
    "nome_social", "data_nascimento", "naturalidade", "estado_civil",
    # Contato
    "email", "e_mail", "telefone", "celular", "whatsapp", "instagram", "facebook",
    # Documento
    "documento", "cpf", "rg", "rne_crnm",
    # Endereço
    "logradouro", "complemento", "cep",
    # Gente nomeada no cadastro do coletivo
    "responsavel_grupo", "nome_entrevistador",
})

#: Valores únicos plantados no cadastro. Nenhum pode sair na resposta.
SENTINELAS_DE_PESSOA = {
    "nome": "Fulana Sentinela Quatro",
    "nome_social": "Ciclana Sentinela Social",
    "email": "fulana.sentinela@exemplo.org",
    "telefone": "(21) 98765-4321",
    "cpf": "123.456.789-09",
    "rg": "11.222.333-4",
    "rne_crnm": "V123456-SENT",
    "instagram": "@fulana_sentinela",
    "facebook": "fulana.sentinela.fb",
    "logradouro": "Rua Sentinela Pessoa",
    "cep": "24210-346",
}
SENTINELAS_DO_COLETIVO = {
    "responsavel_grupo": "Beltrana Responsavel Sentinela",
    "nome_entrevistador": "Entrevistador Sentinela",
    "telefone": "(21) 91234-5678",
    "email": "coletivo.sentinela@exemplo.org",
    "logradouro": "Travessa Sentinela Coletivo",
}
#: Segunda integrante: o Relatório não pode listar ninguém, nem a de cadastro magro.
NOME_DA_OUTRA_INTEGRANTE = "Outra Integrante Sentinela"
#: Abaixo disto, comparar só dígitos daria falso positivo (um total "42"...).
MINIMO_DE_DIGITOS = 8


# --- Detector -----------------------------------------------------------------


def _digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def _textos(dado):
    """Todas as chaves e valores do JSON, em qualquer nível, como texto."""
    if isinstance(dado, dict):
        for chave, valor in dado.items():
            yield str(chave)
            yield from _textos(valor)
    elif isinstance(dado, list | tuple):
        for item in dado:
            yield from _textos(item)
    elif dado is not None:
        yield str(dado)


def _chaves(dado, caminho="$"):
    """Pares (caminho, chave) de todos os dicionários do JSON."""
    if isinstance(dado, dict):
        for chave, valor in dado.items():
            yield f"{caminho}.{chave}", str(chave)
            yield from _chaves(valor, f"{caminho}.{chave}")
    elif isinstance(dado, list | tuple):
        for indice, item in enumerate(dado):
            yield from _chaves(item, f"{caminho}[{indice}]")


def vazamentos(dado, sentinelas) -> list[str]:
    """Lista legível de tudo o que denuncia dado pessoal na resposta.

    Vazia quer dizer resposta limpa. Devolver a lista, e não um booleano, é o
    que faz a mensagem de falha dizer onde foi o vazamento.
    """
    achados = [
        f"chave proibida {caminho}"
        for caminho, chave in _chaves(dado)
        if chave.lower() in CHAVES_PROIBIDAS
    ]

    textos = list(_textos(dado))
    textos_minusculos = [texto.lower() for texto in textos]
    textos_em_digitos = [_digitos(texto) for texto in textos]

    for sentinela in sentinelas:
        if any(sentinela.lower() in texto for texto in textos_minusculos):
            achados.append(f"valor de cadastro {sentinela!r}")
            continue
        # Telefone e documento podem sair noutro formato: "21987654321".
        so_digitos = _digitos(sentinela)
        if len(so_digitos) >= MINIMO_DE_DIGITOS and any(
            so_digitos in texto for texto in textos_em_digitos
        ):
            achados.append(f"valor de cadastro {sentinela!r} (só dígitos)")

    return achados


# --- O detector funciona (roda mesmo sem nenhuma rota do Relatório) ------------
#
# Sem estes testes, uma regressão que nunca falha passaria por uma que protege.


SENTINELAS = [
    *SENTINELAS_DE_PESSOA.values(),
    *SENTINELAS_DO_COLETIVO.values(),
    NOME_DA_OUTRA_INTEGRANTE,
]


def test_detector_aceita_agregado_limpo():
    agregado = {
        "total_coletivos": 1,
        "total_pessoas": 2,
        "por_bairro": [{"nome": "Fonseca", "total": 1}],
        "por_categoria": [{"nome": "Agroecologia", "slug": "agroecologia", "total": 1}],
        "por_cor_raca": [{"rotulo": "Parda", "total": 2}],
    }

    assert vazamentos(agregado, SENTINELAS) == []


@pytest.mark.parametrize(
    "resposta",
    [
        {"email": "qualquer@exemplo.org"},
        {"por_bairro": [{"nome": "Fonseca", "telefone": "x"}]},
        {"dados": [{"detalhe": {"CPF": "x"}}]},
        {"pessoas": []},
        {"documento": None},
    ],
    ids=["raiz", "aninhada", "funda-e-maiuscula", "lista-vazia", "valor-nulo"],
)
def test_detector_pega_chave_de_membro(resposta):
    assert vazamentos(resposta, SENTINELAS)


@pytest.mark.parametrize(
    "resposta",
    [
        {"rotulo": SENTINELAS_DE_PESSOA["nome"]},
        {"destaque": f"Maior coletivo: {SENTINELAS_DO_COLETIVO['responsavel_grupo']}"},
        {"contato": "21987654321"},
        {"x": [{"y": SENTINELAS_DE_PESSOA["email"].upper()}]},
        {SENTINELAS_DE_PESSOA["nome"]: 1},
    ],
    ids=["chave-renomeada", "dentro-de-texto", "so-digitos", "maiusculas", "como-chave"],
)
def test_detector_pega_valor_de_membro_com_qualquer_chave(resposta):
    assert vazamentos(resposta, SENTINELAS)


# --- Descoberta das rotas do Relatório ---------------------------------------


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


def rotas_do_relatorio() -> list[tuple[str, URLPattern]]:
    return sorted(
        (caminho, padrao)
        for caminho, padrao in _rotas(get_resolver().url_patterns)
        if caminho.startswith(PREFIXO_DO_RELATORIO)
    )


def _url(caminho: str) -> str:
    """URL pronta para o GET, preenchendo os parâmetros de ARGUMENTOS_DAS_ROTAS."""
    tem_parametro = "<" in caminho or "(" in caminho
    if not tem_parametro:
        return "/" + caminho
    if caminho not in ARGUMENTOS_DAS_ROTAS:
        pytest.fail(
            f"A rota {caminho!r} tem parâmetro e ficou fora da regressão de LGPD. "
            "Inclua os argumentos dela em ARGUMENTOS_DAS_ROTAS."
        )
    url = caminho
    for nome, valor in ARGUMENTOS_DAS_ROTAS[caminho].items():
        url = re.sub(rf"<(?:\w+:)?{nome}>|\(\?P<{nome}>[^)]*\)", str(valor), url)
    return "/" + url


ROTAS = rotas_do_relatorio()
SEM_ROTAS = "Nenhuma rota do Relatório ainda (backend#56 a #58)."


# --- Os endpoints do Relatório -------------------------------------------------


@pytest.fixture
def da_equipe():
    return get_user_model().objects.create_user(
        username="coordenacao", password="senha-de-teste-123", is_staff=True,
    )


@pytest.fixture
def cadastro_com_sentinelas():
    """Rede mínima com todo campo pessoal preenchido por um sentinela.

    Preencher é o ponto: com o cadastro vazio, a suíte passaria mesmo se o
    endpoint devolvesse as pessoas inteiras. Há dados nos campos agregáveis
    (bairro, categoria, bloco socioeconômico) para o Relatório ter o que somar.
    """
    categoria = Categoria.objects.create(nome="Agroecologia", slug="agroecologia")
    coletivo = Coletivo.objects.create(
        nome="Coletivo Sentinela",
        slug="coletivo-sentinela",
        bairro="Fonseca",
        numero="42",
        complemento="fundos",
        cep="24130-000",
        **SENTINELAS_DO_COLETIVO,
    )
    coletivo.categorias.add(categoria)

    Pessoa.objects.create(
        coletivo=coletivo,
        data_nascimento="1980-05-17",
        bairro="Fonseca",
        municipio="Niterói",
        escolaridade="Ensino médio completo",
        cor_raca="Parda",
        sexo="Feminino",
        identidade_genero="Mulher cis",
        pessoa_com_deficiencia=True,
        qual_deficiencia="Auditiva",
        renda_familiar="Até 1 salário mínimo",
        **SENTINELAS_DE_PESSOA,
    )
    Pessoa.objects.create(
        coletivo=coletivo, nome=NOME_DA_OUTRA_INTEGRANTE, cor_raca="Preta",
    )
    return coletivo


def _corpo(resposta):
    """JSON da resposta; se não for JSON (um CSV, por exemplo), o texto cru."""
    if "json" in resposta.get("Content-Type", ""):
        return resposta.json()
    return resposta.content.decode(errors="replace")


@pytest.mark.skipif(not ROTAS, reason=SEM_ROTAS)
@pytest.mark.parametrize("caminho", [caminho for caminho, _ in ROTAS])
def test_relatorio_nao_expoe_dado_de_membro(api, da_equipe, cadastro_com_sentinelas, caminho):
    """Nenhuma resposta do Relatório traz chave ou valor de dado pessoal."""
    api.force_login(da_equipe)

    resposta = api.get(_url(caminho))

    assert resposta.status_code == 200, resposta.content[:500]
    achados = vazamentos(_corpo(resposta), SENTINELAS)
    assert not achados, f"/{caminho} expõe dado pessoal:\n- " + "\n- ".join(achados)


@pytest.mark.skipif(not ROTAS, reason=SEM_ROTAS)
@pytest.mark.parametrize("caminho,padrao", ROTAS, ids=[caminho for caminho, _ in ROTAS])
def test_relatorio_herda_a_visao_da_equipe(caminho, padrao):
    """Agregado de dado sensível também é só da equipe: sessão, `is_staff`, sem cache."""
    classe = getattr(padrao.callback, "cls", None) or getattr(
        padrao.callback, "view_class", None
    )

    assert classe is not None and issubclass(classe, VisaoDaEquipe), (
        f"/{caminho} precisa herdar de VisaoDaEquipe (rede/views_equipe.py)."
    )


@pytest.mark.skipif(not ROTAS, reason=SEM_ROTAS)
@pytest.mark.parametrize("caminho", [caminho for caminho, _ in ROTAS])
def test_relatorio_recusa_anonimo(api, cadastro_com_sentinelas, caminho):
    resposta = api.get(_url(caminho))

    assert resposta.status_code == 403
    assert not vazamentos(_corpo(resposta), SENTINELAS)
