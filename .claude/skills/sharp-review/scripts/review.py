#!/usr/bin/env python3
"""review.py — driver da skill sharp-review do ecosol-backend.

Três funções, nenhuma dependência além da biblioteca padrão (Python 3.12):

1. ``--checar-diff``  passada determinística das invariantes do projeto sobre um
   diff unificado (LGPD, chave de visibilidade ``ativo``, migrations, N+1,
   contrato da API, API somente leitura, segredos).
2. ``--scaffold``     imprime o esqueleto de uma revisão no layout da casa.
3. ``--validate``     confere que uma revisão arquivada está em conformidade
   (taxonomia, schema por achado, paridade de contagem, comentário raso).

Por que Python e não Node: este repositório é Django puro — Python 3.12 já está
no ambiente de todo mundo, no Dockerfile e no CI. Um driver em Node exigiria um
runtime a mais só para validar markdown.

Uso:
    python review.py --checar-diff <arquivo.diff>
    git diff origin/staging...HEAD | python review.py --checar-diff --stdin
    python review.py --scaffold --pr 7 --counts 2,1,3,0
    python review.py --validate docs/revisoes/REVIEW_feat-admin.md
    python review.py --validate <arquivo> --json

Códigos de saída: 0 = limpo/válido (avisos permitidos), 1 = achados/erros,
2 = erro de uso.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Faixas de severidade (espelham references/taxonomia-severidade.md)
# --------------------------------------------------------------------------
TIERS: list[tuple[str, str]] = [
    ("🔴", "Crítico"),
    ("🟡", "Nocivo"),
    ("🔵", "Incongruência"),
    ("🟣", "Qualidade de código"),
]
EMOJIS = [e for e, _ in TIERS]
TIER_NAME = dict(TIERS)
TIER_ORDER = {e: i for i, e in enumerate(EMOJIS)}

CRITICO, NOCIVO, INCONGRUENCIA, QUALIDADE = EMOJIS

# --------------------------------------------------------------------------
# Validação de revisão arquivada
# --------------------------------------------------------------------------
ROTULOS_OBRIGATORIOS = ["Problema", "Por que importa", "Correção", "Verificação"]
RE_CAMINHO_LINHA = re.compile(r"`[^`\n]+:\d+`")
RE_VEREDICTO = re.compile(r"\b(CONFIRMADO|PLAUSÍVEL|PLAUSIVEL)\b")
RE_CONF = re.compile(r"\bconf(?:iança|ianca)?\s*[:=]?\s*(\d{1,3})\b", re.IGNORECASE)
RE_ROTULO = re.compile(
    r"^\*\*(Problema|Por que importa|Correção|Correcao|Verificação|Verificacao):\*\*\s*(.*)$"
)
RASO = 40  # abaixo disto, um campo explicativo vira aviso

NORMALIZA_ROTULO = {
    "Correcao": "Correção",
    "Verificacao": "Verificação",
}

# --------------------------------------------------------------------------
# Vocabulário do domínio (PRD Técnico §4, §6 e §9.2)
# --------------------------------------------------------------------------

#: Campos do Coletivo que NUNCA podem sair numa resposta pública (PRD §6.1).
CAMPOS_NUNCA_PUBLICOS = [
    # endereço completo
    "logradouro", "numero", "complemento", "cep",
    # dados cadastrais
    "cnpj", "data_inicio", "responsavel_grupo", "motivo_criacao",
    "renda_obtida", "historico_editais",
    # controle interno
    "ativo", "situacao", "nome_entrevistador", "observacoes",
    # flags de consentimento
    "exibir_telefone_publicamente", "exibir_email_publicamente",
    "exibir_instagram_publicamente",
]

#: Campos sensíveis de Pessoa (PRD §4.2). Não saem nem em resposta pública nem
#: em coluna de listagem do Admin sem necessidade (PRD Admin §4.3).
CAMPOS_SENSIVEIS_PESSOA = [
    "cpf", "rg", "rne_crnm", "data_nascimento", "cor_raca", "sexo",
    "identidade_genero", "orientacao_sexual", "pessoa_com_deficiencia",
    "qual_deficiencia", "renda_familiar", "rede_protecao_social",
    "participacao_programas_sociais",
]

#: Campos públicos do Coletivo, conforme o contrato do PRD §9.2.
CAMPOS_PUBLICOS_COLETIVO = {
    "id", "nome", "slug", "descricao", "bairro", "site", "categorias",
    "criado_em", "atualizado_em", "telefone", "email", "instagram",
}


def _quoted(names: list[str]) -> re.Pattern[str]:
    """Casa qualquer um dos nomes como string entre aspas (ex.: ``"cpf"``)."""
    alternativas = "|".join(re.escape(n) for n in names)
    return re.compile(r"""["'](""" + alternativas + r""")["']""")


RE_CAMPO_NUNCA_PUBLICO = _quoted(CAMPOS_NUNCA_PUBLICOS)
RE_CAMPO_SENSIVEL = _quoted(CAMPOS_SENSIVEIS_PESSOA)


# --------------------------------------------------------------------------
# Parsing de diff unificado
# --------------------------------------------------------------------------
@dataclass
class LinhaAdicionada:
    caminho: str
    numero: int
    texto: str


@dataclass
class Diff:
    arquivos: list[str] = field(default_factory=list)
    adicionadas: list[LinhaAdicionada] = field(default_factory=list)
    removidas: list[tuple[str, str]] = field(default_factory=list)
    novos_arquivos: list[str] = field(default_factory=list)

    def tocou(self, *sufixos_ou_prefixos: str) -> list[str]:
        return [
            a for a in self.arquivos
            if any(p in a for p in sufixos_ou_prefixos)
        ]


