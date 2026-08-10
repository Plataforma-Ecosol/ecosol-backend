"""Filtros da API pública.

A busca textual (`q`) não é filtro daqui: é o `SearchFilter` do DRF, com
`search_fields` declarados na view e `SEARCH_PARAM = "q"` em settings.
"""
from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters

from rede.models import Coletivo, Evento, PontoDeInteresse

#: Único formato de data aceito nos parâmetros do contrato público.
FORMATO_ISO = ["%Y-%m-%d"]


class ColetivoFilter(filters.FilterSet):
    """Filtros de listagem de coletivos (Seção 3.3 do PRD).

    `ativo` NÃO é declarado aqui, de propósito (emenda 10.2): é a chave de
    visibilidade pública, o mecanismo com que a equipe do Centro Público tira
    um coletivo do ar. Exposto como parâmetro, permitiria a qualquer pessoa
    listar exatamente os coletivos que a equipe decidiu não exibir. O queryset
    da view fixa `ativo=True`.
    """

    # `NumberFilter` é o que produz o 400 do contrato quando chega texto.
    categoria = filters.NumberFilter(
        field_name="categorias__id",
        label="ID da categoria",
    )
    # Valor público, nunca logradouro.
    bairro = filters.CharFilter(lookup_expr="iexact", label="Bairro")

    class Meta:
        model = Coletivo
        fields = ["categoria", "bairro"]


# --- Evento -----------------------------------------------------------------


class EventoFilter(filters.FilterSet):
    """Filtros de listagem de eventos (Seção 3.3 do PRD desta fatia).

    Como no Coletivo, `ativo` NÃO é declarado aqui (emenda 10.3): é chave de
    visibilidade, não filtro. O queryset da view fixa `ativo=True`.

    `periodo` é explícito e tem padrão `todos`: a rota nua NÃO aplica recorte
    temporal. Um recorte que o cliente não pediu, não vê no contrato e não
    consegue desligar seria uma armadilha — quem consumisse a API para montar
    um histórico da rede receberia uma lista misteriosamente incompleta. A
    agenda pública pede `?periodo=proximos`.
    """

    PROXIMOS = "proximos"
    PASSADOS = "passados"
    TODOS = "todos"
    PERIODOS = [
        (PROXIMOS, "Próximos"),
        (PASSADOS, "Passados"),
        (TODOS, "Todos"),
    ]

    # `ChoiceFilter` é o que produz o 400 do contrato quando chega `periodo=ontem`.
    periodo = filters.ChoiceFilter(
        choices=PERIODOS,
        method="filtrar_por_periodo",
        label="Período",
    )
    # `date__gte`/`date__lte`, e não `gte`/`lte`: `data_inicio` é DateTimeField,
    # e comparar `ate=2026-08-15` direto contra o campo colocaria o limite na
    # MEIA-NOITE do dia 15 — todo evento daquele dia, que é justamente o que se
    # pediu, ficaria de fora. É o bug clássico de intervalo em campo data-hora.
    #
    # `input_formats` fixa ISO 8601 como ÚNICO formato aceito (Seção 3.7): sem
    # isso o Django também aceitaria o formato localizado `15/08/2026`, por
    # causa de `LANGUAGE_CODE = "pt-br"`. Seria um segundo contrato, não
    # documentado, que o frontend passaria a usar sem querer — e `05/08/2026`
    # é ambíguo entre os dois. O contrato público diz AAAA-MM-DD; o resto é 400.
    de = filters.DateFilter(
        field_name="data_inicio", lookup_expr="date__gte",
        input_formats=FORMATO_ISO, label="A partir de",
    )
    ate = filters.DateFilter(
        field_name="data_inicio", lookup_expr="date__lte",
        input_formats=FORMATO_ISO, label="Até",
    )
    bairro = filters.CharFilter(lookup_expr="iexact", label="Bairro")

    class Meta:
        model = Evento
        fields = ["periodo", "de", "ate", "bairro"]

    def filtrar_por_periodo(self, queryset, name, value):
        """Recorta a agenda no tempo, sem perder o evento em andamento.

        `timezone.now()` — e nunca `datetime.now()`: `USE_TZ=True` e o projeto
        roda em `America/Sao_Paulo`; o ingênuo produziria um erro de três horas
        que só aparece na virada do dia.

        A condição é "ainda em aberto": o evento continua na agenda enquanto
        não terminar. Uma feira de três dias tem de aparecer no segundo dia —
        cortar por `data_inicio >= agora` a faria sumir exatamente enquanto
        acontece, o pior momento possível para desaparecer.
        """
        agora = timezone.now()
        em_aberto = Q(data_fim__gte=agora) | Q(
            data_fim__isnull=True, data_inicio__gte=agora,
        )
        if value == self.PROXIMOS:
            return queryset.filter(em_aberto)
        if value == self.PASSADOS:
            # `exclude` da MESMA condição, e não a negação reescrita à mão: é
            # o que garante que `proximos` e `passados` particionem os eventos
            # ativos sem sobra nem sobreposição. Reescrever a negação é onde
            # nasceria o evento que não aparece em nenhum dos dois.
            return queryset.exclude(em_aberto)
        return queryset  # "todos"


# --- Ponto de Interesse -----------------------------------------------------


class PontoDeInteresseFilter(filters.FilterSet):
    """Filtros de listagem de pontos de interesse (Seção 3.5 do PRD).

    Como nos demais, `ativo` NÃO é declarado (emenda 10.3).

    Também não há filtro por coletivo (`?coletivo=<slug>`) nesta fatia: seria
    útil na página de perfil do coletivo, mas essa página é da fatia seguinte,
    e o filtro interage com a guarda do coletivo inativo de um jeito que
    merece ser decidido com o caso de uso na mão.
    """

    # `ChoiceFilter` amarrado às choices do model é o que produz o 400 quando
    # chega `tipo=padaria` — e é o que mantém filtro e cadastro em sincronia
    # no dia em que a equipe criar um tipo novo.
    tipo = filters.ChoiceFilter(
        choices=PontoDeInteresse.TipoPonto.choices, label="Tipo",
    )

    class Meta:
        model = PontoDeInteresse
        fields = ["tipo"]
