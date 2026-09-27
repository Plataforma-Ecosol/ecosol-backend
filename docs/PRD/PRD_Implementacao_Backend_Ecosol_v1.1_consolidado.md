# PRD de Implementação — Backend (Próximo Passo)

**Projeto:** Plataforma de Rede da Economia Solidária de Niterói
**Centro Público de Referência em Economia Solidária (Casa Paul Singer) · ITES / IFRJ Campus Niterói**

| | |
|---|---|
| **Documento** | PRD de Implementação — Fase 1 (Backend primeiro) |
| **Versão** | 1.1 (consolidada — definições validadas) |
| **Deriva de** | PRD Técnico v4.0 (Arquitetura e Requisitos) |
| **Escopo** | Estrutura do monorepo + Django + Models + endpoint `/api/coletivos/` + teste de regressão LGPD + Docker + CI |
| **Meta** | MVP integrado previsto para agosto/2026 |
| **Status** | ✅ Definições fechadas — pronto para desenvolvimento |

---

## 0. Objetivo deste documento

Este PRD detalha **como** implementar os itens 1–3 da Seção 11 do PRD Técnico v4 ("backend primeiro", endpoint de Coletivos com teste de LGPD, e configuração de repositórios/CI). Ele traduz as decisões de arquitetura já validadas em um plano concreto de estrutura de pastas, modelos, contrato de API, testes, empacotamento e integração contínua.

Todas as decisões abertas na versão anterior foram **validadas e incorporadas ao corpo do documento**. Uma decisão nova em relação ao v4 está consolidada aqui e destacada como tal: a adoção de uma estrutura **umbrella (monorepo lógico) com repositórios Git independentes por app** (Seção 1). A Seção 11 define os critérios de aceite (Definition of Done) e a Seção 10 a ordem de execução.

---

## 1. Estrutura do projeto — monorepo umbrella com repositórios Git independentes

> **Decisão nova (consolida/atualiza o v4).** O PRD Técnico v4 previa "repositórios separados". Mantemos essa separação, mas passamos a organizá-la sob uma pasta umbrella comum, `ecosol-fullstack`, que agrupa os apps localmente sem fundir os históricos Git. Cada app permanece um repositório independente, com commits, PRs, CI e deploy próprios.

### 1.1. Layout de diretórios

```
ecosol-fullstack/                 # pasta umbrella (organização local, NÃO versionada)
├── apps/
│   ├── backend/                  # repositório Git independente → GitHub: ecosol-backend
│   │   ├── .git/
│   │   ├── config/               # projeto Django (settings, urls, wsgi/asgi)
│   │   ├── rede/                 # app Django único de domínio (ver 4.8)
│   │   ├── tests/
│   │   ├── manage.py
│   │   ├── requirements.txt
│   │   ├── requirements-dev.txt
│   │   ├── Dockerfile
│   │   ├── .env.example
│   │   ├── .github/workflows/ci.yml
│   │   └── README.md
│   └── frontend/                 # repositório Git independente → GitHub: ecosol-frontend
│       └── .git/                 # (fase 2 — placeholder nesta fase)
├── infra/
│   └── docker-compose.yml        # orquestra backend + Postgres local para desenvolvimento
├── docs/
│   ├── PRD_Tecnico_Ecosol_Niteroi_v4.pdf
│   └── PRD_Implementacao_Backend_v1.1.md   (este documento)
└── README.md                     # visão geral da umbrella e como clonar cada repo
```

### 1.2. Estratégia Git — umbrella não versionada

`ecosol-fullstack/` é **apenas uma pasta local de organização**; **não é** um repositório Git e não versiona o código dos apps. Cada `apps/*` tem seu próprio `.git` e seu próprio repositório remoto no GitHub, e é clonado independentemente. Um `README.md` na raiz da umbrella documenta os repositórios e os comandos de clone; as pastas `docs/` e `infra/` guardam material compartilhado (documentação e orquestração local).

Assim, **commits, branches, PRs e CI acontecem dentro de cada app** — sem submódulos e sem acoplamento de históricos. Nesta fase, só `apps/backend` recebe código; `apps/frontend` fica como repositório vazio/placeholder para a fase 2.