RE_DIFF_GIT = re.compile(r"^diff --git a/(.+?) b/(.+)$")
RE_MAIS_MAIS_MAIS = re.compile(r"^\+\+\+ (?:b/)?(.+?)(?:\t.*)?$")
RE_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def parse_diff(texto: str) -> Diff:
    """Extrai arquivos tocados e linhas adicionadas (com número na versão nova)."""
    d = Diff()
    caminho: str | None = None
    numero = 0
    arquivo_novo = False

    for linha in texto.replace("\r\n", "\n").split("\n"):
        m = RE_DIFF_GIT.match(linha)
        if m:
            caminho = m.group(2)
            arquivo_novo = False
            if caminho not in d.arquivos and caminho != "/dev/null":
                d.arquivos.append(caminho)
            continue
        if linha.startswith("new file mode"):
            arquivo_novo = True
            if caminho and caminho not in d.novos_arquivos:
                d.novos_arquivos.append(caminho)
            continue
        m = RE_MAIS_MAIS_MAIS.match(linha)
        if m:
            alvo = m.group(1)
            if alvo != "/dev/null":
                caminho = alvo
                if caminho not in d.arquivos:
                    d.arquivos.append(caminho)
                if arquivo_novo and caminho not in d.novos_arquivos:
                    d.novos_arquivos.append(caminho)
            continue
        m = RE_HUNK.match(linha)
        if m:
            numero = int(m.group(1))
            continue
        if caminho is None:
            continue
        if linha.startswith("+") and not linha.startswith("+++"):
            d.adicionadas.append(LinhaAdicionada(caminho, numero, linha[1:]))
            numero += 1
        elif linha.startswith("-") and not linha.startswith("---"):
            d.removidas.append((caminho, linha[1:]))
        elif linha.startswith(" ") or linha == "":
            numero += 1

    return d


def sem_comentario(texto: str) -> str:
    """Remove comentário Python de fim de linha (aproximação boa o bastante)."""
    fora_de_aspas = re.sub(r"""(['"]).*?\1""", "''", texto)
    pos = fora_de_aspas.find("#")
    return texto[:pos] if pos != -1 else texto


# --------------------------------------------------------------------------
# Achados
# --------------------------------------------------------------------------
@dataclass
class Achado:
    faixa: str
    regra: str
    caminho: str
    linha: int
    titulo: str
    o_que: str
    por_que: str
    correcao: str
    fonte: str
    tipo: str  # "determinístico" | "heurístico"

    def to_dict(self) -> dict:
        return {
            "faixa": self.faixa,
            "regra": self.regra,
            "caminho": self.caminho,
            "linha": self.linha,
            "titulo": self.titulo,
            "o_que": self.o_que,
            "por_que": self.por_que,
            "correcao": self.correcao,
            "fonte": self.fonte,
            "tipo": self.tipo,
        }


def _add(achados, faixa, regra, caminho, linha, titulo, o_que, por_que,
         correcao, fonte, tipo="determinístico"):
    achados.append(Achado(faixa, regra, caminho, linha, titulo, o_que,
                          por_que, correcao, fonte, tipo))


# --------------------------------------------------------------------------
# Regras por linha adicionada
# --------------------------------------------------------------------------
RE_MODELVIEWSET_ESCRITA = re.compile(r"(?<!ReadOnly)\bModelViewSet\b")
RE_MIXIN_ESCRITA = re.compile(
    r"\b(Create|Update|Destroy|PartialUpdate)ModelMixin\b"
    r"|\bgenerics\.(Create|Update|Destroy|ListCreate|RetrieveUpdate|RetrieveDestroy)"
)
RE_ACTION_ESCRITA = re.compile(
    r"""methods\s*=\s*\[[^\]]*["'](post|put|patch|delete)""", re.IGNORECASE
)
RE_METODO_ESCRITA = re.compile(
    r"^\s*def\s+(create|update|partial_update|destroy|perform_create|perform_update|perform_destroy)\s*\("
)
RE_SEGREDO = re.compile(
    r"""(SECRET_KEY|AWS_SECRET_ACCESS_KEY|AWS_ACCESS_KEY_ID|PASSWORD|SENHA)\s*=\s*["'][^"']{8,}["']""",
    re.IGNORECASE,
)
RE_URL_CREDENCIAL = re.compile(r"""postgres(?:ql)?://[^:/\s"']+:[^@\s"']+@""")
# Ancorado no início da linha: `fields = "__all__"` citado numa docstring que
# *proíbe* o uso (como em `rede/serializers.py`) não é violação.
RE_CAMPOS_ALL = re.compile(r"""^\s*fields\s*=\s*["']__all__["']""")
# Item solto de lista de campos: `"telefone",`. Não casa entrada de dicionário
# (`"telefone": "exibir_telefone_publicamente",`), que é o mapa de consentimento.
RE_ITEM_DE_LISTA = re.compile(r"""^\s*["'][^"']+["'],?\s*$""")
RE_EXCLUDE = re.compile(r"^\s*exclude\s*=")
RE_MODEL_PESSOA = re.compile(r"^\s*model\s*=\s*Pessoa\b")
RE_OMISSAO_VIRA_NULL = re.compile(
    r"""(dados|data|ret|representation)\s*\[[^\]]+\]\s*=\s*(None|["']["'])"""
)
RE_QUERYSET_SEM_JOIN = re.compile(r"\.objects\.(all|filter|exclude)\(")
RE_JOIN = re.compile(r"(select_related|prefetch_related|only|defer)\(")
RE_LISTA_CAMPOS = re.compile(
    r"\b(fields|filterset_fields|search_fields|ordering_fields|list_display|"
    r"list_filter|list_display_links|readonly_fields)\b"
)


