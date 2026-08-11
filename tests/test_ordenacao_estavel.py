"""A ordenação das listagens públicas é total, e por isso a paginação é estável.

Nenhum campo de ordenação do contrato é único — `Evento.data_inicio`,
`PontoDeInteresse.nome` e `Coletivo.nome` todos admitem repetição. Sem um
desempate, `LIMIT`/`OFFSET` sobre os empatados devolve ordem arbitrária a cada
consulta, e um registro pode aparecer duas vezes ou não aparecer em nenhuma
página.

**Por que estes testes olham o SQL, e não a ordem devolvida.** Um teste que
paginasse registros empatados e comparasse as duas páginas passaria mesmo com
o bug: em bases pequenas o Postgres tende a devolver na ordem física, e o
SQLite da suíte local ordena por `rowid` por acaso. O defeito só se manifesta
quando o planejador muda de estratégia — com volume, índice novo ou execução
paralela — que é justamente o que um teste não reproduz. O `ORDER BY` emitido é
a garantia observável: se a chave única está lá, o banco não tem liberdade
nenhuma para variar.
"""
import re
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from rede.models import Coletivo, Evento, PontoDeInteresse

pytestmark = pytest.mark.django_db


def order_by_da_listagem(api, rota, tabela):
    """Devolve as cláusulas `ORDER BY` das consultas feitas em `tabela`.

    O recorte por tabela é essencial: a listagem dispara também o `COUNT` da
    paginação (que não ordena) e as consultas de `prefetch_related` — galeria
    do evento, categorias do coletivo —, e essas trazem o `Meta.ordering` do
    seu próprio model. Sem o recorte, a asserção olharia o `ORDER BY` da
    tabela errada.
    """
    with CaptureQueriesContext(connection) as capturadas:
        resposta = api.get(rota)
    assert resposta.status_code == 200

    return [
        trecho.group(1)
        for consulta in capturadas.captured_queries
        if f'FROM "{tabela}"' in consulta["sql"]
        and (trecho := re.search(r"ORDER BY (.+?)(?: LIMIT|$)", consulta["sql"]))
    ]


def assert_ordem_total(api, rota, tabela, coluna_esperada):
    """Assere que a rota ordena pela coluna do contrato E desempata por id."""
    clausulas = order_by_da_listagem(api, rota, tabela)

    assert clausulas, f"{rota} não emitiu ORDER BY nenhum em {tabela}"
    for clausula in clausulas:
        assert coluna_esperada in clausula, (
            f"{rota}: esperava ordenar por {coluna_esperada}, veio {clausula!r}"
        )
        assert f'"{tabela}"."id"' in clausula, (
            f"{rota}: ORDER BY sem desempate por id — a paginação pode "
            f"repetir ou perder registro. Veio {clausula!r}"
        )


# --- A ordenação padrão de cada endpoint ------------------------------------


def test_eventos_desempatam_por_id(api):
    """Dois eventos no MESMO instante não têm ordem definida entre si."""
    mesmo_instante = timezone.now() + timedelta(days=5)
    for indice in range(2):
        Evento.objects.create(
            titulo=f"Oficina {indice}",
            slug=f"oficina-{indice}",
            data_inicio=mesmo_instante,
        )

    assert_ordem_total(api, "/api/eventos/", "rede_evento", "data_inicio")


def test_pontos_desempatam_por_id(api):
    """Dois pontos podem se chamar igual — "Feira do Centro" não é único."""
    for _ in range(2):
        PontoDeInteresse.objects.create(
            nome="Feira do Centro",
            tipo=PontoDeInteresse.TipoPonto.FEIRA_ARARIBOIA,
            latitude=Decimal("-22.900000"),
            longitude=Decimal("-43.100000"),
        )

    assert_ordem_total(api, "/api/pontos-de-interesse/", "rede_pontodeinteresse", "nome")


def test_coletivos_desempatam_por_id(api):
    """`Coletivo.nome` também não é único — só o slug é."""
    for indice in range(2):
        Coletivo.objects.create(nome="Rede Solidária", slug=f"rede-solidaria-{indice}")

    assert_ordem_total(api, "/api/coletivos/", "rede_coletivo", "nome")


# --- A ordenação que o cliente pede -----------------------------------------


def test_ordering_do_cliente_tambem_desempata(api):
    """O desempate vale para `?ordering=`, não só para o padrão da view.

    É o caso que uma correção feita só no atributo `ordering` das views
    deixaria passar — e o README recomenda `?periodo=passados&ordering=
    -data_inicio` para montar o histórico da rede, que é exatamente uma
    listagem longa e paginada.
    """
    mesmo_instante = timezone.now() - timedelta(days=5)
    for indice in range(2):
        Evento.objects.create(
            titulo=f"Encontro {indice}",
            slug=f"encontro-{indice}",
            data_inicio=mesmo_instante,
        )

    assert_ordem_total(
        api, "/api/eventos/?ordering=-data_inicio", "rede_evento", "data_inicio",
    )
    assert_ordem_total(api, "/api/eventos/?ordering=titulo", "rede_evento", "titulo")


def test_desempate_nao_e_duplicado_quando_o_cliente_ja_ordena_por_id(api):
    """Pedir `?ordering=id` não produz `ORDER BY id, id`.

    `id` não está em `ordering_fields` de nenhuma view, então o DRF o descarta
    e cai na ordenação padrão — o que este teste fixa é que o descarte continua
    valendo e que o SQL não ganha coluna repetida por causa da nova classe.
    """
    Evento.objects.create(
        titulo="Único", slug="unico", data_inicio=timezone.now() + timedelta(days=1),
    )

    clausulas = order_by_da_listagem(api, "/api/eventos/?ordering=id", "rede_evento")

    assert clausulas
    for clausula in clausulas:
        assert len(re.findall(r'"rede_evento"\."id"', clausula)) == 1, (
            f"coluna de desempate repetida no ORDER BY: {clausula!r}"
        )


# --- A ordenação interna da galeria -----------------------------------------


def test_galeria_do_evento_ja_desempata_pelo_model(api):
    """`ImagemEvento.Meta.ordering` já é `["ordem", "id"]` — nada a corrigir.

    Este teste existe para registrar que a garantia da galeria vem do model, e
    não do filtro: o aninhamento não passa pelo `OrdenacaoEstavel`. Se alguém
    tirar o `id` do `Meta.ordering`, duas imagens com a mesma `ordem` voltam a
    trocar de lugar entre requisições, e o slide muda sozinho.
    """
    assert "id" in Evento.imagens.rel.related_model._meta.ordering