### 1.3. Deploy (coerente com a arquitetura desacoplada)

Mesmo sob a umbrella, o deploy é independente por app: Render/Railway aponta para o repositório `ecosol-backend`; Vercel apontará para `ecosol-frontend` na fase 2; banco e storage no Supabase. Nenhum serviço precisa enxergar a umbrella.

---

## 2. Stack e versões (backend)

| Camada | Tecnologia | Versão-alvo | Papel |
|---|---|---|---|
| Linguagem | Python | 3.12 | Runtime |
| Framework | Django | 5.x LTS mais recente estável | Esquema, auth, admin, ORM |
| API | Django REST Framework (DRF) | 3.15+ | Serialização e endpoints REST |
| Filtros | django-filter | 24+ | Filtros de query (`categoria`, `bairro`, `ativo`) |
| Driver DB | psycopg | 3.x | Conexão PostgreSQL |
| Storage | django-storages + boto3 | atual | Upload de imagens ao Storage do Supabase (S3-compatível) |
| Processamento de imagem | Pillow | atual | Suporte a `ImageField` |
| Servidor WSGI | gunicorn | atual | Produção |
| Testes | pytest + pytest-django | atual | Testes unitários e de regressão |
| Lint/format | ruff | atual | Padronização de código |
| Config | django-environ (ou os.environ) | atual | Variáveis de ambiente |

**Gestão de dependências:** `requirements.txt` (produção) + `requirements-dev.txt` (testes/lint), com versões fixadas (pinned) na última estável compatível no momento do desenvolvimento.

---

## 3. Configuração do Django e conexão com o Supabase

Arquitetura **Django-cêntrica** (decisão 8.2 do v4): o Django é dono do esquema, da autenticação e das permissões. Supabase entra **apenas** como Postgres gerenciado + Storage — sem Auth, RLS, PostgREST ou Edge Functions.

### 3.1. Duas conexões (ponto de atrito conhecido do pooler)

O v4 registra que o **modo de transação do pooler do Supabase tem atrito com prepared statements do Django**. A implementação trata isso separando as conexões:

- **App (runtime):** usa o **pooler em modo transação** (porta `6543`). No Django, isso exige desativar cursores server-side e prepared statements:
  - `DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True`
  - `OPTIONS` do psycopg com `prepare_threshold=None` (desativa prepared statements).
- **Migrations:** usam a **conexão direta** (porta `5432`), sem pooler, via a variável separada `DATABASE_DIRECT_URL`. Um alvo dedicado garante que `migrate` não passe pelo pooler.

> Configuração validada na primeira conexão real contra a instância do Supabase (parte do PR de scaffold/models).

### 3.2. Migrations como única fonte de esquema

Ninguém edita tabela pelo painel do Supabase. Toda mudança de esquema passa por migration do Django, versionada no repositório (reforça 8.2).

### 3.3. Storage de imagens (ativo desde esta fase)

`django-storages` com backend S3-compatível apontando para o **Storage do Supabase**. Todo upload passa pelo Django (não há escrita direta do cliente). O storage é configurado **já nesta fase**, pois será usado para **imagens de divulgação de Eventos** (galeria/slide) e para a **capa de Pontos de Interesse** (ver 4.4 e 4.5).

- `DEFAULT_FILE_STORAGE` apontando para o backend S3 do django-storages.
- Bucket dedicado no Supabase Storage; leitura pública das imagens de divulgação (não são dados pessoais).
- Uploads organizados por prefixo (`eventos/`, `pontos-de-interesse/`).

### 3.4. Variáveis de ambiente (`.env`, nunca commitado)

```
DJANGO_SETTINGS_MODULE=config.settings
DJANGO_SECRET_KEY=...
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,<host-de-deploy>
DATABASE_URL=postgres://...@<pooler-host>:6543/postgres        # app (transação)
DATABASE_DIRECT_URL=postgres://...@<direct-host>:5432/postgres  # migrations
# Storage (Supabase, S3-compatible)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=...
AWS_S3_ENDPOINT_URL=...
```

Um `.env.example` (sem segredos) é commitado como documentação.