def checar_linhas(d: Diff, achados: list[Achado]) -> None:
    for la in d.adicionadas:
        p, n, bruto = la.caminho, la.numero, la.texto
        txt = sem_comentario(bruto)
        if not txt.strip():
            continue

        em_serializer = p.endswith("serializers.py")
        em_view = p.endswith("views.py") and "/rede/" in f"/{p}"
        em_filtro = p.endswith("filters.py")
        em_admin = p.endswith("admin.py")
        em_settings = p.endswith("settings.py")
        em_migration = "/migrations/" in p or p.startswith("rede/migrations/")
        em_teste = "/tests/" in f"/{p}" or p.startswith("tests/")

        # ---------- 1. LGPD / blindagem do serializer ----------------------
        if em_serializer:
            if RE_CAMPOS_ALL.search(txt):
                _add(achados, CRITICO, "LGPD-ALL", p, n,
                     'Serializer público com fields = "__all__"',
                     'A classe usa `fields = "__all__"` em vez de declarar a lista '
                     "explícita de campos.",
                     "É lista branca automática: qualquer campo adicionado ao model "
                     "amanhã entra sozinho na resposta pública, sem passar por "
                     "revisão. É exatamente o refactor distraído que a regra de "
                     "blindagem na origem existe para impedir — e aqui o model "
                     "carrega endereço, CNPJ e renda.",
                     "Declarar a lista explícita de campos em `Meta.fields`, no "
                     "padrão do `ColetivoSerializer`.",
                     "PRD Técnico §6.1")
            if RE_EXCLUDE.search(txt):
                _add(achados, CRITICO, "LGPD-EXCLUDE", p, n,
                     "Serializer público usando exclude",
                     "A classe define `exclude` em vez de `fields`.",
                     "`exclude` é lista negra: protege só o que se lembrou de "
                     "listar. O campo sensível criado amanhã não está na lista e "
                     "vaza por omissão. O projeto exige lista branca explícita.",
                     "Trocar por `fields = [...]` com a lista completa dos campos "
                     "públicos previstos no contrato.",
                     "PRD Técnico §6.1")
            if RE_MODEL_PESSOA.search(txt):
                _add(achados, CRITICO, "LGPD-PESSOA", p, n,
                     "Serializer de Pessoa em módulo público",
                     "Um serializer declara `model = Pessoa`.",
                     "Nenhum dado de Pessoa é exposto na interface pública, em "
                     "nenhuma hipótese. O model guarda CPF, RG, cor/raça, "
                     "identidade de gênero, orientação sexual, deficiência e renda "
                     "familiar — dado sensível de pessoa real da rede.",
                     "Remover o serializer. Se a necessidade for do back-office, ela "
                     "se resolve no Django Admin, atrás de autenticação, e não por "
                     "serializer de API.",
                     "PRD Técnico §4.2 e §6.1")
            m = RE_CAMPO_NUNCA_PUBLICO.search(txt)
            parece_lista = bool(
                RE_LISTA_CAMPOS.search(txt) or RE_ITEM_DE_LISTA.match(txt)
            )
            if m and parece_lista:
                campo = m.group(1)
                _add(achados, CRITICO, "LGPD-CAMPO", p, n,
                     f"Campo não público `{campo}` em serializer",
                     f"O campo `{campo}` aparece numa lista de campos do serializer "
                     "público.",
                     "Está na lista do que nunca sai por nenhum caminho — endereço, "
                     "dado cadastral, controle interno ou flag de consentimento. "
                     "Publicá-lo revela a sede (que pode ser a casa de alguém), "
                     "expõe controle interno ou entrega a própria decisão de "
                     "consentimento.",
                     f"Remover `{campo}` da lista. Se o contrato realmente mudou, o "
                     "PRD §9.2 precisa ser emendado no mesmo PR, com justificativa.",
                     "PRD Técnico §6.1 e §9.2")
            m = RE_CAMPO_SENSIVEL.search(txt)
            if m:
                campo = m.group(1)
                _add(achados, CRITICO, "LGPD-SENSIVEL", p, n,
                     f"Campo sensível de Pessoa `{campo}` em serializer",
                     f"O campo sensível `{campo}` aparece num serializer.",
                     "É dado pessoal sensível pela LGPD (identidade, saúde, "
                     "socioeconômico). Não existe caminho público para ele.",
                     f"Remover `{campo}`. Dado sensível vive só no back-office.",
                     "PRD Técnico §4.2 e §6")
            if RE_OMISSAO_VIRA_NULL.search(txt):
                _add(achados, CRITICO, "LGPD-NULL", p, n,
                     "Omissão de contato virando null",
                     "A representação atribui `None`/string vazia a uma chave em vez "
                     "de removê-la do dicionário.",
                     "Sem consentimento a chave precisa ser **removida** do JSON. "
                     "Devolver `null` ainda comunica que existe um dado ali, só "
                     "escondido — perde a minimização — e quebra o tipo do frontend, "
                     "que é `telefone?: string` e não `string | null`.",
                     "Usar `dados.pop(campo, None)`, como em "
                     "`ColetivoSerializer.to_representation`.",
                     "PRD Técnico §6.2")

        # ---------- 2. Chave de visibilidade `ativo` -----------------------
        # Só como código (declaração de filtro, string de campo ou lookup) —
        # citar `ativo` numa docstring explicando a regra não é violação.
        if em_filtro and re.search(
            r"""(^\s*ativo\s*=|["']ativo["']|\bativo__|field_name\s*=\s*["']ativo)""",
            txt,
        ):
            _add(achados, CRITICO, "VIS-FILTRO", p, n,
                 "`ativo` exposto como filtro",
                 "O campo `ativo` aparece em `rede/filters.py`.",
                 "`ativo` é a chave com que a equipe do Centro Público tira um "
                 "coletivo do ar. Exposto como parâmetro, permite a qualquer pessoa "
                 "listar exatamente os coletivos que se decidiu não exibir.",
                 "Remover. O queryset da view fixa `ativo=True`; não há parâmetro "
                 "público para isso.",
                 "Emenda §10.2 do PRD; docstring de `rede/filters.py`")
        if (em_view or em_filtro) and RE_LISTA_CAMPOS.search(txt) \
                and re.search(r"""["']ativo["']""", txt):
            _add(achados, CRITICO, "VIS-CAMPO", p, n,
                 "`ativo` em lista de campos consultáveis",
                 '"ativo" aparece numa lista de campos de filtro, busca ou ordenação.',
                 "Mesmo em `ordering_fields`, permite inferir e enumerar o conjunto "
                 "que a equipe decidiu ocultar.",
                 'Remover "ativo" da lista.',
                 "Emenda §10.2 do PRD")

        # ---------- 3. API somente leitura ---------------------------------
        if em_view:
            if RE_MODELVIEWSET_ESCRITA.search(txt) or RE_MIXIN_ESCRITA.search(txt) \
                    or RE_ACTION_ESCRITA.search(txt) or RE_METODO_ESCRITA.search(txt):
                _add(achados, CRITICO, "SEC-ESCRITA", p, n,
                     "Escrita na API pública",
                     "A view introduz capacidade de escrita (ModelViewSet, mixin de "
                     "escrita, action POST/PUT/PATCH/DELETE ou método de escrita).",
                     "A API pública é somente leitura por decisão de arquitetura: "
                     "não existe autocadastro, e toda escrita passa pelo Django "
                     "Admin, atrás de sessão autenticada. Uma rota de escrita sem "
                     "sessão é escrita anônima no cadastro da rede.",
                     "Manter `ReadOnlyModelViewSet`. Se a necessidade é real, ela "
                     "pertence ao Admin — e exige emenda ao PRD §3 e §7.",
                     "PRD Técnico §3 e §7; docstring de `rede/views.py`")

        # ---------- 4. Segredos e configuração -----------------------------
        if RE_SEGREDO.search(txt) and "env(" not in txt and "environ" not in txt:
            _add(achados, CRITICO, "SEC-SEGREDO", p, n,
                 "Segredo literal no código",
                 "Uma credencial aparece como literal, e não vinda de variável de "
                 "ambiente.",
                 "Segredo em código vaza para todo mundo com acesso ao repositório "
                 "— e o repositório é público (GPLv3). O histórico do Git guarda "
                 "mesmo depois da remoção.",
                 "Ler de `env(...)`, como o resto de `config/settings.py`, e "
                 "**rotacionar** a credencial exposta.",
                 "PRD Técnico §8.2; `config/settings.py`")
        if RE_URL_CREDENCIAL.search(txt) and not p.endswith(".env.example"):
            _add(achados, CRITICO, "SEC-URL", p, n,
                 "URL de banco com credencial",
                 "Uma URL de Postgres com usuário e senha aparece no diff.",
                 "É a credencial do banco de produção do Supabase em texto puro, "
                 "num repositório público.",
                 "Substituir por placeholder e ler de variável de ambiente. "
                 "**Rotacionar** a senha.",
                 "PRD Técnico §8.2")
        if em_settings:
            if re.search(r"\bDEBUG\s*=\s*True\b", txt) or \
                    re.search(r"DJANGO_DEBUG[^)]*default\s*=\s*True", txt):
                _add(achados, CRITICO, "SEC-DEBUG", p, n,
                     "DEBUG ligado por padrão",
                     "`DEBUG` passa a valer `True` por padrão.",
                     "Em produção, `DEBUG=True` expõe stack trace com trecho de "
                     "código, settings e valores de variável — inclusive de "
                     "conexão. É divulgação de informação sensível.",
                     "Manter o default `False`, ligando só por `.env` em "
                     "desenvolvimento.",
                     "`config/settings.py`")
            if re.search(r"""ALLOWED_HOSTS\s*=\s*\[\s*["']\*""", txt):
                _add(achados, CRITICO, "SEC-HOSTS", p, n,
                     'ALLOWED_HOSTS com "*"',
                     "`ALLOWED_HOSTS` aceita qualquer host.",
                     "Desliga a proteção do Django contra Host header poisoning "
                     "(envenenamento de link de reset, cache poisoning).",
                     "Listar os hosts reais, via `DJANGO_ALLOWED_HOSTS`.",
                     "`config/settings.py`")
        if re.search(r"\.raw\(|\.extra\(|\bRawSQL\(", txt):
            _add(achados, CRITICO, "SEC-SQL", p, n,
                 "SQL cru",
                 "A linha usa `.raw()`, `.extra()` ou `RawSQL`.",
                 "SQL montado por concatenação com entrada do usuário é injeção. O "
                 "ORM parametriza por padrão; sair dele é abrir mão disso.",
                 "Reescrever com o ORM. Se for inevitável, usar parâmetros "
                 "(`params=[...]`) e justificar no PR.",
                 "—")
        if re.search(r"ROW LEVEL SECURITY|CREATE POLICY|ENABLE ROW LEVEL", txt, re.I):
            _add(achados, NOCIVO, "ARQ-RLS", p, n,
                 "RLS do Supabase introduzido",
                 "O diff ativa Row Level Security no Postgres.",
                 "A decisão §8.2 é explícita: o isolamento é pela camada de "
                 "permissões do Django, não por RLS — que seria ignorado, já que o "
                 "Django conecta com papel privilegiado. Adicionar RLS cria falsa "
                 "sensação de proteção sem proteger nada.",
                 "Remover, ou emendar a decisão §8.2 com o motivo.",
                 "PRD Técnico §8.2", tipo="heurístico")

        # ---------- 5. Paginação e contrato --------------------------------
        m = re.search(r"max_page_size\s*=\s*(\d+)", txt)
        if m and int(m.group(1)) > 100:
            _add(achados, NOCIVO, "API-TETO", p, n,
                 f"Teto de paginação em {m.group(1)}",
                 f"`max_page_size` passa a {m.group(1)}, acima do teto de 100.",
                 "O teto protege o banco de uma requisição que peça a base inteira "
                 "de uma vez — é o principal item do requisito de listagem abaixo "
                 "de 500 ms.",
                 "Voltar para 100, ou emendar o PRD §9.1 com a medição que "
                 "justifica o novo teto.",
                 "PRD Técnico §9.1; `rede/pagination.py`")
        if re.search(r"pagination_class\s*=\s*None", txt):
            _add(achados, NOCIVO, "API-SEMPAG", p, n,
                 "Paginação desligada na view",
                 "A view define `pagination_class = None`.",
                 "Desfaz a paginação global e devolve a tabela inteira numa "
                 "resposta. Cresce sem limite junto com o cadastro da rede.",
                 "Remover a linha e herdar `PaginacaoPadrao`.",
                 "PRD Técnico §9.1; `rede/pagination.py`")
        if re.search(r"""SEARCH_PARAM["']?\s*[:=]\s*["'](?!q["'])""", txt):
            _add(achados, NOCIVO, "API-BUSCA", p, n,
                 "Parâmetro de busca deixando de ser `q`",
                 "`SEARCH_PARAM` muda de `q`.",
                 "O contrato público chama a busca textual de `q`. Mudar quebra o "
                 "frontend, que está sendo construído em paralelo, e a documentação "
                 "do README.",
                 'Manter `"SEARCH_PARAM": "q"`.',
                 "PRD Técnico §9.2; `config/settings.py`")

        # ---------- 6. Desempenho ------------------------------------------
        if (em_view or em_admin) and RE_QUERYSET_SEM_JOIN.search(txt) \
                and not RE_JOIN.search(txt):
            _add(achados, NOCIVO, "PERF-NPLUS1", p, n,
                 "Queryset sem select_related/prefetch_related",
                 "Um queryset é montado sem otimização de relação na mesma "
                 "expressão.",
                 "Se o serializer ou o `list_display` percorrer uma relação, isso "
                 "vira uma query por item — o N+1 que o requisito de 500 ms proíbe. "
                 "Pode ser falso positivo se nenhuma relação for percorrida.",
                 "Confirmar quais relações são lidas e acrescentar "
                 "`select_related` (FK/OneToOne) ou `prefetch_related` (M2M/reverse "
                 "FK), como em `ColetivoViewSet.queryset`.",
                 "PRD Técnico §2.3 e §7", tipo="heurístico")
        if em_admin:
            m = RE_CAMPO_SENSIVEL.search(txt)
            if m and re.search(r"list_display|list_filter|search_fields", txt):
                _add(achados, NOCIVO, "ADM-SENSIVEL", p, n,
                     f"Campo sensível `{m.group(1)}` em coluna do Admin",
                     f"`{m.group(1)}` aparece em `list_display`, `list_filter` ou "
                     "`search_fields`.",
                     "Minimização vale dentro do cofre também: dado sensível numa "
                     "listagem fica visível a qualquer pessoa com acesso à tela, "
                     "aparece em captura de tela e vaza em ombro alheio. Na tela de "
                     "detalhe, com propósito, tudo bem — em coluna de listagem, não.",
                     f"Tirar `{m.group(1)}` da listagem e deixá-lo só no formulário "
                     "de detalhe.",
                     "PRD de Implementação do Django Admin §4.3")

        # ---------- 7. Migrations ------------------------------------------
        if em_migration:
            m = re.search(r"migrations\.(RemoveField|DeleteModel)\(", txt)
            if m:
                _add(achados, CRITICO, "MIG-DESTRUTIVA", p, n,
                     f"Migration destrutiva ({m.group(1)})",
                     f"A migration executa `{m.group(1)}`.",
                     "Apaga dado já gravado no Postgres do Supabase, de forma "
                     "irreversível. O cadastro veio de entrevista presencial com "
                     "coletivos — o dado perdido não se regenera.",
                     "Explicar no PR o que acontece com os registros existentes. Se "
                     "houver dado a preservar, migração de dados antes da remoção, "
                     "com `reverse_code`.",
                     "—")
            m = re.search(r"migrations\.(RenameField|RenameModel)\(", txt)
            if m:
                _add(achados, NOCIVO, "MIG-RENAME", p, n,
                     f"Renomeação de esquema ({m.group(1)})",
                     f"A migration executa `{m.group(1)}`.",
                     "Se o campo for público, o nome vai na resposta JSON e a "
                     "renomeação quebra o frontend sem aviso.",
                     "Conferir se o campo consta no contrato do PRD §9.2; se "
                     "constar, documentar o breaking change no PR.",
                     "PRD Técnico §9.2")
            if "migrations.RunPython(" in txt and "reverse_code" not in txt:
                _add(achados, NOCIVO, "MIG-IRREVERSIVEL", p, n,
                     "RunPython sem reverse_code",
                     "A migration de dados não declara `reverse_code`.",
                     "Sem função inversa, o `migrate` não volta atrás. Um problema "
                     "em produção deixa de ter rollback.",
                     "Declarar `reverse_code` (ou `migrations.RunPython.noop`, se a "
                     "reversão for de fato vazia — e dizer por quê).",
                     "—")

        # ---------- 8. Qualidade -------------------------------------------
        if re.match(r"^\s*print\(", txt) and not em_teste and not em_migration:
            _add(achados, QUALIDADE, "QA-PRINT", p, n,
                 "print() esquecido",
                 "Há um `print()` em código de aplicação.",
                 "Não vai para lugar nenhum útil em produção (gunicorn), suja o log "
                 "e pode imprimir dado pessoal no stdout do container.",
                 "Remover, ou usar o `logging` do Django se o registro for mesmo "
                 "necessário.",
                 "—")


