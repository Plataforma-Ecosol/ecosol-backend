"""Contrato do endpoint público de pontos de interesse (Seção 8.2 do PRD).

Duas coisas se provam aqui, e as duas são bloqueantes no CI:

1. **A resposta não tem nada além do contrato** — o teste de conjunto exato de
   chaves, lista branca, igual ao dos outros dois endpoints.
2. **O coletivo que a equipe tirou do ar não vaza pelo mapa.** Esta é a única
   travessia de fronteira da API pública: um ponto ativo pode apontar para um
   coletivo inativo, e a chave de visibilidade do Coletivo tem de valer também
   por essa porta lateral.
"""
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from rede.models import Coletivo, PontoDeInteresse
from tests.helpers import PNG_MINIMO

pytestmark = pytest.mark.django_db

#: Conjunto exato de chaves da resposta pública de um ponto (Seção 3.6).
CHAVES_DO_PONTO = {
    "id",
    "nome",
    "tipo",
    "tipo_display",
    "descricao",
    "latitude",
    "longitude",
    "endereco",
    "imagem_capa",
    "coletivo",
    "criado_em",
    "atualizado_em",
}

#: Conjunto exato de chaves do coletivo aninhado — o cartão de visita.
CHAVES_DO_COLETIVO_RESUMIDO = {"id", "nome", "slug"}


@pytest.fixture
def ponto_completo():
    """Ponto com todos os campos preenchidos, sem vínculo com coletivo.

    As coordenadas terminam em dígitos significativos de propósito: com
    `-22.883700` o teste de precisão passaria mesmo se o serializer perdesse
    as casas decimais.
    """
    return PontoDeInteresse.objects.create(
        nome="Feira da Praça Arariboia",
        tipo=PontoDeInteresse.TipoPonto.FEIRA_ARARIBOIA,
        descricao="Feira semanal do circuito.",
        latitude=Decimal("-22.883712"),
        longitude=Decimal("-43.103456"),
        endereco="Praça Arariboia, Centro, Niterói",
    )


@pytest.fixture
def coletivo_ativo():
    """Coletivo visível, com dados internos preenchidos.

    Os dados internos são o ponto: um coletivo vazio passaria no teste de
    vazamento mesmo se o serializer aninhado expusesse o cadastro inteiro.
    """
    return Coletivo.objects.create(
        nome="Sementes do Vale",
        slug="sementes-do-vale",
        descricao="Agroecologia urbana no Fonseca.",
        bairro="Fonseca",
        logradouro="Rua das Palmeiras",
        cep="24130-000",
        cnpj="12.345.678/0001-90",
        telefone="(21) 99999-0000",  # sem consentimento
        nome_entrevistador="João Entrevistador",
    )


def ponto(nome, **extras):
    """Cria um ponto válido com o mínimo necessário para o teste em questão."""
    dados = {
        "nome": nome,
        "tipo": PontoDeInteresse.TipoPonto.LOJA_FISICA,
        "latitude": Decimal("-22.900000"),
        "longitude": Decimal("-43.100000"),
    }
    dados.update(extras)
    return PontoDeInteresse.objects.create(**dados)


def nomes(resposta):
    return [item["nome"] for item in resposta.json()["results"]]


# --- Contrato e exposição ---------------------------------------------------


def test_listagem_responde_200_com_envelope_de_paginacao(api, ponto_completo):
    """(1) A listagem usa o envelope `count / next / previous / results` do DRF."""
    resposta = api.get("/api/pontos-de-interesse/")

    assert resposta.status_code == 200
    assert set(resposta.json().keys()) == {"count", "next", "previous", "results"}
    assert resposta.json()["count"] == 1


def test_resposta_tem_exatamente_as_chaves_do_contrato(api, ponto_completo):
    """(2) O conjunto de chaves da resposta é EXATAMENTE o do contrato.

    Lista branca, como nos outros dois endpoints: pega **o campo que ninguém
    previu**, incluído por acidente daqui a seis meses — inclusive um campo
    que ainda não existe no model.

    Se ele quebrar depois de alguém mexer no serializer, a pergunta é "esse
    campo pode mesmo ser público?", e não "como afrouxo a asserção?".
    """
    detalhe = api.get(f"/api/pontos-de-interesse/{ponto_completo.id}/").json()
    assert set(detalhe.keys()) == CHAVES_DO_PONTO

    item_da_lista = api.get("/api/pontos-de-interesse/").json()["results"][0]
    assert set(item_da_lista.keys()) == CHAVES_DO_PONTO