---

## 4. Modelo de dados

Fonte: Seção 4 do v4. As entidades principais são **Pessoa, Coletivo, Categoria, Evento e Ponto de Interesse**. Convenções: chaves em `snake_case`, datas ISO 8601, `criado_em`/`atualizado_em` em toda entidade.

> **Regra de negócio que NÃO vira código (v4, 4.1):** "coletivo válido tem no mínimo 3 pessoas e é interfamiliar" é verificação **humana** da equipe do Centro Público. O software não valida isso; se o administrador cadastrou, o coletivo é válido. Por isso "família" **não** é entidade do modelo.

### 4.1. Coletivo — o nó da rede

Unidade central e **única entidade exibida na listagem pública**.

| Campo | Tipo | Visibilidade | Observação |
|---|---|---|---|
| `id` | PK | público | |
| `nome` | char | público | |
| `slug` | slug (único) | público | identificador para URL (ex.: `sementes-do-vale`); **usado no detalhe da API e nas URLs do frontend** |
| `descricao` | text | público | |
| `bairro` | char | **público** | dá contexto geográfico sem revelar endereço |
| `site` | url | público | |
| `telefone` | char | **condicional** | só sai na API se `exibir_telefone_publicamente=True` |
| `email` | email | **condicional** | só sai se `exibir_email_publicamente=True` |
| `instagram` | char | **condicional** | só sai se `exibir_instagram_publicamente=True` |
| `exibir_telefone_publicamente` | bool | administrativo | flag de consentimento |
| `exibir_email_publicamente` | bool | administrativo | flag de consentimento |
| `exibir_instagram_publicamente` | bool | administrativo | flag de consentimento |
| `cnpj` | char | administrativo | dado cadastral |
| `data_inicio` | date | administrativo | |
| `responsavel_grupo` | char | administrativo | |
| `motivo_criacao` | text | administrativo | |
| `renda_obtida` | decimal/char | administrativo | |
| `historico_editais` | text | administrativo | se contemplado e em que ano |
| `logradouro` | char | **NUNCA público** | endereço completo — blindado (a sede pode ser a casa de alguém) |
| `numero`, `complemento`, `cep` | char | **NUNCA público** | idem |
| `ativo` | bool | administrativo | **controla a visibilidade pública**; API lista só ativos por padrão |
| `situacao` | char | administrativo | rótulo cadastral informativo (ex.: "regular", "em transição"); **independente** de `ativo` |
| `categorias` | M2M → Categoria | público | um coletivo pode ter várias |
| `criado_em`, `atualizado_em` | datetime | metadados | |
| `nome_entrevistador` | char | administrativo | metadado |
| `observacoes` | text | administrativo | metadado |

Pontos-chave: **`ativo` ≠ `situacao`** (um coletivo pode estar "em transição" e ainda ativo/visível). **`bairro` é público; `logradouro` nunca.** Contatos são **condicionais por consentimento** (Seção 5).

### 4.2. Pessoa — quem compõe o coletivo

**Nenhum dado de Pessoa é exposto na interface pública, em nenhuma hipótese.** Toda Pessoa pertence a um Coletivo (FK obrigatória).

- **Identificação:** `nome`, `nome_social`, `data_nascimento`, `cpf`, `rg`, `rne_crnm`, `naturalidade`, `estado_civil`
- **Contato:** `email`, `instagram`, `facebook`, `site`, `telefone` (preferência WhatsApp)
- **Endereço:** `cep`, `logradouro`, `bairro`, `municipio`, `estado`
- **Escolaridade:** `escolaridade`
- **Empreendimento individual (quando houver):** `empreendimento_individual` — atributo da pessoa, não entidade de rede própria (reflete transição de empreendedor individual para dentro de coletivos)
- **Bloco socioeconômico e de identidade (DADOS SENSÍVEIS):** `cor_raca` (autodeclaração), `sexo`, `identidade_genero`, `orientacao_sexual`, `pessoa_com_deficiencia` (+ `qual_deficiencia`), `renda_familiar`, `rede_protecao_social`, `participacao_programas_sociais`
- **Relação:** `coletivo` (FK)
- **Metadados:** `criado_em`, `atualizado_em`