# --------------------------------------------------------------------------
# Regras entre arquivos
# --------------------------------------------------------------------------
def checar_arquivos(d: Diff, achados: list[Achado]) -> None:
    models = [a for a in d.arquivos if "/models/" in f"/{a}" and a.endswith(".py")
              and not a.endswith("__init__.py")]
    migrations = [a for a in d.arquivos if "/migrations/" in f"/{a}"
                  and a.endswith(".py") and not a.endswith("__init__.py")]
    testes = [a for a in d.arquivos if a.startswith("tests/") or "/tests/" in f"/{a}"]
    serializers = [a for a in d.arquivos if a.endswith("serializers.py")]
    codigo_app = [a for a in d.arquivos
                  if a.endswith(".py")
                  and a.startswith("rede/")
                  and "/migrations/" not in f"/{a}"
                  and not a.endswith("__init__.py")]
    urls = [a for a in d.arquivos if a.endswith("urls.py")]

    # Segredo commitado — checagem de arquivo, não de linha.
    for a in d.arquivos:
        nome = Path(a).name
        if nome == ".env" or (nome.startswith(".env") and not nome.endswith(".example")):
            _add(achados, CRITICO, "SEC-ENV", a, 1,
                 "Arquivo .env no diff",
                 f"O arquivo `{a}` aparece no diff.",
                 "O `.env` guarda `SECRET_KEY`, senha do banco do Supabase e chave "
                 "do Storage. Commitado num repositório público (GPLv3), o segredo "
                 "fica no histórico do Git para sempre — removê-lo num commit "
                 "seguinte não resolve.",
                 "Remover do índice (`git rm --cached`), conferir o `.gitignore` e "
                 "**rotacionar** todas as credenciais que apareceram.",
                 "`.gitignore`; PRD Técnico §8.2")

    if models and not migrations:
        _add(achados, NOCIVO, "MIG-PARIDADE", models[0], 1,
             "Model alterado sem migration no mesmo PR",
             f"O diff altera {', '.join(models)} mas não traz nenhuma migration.",
             "O CI roda `makemigrations --check --dry-run` e vai reprovar. Pior: se "
             "passar por qualquer motivo, o esquema do banco fica dessincronizado "
             "do código. Neste projeto o esquema muda **só** por migration — "
             "ninguém edita tabela pelo painel do Supabase.",
             "Rodar `python manage.py makemigrations rede` e incluir o arquivo "
             "gerado no mesmo PR. (Falso positivo se a alteração não mexeu em "
             "campo — por exemplo, só docstring ou `__str__`.)",
             "PRD Técnico §8.2 e §10.3", tipo="heurístico")

    if serializers and not testes:
        _add(achados, NOCIVO, "LGPD-TESTE", serializers[0], 1,
             "Serializer alterado sem tocar na suíte de LGPD",
             "O diff altera um serializer público mas não altera nenhum teste.",
             "A suíte de regressão de LGPD é a documentação viva da promessa de "
             "privacidade: ela só continua valendo se acompanhar o que o serializer "
             "expõe. Um campo público novo sem asserção nova é uma promessa que "
             "deixou de ser verificada.",
             "Acrescentar a asserção correspondente em `tests/test_api_coletivos.py` "
             "— o campo novo aparece, e o que não é público continua ausente.",
             "PRD Técnico §6.3", tipo="heurístico")
    elif codigo_app and not testes:
        _add(achados, NOCIVO, "TEST-COBERTURA", codigo_app[0], 1,
             "Código de aplicação alterado sem teste",
             f"O diff altera {len(codigo_app)} arquivo(s) de aplicação e nenhum "
             "teste.",
             "O conjunto mínimo de testes cobre models, serializers e as rotas "
             "principais. Comportamento novo sem teste entra sem rede de proteção "
             "— e o próximo PR não tem como saber que quebrou algo.",
             "Acrescentar teste para o comportamento novo, incluindo o caso "
             "negativo (o que **não** deve acontecer).",
             "PRD Técnico §10.3", tipo="heurístico")

    # Colisão de numeração entre migrations novas do próprio diff.
    prefixos: dict[str, list[str]] = {}
    for a in migrations:
        nome = Path(a).name
        m = re.match(r"(\d{4})_", nome)
        if m:
            prefixos.setdefault(m.group(1), []).append(nome)
    for prefixo, nomes in prefixos.items():
        if len(nomes) > 1:
            _add(achados, CRITICO, "MIG-COLISAO", migrations[0], 1,
                 f"Duas migrations com o prefixo {prefixo}",
                 f"O diff traz {', '.join(nomes)} — mesmo número de ordem.",
                 "Duas migrations com o mesmo prefixo geram histórico ramificado: o "
                 "`migrate` falha no merge, e a `staging` fica travada até alguém "
                 "renumerar à mão.",
                 "Renumerar uma delas (`--name`) ou gerar uma migration de "
                 "convergência (`makemigrations --merge`).",
                 "—")

    if urls and "README.md" not in d.arquivos:
        _add(achados, QUALIDADE, "DOC-README", urls[0], 1,
             "Rota alterada sem atualizar o README",
             "O diff mexe em `urls.py` mas não toca o `README.md`.",
             "O README documenta o contrato da API em português — é o que torna o "
             "projeto reaplicável por outra rede da Economia Solidária. Rota nova "
             "não documentada é conhecimento que fica só na cabeça de quem "
             "escreveu. (Falso positivo se a mudança não altera rota pública.)",
             "Acrescentar a rota à tabela da seção 'API pública' do README.",
             "PRD Técnico §7", tipo="heurístico")


