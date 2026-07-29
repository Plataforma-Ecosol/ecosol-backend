"""Regressão de LGPD e contrato do endpoint público de coletivos (PRD Seção 8).

A primeira metade do arquivo é a **regressão de LGPD**: a prova executável de
que a promessa de privacidade do projeto vale em runtime, e não só na
modelagem. É bloqueante no CI — PR que a quebre não entra em `staging` nem em
`main`.

A segunda metade cobre o contrato da API (Seção 3) e o desempenho (anti-N+1).
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from rede.models import Categoria, Coletivo, Pessoa

pytestmark = pytest.mark.django_db

#: Conjunto exato de chaves da resposta pública de um coletivo, sem nenhum
#: contato consentido (Seção 3.4 do PRD).
CHAVES_SEM_CONTATOS = {
    "id",
    "nome",
    "slug",
    "descricao",
    "bairro",
    "site",
    "categorias",
    "criado_em",
    "atualizado_em",
}
CHAVES_DE_CONTATO = {"telefone", "email", "instagram"}


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def coletivo_completo():
    """Coletivo com TODOS os campos sensíveis preenchidos e nenhum consentimento.

    Preencher os campos sensíveis é o ponto: um teste com o cadastro vazio
    passaria mesmo se o serializer os expusesse.
    """
    return Coletivo.objects.create(
        nome="Sementes do Vale",
        slug="sementes-do-vale",
        descricao="Agroecologia urbana no Fonseca.",
        bairro="Fonseca",
        site="https://sementesdovale.org",
        # Contatos preenchidos, mas sem consentimento (defaults em False).
        telefone="(21) 99999-0000",
        email="contato@sementesdovale.org",
        instagram="@sementesdovale",
        # Dados cadastrais — nunca públicos.
        cnpj="12.345.678/0001-90",
        data_inicio="2020-03-15",
        responsavel_grupo="Maria da Silva",
        motivo_criacao="Geração de renda a partir da agroecologia.",
        renda_obtida=Decimal("3500.00"),
        historico_editais="Edital SENAES 2021.",
        # Endereço — nunca público.
        logradouro="Rua das Palmeiras",
        numero="42",
        complemento="fundos",
        cep="24130-000",
        # Controle e metadados — nunca públicos.
        situacao=Coletivo.Situacao.EM_TRANSICAO,
        nome_entrevistador="João Entrevistador",
        observacoes="Anotação interna da equipe.",
    )


# --- Regressão de LGPD ------------------------------------------------------


def test_contatos_sem_consentimento_sao_omitidos(api, coletivo_completo):
    """(1) Sem consentimento, as chaves de contato NÃO EXISTEM na resposta.

    A asserção é `not in`, nunca `is None`: devolver `null` já comunicaria
    "existe um dado aqui, mas foi escondido".
    """
    dados = api.get(f"/api/coletivos/{coletivo_completo.slug}/").json()

    assert "telefone" not in dados
    assert "email" not in dados
    assert "instagram" not in dados


def test_contatos_com_consentimento_aparecem(api, coletivo_completo):
    """(2) Com as três flags ligadas, os três contatos aparecem com o valor certo."""
    Coletivo.objects.filter(pk=coletivo_completo.pk).update(
        exibir_telefone_publicamente=True,
        exibir_email_publicamente=True,
        exibir_instagram_publicamente=True,
    )

    dados = api.get(f"/api/coletivos/{coletivo_completo.slug}/").json()

    assert dados["telefone"] == "(21) 99999-0000"
    assert dados["email"] == "contato@sementesdovale.org"
    assert dados["instagram"] == "@sementesdovale"


def test_consentimento_e_por_campo(api, coletivo_completo):
    """(3) Consentir o e-mail não libera telefone nem instagram."""
    Coletivo.objects.filter(pk=coletivo_completo.pk).update(
        exibir_email_publicamente=True,
    )

    dados = api.get(f"/api/coletivos/{coletivo_completo.slug}/").json()

    assert dados["email"] == "contato@sementesdovale.org"
    assert "telefone" not in dados
    assert "instagram" not in dados


def test_resposta_tem_exatamente_as_chaves_do_contrato(api, coletivo_completo):
    """(4) O conjunto de chaves da resposta é EXATAMENTE o do contrato.

    Este é o teste mais importante do arquivo, e o único que é lista branca.
    Os demais são listas negras: pegam o vazamento que alguém previu. Comparar
    o conjunto inteiro de chaves pega **o campo que ninguém previu**, incluído
    por acidente daqui a seis meses — inclusive um campo que ainda não existe
    no model.

    Se este teste quebrar depois de alguém mexer no serializer, a pergunta é
    "esse campo pode mesmo ser público?", e não "como afrouxo a asserção?".
    NÃO troque a comparação de conjunto por uma verificação de alguns campos.
    """
    detalhe = api.get(f"/api/coletivos/{coletivo_completo.slug}/").json()
    assert set(detalhe.keys()) == CHAVES_SEM_CONTATOS

    # Mesma exigência na listagem, que é a porta mais visitada.
    item_da_lista = api.get("/api/coletivos/").json()["results"][0]
    assert set(item_da_lista.keys()) == CHAVES_SEM_CONTATOS

    # Com consentimento total, o conjunto cresce exatamente pelos três contatos.
    Coletivo.objects.filter(pk=coletivo_completo.pk).update(
        exibir_telefone_publicamente=True,
        exibir_email_publicamente=True,
        exibir_instagram_publicamente=True,
    )
    com_contatos = api.get(f"/api/coletivos/{coletivo_completo.slug}/").json()
    assert set(com_contatos.keys()) == CHAVES_SEM_CONTATOS | CHAVES_DE_CONTATO


def test_endereco_e_dados_cadastrais_nunca_aparecem(api, coletivo_completo):
    """(5) Endereço, dados cadastrais e metadados internos não saem — em lista nem detalhe."""
    proibidos = [
        "logradouro",
        "numero",
        "complemento",
        "cep",
        "cnpj",
        "data_inicio",
        "responsavel_grupo",
        "motivo_criacao",
        "renda_obtida",
        "historico_editais",
        "ativo",
        "situacao",
        "nome_entrevistador",
        "observacoes",
    ]

    detalhe = api.get(f"/api/coletivos/{coletivo_completo.slug}/").json()
    item_da_lista = api.get("/api/coletivos/").json()["results"][0]

    for campo in proibidos:
        assert campo not in detalhe, f"{campo} vazou no detalhe"
        assert campo not in item_da_lista, f"{campo} vazou na listagem"

    # Os valores também não podem aparecer por outro nome ou aninhados.
    resposta = api.get(f"/api/coletivos/{coletivo_completo.slug}/")
    corpo = resposta.content.decode()
    for valor in ("Rua das Palmeiras", "24130-000", "12.345.678/0001-90",
                  "Anotação interna da equipe.", "João Entrevistador"):
        assert valor not in corpo, f"{valor!r} vazou no corpo da resposta"


def test_nenhum_dado_de_pessoa_aparece(api, coletivo_completo):
    """(6) Pessoa não sai por nenhum caminho — nem nome, nem CPF, nem contagem."""
    Pessoa.objects.create(
        coletivo=coletivo_completo,
        nome="Joana Aparecida dos Santos",
        cpf="123.456.789-00",
        email="joana@pessoal.example",
    )

    detalhe = api.get(f"/api/coletivos/{coletivo_completo.slug}/")
    listagem = api.get("/api/coletivos/")

    for resposta in (detalhe, listagem):
        corpo = resposta.content.decode()
        assert "Joana Aparecida dos Santos" not in corpo
        assert "123.456.789-00" not in corpo
        assert "joana@pessoal.example" not in corpo
        # Nem a relação, nem um agregado dela.
        assert "pessoas" not in corpo


def test_flags_de_consentimento_nao_sao_expostas(api, coletivo_completo):
    """(7) As próprias flags de consentimento são dado interno e não saem."""
    Coletivo.objects.filter(pk=coletivo_completo.pk).update(
        exibir_telefone_publicamente=True,
        exibir_email_publicamente=True,
        exibir_instagram_publicamente=True,
    )

    detalhe = api.get(f"/api/coletivos/{coletivo_completo.slug}/").json()
    item_da_lista = api.get("/api/coletivos/").json()["results"][0]

    for flag in (
        "exibir_telefone_publicamente",
        "exibir_email_publicamente",
        "exibir_instagram_publicamente",
    ):
        assert flag not in detalhe
        assert flag not in item_da_lista


# --- Contrato e comportamento -----------------------------------------------


def test_listagem_responde_200_com_envelope_de_paginacao(api, coletivo_completo):
    """(8) A listagem usa o envelope `count / next / previous / results` do DRF."""
    resposta = api.get("/api/coletivos/")

    assert resposta.status_code == 200
    assert set(resposta.json().keys()) == {"count", "next", "previous", "results"}
    assert resposta.json()["count"] == 1


def test_coletivo_inativo_nao_aparece_e_seu_detalhe_da_404(api, coletivo_completo):
    """(9) `ativo=False` some da listagem e o detalhe responde 404.

    `ativo` é o mecanismo com que a equipe do Centro Público tira um coletivo
    do ar: precisa tirar mesmo, e não só esconder da lista.
    """
    oculto = Coletivo.objects.create(nome="Fora do Ar", slug="fora-do-ar", ativo=False)

    slugs = [item["slug"] for item in api.get("/api/coletivos/").json()["results"]]
    assert oculto.slug not in slugs
    assert api.get(f"/api/coletivos/{oculto.slug}/").status_code == 404


def test_busca_q_encontra_por_nome_e_descricao_ignorando_maiusculas(api, coletivo_completo):
    """(10) `q` busca em `nome` e `descricao`, sem diferenciar maiúsculas."""
    Coletivo.objects.create(nome="Ateliê Costura", slug="atelie", descricao="Bordado")

    assert api.get("/api/coletivos/?q=SEMENTES").json()["count"] == 1
    assert api.get("/api/coletivos/?q=agroecologia").json()["count"] == 1  # descrição
    assert api.get("/api/coletivos/?q=inexistente").json()["count"] == 0


def test_filtro_por_categoria(api, coletivo_completo):
    """(11) `categoria=<id>` filtra pelo M2M; `categoria=texto` responde 400."""
    agroecologia = Categoria.objects.create(nome="Agroecologia", slug="agroecologia")
    artesanato = Categoria.objects.create(nome="Artesanato", slug="artesanato")
    coletivo_completo.categorias.add(agroecologia)
    Coletivo.objects.create(nome="Ateliê Costura", slug="atelie").categorias.add(artesanato)

    assert api.get(f"/api/coletivos/?categoria={agroecologia.id}").json()["count"] == 1
    assert api.get(f"/api/coletivos/?categoria={artesanato.id}").json()["count"] == 1
    assert api.get("/api/coletivos/?categoria=texto").status_code == 400


def test_filtro_por_bairro_ignora_maiusculas(api, coletivo_completo):
    """(12) `bairro` filtra por igualdade, sem diferenciar maiúsculas."""
    Coletivo.objects.create(nome="Grupo Icaraí", slug="grupo-icarai", bairro="Icaraí")

    assert api.get("/api/coletivos/?bairro=fonseca").json()["count"] == 1
    assert api.get("/api/coletivos/?bairro=FONSECA").json()["count"] == 1
    assert api.get("/api/coletivos/?bairro=Icaraí").json()["count"] == 1
    assert api.get("/api/coletivos/?bairro=Centro").json()["count"] == 0


def test_ordenacao(api):
    """(13) Sem parâmetro ordena por `nome`; `ordering=-nome` inverte."""
    for nome, slug in (("Zabumba", "zabumba"), ("Abelha", "abelha"), ("Milho", "milho")):
        Coletivo.objects.create(nome=nome, slug=slug)

    def nomes(url):
        return [item["nome"] for item in api.get(url).json()["results"]]

    assert nomes("/api/coletivos/") == ["Abelha", "Milho", "Zabumba"]
    assert nomes("/api/coletivos/?ordering=-nome") == ["Zabumba", "Milho", "Abelha"]
    assert nomes("/api/coletivos/?ordering=nome") == ["Abelha", "Milho", "Zabumba"]


def test_paginacao(api):
    """(14) `page_size=1` pagina; `page_size=500` é limitado a 100; `page=999` dá 404."""
    for indice in range(3):
        Coletivo.objects.create(nome=f"Coletivo {indice}", slug=f"coletivo-{indice}")

    primeira = api.get("/api/coletivos/?page_size=1").json()
    assert len(primeira["results"]) == 1
    assert primeira["count"] == 3
    assert primeira["next"] is not None

    # O teto de 100 vale mesmo com pedido maior — sem devolver erro.
    sem_teto = api.get("/api/coletivos/?page_size=500")
    assert sem_teto.status_code == 200
    assert len(sem_teto.json()["results"]) == 3  # menos que o teto, todos cabem

    assert api.get("/api/coletivos/?page=999").status_code == 404


def test_teto_de_page_size_e_100(api):
    """(14b) Com mais de 100 coletivos, `page_size=500` devolve no máximo 100."""
    Coletivo.objects.bulk_create(
        Coletivo(nome=f"Coletivo {i:03d}", slug=f"coletivo-{i:03d}") for i in range(101)
    )

    resposta = api.get("/api/coletivos/?page_size=500").json()

    assert resposta["count"] == 101
    assert len(resposta["results"]) == 100


def test_detalhe_por_slug(api, coletivo_completo):
    """(15) O detalhe responde 200 e devolve o slug pedido."""
    resposta = api.get(f"/api/coletivos/{coletivo_completo.slug}/")

    assert resposta.status_code == 200
    assert resposta.json()["slug"] == coletivo_completo.slug
    assert resposta.json()["nome"] == "Sementes do Vale"


def test_listagem_nao_tem_n_mais_1(api, django_assert_num_queries):
    """(16) A listagem faz um número CONSTANTE de queries, não uma por coletivo.

    É este teste que transforma "sem N+1" de promessa em garantia: sem ele, o
    `prefetch_related` some no primeiro refactor e ninguém percebe até a
    listagem ficar lenta em produção.
    """
    categorias = [
        Categoria.objects.create(nome=f"Categoria {i}", slug=f"categoria-{i}")
        for i in range(3)
    ]
    for indice in range(10):
        coletivo = Coletivo.objects.create(
            nome=f"Coletivo {indice:02d}", slug=f"coletivo-{indice:02d}",
        )
        coletivo.categorias.add(*categorias)

    # 2 queries: o COUNT da paginação e a página; + 1 do prefetch de categorias.
    with django_assert_num_queries(3):
        resposta = api.get("/api/coletivos/?page_size=10")

    assert len(resposta.json()["results"]) == 10
    assert len(resposta.json()["results"][0]["categorias"]) == 3