> Os dados sensíveis existem só no back-office e **nunca são declarados em nenhum serializer público** (blindagem na origem — Seção 5).

### 4.3. Categoria / Segmento

Classifica os coletivos (artesanato, alimentação, agroecologia, serviços, etc.). **Principal eixo de busca e filtro público.**

- Campos: `id`, `nome`, `slug`
- Relação: M2M com Coletivo

### 4.4. Evento

Agenda da ES divulgada na interface pública (feiras, encontros, formações), mantida pelo administrador. Segue o mesmo padrão de endpoint público de leitura, com **galeria de imagens de divulgação**.

- **Evento:** `id`, `titulo`, `slug`, `descricao`, `data_inicio` (datetime), `data_fim` (datetime, opcional), `local` (char), `bairro` (opcional), `link` (opcional), `ativo` (bool), `criado_em`, `atualizado_em`
- **ImagemEvento** (entidade relacionada — permite um slide de imagens ou apenas uma): `id`, `evento` (FK → Evento), `imagem` (ImageField no Storage), `legenda` (char, opcional), `ordem` (int — controla a sequência do slide), `criado_em`

> No serializer público, o Evento expõe suas imagens como uma **lista ordenada de URLs** (com legenda opcional). Um único registro de imagem produz "apenas uma imagem"; vários produzem o slide.

### 4.5. Ponto de Interesse — o que aparece no mapa

Entidade **separada** do Coletivo. **Única entidade autorizada a ser georreferenciada publicamente.** Cadastrada pelo administrador.

- Campos: `id`, `nome`, `tipo` (enum: `orgao_es` / `loja_fisica` / `feira_arariboia`), `descricao`, `latitude`, `longitude`, `endereco` (exibição pública opcional), `imagem_capa` (ImageField no Storage — **uma imagem de capa de divulgação**, exibida ao clicar no ponto), `coletivo` (FK opcional, quando um coletivo tem ponto físico próprio), `ativo`, `criado_em`, `atualizado_em`

> `imagem_capa` é opcional e única por ponto. Ao clicar no ponto no mapa, o frontend exibe a capa junto com nome/descrição/contato.

### 4.6. Usuário

Modelo de usuário customizado do Django (recomendado desde o início do projeto) para os papéis **Administrador** e **Público Geral**. Como não há autocadastro, na prática as contas com login são as da equipe administrativa. Configurado como `AUTH_USER_MODEL` já na primeira migration.

### 4.7. Relações (resumo)

- Uma **Pessoa** pertence a um **Coletivo**; um Coletivo tem muitas Pessoas.
- Um **Coletivo** tem uma ou mais **Categorias** (M2M).
- Um **Evento** tem zero ou mais **ImagemEvento** (galeria/slide).
- Um **Ponto de Interesse** é independente do Coletivo (pode, opcionalmente, referenciá-lo) e tem uma capa opcional.
- **Eventos** são independentes, mantidos pelo administrador.
- Fora do MVP: registro de conexões/parcerias entre coletivos como entidade própria.

### 4.8. Organização do app Django

**Um único app de domínio `rede`** contém todos os models, admin, serializers e views. Se o tamanho justificar, os arquivos são organizados internamente por assunto (`models/coletivo.py`, `models/pessoa.py`, `models/evento.py`, `models/mapa.py`, etc.), sem fragmentar em múltiplos apps — evitando sobre-engenharia (requisito não funcional do v4). Extração para apps separados fica como refactor futuro, se necessário.

---

## 5. Serializers e blindagem LGPD

A proteção de dados é **requisito de projeto**, garantido na camada de serialização (Seção 6 do v4).

### 5.1. Blindagem na origem

- Serializers públicos declaram campos **explicitamente**, **nunca** `fields = '__all__'`. Um refactor futuro não reintroduz vazamento por acidente.
- **Nenhum dado de Pessoa** é exposto em rota pública. A interface pública opera apenas sobre o subconjunto público do Coletivo.
- **`bairro` sim, `logradouro`/endereço não.**
- Dados sensíveis (cor/raça, identidade de gênero, orientação sexual, saúde/deficiência, situação socioeconômica) **não são sequer declarados** nos serializers públicos.