def checar_diff(texto: str) -> list[Achado]:
    d = parse_diff(texto)
    achados: list[Achado] = []
    checar_linhas(d, achados)
    checar_arquivos(d, achados)
    # dedup por (regra, caminho, linha)
    vistos = set()
    unicos = []
    for a in achados:
        chave = (a.regra, a.caminho, a.linha)
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(a)
    unicos.sort(key=lambda a: (TIER_ORDER[a.faixa], a.caminho, a.linha))
    return unicos


def imprimir_achados(achados: list[Achado], arquivos_tocados: int) -> None:
    contagem = {e: 0 for e in EMOJIS}
    for a in achados:
        contagem[a.faixa] += 1

    resumo = " ".join(f"{e}{contagem[e]}" for e in EMOJIS)
    print(f"passada determinística — {len(achados)} candidato(s)  {resumo}")
    print(f"({arquivos_tocados} arquivo(s) no diff)\n")

    if not achados:
        print("Nenhuma invariante do projeto violada nas linhas adicionadas.")
        print("Isso NÃO é uma revisão completa — é só a camada mecânica.")
        print("Siga para os auditores.")
        return

    faixa_atual = None
    for a in achados:
        if a.faixa != faixa_atual:
            faixa_atual = a.faixa
            print(f"\n=== {a.faixa} {TIER_NAME[a.faixa]} " + "=" * 30)
        print(f"\n[{a.regra}] {a.caminho}:{a.linha} — {a.titulo}  ({a.tipo})")
        print(f"  O quê:    {a.o_que}")
        print(f"  Por quê:  {a.por_que}")
        print(f"  Correção: {a.correcao}")
        if a.fonte and a.fonte != "—":
            print(f"  Fonte:    {a.fonte}")

    print("\n" + "-" * 60)
    print("determinístico = CONFIRMADO por construção; pode pular o verificador.")
    print("heurístico     = candidato; confirme lendo o arquivo antes de virar achado.")


