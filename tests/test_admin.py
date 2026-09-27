"""Testes da área administrativa (PRD Django Admin, Seção 8).

Duas famílias de teste:

* **Fumaça** — abrir listagem, formulário de adição e formulário de edição de
  cada model registrado. Um `fieldsets` ou `list_display` que cite um campo
  inexistente só estoura quando a página é renderizada, nunca no import; abrir
  as três telas é a rede que segura isso.
* **Guarda de LGPD** — asserção de que nenhum atributo sensível de Pessoa virou
  coluna ou filtro de listagem. É o irmão do teste de regressão do serializer.
"""
from decimal import Decimal

import pytest
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse

from rede.models import (
    Categoria,
    Coletivo,
    Evento,
    Pessoa,
    PontoDeInteresse,
    Usuario,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_logado(client):
    """Cliente autenticado como administrador da equipe do Centro Público."""
    usuario = get_user_model().objects.create_superuser(
        username="coordenacao",
        email="coordenacao@exemplo.org",
        password="senha-de-teste-123",
    )
    client.force_login(usuario)
    return client


@pytest.fixture
def registros():
    """Um exemplar de cada entidade, para os formulários de edição."""
    categoria = Categoria.objects.create(nome="Agroecologia", slug="agroecologia")
    coletivo = Coletivo.objects.create(
        nome="Horta Comunitária", slug="horta-comunitaria", bairro="Fonseca"
    )
    coletivo.categorias.add(categoria)
    return {
        "categoria": categoria,
        "coletivo": coletivo,
        "pessoa": Pessoa.objects.create(
            nome="Maria da Silva", coletivo=coletivo, municipio="Niterói"
        ),
        "evento": Evento.objects.create(
            titulo="Feira de Verão",
            slug="feira-verao",
            data_inicio="2026-01-10T09:00:00Z",
        ),
        "pontodeinteresse": PontoDeInteresse.objects.create(
            nome="Feira do Arariboia",
            tipo=PontoDeInteresse.TipoPonto.FEIRA_ARARIBOIA,
            latitude=Decimal("-22.883000"),
            longitude=Decimal("-43.103000"),
        ),
        "usuario": get_user_model().objects.create_user(
            username="voluntaria", password="outra-senha-123"
        ),
    }


# --- 8.1. Fumaça: as telas abrem -------------------------------------------
MODELS_REGISTRADOS = [
    model
    for model in django_admin.site._registry
    if model._meta.app_label == "rede"
]


@pytest.mark.parametrize(
    "model", MODELS_REGISTRADOS, ids=lambda m: m._meta.model_name
)
def test_changelist_abre(admin_logado, model):
    """(1) A listagem de cada model registrado responde 200."""
    url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
    assert admin_logado.get(url).status_code == 200


@pytest.mark.parametrize(
    "model", MODELS_REGISTRADOS, ids=lambda m: m._meta.model_name
)
def test_formulario_de_adicao_abre(admin_logado, model):
    """(2) O formulário de adição de cada model registrado responde 200."""
    url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_add")
    assert admin_logado.get(url).status_code == 200


@pytest.mark.parametrize(
    "model", MODELS_REGISTRADOS, ids=lambda m: m._meta.model_name
)
def test_formulario_de_edicao_abre(admin_logado, registros, model):
    """(3) O formulário de edição de um objeto existente responde 200.

    Deriva a lista do próprio registro do Admin, como os dois testes acima: um
    model registrado numa fatia futura passa a ser coberto sozinho. Uma lista
    fixa de nomes continuaria verde enquanto deixava o model novo sem teste.
    """
    nome_model = model._meta.model_name
    obj = registros[nome_model]
    url = reverse(f"admin:rede_{nome_model}_change", args=[obj.pk])
    assert admin_logado.get(url).status_code == 200


def test_admin_exige_login(client):
    """(4) Anônimo em /admin/ é redirecionado para o login — o cofre é fechado."""
    resposta = client.get(reverse("admin:index"))
    assert resposta.status_code == 302
    assert "/admin/login/" in resposta["Location"]


def test_usuario_registrado_com_useradmin(admin_logado):
    """(5) `Usuario` usa a UserAdmin do Django, preservando o hash da senha.

    Registrar um usuário customizado com um ModelAdmin comum gravaria a senha
    como texto puro — é o erro mais fácil de cometer nesta fatia.
    """
    assert isinstance(django_admin.site._registry[Usuario], UserAdmin)
    url = reverse("admin:rede_usuario_add")
    assert admin_logado.get(url).status_code == 200


# --- 8.2. Guarda de LGPD ----------------------------------------------------
CAMPOS_SENSIVEIS = {
    "cor_raca",
    "sexo",
    "identidade_genero",
    "orientacao_sexual",
    "pessoa_com_deficiencia",
    "qual_deficiencia",
    "renda_familiar",
    "rede_protecao_social",
    "participacao_programas_sociais",
}


def test_pessoa_nao_filtra_nem_lista_por_campo_sensivel():
    """(6) Nenhum atributo sensível de Pessoa é coluna, filtro ou busca.

    NÃO afrouxe este teste. Filtrar a lista de pessoas por cor/raça, identidade
    de gênero ou orientação sexual transformaria o back-office numa ferramenta
    de segmentação por atributo protegido — exatamente o que a LGPD e o
    propósito do projeto rejeitam. Estes dados existem para atender a pessoa,
    não para recortá-la.

    Os campos continuam editáveis na ficha, em bloco explicitamente rotulado
    como sensível; o que se proíbe aqui é a listagem em massa.
    """
    pessoa_admin = django_admin.site._registry[Pessoa]

    assert not CAMPOS_SENSIVEIS & set(pessoa_admin.list_display)
    assert not CAMPOS_SENSIVEIS & set(pessoa_admin.list_filter)
    assert not CAMPOS_SENSIVEIS & set(pessoa_admin.search_fields)


def test_pessoa_tem_bloco_sensivel_rotulado():
    """(6b) O bloco socioeconômico é rotulado, para quem cadastra saber o peso."""
    pessoa_admin = django_admin.site._registry[Pessoa]
    titulos = [titulo for titulo, _ in pessoa_admin.fieldsets]
    assert any("SENSÍVEIS" in (titulo or "") for titulo in titulos)


# --- 8.3. Integração com a visibilidade -------------------------------------
def test_editar_slug_pelo_admin_gera_historico(admin_logado, registros):
    """(7) Trocar o slug pelo formulário do Admin registra o endereço anterior.

    O comportamento já é testado em nível de model; aqui se garante que o
    caminho real do administrador aciona o `save()` e não o contorna.
    """
    coletivo = registros["coletivo"]
    dados = {
        "nome": coletivo.nome,
        "slug": "horta-comunitaria-do-fonseca",
        "descricao": "",
        "bairro": coletivo.bairro,
        "site": "",
        "telefone": "",
        "email": "",
        "instagram": "",
        "cnpj": "",
        "data_inicio": "",
        "responsavel_grupo": "",
        "motivo_criacao": "",
        "renda_obtida": "",
        "historico_editais": "",
        "logradouro": "",
        "numero": "",
        "complemento": "",
        "cep": "",
        "ativo": "on",
        "situacao": Coletivo.Situacao.REGULAR,
        "categorias": list(coletivo.categorias.values_list("pk", flat=True)),
        "nome_entrevistador": "",
        "observacoes": "",
        # Formsets dos inlines somente leitura.
        "pessoas-TOTAL_FORMS": "0",
        "pessoas-INITIAL_FORMS": "0",
        "slugs_anteriores-TOTAL_FORMS": "0",
        "slugs_anteriores-INITIAL_FORMS": "0",
    }
    url = reverse("admin:rede_coletivo_change", args=[coletivo.pk])
    resposta = admin_logado.post(url, dados)

    assert resposta.status_code == 302  # salvou e redirecionou para a listagem
    coletivo.refresh_from_db()
    assert coletivo.slug == "horta-comunitaria-do-fonseca"
    assert list(coletivo.slugs_anteriores.values_list("slug", flat=True)) == [
        "horta-comunitaria"
    ]


def test_ativo_alternado_pelo_formset_da_listagem(admin_logado, registros):
    """(7b) Ligar e desligar `ativo` direto na listagem (`list_editable`) grava.

    Tirar um coletivo do ar é a operação mais frequente da equipe e mexe na
    chave de visibilidade pública mais crítica do projeto. O formset da
    changelist é um caminho de código distinto do formulário de edição
    individual — sem este teste, uma regressão nele passaria despercebida.
    """
    coletivo = registros["coletivo"]
    url = reverse("admin:rede_coletivo_changelist")
    formset = {
        "_save": "Salvar",
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "1",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-id": str(coletivo.pk),
    }

    # Caixa ausente do POST = desmarcada: tira o coletivo do ar.
    assert coletivo.ativo is True
    assert admin_logado.post(url, formset).status_code == 302
    coletivo.refresh_from_db()
    assert coletivo.ativo is False

    # E de volta ao ar, com a caixa marcada.
    assert admin_logado.post(url, {**formset, "form-0-ativo": "on"}).status_code == 302
    coletivo.refresh_from_db()
    assert coletivo.ativo is True


def test_contagem_de_pessoas_nao_infla_com_filtro_de_categoria(
    admin_logado, registros
):
    """(8) A coluna `pessoas` não é multiplicada pelo join do filtro de categoria.

    A contagem sai de `annotate(Count("pessoas", distinct=True))`. Sem o
    `distinct`, o join do filtro de categoria multiplica as linhas: um coletivo
    em 2 categorias com 2 pessoas produz 4 linhas e a coluna mostraria 4.

    O cenário precisa ser exatamente este — **duas** categorias casando com o
    filtro e **duas** pessoas. Filtrar por uma única categoria (`__exact`) não
    duplica nada e faria o teste passar com ou sem `distinct`, dando falsa
    confiança de que a contagem está protegida.
    """
    coletivo = registros["coletivo"]
    segunda_categoria = Categoria.objects.create(nome="Alimentação", slug="alim")
    coletivo.categorias.add(segunda_categoria)
    Pessoa.objects.create(nome="João Pereira", coletivo=coletivo)

    assert coletivo.categorias.count() == 2
    assert coletivo.pessoas.count() == 2

    url = reverse("admin:rede_coletivo_changelist")
    resposta = admin_logado.get(
        url,
        {
            "categorias__id__in": (
                f"{registros['categoria'].pk},{segunda_categoria.pk}"
            )
        },
    )
    linha = resposta.context["cl"].result_list.get(pk=coletivo.pk)

    # Sem `distinct=True` este número seria 4 (2 categorias × 2 pessoas).
    assert linha._num_pessoas == 2
