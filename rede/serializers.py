"""Serializers da API pública do app `rede`.

**Este é o ponto onde a promessa de privacidade do projeto é cumprida.** O
cadastro reúne dados pessoais e sensíveis; o que sai daqui é o que o mundo vê.

Duas regras valem para todo serializer público, sem exceção:

1. **Lista explícita de campos.** Nunca `fields = "__all__"` e nunca
   `exclude`. `exclude` é lista negra: o campo sensível criado amanhã entra
   sozinho na resposta. A blindagem é na origem — campo que não é declarado
   não vaza nem por refactor distraído.
2. **Contato só com consentimento.** Sem a flag ligada, a chave é *removida*
   do JSON — não vira `null`, não vira string vazia (ver
   `ColetivoSerializer.CONTATOS_POR_CONSENTIMENTO`).

O que NUNCA sai por nenhum caminho: qualquer dado de Pessoa, o endereço do
coletivo (`logradouro`, `numero`, `complemento`, `cep`), os dados cadastrais
(`cnpj`, `data_inicio`, `responsavel_grupo`, `motivo_criacao`, `renda_obtida`,
`historico_editais`), o controle interno (`ativo`, `situacao`,
`nome_entrevistador`, `observacoes`) e as próprias flags de consentimento.
`bairro` é o único dado geográfico público: dá contexto sem revelar a sede,
que pode ser a casa de alguém.
"""
from rest_framework import serializers

from rede.models import Categoria, Coletivo


class CategoriaResumoSerializer(serializers.ModelSerializer):
    """Categoria como ela aparece aninhada em um coletivo."""

    class Meta:
        model = Categoria
        fields = ["id", "nome", "slug"]


class ColetivoSerializer(serializers.ModelSerializer):
    """Coletivo como ele aparece na API pública.

    Os campos seguem exatamente o contrato da Seção 3.4 do PRD, nesta ordem.
    Os três últimos — os contatos — só existem na resposta se o coletivo tiver
    dado o consentimento correspondente.
    """

    #: Mapa contato → flag de consentimento. Quem acrescentar um contato novo
    #: ao model declara aqui o consentimento dele; sem entrada neste mapa, o
    #: campo sairia sempre — e é justamente isso que não pode acontecer.
    CONTATOS_POR_CONSENTIMENTO = {
        "telefone": "exibir_telefone_publicamente",
        "email": "exibir_email_publicamente",
        "instagram": "exibir_instagram_publicamente",
    }

    categorias = CategoriaResumoSerializer(many=True, read_only=True)

    class Meta:
        model = Coletivo
        fields = [
            # Institucionais
            "id",
            "nome",
            "slug",
            "descricao",
            "bairro",
            "site",
            # Relacionamento
            "categorias",
            # Datas
            "criado_em",
            "atualizado_em",
            # Contatos condicionais — a chave só existe com consentimento
            "telefone",
            "email",
            "instagram",
        ]

    def to_representation(self, instance):
        """Serializa o coletivo e remove os contatos sem consentimento.

        Omitir a chave, em vez de devolver `null`, é a aplicação prática da
        minimização de dados: `null` ainda comunicaria "existe um dado aqui,
        mas foi escondido". Quem consome a API não recebe sequer o indício.
        """
        dados = super().to_representation(instance)
        for campo, flag in self.CONTATOS_POR_CONSENTIMENTO.items():
            if not getattr(instance, flag, False):
                dados.pop(campo, None)
        return dados