# --------------------------------------------------------------------------
# Validação da revisão arquivada
# --------------------------------------------------------------------------
def preprocessar(texto: str) -> tuple[list[str], list[bool]]:
    """Divide em linhas marcando as que estão dentro de bloco de código.

    Comentário HTML é removido só FORA de bloco (um ``<!--`` dentro de um
    ```suggestion é conteúdo, não comentário) e pode atravessar linhas.
    """
    bruto = texto.replace("\r\n", "\n").split("\n")
    linhas: list[str] = []
    cercadas: list[bool] = []
    em_cerca = False
    em_comentario = False
    for linha in bruto:
        if re.match(r"^\s*(```|~~~)", linha):
            em_cerca = not em_cerca
            linhas.append(linha)
            cercadas.append(True)
            continue
        if em_cerca:
            linhas.append(linha)
            cercadas.append(True)
            continue
        atual = linha
        if em_comentario:
            fim = atual.find("-->")
            if fim == -1:
                linhas.append("")
                cercadas.append(False)
                continue
            atual = atual[fim + 3:]
            em_comentario = False
        atual = re.sub(r"<!--.*?-->", "", atual, flags=re.DOTALL)
        abre = atual.find("<!--")
        if abre != -1:
            atual = atual[:abre]
            em_comentario = True
        linhas.append(atual)
        cercadas.append(False)
    return linhas, cercadas


