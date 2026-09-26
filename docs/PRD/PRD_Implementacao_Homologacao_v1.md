# PRD de Implementação — Ambiente de homologação

**Projeto:** Plataforma de Rede da Economia Solidária de Niterói
**Centro Público de Referência em Economia Solidária (Casa Paul Singer) · ITES / IFRJ Campus Niterói**

| | |
|---|---|
| **Documento** | PRD de Implementação — Fatia 6: Ambiente de homologação (Vercel + Render + Supabase) |
| **Versão** | 1.0 |
| **Data** | 26/09/2026 |
| **Deriva de** | PRD Técnico v4.1 (Seções 2.5, 6, 8.2, 8.5 e 12) · Cartão do Trello "[Deploy] Ambiente de homologação" (Sprint 1) |
| **Escopo** | Deixar backend e frontend prontos para rodar fora do Docker local (PRs S e T) e publicar a branch `staging` dos dois em serviços gerenciados gratuitos, com banco e Storage próprios de homologação |
| **Fora de escopo** | Produção, domínio próprio, e-mail, keep-alive do backend, imagens Docker em registry, dados reais de pessoas, qualquer mudança de contrato da API ou de tela |
| **Repositórios** | `apps/ecosol-backend` (PR S) · `apps/ecosol-frontend` (PR T) · painéis do Supabase, Render e Vercel (Parte manual) |
| **Status** | Não executado |

---

## 0. Objetivo deste documento

Este PRD detalha como tirar a plataforma do `localhost` e colocá-la num endereço que a equipe da Casa Paul Singer consiga abrir. É o ambiente onde acontece a **Sprint Review**: o ITES vê o que foi feito sem precisar do Docker de ninguém.

**Homologação não é produção.** Nada aqui vai para o domínio oficial, nada aqui é indexado por buscador, e **nenhum dado real de pessoa** entra neste ambiente. O cadastro com dado real depende do documento de LGPD da Seção 6.4 do PRD Técnico, que é outro cartão da mesma sprint.

O trabalho tem duas naturezas, e o documento as separa:

- **Parte de código (PRs S e T)** — executável por um agente (Claude Code). São ajustes pequenos que o ambiente local escondia: com `DEBUG=True` e sem HTTPS, o Django serve os próprios estáticos e não confere a origem do formulário. Fora dele, o Admin abre sem estilo e o login dá 403.
- **Parte manual (Seção 7)** — feita por uma pessoa nos painéis do Supabase, Render e Vercel. Envolve criar contas, gerar segredos e colar variáveis. **Um agente não executa esta parte**: segredos não passam por ele.

---

## 1. Estado atual (ponto de partida)

Conferido em 26/09/2026, na `staging` dos três repositórios. A cópia local em `ecosol-fullstack` está igual ao GitHub.

**`apps/ecosol-backend`**

