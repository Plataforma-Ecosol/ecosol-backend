"""Coletivo — o nó central da rede da Economia Solidária."""
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models, transaction

#: Limite da foto do coletivo. Protege o espaço do bucket, e não a tela: o
#: `next/image` reduz a foto na hora de mostrar.
TAMANHO_MAXIMO_DA_FOTO = 5 * 1024 * 1024


def caminho_da_foto(instancia, nome_original):
    """Nome único no bucket: `coletivos/<uuid>.<ext>`.

    O nome original é descartado de propósito. Com `AWS_S3_FILE_OVERWRITE` no
    padrão `True`, dois coletivos que enviassem `foto.jpg` gravariam a mesma
    chave, e o primeiro passaria a mostrar a foto do segundo, sem erro nenhum.
    O nome novo a cada envio também resolve o cache: trocou a foto, mudou a URL.

    Fica no nível do módulo para a migration conseguir referenciá-la.
    """
    extensao = Path(nome_original).suffix.lower()
    return f"coletivos/{uuid.uuid4().hex}{extensao}"


def validar_tamanho_da_foto(arquivo):
    """Recusa foto acima de 5 MB, dizendo o tamanho do arquivo enviado."""
    if arquivo.size > TAMANHO_MAXIMO_DA_FOTO:
        megabytes = f"{arquivo.size / (1024 * 1024):.1f}".replace(".", ",")
        raise ValidationError(
            f"A foto tem {megabytes} MB. O limite é 5 MB.",
            code="foto_grande_demais",
        )


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

    # --- Foto (pública) -----------------------------------------------------
    # Pública sem flag por campo: a equipe só envia a foto com autorização de
    # uso de imagem das pessoas que aparecem nela.
    foto = models.ImageField(
        "foto", upload_to=caminho_da_foto, null=True, blank=True,
        validators=[validar_tamanho_da_foto],
        help_text="Aparece no topo do cartão do coletivo. Até 5 MB.",
    )
    foto_descricao = models.CharField(
        "descrição da foto", max_length=200, blank=True,
        help_text="O que a foto mostra. É o texto lido por quem usa leitor de tela.",
    )

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
