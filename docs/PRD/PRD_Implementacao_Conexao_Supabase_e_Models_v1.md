# PRD de Implementação — Conexão real ao Supabase + Models de Domínio

**Projeto:** Plataforma de Rede da Economia Solidária de Niterói
**Centro Público de Referência em Economia Solidária (Casa Paul Singer) · ITES / IFRJ Campus Niterói**

| | |
|---|---|
| **Documento** | PRD de Implementação — Fatia 1: Conexão Supabase + Models |
| **Versão** | 1.0 |
| **Deriva de** | PRD Técnico v4.1 (Seção 11, **item 1**) e PRD de Implementação — Backend v1.1 (PRs 2 e 3) |
| **Escopo** | Conexão real ao Postgres do Supabase + Usuário customizado + Models (Categoria, Coletivo, Pessoa, Evento + ImagemEvento, Ponto de Interesse) + Storage de imagens |
| **Fora de escopo** | Serializers, endpoint `/api/coletivos/`, testes de LGPD de serialização, Django Admin, frontend (fatias seguintes) |
| **Repositório** | `apps/ecosol-backend` (dentro da umbrella `ecosol-fullstack`) |
| **Status** | Pronto para desenvolvimento — a ser executado via Claude Code |

---

## 0. Objetivo deste documento

Este PRD detalha **como** executar o **item 1 da Seção 11 do PRD Técnico v4.1**:

> *"Backend primeiro: iniciar o Django, conectar ao Postgres do Supabase e criar os Models (Pessoa, Coletivo com slug/ativo/situação, Categoria, Evento, Ponto de Interesse)."*

No mapa de PRs do PRD de Implementação Backend v1.1, isso corresponde a **PR 2 (usuário customizado)** e **PR 3 (models de domínio + conexão Supabase validada)**. O scaffold (PR 1) **já está concluído** no repositório. Este documento é autossuficiente para ser lido por um agente (Claude Code) e transformado em código, sem precisar reabrir os PRDs anteriores — mas não contradiz nenhum deles.

**Decisão de escopo desta fatia (validada):** inclui o **Usuário customizado** como pré-requisito obrigatório (tem de existir antes da primeira migration de qualquer outro model) e inclui **imagens + Storage** (ImagemEvento, `imagem_capa` do Ponto de Interesse, upload via `django-storages` para o Supabase Storage), com um teste de fumaça de upload.

---

## 1. Estado atual do repositório (ponto de partida)

O que **já existe** e **não deve ser refeito** (confirmado no código):

- **`config/settings.py`** — configurado para arquitetura Django-cêntrica. Já contém:
  - Leitura de `.env` via `django-environ`.
  - `INSTALLED_APPS` com `rest_framework`, `django_filters` e o app de domínio `rede`.
  - **Lógica de duas conexões** já pronta: `DJANGO_DB_DIRECT` (usa `DATABASE_DIRECT_URL` para migrations) e `DJANGO_DB_POOLER` (usa `DATABASE_URL` do pooler em runtime, aplicando `DISABLE_SERVER_SIDE_CURSORS=True` e `OPTIONS['prepare_threshold']=None`). **Não reescrever** — apenas usar.
  - Bloco de `STORAGES` S3 (django-storages) protegido por `DJANGO_USE_S3`.
  - `REST_FRAMEWORK` com paginação padrão 20.
  - Comentário-âncora na última linha: *"AUTH_USER_MODEL entra no PR 2, antes de qualquer outro model"*.
