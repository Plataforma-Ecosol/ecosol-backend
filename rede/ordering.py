"""Ordenação da API pública.

Registrada globalmente em `config.settings.REST_FRAMEWORK`, no lugar do
`OrderingFilter` do DRF — pelo mesmo motivo da `PaginacaoPadrao`: o contrato de
listagem é do projeto inteiro, e as três entidades públicas não podem divergir.
"""
from rest_framework.filters import OrderingFilter


class OrdenacaoEstavel(OrderingFilter):
    """`OrderingFilter` que sempre termina a ordenação pela chave primária.

    **O problema.** Nenhum dos campos de ordenação do contrato público é único:
    dois eventos podem começar no mesmo instante (uma feira com três oficinas
    às 18h), dois pontos podem se chamar "Feira do Centro", dois coletivos
    podem repetir o nome. Um `ORDER BY data_inicio` sobre valores repetidos não
    define ordem alguma entre os empatados — o Postgres devolve na ordem que
    for mais barata naquela execução, e ela pode mudar entre uma consulta e a
    seguinte.

    **Por que isso quebra a paginação.** A paginação é `LIMIT`/`OFFSET`, ou
    seja, duas consultas independentes. Se os empatados vierem em ordem
    diferente na página 1 e na página 2, um registro que estava no fim da
    primeira reaparece no início da segunda — e outro, que devia estar ali,
    **some da listagem inteira**. Não há erro, não há log: o mapa simplesmente
    não desenha um marcador que existe no cadastro.

    **A correção.** Acrescentar `pk` como último critério. Ele é único por
    definição, então a ordem passa a ser total: os empatados ganham um
    desempate arbitrário, mas *estável* — o mesmo em toda consulta, que é o que
    a paginação exige.

    O desempate é acrescentado depois da validação do DRF, e não em
    `ordering_fields`: assim vale igualmente para a ordenação padrão da view e
    para a que o cliente pede em `?ordering=`, sem virar um campo que alguém
    possa passar na URL. `pk` continua fora do contrato público.
    """

    #: Nomes que já garantem unicidade — se um deles estiver na ordenação, a
    #: ordem já é total e acrescentar `pk` seria ruído no SQL.
    CHAVES_UNICAS = frozenset({"pk", "id"})

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if not ordering:
            # Sem ordenação nenhuma o DRF não chama `order_by`, e quem ordena é
            # o `Meta.ordering` do model. Não é o caso de nenhuma view pública
            # (as três declaram `ordering`), mas herdar o comportamento do DRF
            # aqui é mais previsível do que inventar uma ordem por conta.
            return ordering

        campos = list(ordering)
        if any(campo.lstrip("-") in self.CHAVES_UNICAS for campo in campos):
            return campos
        campos.append("pk")
        return campos