### 5.2. Contatos por consentimento (estratégia de omissão de chave)

Cada contato (`telefone`, `email`, `instagram`) **só entra na resposta se a flag de consentimento correspondente for verdadeira**. Sem consentimento, **a chave é omitida** do JSON — **não retorna como `null`**.

> **Por quê omitir em vez de `null`:** retornar `null` comunicaria "existe um dado aqui, mas foi escondido". Omitir a chave é a aplicação prática da minimização: o consumidor da API não recebe sequer o indício de que há um dado. No frontend, isso se reflete em tipos TypeScript opcionais (`telefone?: string`), e não `string | null`.

Implementação: método `to_representation` no serializer do Coletivo que remove as chaves de contato sem consentimento após a serialização base — mantendo os campos declarados explicitamente, mas podados conforme as flags.

### 5.3. Serializer explícito do Coletivo (campos públicos)

Campos que **saem** na API pública: `id`, `nome`, `slug`, `descricao`, `bairro`, `site`, `categorias` (lista de `{id, nome, slug}`), `criado_em`, `atualizado_em`, e — **condicionalmente** — `telefone`, `email`, `instagram`.

Campos que **nunca** saem: qualquer dado de Pessoa, `logradouro`/endereço, dados cadastrais administrativos, `situacao`, `observacoes`, flags de consentimento.

> As imagens de Evento e a capa de Ponto de Interesse **são públicas** (material de divulgação, não dados pessoais) e entram nos serializers dessas entidades na fase seguinte, seguindo o mesmo padrão explícito.

---

## 6. Contrato da API pública — endpoint de Coletivos

Implementa a Seção 9 do v4. Serve de **modelo para os demais** endpoints (Eventos e Pontos de Interesse na fase seguinte). Todo endpoint público é **somente leitura** (`GET`) e `AllowAny`.

### 6.1. Convenções

- Chaves em `snake_case`; datas em ISO 8601 (`AAAA-MM-DD` / datetime ISO).
- Respostas de lista usam o envelope de paginação do DRF: `count`, `next`, `previous`, `results`.
- Paginação: `page_size` padrão **20**, máximo **100**.

### 6.2. Endpoints

| Método e path | Descrição | Permissão |
|---|---|---|
| `GET /api/coletivos/` | Lista paginada de coletivos **ativos**. | Público (AllowAny) |
| `GET /api/coletivos/{slug}/` | Detalhe de um coletivo, **buscado por `slug`**. | Público (AllowAny) |

> O detalhe usa `slug` como `lookup_field` (ex.: `/api/coletivos/sementes-do-vale/`), casando com as URLs do frontend (perfil por slug, Seção 11.5 do v4). `slug` é único e indexado.

### 6.3. Parâmetros de consulta (listagem)

| Parâmetro | Tipo | Descrição | Obrigatório |
|---|---|---|---|
| `q` | string | Busca textual em nome e descrição (case-insensitive) | Não |
| `categoria` | int | Filtra pelo id de uma Categoria (M2M) | Não |
| `bairro` | string | Filtra por bairro (valor público, não logradouro) | Não |
| `ativo` | bool | Default: apenas `ativo=true` | Não |
| `ordering` | string | `nome`, `-nome`, `criado_em`, `-criado_em` | Não |
| `page` | int | Número da página (default 1) | Não |
| `page_size` | int | Itens por página (default 20, máx 100) | Não |

### 6.4. Campos da resposta (Coletivo)

Institucionais: `id`, `nome`, `slug`, `descricao`, `bairro`, `site`. Relacionamento: `categorias` (lista, cada uma com `id`/`nome`/`slug`). Datas: `criado_em`, `atualizado_em`. Contatos condicionais (só com consentimento, senão a chave é omitida): `telefone`, `email`, `instagram`.

### 6.5. Erros

| Código | Quando ocorre |
|---|---|
| `400` | Tipo inválido em parâmetro (ex.: `categoria=texto` onde se espera número) |
| `404` | Recurso inexistente (slug não encontrado), ou página fora da faixa (comportamento nativo do DRF) |

