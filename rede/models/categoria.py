"""Categoria / Segmento — eixo de classificação e busca dos coletivos."""
from django.db import models


class Categoria(models.Model):
    """Segmento que classifica coletivos (artesanato, alimentação, agroecologia,
    serviços…).

    É o principal eixo de busca/filtro público (na fatia de API). Relaciona-se
    com Coletivo por M2M.
    """

    nome = models.CharField("nome", max_length=120)
    slug = models.SlugField(
        "slug", max_length=140, unique=True,
        help_text="Identificador único, gerado a partir do nome.",
    )

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["nome"]

    def __str__(self):
        return self.nome