def _trunc(s: str, n: int = 50) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def validar(texto: str) -> dict:
    erros: list[str] = []
    avisos: list[str] = []
    linhas, cercadas = preprocessar(texto)
    limpo = "\n".join(linhas)

    if not re.search(r"^#\s+Revisão de Código\b", limpo, re.M):
        avisos.append('Falta o cabeçalho H1 "# Revisão de Código".')
    if "AGUARDANDO APROVAÇÃO" not in limpo and "Status:" not in limpo:
        avisos.append(
            'Sem linha "Status:" — a revisão deve declarar AGUARDANDO APROVAÇÃO '
            "até ser aprovada."
        )

    declarado: dict[str, int] = {}
    for emoji, nome in TIERS:
        m = re.search(r"^\|[^|]*" + emoji + r"[^|]*\|\s*(\d+)\s*\|", limpo, re.M)
        if not m:
            erros.append(f"A tabela de resumo não tem a contagem de {emoji} {nome}.")
        else:
            declarado[emoji] = int(m.group(1))

    real = {e: 0 for e in EMOJIS}
    achados: list[dict] = []
    faixa_atual: str | None = None
    atual: dict | None = None

    def fechar():
        nonlocal atual
        if atual is not None:
            achados.append(atual)
            atual = None

    for i, linha in enumerate(linhas):
        if cercadas[i]:
            if atual is not None and atual["ultimo"]:
                atual["rotulos"][atual["ultimo"]] += " " + linha.strip()
            continue
        h2 = re.match(r"^##\s+(.*)$", linha)
        if h2:
            fechar()
            faixa_atual = next((e for e in EMOJIS if e in h2.group(1)), None)
            continue
        h3 = re.match(r"^###\s+(.*)$", linha)
        if h3:
            fechar()
            if faixa_atual:
                atual = {
                    "titulo": h3.group(1),
                    "faixa": faixa_atual,
                    "linha": i + 1,
                    "rotulos": {},
                    "ultimo": None,
                }
                real[faixa_atual] += 1
                if not RE_CAMINHO_LINHA.search(h3.group(1)):
                    erros.append(
                        f'{faixa_atual} achado "{_trunc(h3.group(1))}" '
                        f"(linha {i + 1}) não tem `caminho:linha` no título."
                    )
            continue
        if atual is not None:
            m = RE_ROTULO.match(linha)
            if m:
                rot = NORMALIZA_ROTULO.get(m.group(1), m.group(1))
                atual["rotulos"][rot] = (m.group(2) or "").strip()
                atual["ultimo"] = rot
            elif atual["ultimo"] and linha.strip() and not re.match(r"^[-*]\s", linha):
                atual["rotulos"][atual["ultimo"]] += " " + linha.strip()
    fechar()

    for a in achados:
        onde = f'{a["faixa"]} achado "{_trunc(a["titulo"])}" (linha {a["linha"]})'
        for rot in ROTULOS_OBRIGATORIOS:
            if rot not in a["rotulos"]:
                erros.append(f"{onde} está sem **{rot}:**.")
        if "Verificação" in a["rotulos"]:
            v = a["rotulos"]["Verificação"]
            if not RE_VEREDICTO.search(v):
                erros.append(f"{onde} **Verificação:** precisa dizer CONFIRMADO ou "
                             "PLAUSÍVEL.")
            cm = RE_CONF.search(v)
            if not cm:
                erros.append(f'{onde} **Verificação:** precisa de um "conf <0-100>".')
            elif int(cm.group(1)) > 100:
                erros.append(f"{onde} **Verificação:** conf precisa estar entre 0 e 100.")
        for rot in ["Problema", "Por que importa", "Correção"]:
            if rot not in a["rotulos"]:
                continue
            tam = len(a["rotulos"][rot])
            if tam == 0:
                erros.append(f"{onde} tem **{rot}:** vazio.")
            elif tam < RASO:
                avisos.append(
                    f"{onde} tem **{rot}:** raso (<{RASO} caracteres) — o "
                    "comentário precisa ser explicativo."
                )

    for emoji, nome in TIERS:
        if emoji in declarado and declarado[emoji] != real[emoji]:
            erros.append(
                f"O resumo declara {declarado[emoji]} {emoji} {nome}, mas o corpo "
                f"tem {real[emoji]}."
            )

    return {
        "ok": len(erros) == 0,
        "errors": erros,
        "warnings": avisos,
        "summary": {"declared": declarado, "actual": real, "total": len(achados)},
    }


