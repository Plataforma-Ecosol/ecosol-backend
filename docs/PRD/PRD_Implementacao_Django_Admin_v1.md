# PRD de Implementação — Área administrativa (Django Admin)

**Projeto:** Plataforma de Rede da Economia Solidária de Niterói
**Centro Público de Referência em Economia Solidária (Casa Paul Singer) · ITES / IFRJ Campus Niterói**

| | |
|---|---|
| **Documento** | PRD de Implementação — Fatia 3: Área administrativa (Django Admin) |
| **Versão** | 1.0 |
| **Deriva de** | PRD Técnico v4.1 (Seções 3, 5.2 e 6; Seção 11, **item 4**) e PRD de Implementação — Backend v1.1 (item 4 do mapa de PRs) |
| **Escopo** | Registro de todos os models no Django Admin — CRUD completo de Coletivo, Pessoa, Categoria, Evento (com galeria de imagens) e Ponto de Interesse; administração do usuário customizado; controle de `ativo`, `situacao` e da visibilidade de cada contato; upload de imagens; branding em português; configuração de mídia para desenvolvimento local |
| **Fora de escopo** | Qualquer alteração em serializers/endpoints públicos, endpoints de Eventos e Pontos de Interesse (fatia seguinte), frontend Next.js, permissões granulares por grupo além do papel único de Administrador, fluxo de solicitações de titulares LGPD |
| **Repositório** | `apps/ecosol-backend` (dentro da umbrella `ecosol-fullstack`) |
| **Status** | Pronto para desenvolvimento — a ser executado via Claude Code |

---

## 0. Objetivo deste documento

Este PRD detalha **como** executar o **item 4 da Seção 11 do PRD Técnico v4.1**:

> *"Área administrativa a partir do Django Admin, substituindo a planilha por um cadastro estruturado."*

No mapa de PRs do PRD de Implementação Backend v1.1, isso corresponde ao **item 4** (`feat: Django Admin` — registro dos models com controle de `ativo`, `situacao` e visibilidade de cada contato; inline de imagens do Evento e upload de capa do Ponto de Interesse). A fatia anterior — endpoint público de Coletivos e regressão de LGPD — **já está concluída** no repositório.

Esta é a fatia que **coloca a plataforma em uso real dentro do Centro Público**: é aqui que a planilha de cadastro é aposentada e os dados passam a ser inseridos de forma estruturada. É também **o cofre**: a área administrativa reúne todos os dados pessoais e sensíveis do projeto. Por isso, o cuidado aqui é menos com contrato de API e mais com **duas coisas ao mesmo tempo** — ergonomia de cadastro (a equipe vai passar horas nesta tela) e disciplina de privacidade (é daqui que se opera cada chave de visibilidade pública).

O documento é autossuficiente para ser lido por um agente (Claude Code) e transformado em código, sem reabrir os PRDs anteriores. Ele **não contradiz** nenhuma decisão validada; a Seção 10 registra as decisões próprias da fatia e explica por que **não há emendas** ao PRD Técnico v4.1.

---

## 1. Estado atual do repositório (ponto de partida)

O que **já existe** e **não deve ser refeito** (confirmado no código):

- **`rede/models/`** — pacote completo com `Usuario` (customizado, `AUTH_USER_MODEL = "rede.Usuario"`), `Categoria`, `Coletivo`, `ColetivoSlugAnterior`, `Pessoa`, `Evento`, `ImagemEvento` e `PontoDeInteresse`, todos com `verbose_name` em português, `__str__` e `Meta.ordering`. **Nenhum model muda nesta fatia** — o Admin apenas os registra.
- **`config/settings.py`** — DRF, banco (pooler/direta), `AUTH_USER_MODEL` e o bloco de Storage S3 (`DJANGO_USE_S3`) já configurados. `django.contrib.admin` já está em `INSTALLED_APPS` e `XFrameOptionsMiddleware` já protege o admin de clickjacking.
- **`config/urls.py`** — `admin/` (`admin.site.urls`), `health/` e `api/` já roteados.
- **`rede/serializers.py`, `views.py`, `filters.py`, `pagination.py`, `urls.py`** — endpoint público de Coletivos concluído. **Nada aqui é tocado nesta fatia.**
- **`tests/`** — `test_models.py`, `test_api_coletivos.py`, `test_slug_historico.py`, `test_smoke.py`.
- **CI** (`.github/workflows/ci.yml`) rodando `ruff` → `makemigrations --check --dry-run` → `pytest`, com `main` e `staging` protegidas.

