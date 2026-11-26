"""Agregados do Relatório de coletivos (Área da equipe).

Só contagens: nenhuma função daqui devolve registro, nome de coletivo ou dado
de pessoa. Quem chama é a API da equipe (`rede/views_equipe.py`), sempre atrás
da `VisaoDaEquipe`.

Dois endpoints usam este módulo: a distribuição dos coletivos (backend#57) e
os indicadores gerais (backend#56).

O recorte é o **cadastro**. `de` e `ate` olham `criado_em`, o dia em que o
coletivo entrou no sistema, e não `data_inicio`, o dia em que o grupo começou.
Coletivo inativo conta: o Relatório mede a rede cadastrada, não o que está no
ar no site.
"""
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django_filters import rest_framework as filters

from rede.filters import FORMATO_ISO
from rede.models import Coletivo, Pessoa
from rede.views import ordem_alfabetica

#: Pessoas cadastradas a partir das quais o coletivo conta como apto.
#:
#: É a única parte calculável da regra do PRD Técnico 4.1 ("no mínimo 3
#: pessoas e interfamiliar"): família não é entidade do modelo, então o caráter
#: interfamiliar continua verificação humana. É indicador, não validação, e
#: nada impede cadastrar um coletivo com menos pessoas.
MINIMO_DE_PESSOAS_PARA_APTIDAO = 3


class FiltroDoRelatorio(filters.FilterSet):
    """Recorte opcional do Relatório: período do cadastro e situação.

    As datas seguem as regras da API pública (`rede/filters.py`): só
    AAAA-MM-DD, e a comparação é pela **data**, não pelo instante, então
    `ate=2026-03-31` inclui o cadastro das 23h do dia 31. A data é a do fuso do
    projeto (America/Sao_Paulo). Valor inválido em qualquer parâmetro → 400.
    """

    de = filters.DateFilter(
        field_name="criado_em", lookup_expr="date__gte",
        input_formats=FORMATO_ISO, label="Cadastrados a partir de",
    )
    ate = filters.DateFilter(
        field_name="criado_em", lookup_expr="date__lte",
        input_formats=FORMATO_ISO, label="Cadastrados até",
    )
    situacao = filters.ChoiceFilter(choices=Coletivo.Situacao.choices, label="Situação")

    class Meta:
        model = Coletivo
        fields = ["de", "ate", "situacao"]


def por_bairro(coletivos):
    """Coletivos por bairro, do bairro com mais coletivos para o com menos.

    Mesma regra de grafia das opções de filtro (`bairros_em_uso`): "Centro" e
    "centro" são um bairro só, com o nome na grafia mais usada. Quem não tem
    bairro entra numa última linha com `bairro: null`, e por isso a soma das
    linhas é sempre o total.
    """
    linhas = (
        coletivos.values("bairro")
        .annotate(total=Count("pk", distinct=True))
        .order_by("-total", "bairro")
    )
    grupos = {}
    sem_bairro = 0
    for linha in linhas:
        bairro = linha["bairro"]
        if not bairro.strip():
            sem_bairro += linha["total"]
            continue
        # A ordem por `-total` faz a grafia mais usada chegar primeiro.
        grupo = grupos.setdefault(bairro.casefold(), {"bairro": bairro, "total": 0})
        grupo["total"] += linha["total"]

    resultado = sorted(
        grupos.values(),
        key=lambda grupo: (-grupo["total"], ordem_alfabetica(grupo["bairro"])),
    )
    if sem_bairro:
        resultado.append({"bairro": None, "total": sem_bairro})
    return resultado


