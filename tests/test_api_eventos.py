"""Contrato do endpoint público de eventos (Seção 8.1 do PRD desta fatia).

Duas coisas se provam aqui, e as duas são bloqueantes no CI:

1. **A resposta não tem nada além do contrato.** O teste de conjunto exato de
   chaves é lista branca — pega o campo que ninguém previu.
2. **A agenda não perde o evento em andamento.** `periodo=proximos` e
   `periodo=passados` particionam os eventos ativos sem sobra nem
   sobreposição, e uma feira de três dias continua na agenda no segundo dia.
"""
from datetime import datetime, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from rede.models import Evento, ImagemEvento
from tests.helpers import PNG_MINIMO

pytestmark = pytest.mark.django_db

#: Conjunto exato de chaves da resposta pública de um evento (Seção 3.4).
CHAVES_DO_EVENTO = {
    "id",
    "titulo",
    "slug",
    "descricao",
    "data_inicio",
    "data_fim",
    "local",
    "bairro",
    "link",
    "imagens",
    "criado_em",
    "atualizado_em",
}

#: Conjunto exato de chaves de cada imagem aninhada (Seção 4.4).
CHAVES_DA_IMAGEM = {"id", "imagem", "legenda", "ordem"}


@pytest.fixture
def evento_completo():
    """Evento com TODOS os campos preenchidos, inclusive `ativo`.

    Preencher tudo é o ponto: um teste feito sobre um cadastro vazio passaria
    mesmo com o serializer errado.
    """
    return Evento.objects.create(
        titulo="Feira do Circuito Arariboia",
        slug="feira-arariboia-agosto-2026",
        descricao="Feira mensal de agroecologia e artesanato.",
        data_inicio=timezone.now() + timedelta(days=10),
        data_fim=timezone.now() + timedelta(days=11),
        local="Praça Arariboia",
        bairro="Centro",
        link="https://ecosolniteroi.org/feira",
    )


def em(dias):
    """Instante relativo a agora, consciente de fuso (`USE_TZ=True`)."""
    return timezone.now() + timedelta(days=dias)


def slugs(resposta):
    return [item["slug"] for item in resposta.json()["results"]]


# --- Contrato e exposição ---------------------------------------------------


def test_listagem_responde_200_com_envelope_de_paginacao(api, evento_completo):
    """(1) A listagem usa o envelope `count / next / previous / results` do DRF."""
    resposta = api.get("/api/eventos/")

    assert resposta.status_code == 200
    assert set(resposta.json().keys()) == {"count", "next", "previous", "results"}
    assert resposta.json()["count"] == 1


def test_resposta_tem_exatamente_as_chaves_do_contrato(api, evento_completo):
    """(2) O conjunto de chaves da resposta é EXATAMENTE o do contrato.

    Este é o teste mais importante do arquivo, e o único que é lista branca.
    Os demais pegam o vazamento que alguém previu; comparar o conjunto inteiro
    pega **o campo que ninguém previu**, incluído por acidente daqui a seis
    meses — inclusive um campo que ainda não existe no model.

    Se ele quebrar depois de alguém mexer no serializer, a pergunta é "esse
    campo pode mesmo ser público?", e não "como afrouxo a asserção?".
    NÃO troque a comparação de conjunto por uma verificação de alguns campos.
    """
    detalhe = api.get(f"/api/eventos/{evento_completo.slug}/").json()
    assert set(detalhe.keys()) == CHAVES_DO_EVENTO

    # Mesma exigência na listagem, que é a porta mais visitada.
    item_da_lista = api.get("/api/eventos/").json()["results"][0]
    assert set(item_da_lista.keys()) == CHAVES_DO_EVENTO


def test_data_inicio_sai_em_iso_8601_com_fuso(api, evento_completo):
    """(2b) `data_inicio` é data-HORA ISO 8601 com offset (emenda 10.5).

    É a única mudança que esta fatia faz na convenção de datas do projeto — o
    resto da API devolve `AAAA-MM-DD` — e sem esta asserção ela entra sem rede:
    bastaria alguém acrescentar `DATETIME_FORMAT` ao `REST_FRAMEWORK` para
    acertar o Admin, a suíte inteira continuaria verde e o `new Date(...)` da
    agenda passaria a receber `Invalid Date` em produção.

    Comparar com `evento.data_inicio.isoformat()` NÃO funciona: o DRF converte
    para `TIME_ZONE` antes de serializar, e a fixture guarda UTC — daí o
    `localtime()`.
    """
    dados = api.get(f"/api/eventos/{evento_completo.slug}/").json()

    assert dados["data_inicio"] == timezone.localtime(evento_completo.data_inicio).isoformat()
    assert dados["data_inicio"].endswith("-03:00")  # a emenda 10.5 é sobre o offset