### 6.6. Desempenho

Listagens respondem em **< 500 ms**, apoiadas por paginação, índices e consultas sem N+1 (`select_related`/`prefetch_related` para `categorias`). Índices em `slug`, `bairro`, `ativo` e no campo de ordenação.

---

## 7. Testes e integração contínua

### 7.1. Teste de regressão de LGPD (garantia viva)

Teste automatizado que verifica:

1. **(a)** contatos **sem** consentimento são **omitidos** (chave ausente — e não `null`);
2. **(b)** contatos **com** consentimento **aparecem**;
3. **(c)** endereço/`logradouro` e dados sensíveis **nunca** são serializados;
4. **(d)** nenhum dado de Pessoa aparece na resposta pública.

Este teste é a documentação viva da promessa de privacidade: qualquer contribuição que exponha um campo sensível quebra a suíte antes de chegar à produção. Ele **integra o CI** e é bloqueante.

### 7.2. Núcleo mínimo de testes

Cobertura do núcleo: **models** (constraints, relações, defaults de `ativo`, `slug` único), **serializers** (campos explícitos, omissão de contato) e **rotas principais** (listagem, filtros `q`/`categoria`/`bairro`, paginação, ordering, detalhe por slug, erros 400/404, `AllowAny` na leitura e bloqueio de escrita sem sessão).

Ferramenta: `pytest` + `pytest-django`. Meta de execução: rápida o suficiente para rodar em todo PR.

### 7.3. GitHub Actions (CI)

A cada pull request, o CI roda os testes. **PR com teste quebrado não pode ser mesclado em `main` nem `staging`.** Assim, código quebrado — ou um vazamento de dado sensível — não entra no projeto.

Pipeline do backend (`.github/workflows/ci.yml`): checkout → setup Python 3.12 → instalar dependências → `ruff` (lint) → `python manage.py makemigrations --check --dry-run` (garante migrations em dia) → `pytest`. Banco de teste em container Postgres do próprio runner (não usa Supabase no CI).

---

## 8. Empacotamento (Docker)

Docker desde o início (decisão 8.5 do v4). Nesta fase entram o **backend** e um **Postgres local isolado** para desenvolvimento; o placeholder do Next.js entra no compose na fase 2.

- **`apps/backend/Dockerfile`:** imagem Python 3.12-slim, instala dependências, roda `gunicorn` em produção e `runserver` em dev.
- **`infra/docker-compose.yml`:** serviços `backend` e `db` (**Postgres em container, isolado**) para desenvolvimento local — permite subir o ambiente com um comando, **sem tocar o Supabase durante o desenvolvimento**. Homologação/produção usam as variáveis de ambiente apontando para o Supabase.

Benefício futuro (v4): por já estar em Docker, migrar para VPS e auto-hospedagem é possível sem reescrever nada.

---

## 9. Fluxo Git, branches e commits (por repositório)

Aplicado **dentro de cada repositório** (nesta fase, `ecosol-backend`). Fonte: Seção 10 do v4.

- **`main` protegida:** não recebe push direto; só via pull request revisado e aprovado.
- **`staging`:** ambiente de homologação/beta, com deploy próprio, assim como `main`.
- **Branches por tarefa:** `feat/`, `fix/`, `docs/`, `refactor/`, `test/` (ex.: `feat/model-coletivo`).
- **Pull request com revisão obrigatória:** ao menos uma revisão antes do merge; o PR descreve o que muda e por quê; alterações visuais incluem evidências (screenshots).
- **Conventional Commits:** `tipo: descrição` (ex.: `feat: adiciona endpoint de coletivos`) — permite histórico e changelog automáticos.
- **Licença:** GPLv3 em cada repositório, com documentação em português.

---

## 10. Configuração de repositórios no GitHub

- **Organização no GitHub:** **Plataforma Ecosol**, agregando os repositórios.
- **`ecosol-backend`** criado sob GPLv3, com: `README.md` (setup, comandos, arquitetura resumida), `.env.example`, regras de branch (`main` e `staging` protegidas, PR obrigatório) e o workflow de CI.
- **`ecosol-frontend`** criado como placeholder (GPLv3, README) para a fase 2.
- Umbrella local **`ecosol-fullstack`** (não versionada) documentando como clonar ambos.