- **`rede/models.py`** — **vazio de propósito** (apenas docstring). É aqui que o trabalho começa.
- **`rede/apps.py`** — `RedeConfig` já definido.
- **`rede/admin.py`** — praticamente vazio (Admin é fatia posterior; não é foco aqui).
- **`rede/migrations/`** — só `__init__.py` (nenhuma migration ainda).
- **`.env.example`** — já documenta `DATABASE_URL` (pooler 6543), `DATABASE_DIRECT_URL` (direta 5432), `DJANGO_DB_POOLER`, e o bloco de Storage.
- **`infra/docker-compose.yml`** — sobe backend + **Postgres local isolado** (não toca o Supabase). Roda `migrate` + `runserver` na porta 8001.
- **`requirements.txt`** — já inclui `psycopg[binary]`, `django-storages`, `boto3`, `Pillow`, `django-environ`.
- **CI** (`.github/workflows/ci.yml`) e proteção de branch `main` já ativos.

> **Princípio-guia:** esta fatia **adiciona models e valida a conexão real**. Ela **não** altera as decisões de arquitetura já codificadas em `settings.py`. Se algo parecer precisar de mudança em `settings.py`, é sinal de reavaliar — não de reescrever.

---

## 2. Resultado esperado (Definition of Done da fatia)

A fatia está concluída quando **todos** os itens abaixo forem verdadeiros:

1. **`AUTH_USER_MODEL`** aponta para um usuário customizado em `rede` e é a **primeira** migration do app.
2. Os models **Categoria, Coletivo, Pessoa, Evento, ImagemEvento e Ponto de Interesse** existem em `rede/models.py` (ou no pacote `rede/models/`), com os campos deste PRD.
3. `python manage.py makemigrations` gera as migrations e `makemigrations --check --dry-run` fica **limpo** (sem migrations pendentes).
4. **`docker compose up --build`** (a partir de `infra/`) sobe o ambiente local e aplica todas as migrations no **Postgres do container** sem erro.
5. A **conexão real ao Supabase é validada**: com `.env` apontando para o Supabase, `migrate` roda pela **conexão direta** (5432) e um `manage.py shell`/`dbshell` confirma leitura/escrita via **pooler** (6543) — evidência registrada no PR (log ou print).
6. O **Storage do Supabase** aceita um upload de teste (imagem de Evento **ou** capa de Ponto de Interesse) pelo Django, e a URL pública resultante abre. Evidência no PR.
7. `ruff` passa; o CI (lint + `makemigrations --check` + `pytest`) fica **verde**.
8. Um teste mínimo de **models** passa (ver Seção 8): criação de Coletivo com `slug` único, default de `ativo`, relação Pessoa→Coletivo, M2M Coletivo↔Categoria, `situacao` independente de `ativo`.

> Serializers, endpoint público e o teste de regressão de LGPD de serialização **não** fazem parte desta fatia (são a fatia seguinte). Aqui, a proteção LGPD se manifesta apenas na **modelagem** (campos sensíveis existem, mas moram só no back-office; nenhuma exposição é criada nesta fatia).

---

## 3. Conexão real ao Postgres do Supabase

### 3.1. As duas conexões (já codificadas — só operar)

O modo de transação do pooler do Supabase tem atrito conhecido com *prepared statements* e cursores server-side do Django. O `settings.py` **já resolve isso** por flags. O trabalho desta fatia é **operar corretamente**, não recodificar:

| Uso | Conexão | Porta | Variável | Flags |
|---|---|---|---|---|
| **App em runtime** | Transaction Pooler | `6543` | `DATABASE_URL` | `DJANGO_DB_POOLER=True` → desativa cursores server-side e prepared statements |
| **Migrations** | Conexão direta | `5432` | `DATABASE_DIRECT_URL` | `DJANGO_DB_DIRECT=True` só no momento de migrar |

**Comando de migration contra o Supabase (real):**

```bash
# .env com credenciais reais do Supabase
DJANGO_DB_DIRECT=True python manage.py migrate
```

**App/leitura em runtime** usa `DATABASE_URL` (pooler) com `DJANGO_DB_POOLER=True` — sem `DJANGO_DB_DIRECT`.

> Se a conexão direta (5432) der timeout em IPv4, usar a **Session Pooler** (host do pooler, porta 5432, usuário `postgres.SEU_REF`) apenas para as migrations, conforme já anotado no `.env.example`. Registrar no PR qual caminho funcionou.

