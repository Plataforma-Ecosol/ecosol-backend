"""Views da API da equipe (`/api/equipe/`).

Separada da API pública de propósito. Lá tudo é AllowAny e só leitura do que
é público; aqui só entra quem tem sessão de equipe no Django Admin.

Quem chama estas views é o servidor do Next (Área da equipe), repassando o
cookie `sessionid` que o navegador recebeu ao logar no Admin pelo endereço do
site (decisão 8.6 do PRD Técnico). O navegador nunca as chama direto.
"""
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django_filters.utils import translate_validation
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from rede.models import Coletivo
from rede.relatorio import FiltroDoRelatorio, distribuicao


@method_decorator(never_cache, name="dispatch")
class VisaoDaEquipe(APIView):
    """Base de toda view da equipe.

    Só sessão (decisão 8.3): o padrão do DRF também aceita Basic Auth, que
    mandaria usuário e senha em cabeçalho. `never_cache` impede que proxy ou
    CDN guardem uma resposta de quem está logado e a sirvam a outra pessoa.

    "Equipe" é `is_staff`, o mesmo critério de quem entra no Admin. Papéis
    mais finos ficam para o Spike de permissões (backend#31).
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]


class EuView(VisaoDaEquipe):
    """Diz se a sessão é de equipe. Devolve só o nome de quem está logado."""

    def get(self, request):
        usuario = request.user
        return Response({"nome": usuario.get_short_name() or usuario.get_username()})


class DistribuicaoDosColetivosView(VisaoDaEquipe):
    """Distribuição dos coletivos para os gráficos do Relatório (backend#57).

    Por bairro, por categoria e por mês de cadastro, só com contagens (ver
    `rede/relatorio.py`). Filtros opcionais: `de` e `ate` (período do cadastro)
    e `situacao`. Parâmetro inválido responde 400, no mesmo formato da API
    pública.
    """

    def get(self, request):
        filtro = FiltroDoRelatorio(request.query_params, queryset=Coletivo.objects.all())
        if not filtro.is_valid():
            raise translate_validation(filtro.errors)
        return Response(distribuicao(filtro.qs))