def test_data_fim_ausente_sai_null_com_a_chave_presente(api):
    """(2c) Sem `data_fim`, a chave vem no corpo valendo `null`, e não sumida."""
    Evento.objects.create(titulo="Sem fim", slug="sem-fim", data_inicio=em(3))

    dados = api.get("/api/eventos/sem-fim/").json()

    assert "data_fim" in dados
    assert dados["data_fim"] is None


def test_campo_ativo_nunca_aparece(api, evento_completo):
    """(3) `ativo` é chave de visibilidade, não campo de resposta."""
    detalhe = api.get(f"/api/eventos/{evento_completo.slug}/").json()
    item_da_lista = api.get("/api/eventos/").json()["results"][0]

    assert "ativo" not in detalhe
    assert "ativo" not in item_da_lista


def test_evento_inativo_nao_aparece_e_seu_detalhe_da_404(api, evento_completo):
    """(4) `ativo=False` some da listagem e o detalhe responde 404.

    Precisa tirar do ar de verdade: não é 200 com aviso, nem 403 — um 403 já
    confirmaria que o recurso existe.
    """
    oculto = Evento.objects.create(
        titulo="Cancelado", slug="cancelado", data_inicio=em(3), ativo=False,
    )

    assert oculto.slug not in slugs(api.get("/api/eventos/"))
    assert api.get(f"/api/eventos/{oculto.slug}/").status_code == 404


def test_api_e_somente_leitura(api, evento_completo):
    """(5) Nenhum método de escrita existe: a API pública só lê."""
    detalhe = f"/api/eventos/{evento_completo.slug}/"

    assert api.post("/api/eventos/", {"titulo": "X"}).status_code == 405
    assert api.put(detalhe, {"titulo": "X"}).status_code == 405
    assert api.patch(detalhe, {"titulo": "X"}).status_code == 405
    assert api.delete(detalhe).status_code == 405


# --- Período ----------------------------------------------------------------


def test_periodo_proximos_inclui_evento_em_andamento(api):
    """(6) O evento que já começou e ainda não terminou CONTINUA na agenda.

    É o teste que justifica a regra da Seção 3.3. Cortar por
    `data_inicio >= agora` faria a feira de três dias sumir no segundo dia —
    exatamente enquanto acontece, o pior momento possível para desaparecer.
    """
    Evento.objects.create(
        titulo="Terminou", slug="terminou", data_inicio=em(-3), data_fim=em(-2),
    )
    Evento.objects.create(
        titulo="Em andamento", slug="em-andamento", data_inicio=em(-1), data_fim=em(1),
    )
    Evento.objects.create(
        titulo="Futuro", slug="futuro", data_inicio=em(5), data_fim=em(6),
    )

    assert slugs(api.get("/api/eventos/?periodo=proximos")) == ["em-andamento", "futuro"]


def test_periodo_proximos_usa_data_inicio_quando_nao_ha_data_fim(api):
    """(7) Sem `data_fim`, quem decide é `data_inicio`."""
    Evento.objects.create(titulo="Ontem", slug="ontem", data_inicio=em(-1))
    Evento.objects.create(titulo="Amanhã", slug="amanha", data_inicio=em(1))

    assert slugs(api.get("/api/eventos/?periodo=proximos")) == ["amanha"]
    assert slugs(api.get("/api/eventos/?periodo=passados")) == ["ontem"]


def test_proximos_e_passados_sao_complementares(api):
    """(8) Todo evento ativo cai em exatamente um dos dois — nenhum sem lar.

    É o que o `exclude(em_aberto)` do filtro garante. Reescrever a negação à
    mão é onde nasceria o evento que não aparece em nenhum dos dois conjuntos.
    """
    Evento.objects.create(titulo="A", slug="a", data_inicio=em(-3), data_fim=em(-2))
    Evento.objects.create(titulo="B", slug="b", data_inicio=em(-1), data_fim=em(1))
    Evento.objects.create(titulo="C", slug="c", data_inicio=em(5))
    Evento.objects.create(titulo="D", slug="d", data_inicio=em(-5))

    todos = set(slugs(api.get("/api/eventos/")))
    proximos = set(slugs(api.get("/api/eventos/?periodo=proximos")))
    passados = set(slugs(api.get("/api/eventos/?periodo=passados")))

    assert proximos | passados == todos
    assert proximos & passados == set()