### 3.2. Migration como única fonte de esquema

Ninguém edita tabela pelo painel do Supabase. **Toda** mudança de esquema passa por migration versionada no repositório. O painel do Supabase é usado só para inspeção e para pegar as credenciais/host.

### 3.3. Roteiro de validação da conexão (o que provar no PR)

1. `docker compose up --build` sobe local (Postgres do container) e aplica migrations — **prova o esquema**.
2. Com `.env` real: `DJANGO_DB_DIRECT=True python manage.py migrate` cria as tabelas no Supabase — **prova a conexão direta**.
3. Com `DJANGO_DB_POOLER=True` (sem direct): `python manage.py shell` cria e lê um registro simples (ex.: uma `Categoria`) — **prova o runtime via pooler** (e que prepared statements desativados funcionam).
4. Print/log de cada passo anexado ao PR.

### 3.4. Segurança de credenciais

`.env` **nunca** é commitado (já no `.gitignore`). Só o `.env.example` (sem segredos) fica versionado. As credenciais reais do Supabase vivem no `.env` local e, no deploy, nas variáveis de ambiente do serviço gerenciado.

---

## 4. Ordem de execução (sequência de PRs)

Executar **nesta ordem** — a ordem importa para não travar o schema:

| # | Branch | Conteúdo | Bloqueia? |
|---|---|---|---|
| **A** | `feat/usuario-customizado` | Model `Usuario` (custom) + `AUTH_USER_MODEL` + **primeira migration** de `rede`. Nada mais. | Sim — tudo depende dele |
| **B** | `feat/models-dominio` | Categoria, Coletivo, Pessoa, Evento, ImagemEvento, Ponto de Interesse + migrations. Conexão Supabase validada. | Depende de A |
| **C** | `test/models` | Teste mínimo de models (Seção 8), integrado ao CI. | Depende de B |

> **Por que o Usuário vem primeiro:** trocar `AUTH_USER_MODEL` depois que já há migrations de outros models é doloroso (o Django amarra o esquema de auth cedo). Criá-lo antes de qualquer outra tabela evita retrabalho. Esta é a decisão do PRD Backend v1.1 (PR 2).

Cada PR segue Conventional Commits e o fluxo de branch protegida (`main`/`staging` via PR revisado).

---

## 5. Model: Usuário customizado (PR A)

Objetivo mínimo e à prova de futuro: um usuário customizado desde a primeira migration, **sem** sobre-engenharia. Não há autocadastro público; as contas com login são as da equipe administrativa (papel Administrador). O "Público Geral" não faz login (é a interface pública de leitura).

**Abordagem recomendada:** herdar de `AbstractUser` (mantém username/password/permissions do Django, que o Django Admin usa), num model `Usuario` no app `rede`.

```python
# rede/models/usuario.py  (ou em rede/models.py)
from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    """Usuário do back-office (equipe do Centro Público).

    Custom desde o início (PRD Técnico 4.6). Sem autocadastro: as contas
    são criadas pela equipe administrativa. Herdar de AbstractUser mantém
    o Django Admin e o sistema de permissões prontos.
    """
    # Espaço reservado para campos futuros de perfil administrativo,
    # sem adicionar nada especulativo agora.

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
```

**Em `settings.py`**, adicionar (é a única alteração de settings desta fatia, e ela já está prevista pelo comentário-âncora ao final do arquivo):

```python
AUTH_USER_MODEL = "rede.Usuario"
```

**Migration:** `python manage.py makemigrations rede` deve gerar `0001_initial` contendo **apenas** o `Usuario`. Conferir que é a primeira. Aplicar local (compose) e validar.

---

## 6. Models de domínio (PR B)

Convenções (PRD Técnico 0 e 9.1): chaves em `snake_case`, datas ISO 8601, `criado_em`/`atualizado_em` (auto) em toda entidade principal. Usar `verbose_name` em português nos models e campos (o Admin da fatia seguinte se beneficia).

