"""Seção da página "Saiba mais", editável pela equipe no Admin."""
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models

from rede.models.coletivo import validar_tamanho_da_foto


def caminho_da_imagem(instancia, nome_original):
    """Nome único no bucket: `saiba-mais/<uuid>.<ext>`.

    Mesmo motivo da foto do coletivo: com `AWS_S3_FILE_OVERWRITE` no padrão
    `True`, duas seções que enviassem `foto.jpg` gravariam a mesma chave.

    Fica no nível do módulo para a migration conseguir referenciá-la.
    """
    extensao = Path(nome_original).suffix.lower()
    return f"saiba-mais/{uuid.uuid4().hex}{extensao}"


class SecaoSaibaMais(models.Model):
    """Um bloco de conteúdo de um dos subgrupos do "Saiba mais".

    Conteúdo institucional e público: nunca dado pessoal. Contatos da Casa
    (telefone, e-mail, endereço, horário) não moram aqui — continuam no
    `casa.ts` do frontend até existir o model próprio deles.

    O texto é simples, sem HTML nem Markdown: o frontend o mostra com
    `whitespace-pre-line`, e linha em branco separa parágrafos.
    """

    class Subgrupo(models.TextChoices):
        # Os valores são os slugs das rotas do frontend (/saiba-mais/<valor>).
        CASA_AZUL = "casa-azul", "Casa Azul"
        ECONOMIA_SOLIDARIA = "economia-solidaria", "Economia Solidária"
        ITES_IFRJ = "ites-ifrj", "ITES/IFRJ"

    subgrupo = models.CharField(
        "subgrupo", max_length=30, choices=Subgrupo.choices, db_index=True,
    )
    titulo = models.CharField("título", max_length=200)
    slug = models.SlugField(
        "slug", max_length=220, unique=True,
        help_text="Identifica a seção na API (ex.: quem-somos).",
    )
    texto = models.TextField(
        "texto",
        help_text="Texto simples. Deixe uma linha em branco entre os parágrafos.",
    )

    # --- Imagem (pública) ---------------------------------------------------
    # Como a foto do coletivo: a equipe só envia com autorização de uso de
    # imagem das pessoas que aparecem nela.
    imagem = models.ImageField(
        "imagem", upload_to=caminho_da_imagem, null=True, blank=True,
        validators=[validar_tamanho_da_foto],
        help_text="Opcional. Até 5 MB.",
    )
    imagem_descricao = models.CharField(
        "descrição da imagem", max_length=200, blank=True,
        help_text="O que a imagem mostra. É o texto lido por quem usa leitor de tela.",
    )

    ordem = models.PositiveIntegerField(
        "ordem", default=0, help_text="Menor número aparece primeiro no subgrupo.",
    )
    # Nasce despublicada: a equipe escreve, revisa e só então publica.
    publicado = models.BooleanField(
        "publicado", default=False,
        help_text="Só seções publicadas aparecem no site.",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "seção do Saiba mais"
        verbose_name_plural = "seções do Saiba mais"
        # Os valores de `subgrupo` em ordem alfabética coincidem com a ordem
        # do menu (casa-azul, economia-solidaria, ites-ifrj). O `id` no fim
        # desempata seções com a mesma `ordem`. Sem unicidade em
        # (subgrupo, ordem): reordenar duas seções no Admin exigiria um valor
        # temporário para não colidir no meio da troca.
        ordering = ["subgrupo", "ordem", "id"]

    def __str__(self):
        return self.titulo

    def clean(self):
        super().clean()
        if self.imagem and not self.imagem_descricao.strip():
            raise ValidationError(
                {"imagem_descricao": "Descreva a imagem para quem usa leitor de tela."}
            )