O que **não existe ainda** e nasce nesta fatia:

- **`rede/admin.py`** — hoje contém apenas `"""Registros do Django Admin — entram no PR 4."""`. É o arquivo central desta fatia.
- **`MEDIA_URL` / `MEDIA_ROOT`** em `settings.py` e o serviço de mídia em `DEBUG` em `config/urls.py` — **necessários** para que o upload de `ImagemEvento` e `PontoDeInteresse.imagem_capa` funcione no ambiente local (sem S3). Sem isso, salvar uma imagem no Admin quebra. Ver Seção 5.
- **`tests/test_admin.py`** — suíte de fumaça e de guarda de LGPD do Admin (Seção 8).

> **Princípio-guia:** o Admin **não gera migration** — registrar um model no Admin não altera o esquema. Se `makemigrations --check --dry-run` acusar mudança nesta fatia, algo foi tocado que não deveria (um model). Isso é, em si, uma trava de qualidade.

---

## 2. Resultado esperado (Definition of Done da fatia)

A fatia está concluída quando **todos** os itens abaixo forem verdadeiros:

1. Um usuário administrador consegue fazer **login em `/admin/`** e ver, em português, todas as entidades: Coletivos, Pessoas, Categorias, Eventos, Pontos de Interesse e Usuários.
2. **CRUD completo** funciona para Coletivo, Pessoa, Categoria, Evento e Ponto de Interesse.
3. Na tela do Coletivo, o administrador controla `ativo`, `situacao`, as três flags de consentimento e as categorias (M2M), com cada contato **visualmente ao lado** da sua flag de consentimento.
4. O **slug** é preenchido automaticamente a partir do nome ao criar, e **permanece editável** — editá-lo alimenta o histórico de slugs (301) já existente no `save()`.
5. A tela de **Pessoa** organiza os ~25 campos em blocos legíveis, com o **bloco socioeconômico e de identidade claramente rotulado como sensível**.
6. O **Evento** edita sua **galeria de imagens inline** (`ImagemEvento`), com miniatura de pré-visualização; o **Ponto de Interesse** aceita `imagem_capa` e latitude/longitude.
7. **Upload de imagem funciona no ambiente local** do docker-compose (via `MEDIA_ROOT`/`MEDIA_URL`) e, quando `DJANGO_USE_S3=True`, via Supabase Storage — sem alteração de código.
8. O **usuário customizado** (`rede.Usuario`) está registrado com a `UserAdmin` do Django (formulário de senha com hash preservado); é possível criar novas contas da equipe pelo Admin.
9. As listagens (changelists) têm busca, filtros e colunas úteis, **sem N+1** (contagens por `annotate`, relações por `autocomplete_fields`/`list_select_related`).
10. **Nenhum atributo sensível de Pessoa** (cor/raça, identidade de gênero, orientação sexual, deficiência) é usado como `list_filter` ou coluna de `list_display` — ver Seção 4.3.
11. `ruff` passa, `makemigrations --check --dry-run` fica **limpo** (a fatia não cria migration) e o CI fica **verde**.
12. O `README.md` do backend ganha a seção **"Área administrativa"** (como acessar, criar o primeiro superusuário, e as regras de visibilidade que o Admin opera).

---

## 3. O que a área administrativa entrega (escopo funcional)

Implementa a Seção 5.2 do PRD Técnico v4.1 ("Interface Administrativa — Django Admin, com login"):