def test_campo_ativo_nunca_aparece(api, ponto_completo):
    """(3) `ativo` é chave de visibilidade, não campo de resposta."""
    detalhe = api.get(f"/api/pontos-de-interesse/{ponto_completo.id}/").json()
    item_da_lista = api.get("/api/pontos-de-interesse/").json()["results"][0]

    assert "ativo" not in detalhe
    assert "ativo" not in item_da_lista


def test_ponto_inativo_nao_aparece_e_seu_detalhe_da_404(api, ponto_completo):
    """(4) `ativo=False` some da listagem e o detalhe responde 404."""
    oculto = ponto("Loja Fechada", ativo=False)

    assert "Loja Fechada" not in nomes(api.get("/api/pontos-de-interesse/"))
    assert api.get(f"/api/pontos-de-interesse/{oculto.id}/").status_code == 404


def test_api_e_somente_leitura(api, ponto_completo):
    """(5) Nenhum método de escrita existe: a API pública só lê."""
    detalhe = f"/api/pontos-de-interesse/{ponto_completo.id}/"

    assert api.post("/api/pontos-de-interesse/", {"nome": "X"}).status_code == 405
    assert api.put(detalhe, {"nome": "X"}).status_code == 405
    assert api.patch(detalhe, {"nome": "X"}).status_code == 405
    assert api.delete(detalhe).status_code == 405


# --- A guarda do coletivo vinculado -----------------------------------------


def test_coletivo_ativo_aparece_resumido(api, coletivo_ativo):
    """(6) O vínculo visível sai como cartão de visita: só `id`, `nome` e `slug`."""
    alvo = ponto("Loja do Sementes", coletivo=coletivo_ativo)

    dados = api.get(f"/api/pontos-de-interesse/{alvo.id}/").json()

    assert set(dados["coletivo"].keys()) == CHAVES_DO_COLETIVO_RESUMIDO
    assert dados["coletivo"]["nome"] == "Sementes do Vale"
    assert dados["coletivo"]["slug"] == "sementes-do-vale"


def test_coletivo_inativo_nao_vaza(api, coletivo_ativo):
    """(7) Ponto ATIVO vinculado a coletivo INATIVO não denuncia o coletivo.

    É a chave de visibilidade do Coletivo sendo respeitada por uma porta
    lateral: sem esta guarda, o nome e o slug de um coletivo que a equipe
    tirou do ar apareceriam na resposta do mapa, e o link do frontend levaria
    a um 404. A asserção sobre o corpo inteiro é o que pega o vazamento por
    outro nome ou aninhado mais fundo.
    """
    Coletivo.objects.filter(pk=coletivo_ativo.pk).update(ativo=False)
    alvo = ponto("Loja do Sementes", coletivo=coletivo_ativo)

    resposta = api.get(f"/api/pontos-de-interesse/{alvo.id}/")
    listagem = api.get("/api/pontos-de-interesse/")

    assert resposta.json()["coletivo"] is None
    assert listagem.json()["results"][0]["coletivo"] is None
    for corpo in (resposta.content.decode(), listagem.content.decode()):
        assert "Sementes do Vale" not in corpo
        assert "sementes-do-vale" not in corpo


def test_ponto_sem_coletivo_tambem_vem_null(api, coletivo_ativo):
    """(8) O ponto sem vínculo é INDISTINGUÍVEL do ponto com vínculo oculto.

    Essa indistinguibilidade **é** a proteção. Este teste existe para impedir
    que alguém "melhore" o serializer omitindo a chave em um dos dois casos:
    aí o campo faltante passaria a denunciar exatamente o que se quis
    esconder. A ausência de dado nunca pode denunciar a existência do dado.
    """
    Coletivo.objects.filter(pk=coletivo_ativo.pk).update(ativo=False)
    com_vinculo_oculto = ponto("Com vínculo oculto", coletivo=coletivo_ativo)
    sem_vinculo = ponto("Sem vínculo")

    oculto = api.get(f"/api/pontos-de-interesse/{com_vinculo_oculto.id}/").json()
    nenhum = api.get(f"/api/pontos-de-interesse/{sem_vinculo.id}/").json()

    assert oculto["coletivo"] is None
    assert nenhum["coletivo"] is None
    # Mesmas chaves, mesmo valor: nada na resposta separa um caso do outro.
    assert set(oculto.keys()) == set(nenhum.keys())


