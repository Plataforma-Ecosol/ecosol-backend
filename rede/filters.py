"""Filtros da API pública.

A busca textual (`q`) não é filtro daqui: é o `SearchFilter` do DRF, com
`search_fields` declarados na view e `SEARCH_PARAM = "q"` em settings.
"""
from django_filters import rest_framework as filters

from rede.models import Coletivo


class ColetivoFilter(filters.FilterSet):
    """Filtros de listagem de coletivos (Seção 3.3 do PRD).

    `ativo` NÃO é declarado aqui, de propósito (emenda 10.2): é a chave de
    visibilidade pública, o mecanismo com que a equipe do Centro Público tira
    um coletivo do ar. Exposto como parâmetro, permitiria a qualquer pessoa
    listar exatamente os coletivos que a equipe decidiu não exibir. O queryset
    da view fixa `ativo=True`.
    """

    # `NumberFilter` é o que produz o 400 do contrato quando chega texto.
    categoria = filters.NumberFilter(
        field_name="categorias__id",
        label="ID da categoria",
    )
    # Valor público, nunca logradouro.
    bairro = filters.CharFilter(lookup_expr="iexact", label="Bairro")

    class Meta:
        model = Coletivo
        fields = ["categoria", "bairro"]