def test_sem_periodo_lista_todos(api):
    """(9) A rota nua NÃO aplica recorte temporal implícito."""
    Evento.objects.create(titulo="Velho", slug="velho", data_inicio=em(-30))
    Evento.objects.create(titulo="Novo", slug="novo", data_inicio=em(30))

    assert api.get("/api/eventos/").json()["count"] == 2
    assert api.get("/api/eventos/?periodo=todos").json()["count"] == 2


def test_periodo_invalido_responde_400(api, evento_completo):
    """(10) Valor fora da lista de opções é erro de requisição, não silêncio."""
    assert api.get("/api/eventos/?periodo=ontem").status_code == 400


# --- Filtros, ordenação, paginação ------------------------------------------


def test_intervalo_de_ate_inclui_os_dias_limite(api):
    """(11) `de`/`ate` comparam a DATA, não o instante.

    O evento é às 19h de propósito: escrito com evento à meia-noite, este
    teste passaria mesmo com o filtro errado. Comparar `ate=2026-08-15`
    diretamente contra o `DateTimeField` colocaria o limite na meia-noite do
    dia 15, e o evento das 19h — que é o que a pessoa pediu — ficaria de fora.
    """
    dia_15 = timezone.make_aware(datetime(2026, 8, 15, 19, 0))
    dia_10 = timezone.make_aware(datetime(2026, 8, 10, 19, 0))
    Evento.objects.create(titulo="Dia 15", slug="dia-15", data_inicio=dia_15)
    Evento.objects.create(titulo="Dia 10", slug="dia-10", data_inicio=dia_10)

    assert slugs(api.get("/api/eventos/?ate=2026-08-15")) == ["dia-10", "dia-15"]
    assert slugs(api.get("/api/eventos/?de=2026-08-15")) == ["dia-15"]
    assert slugs(api.get("/api/eventos/?de=2026-08-10&ate=2026-08-10")) == ["dia-10"]
    assert api.get("/api/eventos/?de=15/08/2026").status_code == 400


def test_busca_q_encontra_por_titulo_descricao_e_local(api, evento_completo):
    """(12) `q` busca em `titulo`, `descricao` e `local`, ignorando maiúsculas."""
    Evento.objects.create(
        titulo="Roda de conversa", slug="roda", data_inicio=em(2),
        descricao="Formação em cooperativismo.", local="ITES/UFF",
    )

    assert api.get("/api/eventos/?q=circuito").json()["count"] == 1  # título
    assert api.get("/api/eventos/?q=cooperativismo").json()["count"] == 1  # descrição
    assert api.get("/api/eventos/?q=praça").json()["count"] == 1  # local
    assert api.get("/api/eventos/?q=inexistente").json()["count"] == 0


def test_filtro_por_bairro_ignora_maiusculas(api, evento_completo):
    """(13) `bairro` filtra por igualdade, sem diferenciar maiúsculas."""
    Evento.objects.create(
        titulo="Encontro no Fonseca", slug="fonseca", data_inicio=em(2), bairro="Fonseca",
    )

    assert api.get("/api/eventos/?bairro=centro").json()["count"] == 1
    assert api.get("/api/eventos/?bairro=CENTRO").json()["count"] == 1
    assert api.get("/api/eventos/?bairro=Fonseca").json()["count"] == 1
    assert api.get("/api/eventos/?bairro=Icaraí").json()["count"] == 0


def test_ordenacao_padrao_e_cronologica(api):
    """(14) Sem parâmetro, o próximo evento vem primeiro; `-data_inicio` inverte.

    A ordenação pública é o oposto da do `Meta` do model (`-data_inicio`), e é
    de propósito: o Admin quer ver o último cadastro, a agenda lê o tempo para
    frente.
    """
    Evento.objects.create(titulo="Depois", slug="depois", data_inicio=em(20))
    Evento.objects.create(titulo="Antes", slug="antes", data_inicio=em(2))
    Evento.objects.create(titulo="Meio", slug="meio", data_inicio=em(10))

    assert slugs(api.get("/api/eventos/")) == ["antes", "meio", "depois"]
    assert slugs(api.get("/api/eventos/?ordering=-data_inicio")) == [
        "depois", "meio", "antes",
    ]
    assert slugs(api.get("/api/eventos/?ordering=titulo")) == ["antes", "depois", "meio"]