def por_categoria(coletivos):
    """Coletivos por categoria (o segmento), da mais frequente para a menos.

    Um coletivo pode estar em várias categorias e conta em cada uma, então a
    soma das linhas pode passar do total. Quem não tem categoria entra numa
    última linha com `id`, `nome` e `slug` nulos.
    """
    # `values` sobre o M2M usa LEFT JOIN: o coletivo sem categoria vem numa
    # linha com `categorias__id` nulo, na mesma consulta.
    linhas = (
        coletivos.values("categorias__id", "categorias__nome", "categorias__slug")
        .annotate(total=Count("pk", distinct=True))
        .order_by()
    )
    resultado = []
    sem_categoria = 0
    for linha in linhas:
        if linha["categorias__id"] is None:
            sem_categoria = linha["total"]
            continue
        resultado.append({
            "id": linha["categorias__id"],
            "nome": linha["categorias__nome"],
            "slug": linha["categorias__slug"],
            "total": linha["total"],
        })

    resultado.sort(key=lambda linha: (-linha["total"], ordem_alfabetica(linha["nome"])))
    if sem_categoria:
        resultado.append({"id": None, "nome": None, "slug": None, "total": sem_categoria})
    return resultado


def por_mes(coletivos):
    """Cadastros por mês, do primeiro ao último mês com cadastro.

    Os meses sem cadastro no meio da série vêm com `total: 0`: um gráfico de
    linha que pulasse o mês vazio ligaria janeiro a março como se fevereiro não
    existisse. O mês é o do fuso do projeto: um cadastro das 22h de 31/03 é de
    março, embora em UTC já seja abril.
    """
    linhas = (
        coletivos.annotate(mes=TruncMonth("criado_em"))
        .values("mes")
        .annotate(total=Count("pk", distinct=True))
        .order_by("mes")
    )
    totais = {(linha["mes"].year, linha["mes"].month): linha["total"] for linha in linhas}
    if not totais:
        return []

    (ano, mes), ultimo = min(totais), max(totais)
    serie = []
    while (ano, mes) <= ultimo:
        serie.append({"mes": f"{ano:04d}-{mes:02d}", "total": totais.get((ano, mes), 0)})
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return serie


def distribuicao(coletivos):
    """Resposta de `GET /api/equipe/relatorio/distribuicao/`. Quatro consultas, fixas."""
    return {
        "total": coletivos.count(),
        "por_bairro": por_bairro(coletivos),
        "por_categoria": por_categoria(coletivos),
        "por_mes": por_mes(coletivos),
    }


# --- Indicadores gerais (backend#56) -----------------------------------------


def por_situacao(coletivos):
    """Coletivos por situação do cadastro, uma linha para cada valor do model.

    Na ordem de `Coletivo.Situacao`, com zero na situação sem coletivo: os
    cartões do Relatório mostram sempre as mesmas situações. `slug` é o valor
    que o filtro `situacao` da distribuição aceita.
    """
    totais = dict(
        coletivos.values_list("situacao")
        .annotate(total=Count("pk", distinct=True))
        .order_by()
    )
    return [
        {"slug": valor, "nome": rotulo, "total": totais.get(valor, 0)}
        for valor, rotulo in Coletivo.Situacao.choices
    ]


def aptos(coletivos):
    """Quantos coletivos têm ao menos `MINIMO_DE_PESSOAS_PARA_APTIDAO` pessoas.

    Calculado das pessoas cadastradas, a cada consulta: não existe campo de
    aptidão marcado à mão, e o número muda sozinho quando a equipe cadastra
    ou remove uma pessoa.
    """
    return (
        coletivos.annotate(pessoas_cadastradas=Count("pessoas", distinct=True))
        .filter(pessoas_cadastradas__gte=MINIMO_DE_PESSOAS_PARA_APTIDAO)
        .count()
    )


def indicadores_gerais(coletivos):
    """Resposta de `GET /api/equipe/relatorio/indicadores/`. Quatro consultas, fixas.

    `aptos + nao_aptos` é sempre `total_coletivos`. `total_membros` conta as
    pessoas dos coletivos do recorte, inclusive as de coletivo inativo.
    """
    total = coletivos.count()
    com_minimo = aptos(coletivos)
    return {
        "total_coletivos": total,
        "por_situacao": por_situacao(coletivos),
        "aptidao": {
            "minimo_de_pessoas": MINIMO_DE_PESSOAS_PARA_APTIDAO,
            "aptos": com_minimo,
            "nao_aptos": total - com_minimo,
        },
        "total_membros": Pessoa.objects.filter(coletivo__in=coletivos).count(),
    }