- Django 5.2 + DRF, `gunicorn` já em `requirements.txt`, `Dockerfile` com `CMD gunicorn ... --bind 0.0.0.0:8001`.
- Rota `/health/` pronta (`config/urls.py`), feita para smoke test e deploy.
- Configuração por variáveis de ambiente (`django-environ`), com duas conexões de banco: `DATABASE_URL` (pooler) em runtime e `DATABASE_DIRECT_URL` para migrations, ligada por `DJANGO_DB_DIRECT=True`.
- Storage de imagens no Supabase por `DJANGO_USE_S3=True`.
- A flag `DJANGO_IGNORE_DOTENV=True` faz o Django ignorar o `.env` da máquina. Esta fatia usa essa flag na Seção 7.4.
- Guarda na raiz (`conftest.py`, PR #15) que impede o `pytest` de tocar banco remoto.

**O que falta no backend para rodar fora do compose:**

| Problema | Sintoma fora do local | Por que o local esconde |
|---|---|---|
| Nenhum servidor de estáticos | Admin abre **sem CSS** | Com `DEBUG=True`, o `runserver` serve `/static/` sozinho |
| Sem `CSRF_TRUSTED_ORIGINS` | Login do Admin responde **403 CSRF verification failed** | Em `http://localhost` a checagem de origem não se aplica |
| Sem `SECURE_PROXY_SSL_HEADER` | Django acha que a requisição é HTTP atrás do proxy HTTPS do Render | Não há proxy no local |
| Porta fixa `8001` no `CMD` | Render não encontra o processo (ele injeta `PORT`) | O compose publica a 8001 |
| `ALLOWED_HOSTS` só por variável | Health check do Render pode morrer em `400` | O compose já lista os hosts |

**`apps/ecosol-frontend`**

- Next.js 16, todo acesso à API no servidor (`src/lib/api.ts`), sem `NEXT_PUBLIC_*`.
- `next.config.ts` já libera imagens de `*.supabase.co/storage/v1/object/public/**`. **Não precisa mexer.**
- `src/app/robots.ts` libera tudo para os buscadores. Correto para produção; errado para homologação, que seria indexada como se fosse o site oficial.

---

## 2. Resultado esperado (Definition of Done da fatia)

A fatia está concluída quando **todos** os itens abaixo forem verdadeiros:

1. PR S mergeado na `staging` do backend, com CI verde.
2. PR T mergeado na `staging` do frontend, com CI verde.
3. Backend de homologação no ar no Render: `https://<servico>.onrender.com/health/` responde `{"status": "ok"}`.
4. `/admin/` abre **com estilo**, e o login do superusuário funciona.
5. Uma imagem enviada pelo Admin vai para o bucket `divulgacao` do **projeto Supabase de homologação** (não o de produção).
6. Frontend de homologação no ar na Vercel: home, `/coletivos`, perfil, `/eventos` e `/mapa` carregam com dados vindos do backend de homologação.
7. A imagem do item 5 aparece no site.
8. `https://<frontend>.vercel.app/robots.txt` responde `Disallow: /`, e as páginas trazem `<meta name="robots" content="noindex, nofollow">`.
9. Os dados cadastrados são **fictícios**.
10. As duas URLs estão anotadas no cartão "Links e stack do projeto" do Trello, e o `README.md` do backend documenta o deploy.

---

## 3. Decisões desta fatia

### 3.1. Render para o backend, e não Railway

Verificado em 26/09/2026:

- **Render (plano Free):** 750 horas de instância por mês por workspace, o suficiente para um serviço ligado o mês inteiro. Sem cartão de crédito.
- **Railway:** o plano gratuito é um crédito único de US$ 5 no teste e depois US$ 1/mês com recursos mínimos. Continuar exige o Hobby, a partir de US$ 5/mês.

Para um projeto acadêmico sem orçamento, o Render é o caminho. O PRD Técnico (§2.5) cita "Render/Railway"; esta fatia escolhe o primeiro.

**Limitações do Render Free que a equipe precisa conhecer:**

- O serviço **dorme após 15 minutos** sem requisição e leva **cerca de 1 minuto** para acordar. A primeira página depois de um tempo parado demora, ou dá erro e funciona ao recarregar. **Antes de cada Sprint Review, abrir o site uns minutos antes.**
- **Sem terminal** (nem SSH nem shell no painel). Migrations e superusuário rodam da máquina de quem desenvolve (Seção 7.4).
- **Portas de SMTP bloqueadas** (25, 465 e 587). Não afeta esta fatia, mas afeta o cartão de e-mail: lá será preciso um provedor com envio por **API HTTP** (ex.: Brevo), não por SMTP. Registrar isso no cartão de e-mail.
- O Postgres gratuito do Render expira em 30 dias. **Não usar.** O banco é o Supabase.

### 3.2. Projeto Supabase separado para homologação

Homologação usa um **projeto Supabase próprio** (`ecosol-homolog`), e não o de produção. Motivos:

- O incidente registrado no PRD Técnico (§12) mostrou o custo de ambiente que "deveria" ser isolado e não é: 34 objetos sobrescritos no bucket de produção. Separar por projeto torna o isolamento físico, não uma convenção.
- Dados de teste, superusuários de teste e imagens de teste nunca se misturam com o cadastro real.
- No plano gratuito, projeto sem atividade por 7 dias é **pausado**. Reativar pelo painel é um clique. Anotar no cartão para ninguém achar que "o site caiu".

### 3.3. Estáticos pelo WhiteNoise

O Admin é a única parte do backend com arquivos estáticos. Três opções:

1. **WhiteNoise** — o próprio gunicorn serve `/static/`, sem serviço extra. Padrão da documentação do Django para PaaS.
2. Supabase Storage para estáticos — mistura CSS do Admin com imagens de divulgação no mesmo bucket e aumenta o tráfego contado no plano gratuito.
3. CDN à parte — sobre-engenharia para um Admin usado por poucas pessoas.

Fica o **WhiteNoise**, com `CompressedStaticFilesStorage` e **não** a variante `Manifest`. A variante com manifesto exige `collectstatic` antes de qualquer renderização de template com `DEBUG=False`, e **a suíte roda com `DEBUG=False`** (ver `ci.yml`): os 25 testes do Admin quebrariam com `ValueError: Missing staticfiles manifest entry`. O ganho do manifesto (nome com hash, cache longo) não compensa para um Admin interno.

### 3.4. Configuração de segurança por variável, com padrão seguro para o local

`CSRF_TRUSTED_ORIGINS`, cookies `Secure` e o cabeçalho do proxy entram lidos de variáveis de ambiente. O padrão de cada uma mantém o comportamento atual no compose e no CI. Motivo: o ambiente local e a suíte não podem mudar de comportamento por causa do deploy. **Nenhum teste existente pode precisar de ajuste.**

### 3.5. Homologação não é indexável

O propósito da plataforma é ser encontrada (PRD Frontend §0). Justamente por isso, a homologação **não pode** ser encontrada: um coletivo de teste no Google, ou a mesma página em dois domínios, prejudica o site oficial.

A proteção tem duas camadas, porque `robots.txt` sozinho não basta (buscador que chega por link externo pode indexar a URL mesmo bloqueada):

- `robots.txt` com `Disallow: /`;
- `<meta name="robots" content="noindex, nofollow">` em todas as páginas.

Controladas por **uma** variável, `SITE_INDEXAVEL`. Padrão `true`, para não mudar o comportamento de quem roda local nem da produção futura. Na Vercel de homologação, `false`.

### 3.6. Branch publicada: `staging`

Os dois serviços publicam a branch `staging`. É onde o trabalho da sprint é integrado, e é o que a Review deve mostrar. A `main` fica para produção (cartão próprio).

---

## 4. Sequência de trabalho

Continua a numeração das fatias anteriores (a última foi o PR R, do frontend).

| # | Onde | Branch | Conteúdo | Quem | Bloqueia? |
|---|---|---|---|---|---|
| **S** | `ecosol-backend` | `chore/prontidao-para-deploy` | WhiteNoise, CSRF/proxy/cookies por variável, porta `$PORT`, `collectstatic` no build e no CI, `.env.example`, seção "Deploy" no README | Agente | Sim — Render depende dele |
| **T** | `ecosol-frontend` | `feat/indexacao-por-ambiente` | `SITE_INDEXAVEL` no `robots.ts` e no `metadata` do layout, testes, `.env.example`, README | Agente | Sim — Vercel depende dele |
| **M1** | Supabase | — | Projeto `ecosol-homolog`, bucket, chaves S3 | Pessoa | Sim |
| **M2** | Render | — | Web Service do backend | Pessoa | Depende de S e M1 |
| **M3** | Máquina local | — | Migrations e superusuário no banco de homologação | Pessoa | Depende de M1 |
| **M4** | Vercel | — | Projeto do frontend | Pessoa | Depende de T e M2 |
| **M5** | Admin de homologação | — | Dados fictícios e verificação ponta a ponta | Pessoa | Depende de M2–M4 |

S e T são independentes entre si e podem ser feitos em paralelo.

---

## 5. PR S — backend pronto para deploy

Branch `chore/prontidao-para-deploy`, saindo de `staging`.

### 5.1. `requirements.txt`

Acrescentar, com a mesma convenção de versão mínima dos demais:

```
whitenoise>=6.7
```

### 5.2. `config/settings.py`

**a) Hosts.** Manter `DJANGO_ALLOWED_HOSTS` e acrescentar o host que o Render injeta sozinho. O Render define `RENDER_EXTERNAL_HOSTNAME` em todo serviço; aproveitar evita um erro de digitação derrubar o health check em `400`, num erro que não menciona `ALLOWED_HOSTS`.