def test_paginacao(api):
    """(15) `page_size=1` pagina; `page=999` dá 404."""
    for indice in range(3):
        Evento.objects.create(
            titulo=f"Evento {indice}", slug=f"evento-{indice}", data_inicio=em(indice + 1),
        )

    primeira = api.get("/api/eventos/?page_size=1").json()
    assert len(primeira["results"]) == 1
    assert primeira["count"] == 3
    assert primeira["next"] is not None

    assert api.get("/api/eventos/?page=999").status_code == 404


def test_teto_de_page_size_e_100(api):
    """(15b) Com mais de 100 eventos, `page_size=500` devolve no máximo 100."""
    agora = timezone.now()
    Evento.objects.bulk_create(
        Evento(
            titulo=f"Evento {i:03d}",
            slug=f"evento-{i:03d}",
            data_inicio=agora + timedelta(days=i),
        )
        for i in range(101)
    )

    resposta = api.get("/api/eventos/?page_size=500").json()

    assert resposta["count"] == 101
    assert len(resposta["results"]) == 100


def test_detalhe_por_slug(api, evento_completo):
    """(16) O detalhe responde 200 pelo slug; slug inexistente responde 404."""
    resposta = api.get(f"/api/eventos/{evento_completo.slug}/")

    assert resposta.status_code == 200
    assert resposta.json()["slug"] == evento_completo.slug
    assert resposta.json()["titulo"] == "Feira do Circuito Arariboia"

    assert api.get("/api/eventos/evento-que-nao-existe/").status_code == 404


# --- Galeria e desempenho ---------------------------------------------------


def test_imagens_vem_aninhadas_na_ordem_definida(api, evento_completo):
    """(17) A galeria sai ordenada por `ordem`, com o contrato mínimo de imagem.

    As imagens são criadas fora de ordem justamente para que a asserção prove
    a ordenação, e não a ordem de inserção.
    """
    for ordem, legenda in ((2, "Terceira"), (0, "Primeira"), (1, "Segunda")):
        ImagemEvento.objects.create(
            evento=evento_completo,
            imagem=SimpleUploadedFile(f"cartaz-{ordem}.png", PNG_MINIMO, "image/png"),
            legenda=legenda,
            ordem=ordem,
        )

    imagens = api.get(f"/api/eventos/{evento_completo.slug}/").json()["imagens"]

    assert [imagem["legenda"] for imagem in imagens] == ["Primeira", "Segunda", "Terceira"]
    for imagem in imagens:
        assert set(imagem.keys()) == CHAVES_DA_IMAGEM
        assert imagem["imagem"].endswith(".png")
        # Absoluta, não relativa: é o valor que o Next.js joga direto no
        # `<img src>`, e o domínio da API não é o domínio do site.
        assert imagem["imagem"].startswith("http://testserver/media/eventos/")


def test_listagem_nao_tem_n_mais_1(api, django_assert_num_queries):
    """(18) A listagem faz um número CONSTANTE de queries, não uma por evento.

    É este teste que transforma "sem N+1" de promessa em garantia: sem ele, o
    `prefetch_related` some no primeiro refactor e ninguém percebe até a
    agenda ficar lenta em produção.
    """
    for indice in range(10):
        evento = Evento.objects.create(
            titulo=f"Evento {indice:02d}",
            slug=f"evento-{indice:02d}",
            data_inicio=em(indice + 1),
        )
        for ordem in range(3):
            ImagemEvento.objects.create(
                evento=evento,
                imagem=SimpleUploadedFile(
                    f"cartaz-{indice}-{ordem}.png", PNG_MINIMO, "image/png",
                ),
                ordem=ordem,
            )

    # 2 queries: o COUNT da paginação e a página; + 1 do prefetch das imagens.
    with django_assert_num_queries(3):
        resposta = api.get("/api/eventos/?page_size=10")

    assert len(resposta.json()["results"]) == 10
    assert len(resposta.json()["results"][0]["imagens"]) == 3
