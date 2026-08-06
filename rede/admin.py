"""Área administrativa (Django Admin) — o back-office da equipe do Centro Público.

Esta é a Interface 2 do MVP (PRD Técnico 5.2): substitui a planilha de cadastro
por um formulário estruturado. É também o cofre do projeto — reúne todos os
dados pessoais e sensíveis —, então o desenho segue dois cuidados constantes:

* **Ergonomia**: campos organizados em blocos legíveis (`fieldsets`), na mesma
  ordem dos blocos comentados nos models.
* **Privacidade**: cada contato aparece colado à sua flag de consentimento, e
  nenhum atributo sensível de Pessoa entra em listagem ou filtro.

Tudo em português (requisito de Tecnologia Social). O Admin não altera o
esquema: registrar um model aqui nunca gera migration.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from rede.models import (
    Categoria,
    Coletivo,
    ColetivoSlugAnterior,
    Evento,
    ImagemEvento,
    Pessoa,
    PontoDeInteresse,
    Usuario,
)

# --- Identidade da área administrativa -------------------------------------
admin.site.site_header = "Plataforma Ecosol — Rede da Economia Solidária de Niterói"
admin.site.site_title = "Ecosol · Administração"
admin.site.index_title = "Administração"


# --- Usuários (equipe do Centro Público) -----------------------------------
@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """Contas com acesso ao back-office.

    Herda de `UserAdmin` — e não de `ModelAdmin` — de propósito: é o que
    preserva o formulário de senha com hash, os fieldsets de permissão e o
    "adicionar usuário" em duas etapas. Registrar um usuário customizado com um
    ModelAdmin comum gravaria a senha como texto puro.

    Não há autocadastro: as contas são criadas aqui, pela própria equipe
    (PRD Técnico 3 — papel único de Administrador no MVP).
    """


# --- Categorias / segmentos -------------------------------------------------
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    """Segmentos que classificam os coletivos (artesanato, alimentação…)."""

    list_display = ("nome", "slug", "num_coletivos")
    search_fields = ("nome",)
    prepopulated_fields = {"slug": ("nome",)}

    def get_queryset(self, request):
        """Conta os coletivos de cada categoria em uma única consulta.

        Sem o `annotate`, a coluna `num_coletivos` dispararia um `COUNT` por
        linha da listagem (N+1) e a tela ficaria lenta conforme o cadastro
        cresce.
        """
        return super().get_queryset(request).annotate(_num_coletivos=Count("coletivos"))

    @admin.display(description="coletivos", ordering="_num_coletivos")
    def num_coletivos(self, obj):
        """Quantos coletivos estão classificados nesta categoria."""
        return obj._num_coletivos


# --- Inlines do Coletivo (somente leitura) ----------------------------------
class PessoaInline(admin.TabularInline):
    """Quem compõe o coletivo — apenas para consulta.

    Pessoa tem ~25 campos, vários sensíveis. Editá-la aqui dentro geraria um
    formulário gigante e espalharia dado sensível pela tela institucional do
    coletivo. Este inline só responde "quem faz parte?" e leva ao registro
    completo, que é editado em PessoaAdmin.
    """

    model = Pessoa
    extra = 0
    can_delete = False
    fields = ("nome", "nome_social", "municipio", "abrir")
    readonly_fields = fields
    verbose_name_plural = "pessoas do coletivo (somente leitura — edite na tela de Pessoa)"

    def has_add_permission(self, request, obj=None):
        """Pessoa se cadastra na tela própria, nunca por dentro do Coletivo."""
        return False

    @admin.display(description="registro completo")
    def abrir(self, obj):
        """Link para a tela de edição da pessoa."""
        if not obj.pk:
            return "—"
        url = reverse("admin:rede_pessoa_change", args=[obj.pk])
        return format_html('<a href="{}">abrir ficha</a>', url)


class ColetivoSlugAnteriorInline(admin.TabularInline):
    """Endereços antigos que ainda redirecionam para este coletivo.

    O histórico é gerado pelo `save()` do model quando alguém edita o slug; o
    Admin apenas o exibe, para o administrador entender por que um endereço
    antigo continua funcionando. Não se cria nem se apaga slug antigo à mão —
    isso quebraria links já publicados.
    """

    model = ColetivoSlugAnterior
    extra = 0
    can_delete = False
    fields = ("slug", "criado_em")
    readonly_fields = fields
    verbose_name_plural = "endereços anteriores (gerados automaticamente ao trocar o slug)"

    def has_add_permission(self, request, obj=None):
        return False


# --- Coletivos --------------------------------------------------------------
@admin.register(Coletivo)
class ColetivoAdmin(admin.ModelAdmin):
    """Cadastro dos coletivos — o nó central da rede.

    É aqui que se operam as chaves de visibilidade pública. O serializer
    público apenas obedece: `ativo` decide se o coletivo existe para o público,
    e cada `exibir_*_publicamente` decide se aquele contato sai. Por isso cada
    contato aparece imediatamente acima da sua flag de consentimento, no mesmo
    bloco — nunca um longe do outro.
    """

    list_display = ("nome", "bairro", "situacao", "ativo", "num_pessoas")
    # `ativo` editável direto na listagem: tirar ou pôr um coletivo no ar é a
    # operação mais frequente da equipe e não deve exigir abrir o registro.
    list_editable = ("ativo",)
    list_filter = ("ativo", "situacao", "categorias")
    # Também é o que habilita o autocomplete de coletivo em Pessoa e Ponto.
    search_fields = ("nome", "descricao", "bairro", "cnpj")
    prepopulated_fields = {"slug": ("nome",)}
    filter_horizontal = ("categorias",)
    readonly_fields = ("criado_em", "atualizado_em")
    inlines = [PessoaInline, ColetivoSlugAnteriorInline]

    fieldsets = (
        (
            "Identificação pública",
            {
                "fields": ("nome", "slug", "descricao", "bairro", "site"),
                "description": (
                    "Editar o slug troca o endereço público do coletivo. O endereço "
                    "antigo continua funcionando: ele é registrado automaticamente e "
                    "passa a redirecionar para o novo."
                ),
            },
        ),
        (
            "Contatos (visibilidade por consentimento)",
            {
                "fields": (
                    "telefone",
                    "exibir_telefone_publicamente",
                    "email",
                    "exibir_email_publicamente",
                    "instagram",
                    "exibir_instagram_publicamente",
                ),
                "description": (
                    "Cada contato só aparece na interface pública se a caixa logo "
                    "abaixo dele estiver marcada. Sem consentimento registrado, "
                    "deixe desmarcada."
                ),
            },
        ),
        (
            "Dados cadastrais (uso administrativo — nunca públicos)",
            {
                "fields": (
                    "cnpj",
                    "data_inicio",
                    "responsavel_grupo",
                    "motivo_criacao",
                    "renda_obtida",
                    "historico_editais",
                ),
            },
        ),
        (
            "Endereço completo (nunca público)",
            {
                "fields": ("logradouro", "numero", "complemento", "cep"),
                "description": (
                    "Nenhum destes campos sai na interface pública — lá o único dado "
                    "geográfico é o bairro."
                ),
            },
        ),
        (
            "Controle e classificação",
            {
                "fields": ("ativo", "situacao", "categorias"),
                "description": (
                    "`ativo` e `situação` são independentes: um coletivo pode estar "
                    "'em transição' e continuar visível, ou 'regular' e fora do ar."
                ),
            },
        ),
        (
            "Metadados",
            {
                "fields": (
                    "nome_entrevistador",
                    "observacoes",
                    "criado_em",
                    "atualizado_em",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        """Conta as pessoas de cada coletivo em uma única consulta.

        `distinct=True` é obrigatório aqui: filtrar a listagem por categoria
        (M2M) faz o SQL duplicar linhas, e sem ele a contagem de pessoas sairia
        multiplicada pelo número de categorias do coletivo.
        """
        return (
            super()
            .get_queryset(request)
            .annotate(_num_pessoas=Count("pessoas", distinct=True))
        )

    @admin.display(description="pessoas", ordering="_num_pessoas")
    def num_pessoas(self, obj):
        """Quantas pessoas compõem este coletivo."""
        return obj._num_pessoas


# --- Pessoas ----------------------------------------------------------------
@admin.register(Pessoa)
class PessoaAdmin(admin.ModelAdmin):
    """Cadastro das pessoas que compõem os coletivos.

    Nenhum dado de Pessoa é exposto na interface pública, em nenhuma hipótese.
    Ainda assim a minimização vale aqui dentro: os atributos do bloco
    socioeconômico e de identidade NÃO entram em `list_display` nem em
    `list_filter`. Filtrar a lista de pessoas por cor/raça ou orientação sexual
    transformaria o back-office numa ferramenta de segmentação por atributo
    protegido — exatamente o que a LGPD e o propósito do projeto rejeitam.
    """

    list_display = ("__str__", "coletivo", "municipio")
    list_filter = ("coletivo", "estado")
    # Localizam o registro; nenhum atributo sensível é pesquisável.
    search_fields = ("nome", "nome_social", "cpf")
    # Não materializa todos os coletivos num <select> ao abrir o formulário.
    autocomplete_fields = ("coletivo",)
    # A coluna `coletivo` atravessa FK — sem isto seria uma consulta por linha.
    list_select_related = ("coletivo",)
    readonly_fields = ("criado_em", "atualizado_em")

    fieldsets = (
        ("Vínculo", {"fields": ("coletivo",)}),
        (
            "Identificação",
            {
                "fields": (
                    "nome",
                    "nome_social",
                    "data_nascimento",
                    "cpf",
                    "rg",
                    "rne_crnm",
                    "naturalidade",
                    "estado_civil",
                ),
            },
        ),
        (
            "Contato",
            {"fields": ("email", "instagram", "facebook", "site", "telefone")},
        ),
        (
            "Endereço",
            {"fields": ("cep", "logradouro", "bairro", "municipio", "estado")},
        ),
        ("Escolaridade", {"fields": ("escolaridade",)}),
        ("Empreendimento individual", {"fields": ("empreendimento_individual",)}),
        (
            "Bloco socioeconômico e de identidade — DADOS SENSÍVEIS (LGPD)",
            {
                "classes": ("collapse",),
                "description": (
                    "DADOS SENSÍVEIS. Preencha somente com informação declarada pela "
                    "própria pessoa e com finalidade definida. Estes campos existem "
                    "apenas no back-office: nunca aparecem na interface pública, nem "
                    "nas colunas ou filtros desta listagem."
                ),
                "fields": (
                    "cor_raca",
                    "sexo",
                    "identidade_genero",
                    "orientacao_sexual",
                    "pessoa_com_deficiencia",
                    "qual_deficiencia",
                    "renda_familiar",
                    "rede_protecao_social",
                    "participacao_programas_sociais",
                ),
            },
        ),
        ("Metadados", {"fields": ("criado_em", "atualizado_em")}),
    )


# --- Eventos ----------------------------------------------------------------
class ImagemEventoInline(admin.TabularInline):
    """Galeria de divulgação do evento.

    São imagens públicas (cartaz, foto de divulgação) — não dado pessoal. A
    miniatura evita o erro clássico de subir a imagem errada e só descobrir
    depois de publicada.
    """

    model = ImagemEvento
    extra = 1
    fields = ("imagem", "previa", "legenda", "ordem")
    readonly_fields = ("previa",)

    @admin.display(description="prévia")
    def previa(self, obj):
        """Miniatura da imagem já salva (vazio enquanto não há upload)."""
        if not obj.pk or not obj.imagem:
            return "—"
        return format_html('<img src="{}" style="height: 60px;" />', obj.imagem.url)


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    """Agenda pública da Economia Solidária (feiras, encontros, formações)."""

    list_display = ("titulo", "data_inicio", "data_fim", "ativo")
    list_filter = ("ativo",)
    date_hierarchy = "data_inicio"
    search_fields = ("titulo", "descricao", "local", "bairro")
    prepopulated_fields = {"slug": ("titulo",)}
    readonly_fields = ("criado_em", "atualizado_em")
    inlines = [ImagemEventoInline]

    fieldsets = (
        ("Identificação", {"fields": ("titulo", "slug", "descricao")}),
        ("Quando", {"fields": ("data_inicio", "data_fim")}),
        ("Onde", {"fields": ("local", "bairro")}),
        ("Divulgação", {"fields": ("link",)}),
        ("Controle", {"fields": ("ativo",)}),
        ("Metadados", {"fields": ("criado_em", "atualizado_em")}),
    )


# --- Pontos de interesse ----------------------------------------------------
@admin.register(PontoDeInteresse)
class PontoDeInteresseAdmin(admin.ModelAdmin):
    """O que aparece no mapa público.

    Única entidade georreferenciada publicamente — latitude/longitude vivem só
    aqui, nunca no Coletivo. Aqui o endereço PODE ser público, porque é ponto de
    referência da Economia Solidária, não a sede de um coletivo.
    """

    list_display = ("nome", "tipo", "coletivo", "ativo")
    list_filter = ("tipo", "ativo")
    search_fields = ("nome", "endereco")
    autocomplete_fields = ("coletivo",)
    list_select_related = ("coletivo",)
    readonly_fields = ("criado_em", "atualizado_em")

    fieldsets = (
        ("Identificação", {"fields": ("nome", "tipo", "descricao")}),
        (
            "Localização",
            {
                "fields": ("latitude", "longitude", "endereco"),
                "description": (
                    "Coordenadas em graus decimais (ex.: -22.883000, -43.103000). "
                    "Podem ser copiadas do OpenStreetMap ou de outro mapa."
                ),
            },
        ),
        ("Imagem", {"fields": ("imagem_capa",)}),
        (
            "Vínculo",
            {
                "fields": ("coletivo",),
                "description": (
                    "Opcional — preencha apenas quando o ponto for a sede física de "
                    "um coletivo já cadastrado."
                ),
            },
        ),
        ("Controle", {"fields": ("ativo",)}),
        ("Metadados", {"fields": ("criado_em", "atualizado_em")}),
    )