```python
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# O Render injeta o próprio host em toda instância. Somar aqui evita depender
# de alguém digitar o endereço certo no painel: um host errado derruba o health
# check com 400, e a mensagem não menciona ALLOWED_HOSTS.
_host_render = env("RENDER_EXTERNAL_HOSTNAME", default="")
if _host_render:
    ALLOWED_HOSTS.append(_host_render)
```

**b) Middleware.** `WhiteNoiseMiddleware` logo **depois** do `SecurityMiddleware` e antes de todos os outros (ordem exigida pela documentação do WhiteNoise):

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # ... restante igual
]
```

**c) Storages sempre declarados.** Hoje `STORAGES` só existe quando `DJANGO_USE_S3=True`. Passa a existir sempre, com o S3 trocando apenas o `default`:

```python
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Sem "Manifest" de propósito: a variante com manifesto exige collectstatic
    # antes de renderizar qualquer template com DEBUG=False — e a suíte roda com
    # DEBUG=False. Ver a Seção 3.3 do PRD de homologação.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

if env.bool("DJANGO_USE_S3", default=False):
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    # ... restante do bloco S3 igual
```

Conferir que a fixture `media_temporaria` de `tests/conftest.py` continua funcionando: ela faz `{**settings.STORAGES, "default": ...}`, então preserva o `staticfiles`. **Não alterar a fixture.**

**d) HTTPS atrás de proxy e origem do CSRF.** Tudo por variável, com padrão igual ao comportamento atual:

```python
# --- HTTPS atrás de proxy (Render, Vercel) ---------------------------------
# O Render termina o HTTPS e repassa HTTP ao gunicorn, avisando no cabeçalho
# X-Forwarded-Proto. Sem confiar nele, o Django acha que a requisição é HTTP.
# Só ligar onde há proxy de verdade: confiar no cabeçalho sem proxy na frente
# deixaria qualquer cliente se declarar HTTPS.
if env.bool("DJANGO_ATRAS_DE_PROXY_HTTPS", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Origens aceitas no POST de formulário (login do Admin). Em HTTPS o Django
# confere o cabeçalho Origin contra esta lista; vazia, o login dá 403.
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Cookies de sessão e CSRF só por HTTPS. Desligado por padrão: o compose e o
# CI falam HTTP, e cookie Secure em HTTP simplesmente não volta.
SESSION_COOKIE_SECURE = env.bool("DJANGO_COOKIES_SEGUROS", default=False)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
```

**e) Não mexer** em: conexões de banco, bloco S3 (além do item c), REST_FRAMEWORK, `AUTH_USER_MODEL`.

### 5.3. `Dockerfile`

Duas mudanças:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

# Estáticos do Admin empacotados na imagem, servidos pelo WhiteNoise.
# SECRET_KEY de mentira só para o comando carregar as settings: o
# collectstatic não usa banco nem segredo, e a chave de verdade chega em runtime.
RUN DJANGO_SECRET_KEY=somente-build DJANGO_IGNORE_DOTENV=True \
    python manage.py collectstatic --noinput

EXPOSE 8001

# O Render (e a maioria dos PaaS) injeta a porta em $PORT. Fora deles vale a
# 8001 de sempre. Em dev o docker-compose sobrescreve este CMD por runserver.
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8001} --workers 2 --timeout 60"]
```

- `--workers 2`: a instância Free tem 512 MB de RAM; dois workers do Django cabem com folga.
- `--timeout 60`: o pooler do Supabase às vezes demora na primeira conexão depois de o serviço acordar.
- **Não** trocar `requirements-dev.txt` por `requirements.txt` nesta fatia (reduziria a imagem, mas muda o que o compose local instala; fica para o cartão de registry).

Conferir que `staticfiles/` continua no `.dockerignore` (está) e no `.gitignore`.

### 5.4. CI (`.github/workflows/ci.yml`)

Acrescentar um passo **depois** do pytest. É o único jeito de pegar, no PR, um erro que só apareceria no build do Render:

```yaml
      - name: Estáticos (collectstatic)
        run: python manage.py collectstatic --noinput
```

### 5.5. Testes

Criar `tests/test_prontidao_deploy.py`. Os testes provam as promessas desta fatia, não a mecânica:

1. **O Admin serve CSS com `DEBUG=False`.** Rodar `collectstatic` para um `STATIC_ROOT` temporário (`tmp_path`, via `settings`), pedir `/static/admin/css/base.css` pelo `client` e conferir `200` e `Content-Type` de CSS. É o teste que falharia hoje.
2. **O login do Admin aceita a origem confiável.** Com `settings.CSRF_TRUSTED_ORIGINS = ["https://homolog.exemplo"]`, fazer `POST /admin/login/` com `enforce_csrf_checks=True`, `secure=True`, cabeçalho `Origin` igual e token CSRF válido: não pode dar `403`. Com `Origin` diferente: tem de dar `403`. O segundo caso é o que prova que a lista é respeitada, e não ignorada.
3. **`RENDER_EXTERNAL_HOSTNAME` entra em `ALLOWED_HOSTS`.** Testar a função/trecho isolado (se necessário, extrair para uma função pequena em `config/settings.py` ou `config/ambiente.py` e testar a função, sem recarregar o módulo de settings).
4. **Padrões intactos.** Sem as variáveis novas: `SESSION_COOKIE_SECURE is False`, `CSRF_TRUSTED_ORIGINS == []`, e `SECURE_PROXY_SSL_HEADER` ausente. Garante que o compose e o CI não mudaram de comportamento.

Toda a suíte existente (112+ casos) tem de continuar verde **sem nenhuma alteração**.

### 5.6. `.env.example`

Acrescentar, comentado no estilo do arquivo:

```bash
# --- Deploy (homologação / produção) --------------------------------------
# Ligue onde houver proxy HTTPS na frente (Render). Nunca no local.
DJANGO_ATRAS_DE_PROXY_HTTPS=False
# Origens do login do Admin, com esquema. Ex.: https://ecosol-backend-homolog.onrender.com
DJANGO_CSRF_TRUSTED_ORIGINS=
# Cookies só por HTTPS. True em homologação e produção.
DJANGO_COOKIES_SEGUROS=False
```

### 5.7. `README.md` do backend

Nova seção **"Deploy (homologação)"**, logo depois de "Dois ambientes, separados de propósito", com:

- tabela de variáveis do Render (Seção 7.2 deste PRD, sem valores reais);
- o comando de migrations da Seção 7.4, **com a `DJANGO_IGNORE_DOTENV=True`** e o motivo;
- o aviso do Render Free (dorme em 15 min, sem terminal, sem SMTP).

### 5.8. Commits sugeridos

```
build(deps): adicionar whitenoise para servir os estáticos do Admin
feat(settings): configurar HTTPS atrás de proxy, CSRF e cookies por variável
build(docker): coletar estáticos na imagem e escutar na porta do PaaS
ci: conferir o collectstatic em todo PR
test: provar CSS do Admin, origem do CSRF e padrões do ambiente local
docs: documentar o deploy de homologação
```

---

## 6. PR T — frontend não indexável em homologação

Branch `feat/indexacao-por-ambiente`, saindo de `staging`.

### 6.1. `src/lib/site.ts`

Centralizar a leitura, como já é feito com `SITE_URL` (o comentário do arquivo explica por quê: três lugares precisam do mesmo valor):

```ts
/**
 * O site pode ser indexado por buscadores?
 *
 * `false` só em homologação. Lá o site existe para a equipe conferir o
 * trabalho da sprint — e um coletivo de teste no Google, ou a mesma página em
 * dois domínios, atrapalha o site oficial, cujo propósito é ser encontrado.
 * Qualquer valor que não seja exatamente "false" conta como indexável: o erro
 * de digitação cai no comportamento de produção, que é o padrão do projeto.
 */
export const SITE_INDEXAVEL = process.env.SITE_INDEXAVEL?.trim().toLowerCase() !== "false";
```

### 6.2. `src/app/robots.ts`

- Indexável (comportamento atual): `rules: { userAgent: "*", allow: "/" }` + `sitemap` + `host`.
- Não indexável: `rules: { userAgent: "*", disallow: "/" }`, **sem** `sitemap` (apontar o mapa do site e ao mesmo tempo proibir o acesso é mensagem contraditória).
- Atualizar o comentário do arquivo: a frase "Tudo é liberado" deixa de ser incondicional.

### 6.3. `src/app/layout.tsx`

No `metadata` exportado, acrescentar:

```ts
robots: SITE_INDEXAVEL ? undefined : { index: false, follow: false },
```

Isso gera `<meta name="robots" content="noindex, nofollow">` em todas as páginas. É a camada que vale para quem chega por link externo, que o `robots.txt` não cobre.

Se alguma página definir `robots` no próprio `generateMetadata`, conferir que não sobrescreve o do layout em homologação.

### 6.4. Testes

Criar `src/app/robots.test.ts`, no padrão de `sitemap.test.ts` (mesma técnica para variar `process.env` e reimportar o módulo):

1. Sem `SITE_INDEXAVEL`: `allow: "/"` e `sitemap` presente.
2. `SITE_INDEXAVEL=false`: `disallow: "/"` e **sem** `sitemap`.
3. `SITE_INDEXAVEL=FALSE` e `" false "`: também não indexável.
4. `SITE_INDEXAVEL=nao` (valor inesperado): indexável. Documenta a decisão do comentário da 6.1.

E um teste do `metadata` do layout: com `SITE_INDEXAVEL=false`, `metadata.robots` é `{ index: false, follow: false }`; sem a variável, é `undefined`.

### 6.5. `.env.example` e `README.md`

Acrescentar ao `.env.example`:

```bash
# O site pode ser indexado por buscadores? "false" SÓ em homologação.
# Em produção e no local, deixe sem definir (ou "true").
SITE_INDEXAVEL=true
```

No `README.md`, acrescentar a variável à tabela "Variáveis de ambiente".

### 6.6. Commits sugeridos

```
feat(seo): bloquear indexação quando SITE_INDEXAVEL=false
test(seo): cobrir robots e metadata nos dois modos de indexação
docs: documentar SITE_INDEXAVEL
```

---

## 7. Parte manual (painéis)

**Executada por uma pessoa**, depois do merge de S e T na `staging`. Nenhum segredo desta seção vai para repositório, Trello, chat ou PRD. O lugar deles é o painel de cada serviço.

### 7.1. M1 — Supabase de homologação

1. Em <https://supabase.com/dashboard>, **New project**:
   - Nome: `ecosol-homolog`
   - Região: **South America (São Paulo)** — a mesma do projeto de produção e do `AWS_S3_REGION_NAME=sa-east-1`
   - Senha do banco: gerar uma forte e guardar no gerenciador de senhas da equipe.
2. **Connect** (botão no topo do projeto) → copiar **duas** URLs:
   - **Transaction pooler** (porta **6543**) → vai em `DATABASE_URL`.
   - **Session pooler** (porta **5432**, usuário `postgres.<ref>`) → vai em `DATABASE_DIRECT_URL`.
   - **Não usar** a "Direct connection" (`db.<ref>.supabase.co`): ela só responde por IPv6, e nem o Render nem a maioria das redes domésticas saem por IPv6. O `.env.example` do backend já avisa isso.
3. **Storage → New bucket**: nome `divulgacao`, marcado como **Public bucket**.
4. **Storage → S3 Configuration** (ou "S3 Connection"): gerar um **access key** e anotar:
   - `Access key ID` → `AWS_ACCESS_KEY_ID`
   - `Secret access key` → `AWS_SECRET_ACCESS_KEY` (aparece uma vez só)
   - `Endpoint` → `AWS_S3_ENDPOINT_URL` (formato `https://<ref>.supabase.co/storage/v1/s3`)
5. **Não** ligar Auth, RLS nem APIs automáticas. O Django é dono do esquema (PRD Técnico §8.2).

### 7.2. M2 — Backend no Render

1. Em <https://dashboard.render.com>, **New → Web Service → Git repository** → `Plataforma-Ecosol/ecosol-backend`.
2. Configurar:

   | Campo | Valor |
   |---|---|
   | Name | `ecosol-backend-homolog` |
   | Region | a mais próxima disponível (hoje, Ohio ou Virginia; o Render não tem região no Brasil) |
   | Branch | `staging` |
   | Runtime | **Docker** |
   | Instance type | **Free** |
   | Health Check Path | `/health/` |
   | Auto-Deploy | **On Commit** |

3. **Environment** → variáveis:

   | Variável | Valor |
   |---|---|
   | `DJANGO_SECRET_KEY` | gerar: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
   | `DJANGO_DEBUG` | `False` |
   | `DJANGO_IGNORE_DOTENV` | `True` |
   | `DJANGO_ALLOWED_HOSTS` | `ecosol-backend-homolog.onrender.com` |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://ecosol-backend-homolog.onrender.com` |
   | `DJANGO_ATRAS_DE_PROXY_HTTPS` | `True` |
   | `DJANGO_COOKIES_SEGUROS` | `True` |
   | `DATABASE_URL` | Transaction pooler (6543) do projeto **ecosol-homolog** |
   | `DATABASE_DIRECT_URL` | Session pooler (5432) do projeto **ecosol-homolog** |
   | `DJANGO_DB_POOLER` | `True` |
   | `DJANGO_USE_S3` | `True` |
   | `AWS_ACCESS_KEY_ID` | da Seção 7.1 |
   | `AWS_SECRET_ACCESS_KEY` | da Seção 7.1 |
   | `AWS_STORAGE_BUCKET_NAME` | `divulgacao` |
   | `AWS_S3_ENDPOINT_URL` | da Seção 7.1 |
   | `AWS_S3_REGION_NAME` | `sa-east-1` |

   **Não** definir `PORT`: o Render injeta sozinho.
   Se o Render der outro nome ao serviço, ajustar os dois endereços acima (o `RENDER_EXTERNAL_HOSTNAME` cobre o `ALLOWED_HOSTS`, mas **não** o CSRF).

4. **Create Web Service** e acompanhar o log do build. Esperado: `collectstatic` copiando os arquivos do Admin, depois `gunicorn` escutando na porta informada.
5. O primeiro deploy fica **vermelho no health check** enquanto não houver migrations? Não: `/health/` não consulta o banco. Se ficar vermelho, ver a Seção 9.

### 7.3. Antes das migrations: conferir para onde se está apontando

O `.env` da máquina de desenvolvimento aponta para o **Supabase de produção** (PRD Técnico §12). Rodar `migrate` com ele por engano altera o banco real. Por isso, o procedimento abaixo **ignora o `.env` por inteiro** (`DJANGO_IGNORE_DOTENV=True`) e define só as variáveis de homologação, na sessão atual do terminal. Fechar o terminal apaga tudo.

### 7.4. M3 — Migrations e superusuário (PowerShell, na máquina local)

Dentro de `ecosol-fullstack\apps\ecosol-backend`, com o `venv` ativado:

```powershell
# 1. Isolar: nada do .env (que aponta para produção) entra nesta sessão.
$env:DJANGO_IGNORE_DOTENV = "True"
$env:DJANGO_SECRET_KEY    = "so-para-este-terminal"
$env:DJANGO_DB_DIRECT     = "True"
$env:DATABASE_DIRECT_URL  = "<Session pooler 5432 do ecosol-homolog>"

# 2. Conferir o destino ANTES de escrever qualquer coisa.
python -c "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();from django.conf import settings as s;print(s.DATABASES['default']['HOST'])"
#    Tem de aparecer o host do pooler (aws-...pooler.supabase.com) e, na URL
#    que você colou, o usuário postgres.<ref DO HOMOLOG>. Se aparecer outro
#    projeto, PARAR.

# 3. Aplicar as migrations.
python manage.py migrate

# 4. Criar o superusuário da homologação.
python manage.py createsuperuser

# 5. Encerrar a sessão (apaga as variáveis).
exit
```

**Nunca** rodar `pytest` nesta sessão. A guarda do `conftest.py` barra, mas não se testa a guarda de propósito.

### 7.5. M4 — Frontend na Vercel

1. Em <https://vercel.com/new>, importar `Plataforma-Ecosol/ecosol-frontend`. A Vercel detecta o Next.js; não mudar comando de build nem pasta de saída.
2. **Environment Variables** (marcar **Production** e **Preview**):

   | Variável | Valor |
   |---|---|
   | `API_URL` | `https://ecosol-backend-homolog.onrender.com` |
   | `API_URL_PUBLICA` | o mesmo endereço |
   | `SITE_URL` | o endereço que a Vercel der ao projeto (ex.: `https://ecosol-frontend.vercel.app`) |
   | `SITE_INDEXAVEL` | `false` |

3. **Deploy**. Depois, em **Settings → Git → Production Branch**, trocar para `staging` e disparar um novo deploy (**Deployments → Redeploy**).
4. Se o endereço final for diferente do usado em `SITE_URL`, corrigir a variável e fazer **Redeploy** (ela entra no `canonical`, no Open Graph e no sitemap).
5. Em **Settings → Deployment Protection**, deixar a proteção **desligada** para o endereço de produção do projeto: a equipe da Casa Paul Singer precisa abrir sem conta na Vercel.

### 7.6. M5 — Dados fictícios e verificação

1. Abrir `https://ecosol-backend-homolog.onrender.com/admin/` (esperar até 1 minuto se o serviço estiver dormindo) e entrar com o superusuário.
2. Cadastrar **somente dados inventados**:
   - 2 categorias;
   - 3 coletivos ativos (um com e-mail/telefone **com** consentimento de exibição, um **sem**) — para conferir a regra de omissão na tela;
   - 1 evento futuro com **uma foto**;
   - 1 evento passado;
   - 2 pontos de interesse com coordenadas em Niterói (ex.: Centro e Icaraí).
3. Pessoas: **não cadastrar**. Nenhuma tela pública mostra Pessoa, e dado de pessoa só entra depois do documento de LGPD.
4. Percorrer o checklist da Seção 8.

---

## 8. Checklist de aceite (para marcar no cartão do Trello)

**PR S**
- [ ] `whitenoise` em `requirements.txt` e middleware na posição certa.
- [ ] `STORAGES` sempre declarado; S3 troca só o `default`; `CompressedStaticFilesStorage` sem manifesto.
- [ ] `DJANGO_ATRAS_DE_PROXY_HTTPS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_COOKIES_SEGUROS` lidos do ambiente, com padrão que não muda o local.
- [ ] `RENDER_EXTERNAL_HOSTNAME` somado a `ALLOWED_HOSTS`.
- [ ] `collectstatic` no `Dockerfile` e no CI; `CMD` usando `${PORT:-8001}`.
- [ ] `tests/test_prontidao_deploy.py` com os quatro grupos da Seção 5.5; suíte antiga verde **sem alteração**.
- [ ] `docker compose up --build` (em `infra/`) continua subindo e o Admin local abre.
- [ ] `.env.example` e README atualizados.

**PR T**
- [ ] `SITE_INDEXAVEL` centralizado em `src/lib/site.ts`.
- [ ] `robots.ts` e `metadata` do layout respeitando a variável.
- [ ] Testes da Seção 6.4 passando; `lint`, `tsc`, `vitest` e `next build` verdes.
- [ ] `.env.example` e README atualizados.

**Parte manual**
- [ ] Projeto `ecosol-homolog` no Supabase, com bucket público `divulgacao` e chave S3.
- [ ] Serviço `ecosol-backend-homolog` no Render, branch `staging`, health check verde.
- [ ] Migrations aplicadas **no banco de homologação** (destino conferido antes) e superusuário criado.
- [ ] Projeto do frontend na Vercel, branch de produção `staging`, variáveis nas duas abas.
- [ ] `/admin/` com estilo e login funcionando.
- [ ] Foto do evento aparece no bucket do **homolog** e no site.
- [ ] Home, `/coletivos`, perfil, `/eventos` e `/mapa` carregam.
- [ ] Coletivo sem consentimento não mostra contato no perfil.
- [ ] `/robots.txt` com `Disallow: /` e `<meta name="robots" content="noindex, nofollow">` no HTML.
- [ ] URLs anotadas no cartão "Links e stack do projeto".

---

## 9. Problemas prováveis e como diagnosticar

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Health check do Render falha com `400` | Host fora de `ALLOWED_HOSTS` | Conferir se o PR S (com `RENDER_EXTERNAL_HOSTNAME`) está na `staging`; conferir `DJANGO_ALLOWED_HOSTS` |
| Admin sem CSS | Build sem `collectstatic` ou middleware fora de ordem | Procurar "static files copied" no log do build; conferir a posição do `WhiteNoiseMiddleware` |
| Login do Admin: `403 CSRF verification failed` | `DJANGO_CSRF_TRUSTED_ORIGINS` sem `https://` ou com barra no fim | Valor exato: `https://<servico>.onrender.com`, sem barra |
| Login volta para a tela de login sem erro | Cookie `Secure` sem o Django saber que está em HTTPS | `DJANGO_ATRAS_DE_PROXY_HTTPS=True` |
| `OperationalError` / timeout no banco | URL da "Direct connection" (IPv6) | Usar as URLs de pooler da Seção 7.1 |
| `prepared statement ... already exists` | `DJANGO_DB_POOLER` desligado com a URL 6543 | `DJANGO_DB_POOLER=True` |
| Página do site dá erro 500 na primeira visita | Backend dormindo (Render Free) | Recarregar após ~1 minuto. Esperado; ver Seção 3.1 |
| Imagem quebrada no site | Bucket não público, ou endpoint S3 de outro projeto | Conferir "Public bucket" e o `<ref>` do `AWS_S3_ENDPOINT_URL` |
| Site inteiro fora e Supabase "Paused" | 7 dias sem uso no plano gratuito | Reativar no painel do Supabase |

---

## 10. O que esta fatia deixa preparado (e não faz)

- **Produção** (cartão próprio): repete a Parte manual com o projeto Supabase de produção, a branch `main`, `SITE_INDEXAVEL` sem definir e domínio próprio. O código dos PRs S e T já serve sem mudança.
- **Keep-alive**: um agendamento (ex.: GitHub Actions a cada 14 minutos em `/health/`) evitaria o backend dormir, cabendo nas 750 horas. Não entra agora: homologação é usada em momentos marcados, e o aviso da Seção 3.1 resolve.
- **E-mail**: o bloqueio de SMTP do Render Free define o desenho do cartão de e-mail (provedor com API HTTP).
- **Registry de imagens**: segue no cartão próprio do backlog.

---

## 11. Instruções para o Claude Code (como executar)

1. Esta fatia tem **duas partes**. O agente executa **somente os PRs S e T** (Seções 5 e 6). A Parte manual (Seção 7) é de uma pessoa: **não** criar contas, **não** gerar nem pedir segredos, **não** tentar acessar painéis.
2. **Antes de tudo**, rodar `git status` em `apps/ecosol-backend` e `apps/ecosol-frontend`: se houver alteração não commitada, **parar e avisar**. Não commitar trabalho alheio, não usar `stash` sem perguntar.
3. Atualizar a `staging` local (`git pull`) e criar as branches a partir dela.
4. Ler, antes de escrever código: este documento inteiro; `config/settings.py`, `tests/conftest.py`, `conftest.py` da raiz, `Dockerfile` e `ci.yml` do backend; `src/lib/site.ts`, `src/app/robots.ts`, `src/app/layout.tsx` e `src/app/sitemap.test.ts` do frontend.
5. **Testes do backend rodam dentro do container** (decisão registrada no PRD Técnico §12): `docker compose run --rm backend pytest` a partir de `apps/ecosol-backend/infra`. **Nunca** rodar `pytest` direto na máquina: o `.env` aponta para produção.
6. Rodar a suíte inteira e o lint a cada commit (`ruff check .` e `pytest` no backend; `npm run lint`, `npm run typecheck`, `npm test` e `npm run build` no frontend). Só seguir com tudo verde.
7. Nenhuma dependência além do `whitenoise`. Querer outra é sinal de parar e perguntar.
8. **Não alterar** testes existentes nem a fixture `media_temporaria`. Se algum teste antigo quebrar, o erro está na implementação.
9. Manter tudo em português — código, comentários, commits e documentação. Comentário explica *por quê*, não *o quê*, no estilo do código existente.
10. **Não dar push sem autorização explícita.** Commit local é livre; `push`, PR e merge só quando o Jean pedir.
11. Diante de qualquer ambiguidade que envolva segredo, banco remoto ou Storage: **parar e perguntar**.

---

*Fatia derivada das Seções 2.5 e 8.5 do PRD Técnico v4.1 e do cartão "[Deploy] Ambiente de homologação" da Sprint 1. Não altera decisões de arquitetura. Registra uma escolha que o v4.1 deixava aberta (Render, e não Railway, Seção 3.1) e uma restrição que afeta o cartão de e-mail (SMTP bloqueado no Render Free). Após a execução, atualizar a Seção 12 do PRD Técnico com o endereço da homologação.*
