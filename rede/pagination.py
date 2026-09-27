"""Paginação da API pública.

Registrada globalmente em `config.settings.REST_FRAMEWORK`, e não view a view:
o contrato de paginação é do projeto inteiro. Eventos e Pontos de Interesse
herdam o mesmo comportamento sem repetir código — e sem risco de divergirem.
"""
from rest_framework.pagination import PageNumberPagination


class PaginacaoPadrao(PageNumberPagination):
    """Envelope `count / next / previous / results`, com teto de 100 itens.

    O teto protege o banco de uma requisição que peça a base inteira de uma
    vez — é o principal item do requisito de listagem abaixo de 500 ms.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