> **Regra de negócio que NÃO vira código:** "coletivo válido tem no mínimo 3 pessoas e é interfamiliar" é verificação **humana** da equipe. O software não valida; se o administrador cadastrou, é válido. Por isso **"família" não é entidade** do modelo.

### 6.1. Categoria / Segmento

Classifica coletivos (artesanato, alimentação, agroecologia, serviços…). É o principal eixo de busca/filtro público (na fatia de API). M2M com Coletivo.

| Campo | Tipo | Regras |
|---|---|---|
| `id` | BigAutoField (PK) | automático |
| `nome` | `CharField` | obrigatório |
| `slug` | `SlugField(unique=True)` | único, indexado; gerado a partir do nome |

`__str__` retorna `nome`. `Meta.ordering = ["nome"]`.

### 6.2. Coletivo — o nó da rede

Unidade central e única entidade exibida na listagem pública. Agrupa uma ou mais pessoas/empreendimentos.

**Identificação pública:**

| Campo | Tipo | Regras |
|---|---|---|
| `nome` | `CharField` | obrigatório |
| `slug` | `SlugField(unique=True)` | único, **indexado** (usado na URL de detalhe e no frontend, ex. `sementes-do-vale`) |
| `descricao` | `TextField` | opcional |
| `bairro` | `CharField` | **público** — dá contexto geográfico sem revelar endereço; indexar (filtro público) |
| `site` | `URLField` | opcional |

**Contatos (visibilidade condicional por consentimento — a poda acontece no serializer da fatia seguinte; aqui apenas modelar campo + flag):**

| Campo | Tipo | Flag de consentimento |
|---|---|---|
| `telefone` | `CharField` | `exibir_telefone_publicamente` (`BooleanField`, default `False`) |
| `email` | `EmailField` | `exibir_email_publicamente` (`BooleanField`, default `False`) |
| `instagram` | `CharField` | `exibir_instagram_publicamente` (`BooleanField`, default `False`) |

**Dados cadastrais (uso administrativo — nunca públicos):**

`cnpj` (`CharField`), `data_inicio` (`DateField`), `responsavel_grupo` (`CharField`), `motivo_criacao` (`TextField`), `renda_obtida` (`DecimalField` ou `CharField` — ver nota), `historico_editais` (`TextField`).

> Nota sobre `renda_obtida`: se houver necessidade de cálculo/ordenação, usar `DecimalField(max_digits=..., decimal_places=2, null=True, blank=True)`. Se for texto livre da entrevista, `CharField`. Padrão recomendado: `DecimalField` nulo.

**Endereço completo (NUNCA público — a sede pode ser a casa de alguém):**

`logradouro`, `numero`, `complemento`, `cep` (todos `CharField`, `blank=True`).

**Controle e classificação:**

| Campo | Tipo | Regras |
|---|---|---|
| `ativo` | `BooleanField` | **default `True`**; **controla a visibilidade pública** (a API lista só ativos por padrão). **Indexar.** |
| `situacao` | `CharField` | rótulo cadastral informativo (ex. "regular", "em transição"); **independente** de `ativo`. Sugestão: `choices` com default "regular", mas texto livre é aceitável. |
| `categorias` | `ManyToManyField(Categoria, related_name="coletivos")` | um coletivo pode ter várias |

**Metadados:** `nome_entrevistador` (`CharField`, blank), `observacoes` (`TextField`, blank), `criado_em` (`auto_now_add`), `atualizado_em` (`auto_now`).

**Pontos-chave a não perder:**
- `ativo` **≠** `situacao`: um coletivo pode estar "em transição" **e** continuar `ativo=True` (visível). São campos ortogonais.
- `bairro` é público; `logradouro`/`cep`/endereço completo **nunca**.
- Contatos são **condicionais**: o campo existe sempre; a flag decide a exposição (a poda é feita no serializer, fatia seguinte — aqui só garantir campo + flag + defaults).

