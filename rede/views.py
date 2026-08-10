"""Views da API pública.

Somente leitura. A API pública expõe apenas o que é público — não há nenhuma
rota de escrita neste projeto, por decisão de arquitetura: o cadastro vive no
Django Admin, atrás de autenticação.
"""
from django.http import HttpResponsePermanentRedirect
from rest_framework.permissions import AllowAny
from rest_framework.reverse import reverse
from rest_framework.viewsets import ReadOnlyModelViewSet

from rede.filters import ColetivoFilter, EventoFilter, PontoDeInteresseFilter
from rede.models import Coletivo, ColetivoSlugAnterior, Evento, PontoDeInteresse
from rede.serializers import (
    ColetivoSerializer,
    EventoSerializer,
    PontoDeInteresseSerializer,
)


class ColetivoViewSet(ReadOnlyModelViewSet):
    """Lista e detalhe de coletivos ativos.

    Este é o primeiro endpoint público do projeto e serve de modelo para os
    demais (Eventos e Pontos de Interesse): serializer explícito, omissão por
    consentimento, paginação, filtros e ausência de N+1.
    """

    # Explícito, mesmo com o padrão global já permitindo leitura: um endpoint
    # público deve *declarar* que é público, para quem ler o código depois.
    permission_classes = [AllowAny]

    # O slug é a identidade pública do coletivo, e casa com a URL do frontend.
    lookup_field = "slug"

    # `ativo=True` fixo (emenda 10.2) — o inativo não existe para o público.
    # `prefetch_related` evita o N+1 das categorias na listagem.
    queryset = Coletivo.objects.filter(ativo=True).prefetch_related("categorias")
    serializer_class = ColetivoSerializer

    filterset_class = ColetivoFilter
    search_fields = ["nome", "descricao"]
    ordering_fields = ["nome", "criado_em"]
    ordering = ["nome"]

    def retrieve(self, request, *args, **kwargs):
        """Detalhe por slug, com 301 quando o slug pedido é um slug antigo.

        O histórico é consultado ANTES de deixar o DRF levantar o 404: é o que
        mantém de pé os links já publicados. Ele não fura, porém, a regra de
        visibilidade — slug antigo de coletivo inativo continua respondendo
        404, como se nunca tivesse existido.
        """
        slug = kwargs.get(self.lookup_field)
        if not self.get_queryset().filter(slug=slug).exists():
            redirecionamento = self._redirecionar_slug_antigo(request, slug)
            if redirecionamento is not None:
                return redirecionamento
        return super().retrieve(request, *args, **kwargs)

    def _redirecionar_slug_antigo(self, request, slug):
        """Devolve o 301 para a URL canônica, ou `None` se não houver histórico.

        O 301 (e não o 302) é o que fecha o ciclo de SEO: o buscador consolida
        no endereço novo a autoridade do antigo, em vez de indexar duplicata.
        """
        historico = (
            ColetivoSlugAnterior.objects.select_related("coletivo")
            .filter(slug=slug, coletivo__ativo=True)
            .first()
        )
        if historico is None:
            return None
        url_canonica = reverse(
            "coletivo-detail",
            kwargs={self.lookup_field: historico.coletivo.slug},
            request=request,
        )
        return HttpResponsePermanentRedirect(url_canonica)


class EventoViewSet(ReadOnlyModelViewSet):
    """Lista e detalhe de eventos ativos — a agenda pública da rede.

    Segue o padrão do `ColetivoViewSet`, com uma diferença deliberada: não há
    `retrieve()` sobrescrito. Trocar o slug de um evento quebra o link antigo,
    e isso é aceito — o histórico de slugs do Coletivo existe porque o perfil
    dele é ativo permanente de visibilidade (vai no cartaz, no WhatsApp, no
    buscador), enquanto o link de um evento tem a vida útil do evento.
    """

    permission_classes = [AllowAny]

    lookup_field = "slug"

    # `ativo=True` fixo (emenda 10.3) — o inativo não existe para o público.
    # `prefetch_related` evita o N+1 da galeria: sem ele, seria uma query por
    # evento listado.
    queryset = Evento.objects.filter(ativo=True).prefetch_related("imagens")
    serializer_class = EventoSerializer

    filterset_class = EventoFilter
    search_fields = ["titulo", "descricao", "local"]
    ordering_fields = ["data_inicio", "titulo"]
    # Cronológica CRESCENTE, e não o `-data_inicio` do `Meta` do model: são
    # públicos diferentes. O Admin quer ver o que foi cadastrado por último; a
    # agenda pública lê o tempo para frente, o próximo evento primeiro. Para o
    # histórico, o cliente pede `?periodo=passados&ordering=-data_inicio`.
    ordering = ["data_inicio"]


class PontoDeInteresseViewSet(ReadOnlyModelViewSet):
    """Lista e detalhe de pontos de interesse ativos — o mapa público.

    Detalhe por `id`, e não por slug (emenda 10.2): o ponto não é página
    indexável, é marcador de mapa. O cliente carrega a listagem inteira
    (`?page_size=100`) e abre o detalhe a partir do objeto que já tem em mãos.
    Acrescentar um slug ao model só por simetria custaria campo, migration,
    backfill e — para ser coerente com o Coletivo — todo o mecanismo de
    histórico e 301, a serviço de uma URL que ninguém publica.
    """

    permission_classes = [AllowAny]

    # `ativo=True` fixo (emenda 10.3). O `select_related` é obrigatório aqui,
    # e não otimização opcional: o serializer atravessa a FK e ainda lê
    # `coletivo.ativo` na guarda de visibilidade — sem ele, essa guarda por si
    # só criaria o N+1 que ela deveria custar zero.
    queryset = PontoDeInteresse.objects.filter(ativo=True).select_related("coletivo")
    serializer_class = PontoDeInteresseSerializer

    filterset_class = PontoDeInteresseFilter
    search_fields = ["nome", "descricao", "endereco"]
    ordering_fields = ["nome"]
    ordering = ["nome"]
