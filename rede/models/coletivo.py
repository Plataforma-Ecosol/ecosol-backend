"""Coletivo — o nó central da rede da Economia Solidária."""
from django.db import models, transaction


class Coletivo(models.Model):
    """Unidade central e única entidade exibida na listagem pública.

    Agrupa uma ou mais pessoas/empreendimentos. A visibilidade pública é
    controlada por `ativo`; os contatos só aparecem se a flag de consentimento
    correspondente estiver ligada (a poda é feita no serializer, fatia
    seguinte — aqui só existem campo + flag + defaults).

    Endereço completo, dados cadastrais e contatos sem consentimento são de
    uso exclusivo do back-office e NUNCA públicos. `bairro` é o único dado
    geográfico público (contexto, sem revelar a sede).
    """

    class Situacao(models.TextChoices):
        REGULAR = "regular", "Regular"
        EM_TRANSICAO = "em_transicao", "Em transição"
        ENCERRADO = "encerrado", "Encerrado"

    # --- Identificação pública ---------------------------------------------
    nome = models.CharField("nome", max_length=200)
    slug = models.SlugField(
        "slug", max_length=220, unique=True,
        help_text="Usado na URL de detalhe (ex.: sementes-do-vale).",
    )
    descricao = models.TextField("descrição", blank=True)
    bairro = models.CharField(
        "bairro", max_length=120, blank=True, db_index=True,
        help_text="Público — dá contexto geográfico sem revelar o endereço.",
    )
    site = models.URLField("site", blank=True)

    # --- Contatos (visibilidade condicional por consentimento) -------------
    telefone = models.CharField("telefone", max_length=40, blank=True)
    exibir_telefone_publicamente = models.BooleanField(
        "exibir telefone publicamente", default=False,
    )
    email = models.EmailField("e-mail", blank=True)
    exibir_email_publicamente = models.BooleanField(
        "exibir e-mail publicamente", default=False,
    )
    instagram = models.CharField("instagram", max_length=120, blank=True)
    exibir_instagram_publicamente = models.BooleanField(
        "exibir instagram publicamente", default=False,
    )

    # --- Dados cadastrais (uso administrativo — nunca públicos) -------------
    cnpj = models.CharField("CNPJ", max_length=18, blank=True)
    data_inicio = models.DateField("data de início", null=True, blank=True)
    responsavel_grupo = models.CharField(
        "responsável pelo grupo", max_length=200, blank=True,
    )
    motivo_criacao = models.TextField("motivo de criação", blank=True)
    renda_obtida = models.DecimalField(
        "renda obtida", max_digits=12, decimal_places=2, null=True, blank=True,
    )
    historico_editais = models.TextField("histórico de editais", blank=True)

    # --- Endereço completo (NUNCA público) ---------------------------------
    logradouro = models.CharField("logradouro", max_length=200, blank=True)
    numero = models.CharField("número", max_length=20, blank=True)
    complemento = models.CharField("complemento", max_length=120, blank=True)
    cep = models.CharField("CEP", max_length=9, blank=True)

    # --- Controle e classificação ------------------------------------------
    ativo = models.BooleanField(
        "ativo", default=True, db_index=True,
        help_text="Controla a visibilidade pública (a API lista só ativos).",
    )
    situacao = models.CharField(
        "situação", max_length=20, choices=Situacao.choices,
        default=Situacao.REGULAR,
        help_text="Rótulo cadastral informativo, independente de `ativo`.",
    )
    categorias = models.ManyToManyField(
        "rede.Categoria", related_name="coletivos", blank=True,
        verbose_name="categorias",
    )

    # --- Metadados ---------------------------------------------------------
    nome_entrevistador = models.CharField(
        "nome do entrevistador", max_length=200, blank=True,
    )
    observacoes = models.TextField("observações", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "coletivo"
        verbose_name_plural = "coletivos"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        """Salva o coletivo e registra o slug anterior quando ele muda.

        O slug é a identidade pública do coletivo — é o que vai no cartaz, no
        WhatsApp e no índice do buscador. Quem edita o slug no back-office não
        precisa saber que este histórico existe: a troca é registrada aqui, e a
        API responde 301 do endereço antigo para o novo.
        """
        slug_antigo = (
            Coletivo.objects.filter(pk=self.pk).values_list("slug", flat=True).first()
            if self.pk
            else None
        )
        with transaction.atomic():
            # O slug atual sempre vence o histórico: se este slug já foi de
            # alguém (inclusive deste mesmo coletivo, num vaivém a→b→a), a
            # entrada antiga sai para não haver dois donos do mesmo slug.
            ColetivoSlugAnterior.objects.filter(slug=self.slug).delete()
            super().save(*args, **kwargs)
            if slug_antigo and slug_antigo != self.slug:
                ColetivoSlugAnterior.objects.update_or_create(
                    slug=slug_antigo, defaults={"coletivo": self},
                )


class ColetivoSlugAnterior(models.Model):
    """Slug que um coletivo já usou — garante estabilidade dos links publicados.

    Um slug corrigido no back-office não pode transformar em 404 os endereços
    que já circulam. Com o histórico, a API responde 301 para a URL canônica, e
    o buscador consolida no endereço novo a autoridade do antigo.

    O histórico NÃO fura a regra de visibilidade: slug antigo de coletivo
    inativo continua respondendo 404 (a poda é feita na view).
    """

    coletivo = models.ForeignKey(
        "rede.Coletivo", on_delete=models.CASCADE, related_name="slugs_anteriores",
        verbose_name="coletivo",
    )
    slug = models.SlugField(
        "slug anterior", max_length=220, unique=True,
        help_text="Único — um slug jamais aponta para dois coletivos.",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "slug anterior de coletivo"
        verbose_name_plural = "slugs anteriores de coletivos"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.slug} → {self.coletivo.slug}"