- Gestão de **usuários e papéis** (equipe do Centro Público).
- Cadastro e edição de **Pessoas**, incluindo o bloco sensível — atrás de autenticação.
- Cadastro e edição de **Coletivos**, com controle de `ativo`, `situacao` e da visibilidade de cada contato.
- Cadastro de **Categorias, Eventos e Pontos de Interesse** (com geolocalização e imagens).
- Substitui o tratamento atual (planilha) por um cadastro estruturado e robusto.

**Papéis (v4.1, Seção 3):** dois papéis — **Administrador** (equipe do Centro Público, acesso completo ao back-office) e **Público Geral** (somente leitura da interface pública, **não faz login**). No MVP, portanto, **todas as contas com acesso ao Admin são da equipe administrativa**. Não há autocadastro. Permissões granulares por grupo (limitar um usuário a só Eventos, por exemplo) existem de graça no Django, mas **não fazem parte desta fatia** — o papel único de Administrador basta para o MVP.

---

## 4. Princípios de design do Admin

A área administrativa não expõe dados publicamente (está atrás de login), mas **é a origem de tudo que um dia será público**. Três princípios regem o desenho.

### 4.1. O Admin é onde as chaves de visibilidade são operadas

O serializer público (fatia anterior) apenas **obedece** ao que o Admin definiu: `ativo` decide se o coletivo existe para o público; cada `exibir_*_publicamente` decide se aquele contato sai. Logo, o Admin tem de tornar esses interruptores **impossíveis de acionar por engano**:

- Cada contato aparece **imediatamente ao lado** da sua flag de consentimento, no mesmo bloco (`fieldset`). O administrador vê "telefone" e, na linha seguinte, "exibir telefone publicamente" — nunca um longe do outro.
- `ativo` e `situacao` ficam juntos, num bloco de "Controle e classificação", com os `help_text` dos models reforçando que são independentes.
- `ativo` entra em `list_editable` na listagem, para tirar/pôr um coletivo do ar rapidamente — a operação mais frequente da equipe.

### 4.2. Blocos legíveis para muitos campos (fieldsets)

Coletivo e Pessoa têm dezenas de campos. Jogar todos numa lista única é o que torna a planilha ruim. Cada tela é dividida em `fieldsets` que **espelham os blocos comentados no model**, na mesma ordem, com títulos em português.

### 4.3. Minimização também vale dentro do cofre

O bloco socioeconômico e de identidade de Pessoa (cor/raça, sexo, identidade de gênero, orientação sexual, deficiência, renda, programas sociais) é dado **sensível**. Mesmo internamente:

- Fica num `fieldset` **explicitamente rotulado como sensível**, para que quem cadastra saiba o peso do que está manuseando.
- **Nunca** é `list_display` nem `list_filter`. Filtrar a lista de pessoas por cor/raça ou orientação sexual transformaria o back-office numa ferramenta de segmentação por atributo protegido — exatamente o que a LGPD e o propósito do projeto rejeitam. Colunas de listagem de Pessoa se limitam a nome/nome social, coletivo e município.
- A busca de Pessoa (`search_fields`) cobre nome, nome social e CPF (identificação para localizar o registro), **não** os atributos sensíveis.

> Este princípio ganha um **teste de guarda** (Seção 8.2), no mesmo espírito do teste de regressão de LGPD do serializer: uma asserção automatizada de que nenhum campo sensível entrou em `list_display`/`list_filter` de Pessoa. É documentação viva — quebra antes de chegar à produção se alguém "melhorar" a listagem por acidente.

---

## 5. Configurações necessárias (settings e urls)

Duas alterações pequenas e localizadas, exigidas pelo upload de imagens. **Nenhuma dependência nova** — `django-storages`/`Pillow` já estão no projeto.

### 5.1. `config/settings.py` — mídia para desenvolvimento local

Abaixo do bloco de arquivos estáticos, acrescentar:

```python
# --- Arquivos de mídia (uploads) ------------------------------------------
# Em produção/homologação o upload vai para o Supabase Storage (bloco S3,
# DJANGO_USE_S3=True). No ambiente local do docker-compose (sem S3) os
# arquivos vão para o sistema de arquivos, servidos só em DEBUG (ver urls).
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
```