`Meta.ordering = ["nome"]`; índices em `slug`, `bairro`, `ativo`.

### 6.3. Pessoa — quem compõe o coletivo

**Nenhum dado de Pessoa é exposto na interface pública, em nenhuma hipótese.** Toda Pessoa pertence a um Coletivo (**FK obrigatória**).

- **Relação:** `coletivo = ForeignKey(Coletivo, on_delete=PROTECT ou CASCADE, related_name="pessoas")`.
  > Recomendação: `on_delete=models.PROTECT` para não apagar pessoas por acidente ao remover um coletivo; decidir no PR e registrar. (`CASCADE` é aceitável se a equipe preferir remoção conjunta.)
- **Identificação:** `nome`, `nome_social`, `data_nascimento` (`DateField`), `cpf`, `rg`, `rne_crnm`, `naturalidade`, `estado_civil`.
- **Contato:** `email`, `instagram`, `facebook`, `site`, `telefone` (preferência WhatsApp).
- **Endereço:** `cep`, `logradouro`, `bairro`, `municipio`, `estado`.
- **Escolaridade:** `escolaridade`.
- **Empreendimento individual (quando houver):** `empreendimento_individual` (`CharField`/`TextField`, blank) — atributo da pessoa, **não** entidade própria.
- **Bloco socioeconômico e de identidade (DADOS SENSÍVEIS — só back-office):** `cor_raca` (autodeclaração), `sexo`, `identidade_genero`, `orientacao_sexual`, `pessoa_com_deficiencia` (`BooleanField`) + `qual_deficiencia`, `renda_familiar`, `rede_protecao_social`, `participacao_programas_sociais`.
- **Metadados:** `criado_em`, `atualizado_em`.

> Campos livres devem ser `blank=True` (e `null=True` quando não-string) para caber na realidade do cadastro. Os sensíveis existem **apenas** no modelo/back-office e **nunca** serão declarados em serializer público (garantia da fatia seguinte).

### 6.4. Evento (+ ImagemEvento)

Agenda da ES divulgada na interface pública (feiras, encontros, formações), mantida pelo administrador. Segue o padrão de leitura pública na fatia de API. **Inclui galeria de imagens de divulgação.**

**Evento:**

| Campo | Tipo | Regras |
|---|---|---|
| `titulo` | `CharField` | obrigatório |
| `slug` | `SlugField(unique=True)` | indexado |
| `descricao` | `TextField` | opcional |
| `data_inicio` | `DateTimeField` | obrigatório |
| `data_fim` | `DateTimeField` | opcional (`null=True, blank=True`) |
| `local` | `CharField` | opcional |
| `bairro` | `CharField` | opcional |
| `link` | `URLField` | opcional |
| `ativo` | `BooleanField` | default `True` |
| `criado_em` / `atualizado_em` | datetime | auto |

**ImagemEvento** (galeria — permite um slide de imagens ou apenas uma):

| Campo | Tipo | Regras |
|---|---|---|
| `evento` | `ForeignKey(Evento, on_delete=CASCADE, related_name="imagens")` | ao apagar o evento, apaga as imagens |
| `imagem` | `ImageField(upload_to="eventos/")` | armazenada no Storage do Supabase |
| `legenda` | `CharField` | opcional |
| `ordem` | `PositiveIntegerField(default=0)` | controla a sequência do slide |
| `criado_em` | datetime | auto |

`ImagemEvento.Meta.ordering = ["ordem", "id"]`. As imagens são **públicas** (material de divulgação, não dado pessoal).

### 6.5. Ponto de Interesse — o que aparece no mapa

Entidade **separada** do Coletivo. **Única entidade autorizada a ser georreferenciada publicamente.** Cadastrada pelo administrador.