---

## 11. Ordem de execução (sequência de PRs)

Cada item é um PR revisável e testável isoladamente:

1. **`chore: scaffold do projeto`** — estrutura de pastas, `config/` (settings por ambiente), `requirements.txt`/`requirements-dev.txt`, Dockerfile, docker-compose (backend + Postgres isolado), `.env.example`, **configuração do django-storages/Supabase Storage**, CI base (lint + testes vazios passando).
2. **`feat: usuário customizado`** — `AUTH_USER_MODEL` e primeira migration (antes de qualquer outro model, para não travar depois).
3. **`feat: models de domínio`** — Categoria, Coletivo (com slug/ativo/situacao/flags de consentimento), Pessoa (com bloco sensível), Evento + ImagemEvento, Ponto de Interesse (com `imagem_capa`); migrations; conexão ao Supabase validada.
4. **`feat: Django Admin`** — registro dos models no Admin com controle de `ativo`, `situacao` e visibilidade de cada contato; inline de imagens do Evento e upload de capa do Ponto de Interesse (substitui a planilha).
5. **`feat: serializer + endpoint de coletivos`** — serializer explícito com omissão de contato, ViewSet somente-leitura, filtros/busca/ordering/paginação, rotas `/api/coletivos/` e detalhe por slug.
6. **`test: regressão LGPD + núcleo`** (**PR próprio**) — a suíte da Seção 7, integrada ao CI como bloqueante.
7. **`docs: LGPD a documentar antes do uso real`** (**PR próprio**) — base legal, política de retenção e procedimento para solicitações de titulares (v4, 6.4). Documento, não código.

Após esta fase, replica-se o padrão do endpoint para **Eventos** (com galeria de imagens) e **Pontos de Interesse** (com capa), e inicia-se o **frontend Next.js** (fase 2).

---

## 12. Critérios de aceite (Definition of Done desta fase)

A fase é considerada concluída quando:

1. A estrutura umbrella existe (pasta local não versionada), com `apps/backend` como repositório Git independente e `apps/frontend` como placeholder.
2. O projeto Django sobe localmente via `docker-compose up` com um comando, usando Postgres isolado em container.
3. Os Models (Usuário customizado, Categoria, Coletivo, Pessoa, Evento + ImagemEvento, Ponto de Interesse com capa) estão criados, com migrations versionadas, e o Django conecta ao Postgres do Supabase (app via pooler; migrations via conexão direta).
4. O `django-storages`/Supabase Storage está configurado e aceita upload de imagens de Evento e capa de Ponto de Interesse pelo Admin.
5. O Django Admin permite CRUD completo e controle de `ativo`/`situacao`/consentimento, com inline de imagens de Evento.
6. `GET /api/coletivos/` e o detalhe por slug respondem conforme o contrato da Seção 6 (filtros, busca, ordering, paginação, erros 400/404), em < 500 ms e sem N+1.
7. O teste de regressão de LGPD passa e é bloqueante no CI; nenhum dado de Pessoa, endereço ou campo sensível aparece na API pública; contatos sem consentimento têm a chave omitida.
8. O CI (GitHub Actions) roda lint + checagem de migrations + testes em todo PR; `main` e `staging` estão protegidas.
9. Os repositórios estão sob a organização **Plataforma Ecosol**, sob GPLv3, com README em português e `.env.example`.

---

## 13. Fora do escopo desta fase

Frontend Next.js (fase 2); endpoints de Eventos e Pontos de Interesse (replicam o padrão depois, já com imagens); mapa Leaflet/OSM; qualquer transação (escambo, moeda Arariboia); autocadastro público; registro de parcerias entre coletivos; mensageria; exibição pública de logradouro/localização exata de coletivos; JWT (fica como evolução futura para mobile, conforme decisão 8.3).

---

*Definições validadas e consolidadas. Este documento é a base aprovada para o desenvolvimento da Fase 1, na sequência de PRs da Seção 10/11.*