# --------------------------------------------------------------------------
# Esqueleto
# --------------------------------------------------------------------------
def parse_counts(spec: str | None) -> dict[str, int]:
    out = {e: 0 for e in EMOJIS}
    if not spec:
        return out
    partes = [p.strip() for p in spec.split(",")]
    for i, e in enumerate(EMOJIS):
        if i < len(partes) and partes[i].isdigit():
            out[e] = int(partes[i])
    return out


def scaffold(args) -> str:
    counts = parse_counts(args.counts)
    alvo = args.target or "<alvo>"
    branch = args.branch or "<branch>"
    sha = args.sha or "<sha>"
    revisado = f"PR #{args.pr}" if args.pr else (args.range or "<intervalo do diff>")
    envio = (
        f"Posta no PR #{args.pr} como comentários inline após a aprovação."
        if args.pr
        else "Comentários inline no PR após a aprovação (ou agir sobre este arquivo, "
             "se o alvo não for um PR)."
    )

    def stub(n: int, m: int) -> str:
        return (
            f"### {n}.{m} <título> — `caminho/do/arquivo.py:1`\n"
            "**Problema:** TODO — o que está errado neste código específico "
            "(nomeie o símbolo/linha).\n"
            "**Por que importa:** TODO — a consequência concreta (o que quebra, "
            "vaza, fica lento ou confunde, e quando).\n"
            "**Correção:** TODO — remédio concreto; use bloco ```suggestion quando a "
            "mudança for exata.\n"
            "**Verificação:** PLAUSÍVEL · conf 50\n"
            "- [ ] aprovar   - [ ] descartar\n"
        )

    def dica(n: int) -> str:
        return (
            "<!-- Nenhum achado nesta faixa. Para adicionar um, siga o schema:\n"
            f"### {n}.1 <título> — `caminho/do/arquivo.py:LINHA`\n"
            "**Problema:** ...\n**Por que importa:** ...\n**Correção:** ...\n"
            "**Verificação:** CONFIRMADO|PLAUSÍVEL · conf <0-100>\n"
            "- [ ] aprovar   - [ ] descartar\n-->\n"
        )

    out = [f"# Revisão de Código — {alvo} ({branch} @ {sha})"]
    if args.slug:
        out.append(f"<!-- slug: {args.slug} -->")
    out.append(
        f"> Revisado: {revisado} · Motor: sharp-review (multi-agente + verificação) "
        "· Status: AGUARDANDO APROVAÇÃO"
    )
    out.append("> Edite este arquivo (aprovar/descartar cada achado) antes do envio.\n")
    out.append("## 0. Resumo\n<veredicto em um parágrafo>\n")
    out.append("| Severidade | Quantidade |\n|---|---|")
    for emoji, nome in TIERS:
        out.append(f"| {emoji} {nome} | {counts[emoji]} |")
    out.append("")
    for idx, (emoji, nome) in enumerate(TIERS):
        n = idx + 1
        out.append(f"## {n}. {emoji} {nome}")
        if counts[emoji] > 0:
            for m in range(1, counts[emoji] + 1):
                out.append(stub(n, m))
        else:
            out.append(dica(n))
        out.append("")
    out.append("## 5. Envio")
    out.append(envio)
    out.append('Para descartar um achado, marque "descartar" (ou apague o bloco) '
               "antes da aprovação.")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def ler_texto(args) -> str | None:
    if args.stdin:
        return sys.stdin.read()
    alvo = args.file or args.positional
    if alvo:
        caminho = Path(alvo)
        if not caminho.exists():
            print(f"Arquivo não encontrado: {alvo}", file=sys.stderr)
            raise SystemExit(2)
        return caminho.read_text(encoding="utf-8")
    return None


def main() -> int:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")  # Windows
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(
        prog="review.py",
        description="Driver da skill sharp-review (ecosol-backend).",
    )
    p.add_argument("positional", nargs="?", help="arquivo (diff ou revisão .md)")
    p.add_argument("--checar-diff", dest="checar", action="store_true",
                   help="passada determinística das invariantes sobre um diff")
    p.add_argument("--validate", action="store_true",
                   help="valida uma revisão .md arquivada (ação padrão)")
    p.add_argument("--scaffold", action="store_true",
                   help="imprime o esqueleto de uma revisão")
    p.add_argument("-f", "--file", help="arquivo de entrada")
    p.add_argument("--stdin", action="store_true", help="lê da entrada padrão")
    p.add_argument("--json", action="store_true", help="saída em JSON")
    p.add_argument("-q", "--quiet", action="store_true")
    p.add_argument("--target")
    p.add_argument("--branch")
    p.add_argument("--sha")
    p.add_argument("--range")
    p.add_argument("--pr")
    p.add_argument("--slug")
    p.add_argument("--counts", help="contagens na ordem 🔴,🟡,🔵,🟣 (ex.: 2,1,3,0)")
    args = p.parse_args()

    if args.scaffold:
        sys.stdout.write(scaffold(args))
        return 0

    texto = ler_texto(args)
    if texto is None:
        print("Sem entrada. Passe um caminho de arquivo, --file <caminho> ou "
              "--stdin (veja --help).", file=sys.stderr)
        return 2

    if args.checar:
        achados = checar_diff(texto)
        if args.json:
            print(json.dumps(
                {
                    "ok": len(achados) == 0,
                    "total": len(achados),
                    "por_faixa": {
                        e: sum(1 for a in achados if a.faixa == e) for e in EMOJIS
                    },
                    "achados": [a.to_dict() for a in achados],
                },
                ensure_ascii=False, indent=2,
            ))
        elif not args.quiet:
            imprimir_achados(achados, len(parse_diff(texto).arquivos))
        return 1 if achados else 0

    res = validar(texto)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["ok"] else 1
    if not args.quiet:
        s = res["summary"]
        estado = "OK  " if res["ok"] else "FALHOU"
        resumo = " ".join(f"{e}{s['actual'][e]}" for e in EMOJIS)
        print(f"{estado}  {s['total']} achado(s) — {resumo}")
        for e in res["errors"]:
            print(f"  erro:  {e}")
        for w in res["warnings"]:
            print(f"  aviso: {w}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