> Quando `DJANGO_USE_S3=True`, o `STORAGES["default"]` aponta para o S3 e `MEDIA_ROOT` fica ocioso — manter as duas definições é inofensivo e evita que o ambiente local quebre ao salvar uma imagem. O `.gitignore` do backend deve ignorar `media/` (uploads locais não são versionados).

### 5.2. `config/urls.py` — servir mídia em `DEBUG`

O Django não serve `MEDIA` sozinho. Em desenvolvimento (`DEBUG=True`), acrescentar ao final:

```python
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

> Em produção, quem serve a mídia é o Supabase Storage; este trecho fica inerte porque `DEBUG=False`. É o padrão recomendado pela documentação do Django e não é rota de produção.

### 5.3. Branding do Admin (português)

No topo de `rede/admin.py`, definir o cabeçalho da área administrativa (requisito de Tecnologia Social — tudo em português):

```python
admin.site.site_header = "Plataforma Ecosol — Rede da Economia Solidária de Niterói"
admin.site.site_title = "Ecosol · Administração"
admin.site.index_title = "Administração"
```

---

## 6. Ordem de execução (sequência de PRs)

Continua a numeração por letras da fatia anterior (que terminou no **PR F**). Executar **nesta ordem**:

| # | Branch | Conteúdo | Depende de |
|---|---|---|---|
| **G** | `feat/admin-base` | Branding do Admin; `MEDIA_URL`/`MEDIA_ROOT` + serviço de mídia em DEBUG; `UsuarioAdmin` (via `UserAdmin`); `CategoriaAdmin` (com `prepopulated_fields`) | — |
| **H** | `feat/admin-coletivo-pessoa` | `ColetivoAdmin` (fieldsets, contato+flag pareados, `filter_horizontal` de categorias, `list_editable` de `ativo`, inlines read-only de Pessoa e de slug anterior); `PessoaAdmin` (fieldsets com bloco sensível rotulado, `autocomplete_fields`) | G |
| **I** | `feat/admin-evento-ponto` | `EventoAdmin` (+ `ImagemEventoInline` com miniatura); `PontoDeInteresseAdmin`; `tests/test_admin.py`; seção "Área administrativa" no README | H |

> **Por que abrir por `admin-base`:** `UsuarioAdmin` e a configuração de mídia são fundações — sem a mídia, os PRs seguintes não têm como validar upload; sem o `UserAdmin`, criar contas da equipe fica travado. É o PR pequeno que destrava os outros dois.

Cada PR sai de `staging`, segue Conventional Commits em português e vai a revisão. `main` e `staging` permanecem protegidas.

---

## 7. Implementação

Arquivo único **`rede/admin.py`**, com seções comentadas por assunto (o volume — ~7 registros — não justifica fragmentar em pacote `admin/`; fica como refactor futuro se crescer). Estilo, docstrings e comentários em português, como no restante do projeto.

Regra transversal: **`readonly_fields = ("criado_em", "atualizado_em")`** em todo admin que tenha esses campos (são `auto_now_add`/`auto_now` — nunca editáveis à mão).

### 7.1. `UsuarioAdmin` (PR G)

Registrar `rede.Usuario` herdando de `django.contrib.auth.admin.UserAdmin`:

```python
from django.contrib.auth.admin import UserAdmin
from rede.models import Usuario

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    pass
```

> **Gotcha obrigatório:** registrar o usuário customizado com um `ModelAdmin` comum quebra o formulário de senha (a senha entraria como texto puro). Herdar de `UserAdmin` preserva o hash, os fieldsets de permissão e o "add user" em duas etapas. Este é o registro mais fácil de errar da fatia.

### 7.2. `CategoriaAdmin` (PR G)

| Atributo | Valor |
|---|---|
| `prepopulated_fields` | `{"slug": ("nome",)}` |
| `list_display` | `("nome", "slug", "num_coletivos")` |
| `search_fields` | `("nome",)` |

`num_coletivos` é coluna calculada por `annotate(Count("coletivos"))` no `get_queryset` — evita N+1 na listagem.

### 7.3. `ColetivoAdmin` (PR H)

| Atributo | Valor | Motivo |
|---|---|---|
| `prepopulated_fields` | `{"slug": ("nome",)}` | Preenche o slug ao criar; **continua editável** (alimenta o 301) |
| `list_display` | `("nome", "bairro", "situacao", "ativo", "num_pessoas")` | Visão de spreadsheet |
| `list_editable` | `("ativo",)` | Tirar/pôr do ar sem abrir o registro |
| `list_filter` | `("ativo", "situacao", "categorias")` | Recortes mais usados |
| `search_fields` | `("nome", "descricao", "bairro", "cnpj")` | Também habilita autocomplete a partir de Pessoa/Ponto |
| `filter_horizontal` | `("categorias",)` | Seletor duplo para o M2M |
| `readonly_fields` | `("criado_em", "atualizado_em")` | |
| `inlines` | `[PessoaInline, ColetivoSlugAnteriorInline]` | Ambos **read-only** (ver abaixo) |

`fieldsets`, na ordem dos blocos do model — **contato e flag no mesmo bloco** (princípio 4.1):

1. **Identificação pública** — `nome`, `slug`, `descricao`, `bairro`, `site`
2. **Contatos (visibilidade por consentimento)** — `telefone`, `exibir_telefone_publicamente`, `email`, `exibir_email_publicamente`, `instagram`, `exibir_instagram_publicamente`
3. **Dados cadastrais (uso administrativo — nunca públicos)** — `cnpj`, `data_inicio`, `responsavel_grupo`, `motivo_criacao`, `renda_obtida`, `historico_editais`
4. **Endereço completo (nunca público)** — `logradouro`, `numero`, `complemento`, `cep`
5. **Controle e classificação** — `ativo`, `situacao`, `categorias`
6. **Metadados** — `nome_entrevistador`, `observacoes`, `criado_em`, `atualizado_em`

`num_pessoas` é coluna por `annotate(Count("pessoas"))`.

**`PessoaInline`** — `TabularInline` **read-only** (`can_delete = False`, `extra = 0`, `has_add_permission → False`), exibindo apenas `nome`/`nome_social`, `municipio` e um link para a Pessoa. Serve para **ver a composição do coletivo** sem transformar a tela do Coletivo num formulário gigante — a edição de Pessoa vive na tela própria (decisão 10.1).

**`ColetivoSlugAnteriorInline`** — `TabularInline` **read-only** de `slugs_anteriores` (`slug`, `criado_em`), sem adicionar/apagar. O histórico é gerado pelo `save()` do model; o Admin só o **exibe**, para o administrador entender por que um endereço antigo redireciona.

### 7.4. `PessoaAdmin` (PR H)

| Atributo | Valor | Motivo |
|---|---|---|
| `list_display` | `("__str__", "coletivo", "municipio")` | **Sem** campo sensível (4.3) |
| `list_filter` | `("coletivo", "estado")` | Recortes não sensíveis |
| `search_fields` | `("nome", "nome_social", "cpf")` | Localizar o registro |
| `autocomplete_fields` | `("coletivo",)` | Não carregar todos os coletivos num `<select>` |
| `readonly_fields` | `("criado_em", "atualizado_em")` | |

`fieldsets`, espelhando os blocos do model:

1. **Vínculo** — `coletivo`
2. **Identificação** — `nome`, `nome_social`, `data_nascimento`, `cpf`, `rg`, `rne_crnm`, `naturalidade`, `estado_civil`
3. **Contato** — `email`, `instagram`, `facebook`, `site`, `telefone`
4. **Endereço** — `cep`, `logradouro`, `bairro`, `municipio`, `estado`
5. **Escolaridade** — `escolaridade`
6. **Empreendimento individual** — `empreendimento_individual`
7. **Bloco socioeconômico e de identidade — DADOS SENSÍVEIS (LGPD)** — `cor_raca`, `sexo`, `identidade_genero`, `orientacao_sexual`, `pessoa_com_deficiencia`, `qual_deficiencia`, `renda_familiar`, `rede_protecao_social`, `participacao_programas_sociais`. Usar `classes: ("collapse",)` e uma `description` no fieldset lembrando a natureza sensível.
8. **Metadados** — `criado_em`, `atualizado_em`

### 7.5. `EventoAdmin` + `ImagemEventoInline` (PR I)

`EventoAdmin`:

| Atributo | Valor |
|---|---|
| `prepopulated_fields` | `{"slug": ("titulo",)}` |
| `list_display` | `("titulo", "data_inicio", "data_fim", "ativo")` |
| `list_filter` | `("ativo",)` |
| `date_hierarchy` | `"data_inicio"` |
| `search_fields` | `("titulo", "descricao", "local", "bairro")` |
| `readonly_fields` | `("criado_em", "atualizado_em")` |
| `inlines` | `[ImagemEventoInline]` |

`ImagemEventoInline` — `TabularInline` de `imagens`, `extra = 1`, campos `("imagem", "preview", "legenda", "ordem")`, com `preview` em `readonly_fields`: um método que devolve `<img>` (via `format_html`, altura ~60px) quando há imagem, e vazio caso contrário. Ordenação por `ordem` (já no `Meta` do model).

### 7.6. `PontoDeInteresseAdmin` (PR I)

| Atributo | Valor |
|---|---|
| `list_display` | `("nome", "tipo", "bairro_ou_endereco", "ativo")` — ou simplesmente `("nome", "tipo", "ativo", "coletivo")` |
| `list_filter` | `("tipo", "ativo")` |
| `search_fields` | `("nome", "endereco")` |
| `autocomplete_fields` | `("coletivo",)` |
| `readonly_fields` | `("criado_em", "atualizado_em")` |

`fieldsets`: **Identificação** (`nome`, `tipo`, `descricao`) · **Localização** (`latitude`, `longitude`, `endereco`) · **Imagem** (`imagem_capa`) · **Vínculo** (`coletivo`) · **Controle** (`ativo`) · **Metadados** (`criado_em`, `atualizado_em`).

> Latitude/longitude são campos de texto numérico simples no MVP (sem widget de mapa no Admin — evita sobre-engenharia). A geocodificação via Nominatim e um eventual seletor de mapa ficam para o frontend/futuro, conforme v4.1 §2.4.

### 7.7. O que não tocar

- **Nenhum model** muda — se `makemigrations` quiser gerar algo, parar e revisar.
- `serializers.py`, `views.py`, `filters.py`, `pagination.py`, `rede/urls.py` — intocados (são a fatia pública anterior).
- `config/settings.py` recebe **apenas** o bloco de mídia (5.1). `config/urls.py`, **apenas** o serviço de mídia em DEBUG (5.2). Nenhuma dependência nova.

---

## 8. Testes desta fatia (PR I)

`pytest` + `pytest-django`, nomes e docstrings em português, no estilo de `tests/test_models.py`. Arquivo `tests/test_admin.py`.

### 8.1. Fumaça do Admin (as telas abrem)

Com um superusuário logado (fixture), para **cada** model registrado:

1. `test_changelist_abre` — `GET` da listagem responde `200`.
2. `test_formulario_de_adicao_abre` — `GET` do "add" responde `200`.
3. `test_formulario_de_edicao_abre` — criado um objeto, `GET` do "change" responde `200`.
4. `test_admin_exige_login` — usuário anônimo em `/admin/` é redirecionado (`302`) para o login. O cofre é fechado por padrão.
5. `test_usuario_registrado_com_useradmin` — o "add user" do `Usuario` abre e o admin registrado é subclasse de `UserAdmin` (garante o formulário de senha com hash).

> Testes de fumaça de Admin pegam o erro mais comum da fatia: um `fieldsets`/`list_display` que referencia um campo inexistente ou mal escrito só estoura quando a página é renderizada — nunca em import. Abrir as três telas de cada model é a rede que segura isso.

### 8.2. Guarda de LGPD do Admin (o irmão do teste de regressão do serializer)

6. `test_pessoa_nao_filtra_nem_lista_por_campo_sensivel` — asserção de que **nenhum** de `{cor_raca, sexo, identidade_genero, orientacao_sexual, pessoa_com_deficiencia, qual_deficiencia, renda_familiar, rede_protecao_social, participacao_programas_sociais}` aparece em `PessoaAdmin.list_display` **nem** em `PessoaAdmin.list_filter`. Comentário no teste explicando **por quê**, para ninguém afrouxá-lo.

### 8.3. Integração com a visibilidade (opcional, recomendado)

7. `test_editar_slug_pelo_admin_gera_historico` — um `POST` no change form do Coletivo alterando o slug cria a entrada em `ColetivoSlugAnterior`. Confirma que a operação real do administrador aciona o `save()` do model (o comportamento já é testado em nível de model; aqui garante que o caminho do Admin não o contorna).

### 8.4. O que NÃO testar aqui

Endpoints de Eventos e Pontos de Interesse (fatia seguinte), integração real com o Supabase Storage (o upload local basta; S3 é validado em homologação), frontend. Não antecipar.

### 8.5. CI

O CI existente (`ruff` → `makemigrations --check --dry-run` → `pytest`) cobre esta suíte sem alteração. O `makemigrations --check` **limpo** é, aqui, parte do aceite: prova que a fatia não mexeu no esquema.

---

## 9. Desempenho

O Admin não é rota pública, mas uma changelist com N+1 trava a tela da equipe. Boas práticas mínimas, sem sobre-engenharia:

- **Contagens por `annotate`** (`num_pessoas`, `num_coletivos`) — nunca chamar `.count()` por linha no `list_display`.
- **`autocomplete_fields`** nas FKs (`Pessoa.coletivo`, `PontoDeInteresse.coletivo`) — não materializa todos os coletivos num `<select>`; exige `search_fields` no `ColetivoAdmin` (já previsto em 7.3).
- **`list_select_related`** onde o `list_display` atravessa FK (ex.: Pessoa → coletivo).
- Inlines read-only leves (poucos campos), sem carregar as ~25 colunas de Pessoa dentro do Coletivo.

---

## 10. Decisões desta fatia (e por que não há emendas ao v4.1)

Diferente da fatia de Coletivos, esta **não diverge** do PRD Técnico v4.1 — a Seção 5.2 e o item 4 da Seção 11 já preveem o Django Admin como a Interface 2 do MVP. Registram-se aqui apenas decisões de implementação, para constarem no corpo dos PRs.

### 10.1. Pessoa em tela própria, com inline read-only no Coletivo

Pessoa tem ~25 campos, vários sensíveis. Editá-la **dentro** do Coletivo (inline editável) geraria um formulário gigante e misturaria dado sensível de pessoa com o cadastro institucional do coletivo. Decisão: **edição de Pessoa em `PessoaAdmin` próprio**; no Coletivo, um **inline read-only** que só mostra quem o compõe e linka para o registro. Preserva a visão de composição sem inchar a tela nem espalhar dado sensível.

### 10.2. Sem widget de mapa no Admin

Latitude/longitude do Ponto de Interesse são campos numéricos simples no MVP. Um seletor de mapa no Admin é conveniência que o v4.1 não pede e que a equipe pode suprir colando coordenadas do OSM. Fica para depois, sem retrabalho.

### 10.3. Permissões: papel único de Administrador no MVP

O v4.1 define dois papéis, sendo que o Público **não loga**. Logo, no MVP toda conta do Admin é da equipe (Administrador), com acesso completo. A granularidade por grupo do Django existe e pode ser ligada depois **sem código** — não é escopo desta fatia.

### 10.4. Configuração de mídia local é pré-requisito, não recurso novo

`MEDIA_URL`/`MEDIA_ROOT` e o serviço de mídia em DEBUG (Seção 5) não são funcionalidade nova: são o que faz o upload de imagem — já previsto no v4.1 §2.4 e no Backend v1.1 (item 4) — funcionar no ambiente local. Em produção quem serve é o Supabase Storage.

---

## 11. Checklist de aceite (para marcar no PR)

- [ ] `/admin/` abre em português (branding aplicado) e exige login (anônimo → `302`).
- [ ] `Usuario` registrado via `UserAdmin` (formulário de senha com hash preservado); dá para criar conta da equipe.
- [ ] Coletivo com fieldsets na ordem dos blocos; **cada contato ao lado da sua flag**; `filter_horizontal` de categorias; `ativo` em `list_editable`.
- [ ] Slug preenchido automaticamente e **editável**; editar slug cria `ColetivoSlugAnterior`.
- [ ] Inlines read-only de Pessoa e de slug anterior no Coletivo.
- [ ] Pessoa com bloco sensível rotulado; **nenhum campo sensível em `list_display`/`list_filter`**; `autocomplete_fields` para coletivo.
- [ ] Evento com galeria `ImagemEvento` inline e miniatura de pré-visualização; `date_hierarchy` por `data_inicio`.
- [ ] Ponto de Interesse com latitude/longitude, `imagem_capa` e `coletivo` por autocomplete.
- [ ] Upload de imagem funciona no docker-compose local (`MEDIA_ROOT`/`MEDIA_URL` + mídia em DEBUG); `media/` no `.gitignore`.
- [ ] `test_admin.py`: fumaça (changelist/add/change de cada model), login exigido, `UserAdmin`, guarda de LGPD de Pessoa.
- [ ] Contagens por `annotate`; FKs por `autocomplete_fields`; sem N+1 nas listagens.
- [ ] `makemigrations --check --dry-run` **limpo** (a fatia não cria migration).
- [ ] `README.md` do backend com a seção "Área administrativa" (acesso + `createsuperuser` + regras de visibilidade).
- [ ] `ruff` verde; CI verde; Conventional Commits; PRs revisados para `staging`.

---

## 12. Instruções para o Claude Code (como executar)

1. Trabalhar **dentro de `apps/ecosol-backend`** (é o repositório Git independente).
2. **Antes de tudo**, rodar `git status`: se houver alterações não commitadas na árvore, **parar e avisar** — não commitar trabalho alheio junto, não usar `stash` sem perguntar.
3. Ler `rede/models/coletivo.py`, `rede/models/pessoa.py`, `rede/models/evento.py`, `rede/models/ponto_interesse.py`, `rede/models/usuario.py`, `config/settings.py` e `config/urls.py` **antes** de escrever código. O código existente é a referência de estilo.
4. Seguir a ordem de PRs da Seção 6 (Base → Coletivo/Pessoa → Evento/Ponto). Um PR por branch, saindo de `staging`.
5. **Não** alterar nenhum model. Se `makemigrations --check --dry-run` acusar mudança, **parar** — algo foi tocado indevidamente. O Admin não gera migration.
6. Alterar `config/settings.py` **apenas** com o bloco de mídia (5.1) e `config/urls.py` **apenas** com o serviço de mídia em DEBUG (5.2). Nenhuma dependência nova. Acrescentar `media/` ao `.gitignore`.
7. Validar localmente com `docker compose up --build` a partir de `infra/`; criar um superusuário (`python manage.py createsuperuser`) e conferir manualmente cada tela, inclusive **um upload de imagem** de Evento.
8. Rodar `ruff check .`, `makemigrations --check --dry-run` e `pytest` a cada commit; só seguir com tudo verde.
9. Manter tudo em português (docstrings, comentários, mensagens de commit, descrição de PR) — requisito de Tecnologia Social do projeto.
10. Diante de qualquer dúvida sobre exposição de dado ou sobre colocar um campo sensível em listagem/filtro: **não colocar** e, se preciso, parar e perguntar. O Admin é o cofre — na dúvida, fecha-se.

---

*Fatia derivada da Seção 11, item 4 do PRD Técnico v4.1 e do item 4 do mapa de PRs do PRD de Implementação Backend v1.1. Sem emendas de arquitetura (Seção 10). As fatias seguintes: replicação do padrão de endpoint público para Eventos e Pontos de Interesse, e frontend Next.js.*