| Campo | Tipo | Regras |
|---|---|---|
| `nome` | `CharField` | obrigatório |
| `tipo` | `CharField(choices=...)` | enum: `orgao_es` / `loja_fisica` / `feira_arariboia` (usar `TextChoices`) |
| `descricao` | `TextField` | opcional |
| `latitude` | `DecimalField` | ex. `max_digits=9, decimal_places=6` |
| `longitude` | `DecimalField` | ex. `max_digits=9, decimal_places=6` |
| `endereco` | `CharField` | exibição pública **opcional** (aqui o endereço PODE ser público, pois é ponto de referência da ES, não sede de coletivo) |
| `imagem_capa` | `ImageField(upload_to="pontos-de-interesse/", null=True, blank=True)` | **uma** capa opcional, no Storage; exibida ao clicar no ponto |
| `coletivo` | `ForeignKey(Coletivo, null=True, blank=True, on_delete=SET_NULL, related_name="pontos")` | opcional — quando um coletivo tem ponto físico próprio |
| `ativo` | `BooleanField` | default `True` |
| `criado_em` / `atualizado_em` | datetime | auto |

`TextChoices` sugerido:

```python
class TipoPonto(models.TextChoices):
    ORGAO_ES = "orgao_es", "Órgão da Economia Solidária"
    LOJA_FISICA = "loja_fisica", "Loja física"
    FEIRA_ARARIBOIA = "feira_arariboia", "Feira do Circuito Arariboia"
```

### 6.6. Relações (resumo — validar no teste)

- Uma **Pessoa** pertence a um **Coletivo** (FK obrigatória); um Coletivo tem muitas Pessoas.
- Um **Coletivo** tem uma ou mais **Categorias** (M2M).
- Um **Evento** tem zero ou mais **ImagemEvento** (galeria/slide).
- Um **Ponto de Interesse** é independente do Coletivo (FK opcional) e tem **uma** capa opcional.
- Latitude/longitude vivem **só** no Ponto de Interesse — **nunca** no Coletivo.

### 6.7. Organização do app

**Um único app de domínio `rede`.** Se `models.py` ficar grande, dividir internamente em pacote `rede/models/` (`usuario.py`, `categoria.py`, `coletivo.py`, `pessoa.py`, `evento.py`, `ponto_interesse.py`) com um `__init__.py` que reexporta tudo — **sem** fragmentar em múltiplos apps (evita sobre-engenharia). Manter `models.py` único também é aceitável nesta fatia.

---

## 7. Storage de imagens (Supabase Storage)

O `settings.py` já traz o bloco `STORAGES` (django-storages, backend S3-compatível) sob a flag `DJANGO_USE_S3`. Esta fatia **ativa e valida** o caminho de upload.

- **Ativação:** `DJANGO_USE_S3=True` no `.env`, com `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL` (`https://SEU_REF.supabase.co/storage/v1/s3`), `AWS_S3_REGION_NAME` (default `sa-east-1`).
- **Bucket:** dedicado no Supabase Storage (ex. `divulgacao`), com **leitura pública** das imagens (não são dados pessoais). Uploads organizados por prefixo (`eventos/`, `pontos-de-interesse/`) — já refletido nos `upload_to`.
- **Todo upload passa pelo Django** (não há escrita direta do cliente).
- **Dev local:** com `DJANGO_USE_S3=False`, as imagens caem em armazenamento local — suficiente para desenvolvimento sem tocar o Supabase.

**Teste de fumaça (obrigatório no PR B):** com `DJANGO_USE_S3=True` apontando ao Supabase, subir uma `ImagemEvento` (ou `imagem_capa`) via `manage.py shell` ou Admin, e confirmar que a **URL pública abre**. Anexar evidência ao PR. (Não precisa ser teste automatizado no CI — o CI não fala com o Supabase; ver 8.3.)

---

## 8. Testes desta fatia (PR C)

Escopo enxuto: esta fatia entrega **models + conexão + storage**, então o teste automatizado cobre **models e constraints**, não serialização (que é da fatia seguinte).

### 8.1. Núcleo de teste de models

Com `pytest` + `pytest-django`, cobrir:

1. Criar `Coletivo` com `slug` e garantir **unicidade** (`slug` duplicado levanta erro).
2. Default de `ativo` é `True`.
3. `situacao` **independe** de `ativo` (setar `situacao="em transição"` mantém `ativo=True`).
4. Criar `Pessoa` **exige** `coletivo` (FK obrigatória).
5. M2M `Coletivo.categorias` funciona (associar duas categorias, contar).
6. `Evento` aceita zero ou mais `ImagemEvento`, ordenadas por `ordem`.
7. `PontoDeInteresse` aceita `coletivo=None` e `tipo` restrito às choices.

### 8.2. O que NÃO testar aqui

Serializers, endpoint `/api/coletivos/`, omissão de contato por consentimento e o teste de regressão de LGPD de serialização — **tudo isso é da fatia seguinte**. Não antecipar.

### 8.3. CI

O CI (já existente) roda `ruff` → `makemigrations --check --dry-run` → `pytest` num **Postgres de container do runner** (não usa Supabase). O teste de storage/Supabase é validação **manual** no PR (fumaça), pois o CI não tem credenciais nem deve falar com o Supabase.

---

## 9. Checklist de aceite (para marcar no PR)

- [ ] `AUTH_USER_MODEL = "rede.Usuario"` e `0001_initial` contém só o `Usuario`.
- [ ] Models Categoria, Coletivo, Pessoa, Evento, ImagemEvento, Ponto de Interesse criados com os campos deste PRD.
- [ ] `slug` único e indexado em Coletivo, Categoria, Evento; índices em `Coletivo.bairro` e `Coletivo.ativo`.
- [ ] `ativo` default `True`; `situacao` independente de `ativo`.
- [ ] Pessoa com FK obrigatória a Coletivo; nenhum vazamento de sensível criado (não há serializer nesta fatia).
- [ ] `makemigrations --check --dry-run` limpo.
- [ ] `docker compose up --build` aplica migrations no Postgres local.
- [ ] Migration real no Supabase via conexão direta (5432) — evidência anexada.
- [ ] Leitura/escrita em runtime via pooler (6543) — evidência anexada.
- [ ] Upload de imagem ao Supabase Storage funciona e a URL pública abre — evidência anexada.
- [ ] Teste de models passa; CI verde (lint + migrations-check + pytest).
- [ ] Conventional Commits; PR revisado; `main`/`staging` protegidas.

---

## 10. Instruções para o Claude Code (como executar)

1. Trabalhar **dentro de `apps/ecosol-backend`** (é o repositório Git independente).
2. **Não** reescrever `config/settings.py` além de adicionar `AUTH_USER_MODEL`. A lógica de conexão (pooler/direct) e o bloco de Storage **já estão prontos** — apenas usá-los.
3. Seguir a ordem de PRs da Seção 4 (Usuário → Models → Teste). Um PR por branch, Conventional Commits.
4. Gerar migrations com `makemigrations rede`; nunca editar tabela pelo painel do Supabase.
5. Rodar o ambiente local com `docker compose up --build` a partir de `infra/` para validar o esquema antes de tocar o Supabase.
6. Para a validação real do Supabase, usar um `.env` local com as credenciais (nunca commitar). Migrations com `DJANGO_DB_DIRECT=True`; runtime com `DJANGO_DB_POOLER=True`.
7. Registrar no corpo de cada PR as evidências pedidas na Seção 9 (logs/prints de migration real, runtime via pooler e upload ao Storage).
8. Manter tudo em português (models, verbose_name, docstrings, mensagens de commit) — requisito de Tecnologia Social do projeto.

---

*Fatia derivada da Seção 11, item 1 do PRD Técnico v4.1 e dos PRs 2–3 do PRD de Implementação Backend v1.1. Não altera nenhuma decisão de arquitetura já validada; apenas a executa. As fatias seguintes: serializers + endpoint `/api/coletivos/` com teste de regressão de LGPD, depois Django Admin, depois frontend Next.js.*
