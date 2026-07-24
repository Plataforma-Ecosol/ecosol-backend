"""Ponto de Interesse — a única entidade georreferenciada publicamente."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PontoDeInteresse(models.Model):
    """O que aparece no mapa público. Entidade SEPARADA do Coletivo e a única
    autorizada a ser georreferenciada publicamente. Cadastrada pelo
    administrador.

    Latitude/longitude vivem SÓ aqui — nunca no Coletivo. Aqui o endereço PODE
    ser público, pois é ponto de referência da ES, não a sede de um coletivo.
    """

    class TipoPonto(models.TextChoices):
        ORGAO_ES = "orgao_es", "Órgão da Economia Solidária"
        LOJA_FISICA = "loja_fisica", "Loja física"
        FEIRA_ARARIBOIA = "feira_arariboia", "Feira do Circuito Arariboia"

    nome = models.CharField("nome", max_length=200)
    tipo = models.CharField(
        "tipo", max_length=20, choices=TipoPonto.choices,
    )
    descricao = models.TextField("descrição", blank=True)
    latitude = models.DecimalField(
        "latitude", max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        "longitude", max_digits=9, decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    endereco = models.CharField(
        "endereço", max_length=255, blank=True,
        help_text="Exibição pública opcional (ponto de referência da ES).",
    )
    imagem_capa = models.ImageField(
        "imagem de capa", upload_to="pontos-de-interesse/",
        null=True, blank=True,
        help_text="Capa opcional exibida ao clicar no ponto.",
    )
    coletivo = models.ForeignKey(
        "rede.Coletivo", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pontos", verbose_name="coletivo",
        help_text="Opcional — quando um coletivo tem ponto físico próprio.",
    )
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "ponto de interesse"
        verbose_name_plural = "pontos de interesse"
        ordering = ["nome"]

    def __str__(self):
        return self.nome
