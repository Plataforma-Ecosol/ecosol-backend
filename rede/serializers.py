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

Uma terceira regra vale para **todos** os serializers públicos, e não só para
o Coletivo: **`ativo` nunca sai na resposta**. Ele é a chave de visibilidade
com que a equipe do Centro Público tira um registro do ar; expor o campo não
vaza dado pessoal, mas denuncia a existência de um recurso oculto e convida a
tratar a resposta como se `ativo` fosse filtrável.
"""
from rest_framework import serializers

from rede.models import Categoria, Coletivo, Evento, ImagemEvento


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


# --- Evento -----------------------------------------------------------------


class ImagemEventoSerializer(serializers.ModelSerializer):
    """Imagem da galeria como ela aparece aninhada em um evento.

    Cartaz e foto de divulgação são conteúdo público por natureza — aqui não
    há a questão de consentimento que existe nos contatos do coletivo. A
    guarda é de contrato: nada de `evento` (que traria recursão) e nada de
    `criado_em` (ruído interno da imagem, que ninguém consome).

    `imagem` sai como URL absoluta: o DRF resolve o `ImageField` contra o
    `request`. Com `DJANGO_USE_S3=True` é a URL pública do Supabase Storage;
    localmente, `http://localhost:8001/media/eventos/...`.
    """

    class Meta:
        model = ImagemEvento
        fields = ["id", "imagem", "legenda", "ordem"]


class EventoSerializer(serializers.ModelSerializer):
    """Evento como ele aparece na API pública.

    Os campos seguem exatamente o contrato da Seção 3.4 do PRD desta fatia,
    nesta ordem. Não há `to_representation` aqui: nenhum campo do evento é
    condicional — `data_fim` vazia é ausência legítima, e sai como `null`.

    `data_inicio` e `data_fim` são data-hora com fuso (`2026-08-15T18:00:00
    -03:00`), e não datas: um evento tem hora (emenda 10.5).
    """

    imagens = ImagemEventoSerializer(many=True, read_only=True)

    class Meta:
        model = Evento
        fields = [
            # Identificação
            "id",
            "titulo",
            "slug",
            "descricao",
            # Quando
            "data_inicio",
            "data_fim",
            # Onde
            "local",
            "bairro",
            # Divulgação
            "link",
            "imagens",
            # Datas
            "criado_em",
            "atualizado_em",
        ]