def test_nenhum_dado_interno_do_coletivo_vinculado_aparece(api, coletivo_ativo):
    """(9) O vínculo visível não é uma segunda porta para o cadastro do coletivo."""
    alvo = ponto("Loja do Sementes", coletivo=coletivo_ativo)

    corpo = api.get(f"/api/pontos-de-interesse/{alvo.id}/").content.decode()

    for valor in (
        "Rua das Palmeiras",
        "24130-000",
        "12.345.678/0001-90",
        "(21) 99999-0000",  # contato sem consentimento
        "João Entrevistador",
    ):
        assert valor not in corpo, f"{valor!r} vazou pelo coletivo vinculado"


# --- Georreferência ---------------------------------------------------------


def test_latitude_e_longitude_sao_numeros_no_json(api, ponto_completo):
    """(10) As coordenadas saem como número, não como string.

    O DRF serializaria o `DecimalField` como `"-22.883712"` por padrão. String
    quebra o Leaflet SILENCIOSAMENTE — o marcador simplesmente não aparece, e
    não há erro no console para investigar.
    """
    dados = api.get(f"/api/pontos-de-interesse/{ponto_completo.id}/").json()

    assert isinstance(dados["latitude"], float)
    assert isinstance(dados["longitude"], float)
    assert not isinstance(dados["latitude"], str)


def test_coordenadas_preservam_as_seis_casas_decimais(api, ponto_completo):
    """(11) A precisão do cadastro (6 casas, ~0,1 m) vai e volta intacta."""
    dados = api.get(f"/api/pontos-de-interesse/{ponto_completo.id}/").json()

    assert Decimal(str(dados["latitude"])) == ponto_completo.latitude
    assert Decimal(str(dados["longitude"])) == ponto_completo.longitude
    assert dados["latitude"] == -22.883712
    assert dados["longitude"] == -43.103456


# --- Filtros, ordenação, paginação, imagem ----------------------------------


def test_filtro_por_tipo(api):
    """(12) `tipo` filtra pelas choices do model; valor fora delas responde 400."""
    ponto("Casa Paul Singer", tipo=PontoDeInteresse.TipoPonto.ORGAO_ES)
    ponto("Loja da Rede", tipo=PontoDeInteresse.TipoPonto.LOJA_FISICA)
    ponto("Feira do Centro", tipo=PontoDeInteresse.TipoPonto.FEIRA_ARARIBOIA)

    base = "/api/pontos-de-interesse/?tipo="
    assert nomes(api.get(f"{base}orgao_es")) == ["Casa Paul Singer"]
    assert nomes(api.get(f"{base}loja_fisica")) == ["Loja da Rede"]
    assert nomes(api.get(f"{base}feira_arariboia")) == ["Feira do Centro"]
    assert api.get(f"{base}padaria").status_code == 400


def test_tipo_display_traz_o_rotulo_em_portugues(api, ponto_completo):
    """(13) O rótulo vem pronto, para o cliente não reimplementar a tradução.

    Reimplementá-la no frontend garantiria divergência no dia em que a equipe
    criar um tipo novo no Admin.
    """
    dados = api.get(f"/api/pontos-de-interesse/{ponto_completo.id}/").json()

    assert dados["tipo"] == "feira_arariboia"
    assert dados["tipo_display"] == ponto_completo.get_tipo_display()
    assert dados["tipo_display"] == "Feira do Circuito Arariboia"


def test_busca_q_encontra_por_nome_descricao_e_endereco(api, ponto_completo):
    """(14) `q` busca em `nome`, `descricao` e `endereco`, ignorando maiúsculas."""
    ponto(
        "Casa Paul Singer",
        descricao="Centro Público de Referência.",
        endereco="Rua Visconde de Sepetiba, Centro",
    )

    base = "/api/pontos-de-interesse/?q="
    assert api.get(f"{base}singer").json()["count"] == 1  # nome
    assert api.get(f"{base}referência").json()["count"] == 1  # descrição
    assert api.get(f"{base}sepetiba").json()["count"] == 1  # endereço
    assert api.get(f"{base}inexistente").json()["count"] == 0


