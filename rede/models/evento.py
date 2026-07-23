"""Evento e ImagemEvento — agenda pública da Economia Solidária."""
from django.db import models


class Evento(models.Model):
    """Agenda da ES divulgada na interface pública (feiras, encontros,
    formações), mantida pelo administrador. Inclui galeria de imagens de
    divulgação (ImagemEvento).
    """

    titulo = models.CharField("título", max_length=200)
    slug = models.SlugField("slug", max_length=220, unique=True, db_index=True)
    descricao = models.TextField("descrição", blank=True)
    data_inicio = models.DateTimeField("data de início")
    data_fim = models.DateTimeField("data de fim", null=True, blank=True)
    local = models.CharField("local", max_length=200, blank=True)
    bairro = models.CharField("bairro", max_length=120, blank=True)
    link = models.URLField("link", blank=True)
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "evento"
        verbose_name_plural = "eventos"
        ordering = ["-data_inicio"]

    def __str__(self):
        return self.titulo


class ImagemEvento(models.Model):
    """Imagem da galeria de um Evento (permite um slide ou apenas uma).

    São imagens PÚBLICAS (material de divulgação, não dado pessoal),
    armazenadas no Storage do Supabase sob o prefixo `eventos/`.
    """

    evento = models.ForeignKey(
        "rede.Evento", on_delete=models.CASCADE, related_name="imagens",
        verbose_name="evento",
    )
    imagem = models.ImageField("imagem", upload_to="eventos/")
    legenda = models.CharField("legenda", max_length=200, blank=True)
    ordem = models.PositiveIntegerField(
        "ordem", default=0, help_text="Controla a sequência do slide.",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "imagem de evento"
        verbose_name_plural = "imagens de evento"
        ordering = ["ordem", "id"]

    def __str__(self):
        return self.legenda or f"Imagem {self.pk} de {self.evento}"