def test_ordenacao_por_nome(api):
    """(15) Sem parâmetro ordena por `nome`; `ordering=-nome` inverte."""
    for nome in ("Zabumba", "Abelha", "Milho"):
        ponto(nome)

    assert nomes(api.get("/api/pontos-de-interesse/")) == ["Abelha", "Milho", "Zabumba"]
    assert nomes(api.get("/api/pontos-de-interesse/?ordering=-nome")) == [
        "Zabumba", "Milho", "Abelha",
    ]


def test_paginacao(api):
    """(15b) `page_size` pagina, o teto é 100 e `page=999` responde 404.

    O teto vale também para o mapa, que pede `?page_size=100`: não há exceção
    de "listagem sem paginação". No dia em que a ES de Niterói passar de 100
    pontos de referência, o cliente pagina como qualquer outro.
    """
    PontoDeInteresse.objects.bulk_create(
        PontoDeInteresse(
            nome=f"Ponto {i:03d}",
            tipo=PontoDeInteresse.TipoPonto.LOJA_FISICA,
            latitude=Decimal("-22.900000"),
            longitude=Decimal("-43.100000"),
        )
        for i in range(101)
    )

    primeira = api.get("/api/pontos-de-interesse/?page_size=1").json()
    assert len(primeira["results"]) == 1
    assert primeira["count"] == 101
    assert primeira["next"] is not None

    no_teto = api.get("/api/pontos-de-interesse/?page_size=500").json()
    assert no_teto["count"] == 101
    assert len(no_teto["results"]) == 100

    assert api.get("/api/pontos-de-interesse/?page=999").status_code == 404


def test_detalhe_por_id(api, ponto_completo):
    """(16) O detalhe responde 200 pelo id; id inexistente responde 404.

    Por id, e não por slug (emenda 10.2): o ponto é marcador de mapa, não
    página indexável.
    """
    resposta = api.get(f"/api/pontos-de-interesse/{ponto_completo.id}/")

    assert resposta.status_code == 200
    assert resposta.json()["id"] == ponto_completo.id
    assert resposta.json()["nome"] == "Feira da Praça Arariboia"

    assert api.get("/api/pontos-de-interesse/999999/").status_code == 404


def test_imagem_capa_ausente_vem_null_e_presente_vem_url(api):
    """(17) A capa é ausência legítima, não segredo: sai `null`, com a chave presente."""
    sem_capa = ponto("Sem capa")
    com_capa = ponto(
        "Com capa",
        imagem_capa=SimpleUploadedFile("capa.png", PNG_MINIMO, "image/png"),
    )

    resposta_sem = api.get(f"/api/pontos-de-interesse/{sem_capa.id}/").json()
    resposta_com = api.get(f"/api/pontos-de-interesse/{com_capa.id}/").json()

    assert resposta_sem["imagem_capa"] is None
    assert resposta_com["imagem_capa"].endswith(".png")
    # Absoluta, não relativa: é o valor que o mapa usa no popup do marcador.
    assert resposta_com["imagem_capa"].startswith(
        "http://testserver/media/pontos-de-interesse/"
    )


def test_listagem_nao_tem_n_mais_1(api, django_assert_num_queries, coletivo_ativo):
    """(18) A listagem faz um número CONSTANTE de queries, não uma por ponto.

    Aqui o `select_related` não é otimização opcional: a guarda do coletivo
    inativo lê `instance.coletivo.ativo` para cada ponto: sem ele, a própria
    guarda de privacidade criaria o N+1.
    """
    for indice in range(10):
        ponto(f"Ponto {indice:02d}", coletivo=coletivo_ativo)

    # 2 queries: o COUNT da paginação e a página, já com o JOIN do coletivo.
    with django_assert_num_queries(2):
        resposta = api.get("/api/pontos-de-interesse/?page_size=10")

    resultados = resposta.json()["results"]
    assert len(resultados) == 10
    assert resultados[0]["coletivo"]["slug"] == "sementes-do-vale"
