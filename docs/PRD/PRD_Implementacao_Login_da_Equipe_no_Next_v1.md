# PRD — Login da equipe valendo na página Next (Área da equipe)

23/11/2026 · Jean Macedo

## Contexto e objetivo

O cadastro da plataforma vive no Django Admin, no Render (`ecosol-backend-homolog.onrender.com/admin/`). O login grava o cookie de sessão (`sessionid`) preso a esse endereço. O site público fica na Vercel (`ecosol-frontend.vercel.app`) e, até hoje, não precisava saber quem está logado.

Isso muda com a Área da equipe no Next: o Relatório de coletivos (frontend#66 a #70) e, mais adiante, os insights do épico frontend#24. Essas páginas são só para a equipe. Como o navegador nunca entrega à Vercel um cookie que pertence ao Render, o Next enxerga todo mundo como anônimo, inclusive quem acabou de logar no Admin.

Este PRD resolve isso fazendo o Admin abrir também pelo endereço do site. O login, os usuários e as senhas continuam os mesmos, e o Django continua sendo quem autentica e autoriza.

**História:** como membro da equipe da Casa Paul Singer, quero entrar uma vez no Admin e abrir o Relatório da Área da equipe sem novo login, para acompanhar os coletivos sem trocar de sistema.

- **Card:** [\[Spike\] Login do Admin valendo na página Next (Vercel × Render) · 2 pts](https://github.com/Plataforma-Ecosol/ecosol-backend/issues/24) (backend#24)
- **Depende dele:** backend#58 (restringir o Relatório à equipe, "no padrão do backend#24"), backend#55 a #57 (API de agregados) e frontend#66 a #70 (Relatório).
- **PRDs e decisões anteriores:** PRD Técnico v4.1, decisões 8.3 (sessão httpOnly, sem JWT) e 8.4 (Admin como Interface 2); PRD Admin com Unfold v1 (menu lateral montado à mão); PRD do Frontend v1.1, Seção 10.1 (o navegador nunca fala com a API).
- **Escopo:** os dois repositórios. No backend, um endpoint, um item no menu do Admin e documentação. No frontend, o rewrite, a camada de acesso e a rota `/equipe/relatorio`. Nenhuma model nem migration.
- **Ponto de partida:** `staging` do backend (PR #54, já com o Unfold e a identidade da Casa Azul) e `staging` do frontend (PR #65).
- **Entrega:** um PR por repositório. O do backend fecha o backend#24; o do frontend fecha uma sub-issue nova no `ecosol-frontend` (ver "Ajustes nos cards").

## Decisões de 23/11

- **Caminho 1: rewrite no Next.** O site passa a responder `/admin/` e `/static/` repassando a requisição ao Django. O cookie de sessão fica gravado no endereço do site, e as páginas da Área da equipe passam a enxergá-lo.
- **Os caminhos 2 e 3 ficam descartados.** Subdomínios com cookie no domínio pai dependem do domínio próprio, que ainda não foi registrado. CORS com `SameSite=None` não funciona bem: `vercel.app` e `onrender.com` estão na Public Suffix List, então o cookie conta como de terceiros e os navegadores bloqueiam. Ele também quebraria a decisão de que o navegador não fala com a API.
- **`/api/*` fica fora do rewrite.** Quem chama a API é o servidor do Next, repassando o `sessionid`. O navegador continua sem falar com a API, e o backend continua sem CORS.
- **Rota do site: `/equipe/relatorio`.** A página do spike já é a rota de verdade, protegida e só com uma saudação. O frontend#67 preenche o conteúdo depois, na mesma página.
- **Prefixo da API da equipe: `/api/equipe/`.** O endpoint do spike passa a ser `GET /api/equipe/eu/` (o card fala em `/api/painel/eu/`).
- **"Equipe" é `is_staff`.** É o mesmo critério de quem consegue entrar no Admin. Papéis mais finos ficam para o Spike de permissões (backend#31).
- **As duas portas do Admin ficam abertas.** O endereço do Render continua respondendo, porque o rewrite depende dele. Não vamos bloquear o acesso direto, mas nenhum link aponta mais para ele: o "Área da equipe" do rodapé e o item "Relatório" do Admin passam a usar o endereço do site.
- **A autorização fica sempre no Django.** O Next só repassa o cookie e obedece a resposta. Não há `proxy.ts` nesta entrega.

## Como funciona

```
Navegador                  Next (Vercel)                     Django (Render)
   │  GET /admin/login/        │                                   │
   │──────────────────────────>│  rewrite: GET /admin/login/       │
   │                           │──────────────────────────────────>│
   │  POST /admin/login/ (CSRF)│──────────────────────────────────>│ valida usuário
   │<──────────────────────────│<──────── Set-Cookie: sessionid ───│
   │  (cookie gravado no endereço do site)                         │
   │                                                               │
   │  GET /equipe/relatorio    │                                   │
   │──────────────────────────>│  GET /api/equipe/eu/              │
   │                           │  Cookie: sessionid=...            │
   │                           │──────────────────────────────────>│ 200 se is_staff
   │<──── página renderizada ──│<───────── {"nome": "..."} ────────│ 403 se não
```

Acesso pelo caminho normal:

1. Rodapé do site → "Área da equipe" → `site/admin/` → login.
2. Admin → menu "Equipe" → "Relatório" → `site/equipe/relatorio`.
3. A página repassa o `sessionid` ao Django, recebe 200 e mostra o relatório.

Quem abre `/equipe/relatorio` sem estar logado vai para `/admin/login/?next=/equipe/relatorio` e, depois do login, volta para o relatório. Quem entrar pelo endereço do Render e clicar em "Relatório" faz login de novo uma vez, porque o cookie do Render não vale no site.

## Parte 1 — Backend

### Endpoint `GET /api/equipe/eu/`

Arquivo novo `rede/views_equipe.py`. A classe base `VisaoDaEquipe` é o padrão que o backend#58 pede: os endpoints do Relatório (backend#56 e #57) herdam dela.

```python
"""Views da API da equipe (`/api/equipe/`).

Separada da API pública de propósito. Lá tudo é AllowAny e só leitura do que
é público; aqui só entra quem tem sessão de equipe no Django Admin.
"""
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView


@method_decorator(never_cache, name="dispatch")
class VisaoDaEquipe(APIView):
    """Base de toda view da equipe.

    Só sessão (decisão 8.3): o padrão do DRF também aceita Basic Auth, que
    mandaria usuário e senha em cabeçalho. `never_cache` impede que proxy ou
    CDN guardem uma resposta de quem está logado e a sirvam a outra pessoa.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]


class EuView(VisaoDaEquipe):
    """Diz se a sessão é de equipe. Devolve só o nome de quem está logado."""

    def get(self, request):
        usuario = request.user
        return Response({"nome": usuario.get_short_name() or usuario.get_username()})
```

Em `rede/urls.py`:

```python
path("equipe/eu/", EuView.as_view(), name="equipe-eu"),
```

Respostas:

| Situação | Status | Corpo |
| --- | --- | --- |
| Sem sessão | 403 | mensagem padrão do DRF |
| Logado sem `is_staff` | 403 | mensagem padrão do DRF |
| Logado com `is_staff` | 200 | `{"nome": "..."}` |

O DRF responde 403 (e não 401) para anônimo quando só há `SessionAuthentication`, porque ela não define cabeçalho `WWW-Authenticate`. O backend#58 aceita os dois. O frontend trata 401 e 403 da mesma forma.

### Item "Relatório" no menu do Admin

Novo grupo no `UNFOLD["SIDEBAR"]["navigation"]` do `config/settings.py`, depois de "Acesso":

```python
{
    "title": "Equipe",
    "items": [
        {
            "title": "Relatório",
            "icon": "bar_chart",
            # Endereço absoluto: a página vive no site, não no Admin.
            "link": f"{URL_SITE_PUBLICO.rstrip('/')}/equipe/relatorio",
            "permission": lambda request: request.user.is_staff,
        },
    ],
},
```

Os testes do menu em `tests/test_identidade_admin.py` assumem que todo item é uma `changelist` do Admin. Eles precisam separar os itens internos do externo:

- `test_menu_cobre_todo_model_registrado` compara só os links que começam com `/`.
- `test_itens_do_menu_abrem` é parametrizado só com os itens internos.
- Teste novo para o item externo: aponta para `URL_SITE_PUBLICO + "/equipe/relatorio"` e só aparece para `is_staff`.

### Nada muda na API pública

As views públicas continuam `AllowAny` e só leitura. O `REST_FRAMEWORK` global não é alterado. A restrição a sessão fica na `VisaoDaEquipe` para não mexer no que já funciona.

## Parte 2 — Frontend

### Rewrite em `next.config.ts`

```ts
/** Onde o servidor do Next encontra o Django. O mesmo valor da `lib/api.ts`. */
const API_INTERNA = (process.env.API_URL ?? "http://localhost:8001").replace(/\/+$/, "");

const nextConfig: NextConfig = {
  // O Django Admin exige barra no fim (`/admin/login/`). O padrão do Next é
  // tirar essa barra com um 308, e o Django devolve um 301 para pô-la de volta:
  // laço infinito. Sem o redirecionamento do Next, a barra chega ao Django.
  skipTrailingSlashRedirect: true,

  async rewrites() {
    return [
      { source: "/admin", destination: `${API_INTERNA}/admin/` },
      { source: "/admin/:caminho*", destination: `${API_INTERNA}/admin/:caminho*` },
      // CSS, JS e imagens do Admin (STATIC_URL do Django).
      { source: "/static/:caminho*", destination: `${API_INTERNA}/static/:caminho*` },
    ];
  },

  images: { /* como está hoje */ },
};
```

- **Lido no build.** `rewrites()` é avaliado no `next build`. Na Vercel, `API_URL` já existe nas variáveis do projeto. No `Dockerfile`, `API_URL` precisa estar definido antes do `npm run build` (hoje já está, conferir).
- **Barra no fim.** Conferir no spike se `:caminho*` preserva a barra final. Se não preservar, acrescentar antes uma regra com `source: "/admin/:caminho*/"` e `destination` também terminando em `/`. Ver "Pontos a verificar".
- **`/static/` livre.** A pasta `public/` do frontend só tem `brand/`, então não há conflito.

### Acesso à API da equipe em `src/lib/api.ts`

Continua sendo a única porta para o Django, agora com uma seção da equipe. O comentário do topo do arquivo passa a dizer que há duas fronteiras: a pública (com cache) e a da equipe (sem cache, com cookie).

```ts
import { cookies } from "next/headers";

/** Nome do cookie de sessão do Django (`SESSION_COOKIE_NAME`, padrão). */
const COOKIE_DA_SESSAO = "sessionid";

export type UsuarioDaEquipe = { nome: string };

/**
 * Quem está logado como equipe, ou `null`.
 *
 * NÃO usa `buscar()`: ela guarda resposta em cache (`revalidate`), e uma
 * resposta de quem está logado não pode ser reaproveitada para outra pessoa.
 * Só o `sessionid` é repassado, nenhum outro cookie do navegador.
 */
export async function buscarUsuarioDaEquipe(): Promise<UsuarioDaEquipe | null> {
  const sessao = (await cookies()).get(COOKIE_DA_SESSAO)?.value;
  if (!sessao) return null;

  const resposta = await fetch(montarUrl("/api/equipe/eu/"), {
    headers: { cookie: `${COOKIE_DA_SESSAO}=${sessao}` },
    cache: "no-store",
  });

  if (resposta.status === 401 || resposta.status === 403) return null;
  if (!resposta.ok) {
    throw new ErroDaApi("Falha ao consultar a sessão da equipe", resposta.status);
  }
  return (await resposta.json()) as UsuarioDaEquipe;
}
```

### Guarda das páginas em `src/lib/equipe.ts` (novo)

```ts
import { redirect } from "next/navigation";

import { buscarUsuarioDaEquipe, type UsuarioDaEquipe } from "@/lib/api";

/**
 * Chamada no topo de toda página de `/equipe`. Sem sessão de equipe, manda
 * para o login do Admin, que devolve a pessoa a `voltarPara` depois.
 *
 * Fica na página, e não num layout: o layout não roda de novo a cada
 * navegação, e a checagem precisa valer em toda requisição.
 */
export async function exigirEquipe(voltarPara: string): Promise<UsuarioDaEquipe> {
  const usuario = await buscarUsuarioDaEquipe();
  if (!usuario) redirect(`/admin/login/?next=${encodeURIComponent(voltarPara)}`);
  return usuario;
}
```

### Rota `src/app/equipe/relatorio/page.tsx` (nova)

```tsx
import type { Metadata } from "next";

import { exigirEquipe } from "@/lib/equipe";

export const metadata: Metadata = {
  title: "Relatório da equipe",
  // Sempre fora do buscador, em qualquer ambiente.
  robots: { index: false, follow: false },
};

export default async function RelatorioDaEquipe() {
  const usuario = await exigirEquipe("/equipe/relatorio");

  return (
    <section>
      <h1>Relatório da equipe</h1>
      <p>Olá, {usuario.nome}.</p>
      <p>Os indicadores dos coletivos chegam aqui no próximo card.</p>
    </section>
  );
}
```

O visual segue a base do site (cores e fonte dos títulos). Os cards do frontend#67 entram nesta mesma página. Se o Django estiver fora do ar, o `ErroDaApi` cai no `error.tsx` que já existe. Os estados próprios do Relatório ficam no frontend#70.

### Link "Área da equipe" em `src/lib/site.ts`

O padrão de `ENDERECO_DA_AREA_DA_EQUIPE` passa a ser `${ENDERECO_DO_SITE}/admin/`. `ADMIN_URL` continua valendo para sobrescrever, se um dia o Admin ganhar endereço próprio. O comentário do rodapé em `layout.tsx` ("em outro domínio") é atualizado.

### `robots.ts` e `sitemap.ts`

- Produção: `disallow: ["/admin/", "/equipe/"]` junto do `allow: "/"`. O comentário "Não há área restrita neste projeto" é reescrito.
- Homologação: continua bloqueando tudo.
- `sitemap.ts`: não muda. As rotas da equipe nunca entram nele.

## Parte 3 — Configuração dos ambientes

| Onde | Variável | Mudança |
| --- | --- | --- |
| Render (homologação) | `DJANGO_CSRF_TRUSTED_ORIGINS` | acrescentar `https://ecosol-frontend.vercel.app` à lista, separado por vírgula |
| Vercel | `API_URL` | nenhuma (já aponta para o Render) |
| Vercel | `ADMIN_URL` | remover, se estiver definida, para o link usar o padrão novo |
| `infra/docker-compose.yml` do backend | `DJANGO_CSRF_TRUSTED_ORIGINS` | `http://localhost:3000` (o Next do compose) |
| `.env` local (sem compose) | `DJANGO_CSRF_TRUSTED_ORIGINS` | `http://localhost:3000` |

**Por que o CSRF.** O Django confere o `Origin` do POST de login. Pelo rewrite, o `Origin` é o do site e o `Host` é o do Render. Sem o site na lista de origens confiáveis, o login responde 403.

O README hoje diz para não ligar `DJANGO_CSRF_TRUSTED_ORIGINS` no local. Essa recomendação continua valendo para as outras duas variáveis de deploy (`DJANGO_ATRAS_DE_PROXY_HTTPS` e `DJANGO_COOKIES_SEGUROS`). Incluir `http://localhost:3000` na lista de CSRF é seguro e passa a ser necessário. O README é ajustado para separar os dois casos.

**Ordem de deploy:** 1) variável no Render; 2) PR do backend na `staging`; 3) PR do frontend na `staging`.

## Documentação

- **PRD Técnico v4.1:** nova decisão **8.6. Área da equipe no Next pela mesma origem**, com o caminho escolhido, os descartados e o motivo. É a "nota curta em `docs/`" que o card pede, no lugar onde ficam as decisões de arquitetura. Nota na 8.4: o Next deixa de ser só leitura pública e ganha a Área da equipe, mas a autenticação continua inteira no Django.
- **README do backend:** seção nova "API da equipe" (`GET /api/equipe/eu/`, autenticação, respostas). Na "Área administrativa", o endereço oficial do Admin passa a ser o do site. Na tabela "Variáveis do Render", o valor novo de `DJANGO_CSRF_TRUSTED_ORIGINS`.
- **Frontend:** comentários de `.env.example` (`ADMIN_URL`), `lib/api.ts`, `robots.ts` e do rodapé.
- **Aviso à Casa Paul Singer:** o endereço do Admin passa a ser `ecosol-frontend.vercel.app/admin/`. Pedir para atualizarem os favoritos.

## Testes

### Backend (`tests/test_api_equipe.py`, novo)

- Anônimo em `/api/equipe/eu/` recebe 403.
- Usuário ativo sem `is_staff` recebe 403.
- Usuário `is_staff` logado recebe 200 com exatamente a chave `nome`.
- Usuário `is_staff` mandando Basic Auth (sem sessão) recebe 403. Prova que só a sessão vale.
- A resposta traz `Cache-Control` com `no-store` e `private`.
- Ajustes e teste novo em `tests/test_identidade_admin.py` (ver Parte 1).
- A suíte da API pública passa sem alteração.

### Frontend (Vitest)

- `buscarUsuarioDaEquipe`: sem cookie, devolve `null` sem chamar `fetch`; 403 e 401 devolvem `null`; 200 devolve o nome; 500 lança `ErroDaApi`; o `fetch` sai com `cache: "no-store"` e com só o `sessionid` no cabeçalho `cookie`. Mock de `next/headers`.
- `exigirEquipe`: sem usuário, chama `redirect` com `/admin/login/?next=%2Fequipe%2Frelatorio`.
- `next.config.ts`: `rewrites()` devolve as três regras com o destino a partir de `API_URL`, e `skipTrailingSlashRedirect` é `true`.
- `site.test.ts`: sem `ADMIN_URL`, o link é `${SITE_URL}/admin/`; com `ADMIN_URL`, vale ela.
- `robots.test.ts`: produção bloqueia `/admin/` e `/equipe/`; homologação continua bloqueando tudo.

### Roteiro manual na homologação

1. Rodapé → "Área da equipe" abre `vercel.app/admin/login/` com o visual do Unfold completo (CSS carregado).
2. Login funciona. Na aba Aplicativo do navegador, o `sessionid` aparece no domínio do site.
3. Editar e salvar um coletivo funciona (POST com CSRF pelo rewrite).
4. Enviar uma imagem de evento pelo Admin funciona (upload passando pela Vercel).
5. Menu "Equipe" → "Relatório" abre `/equipe/relatorio` com "Olá, <nome>".
6. Numa janela anônima, `/equipe/relatorio` leva ao login e, depois dele, volta ao relatório.
7. "Sair" no Admin encerra a sessão, e `/equipe/relatorio` volta a pedir login.
8. Com o Render dormindo (15 min sem acesso), anotar o que acontece no primeiro acesso ao `/admin/`.
9. Na aba Rede, as páginas do Admin não vêm do cache da Vercel (cabeçalho `x-vercel-cache` diferente de `HIT`).
10. O Admin pelo endereço do Render continua funcionando.
11. `/equipe/relatorio` tem `noindex` no HTML, e `/robots.txt` continua bloqueando tudo na homologação.
12. Celular (360 px) e desktop.

## Pontos a verificar no spike

São as incertezas que o spike existe para resolver. O resultado de cada uma vai para a decisão 8.6 e para o PR.

- **Barra no fim pelo rewrite.** Confirmar que `/admin/login/` chega ao Django com a barra, sem 301 em laço.
- **`Host` que chega ao Render.** Ver qual `Host` a Vercel manda no rewrite e se `ALLOWED_HOSTS` aceita. No compose, conferir `backend:8001` (já aceito).
- **Redirecionamentos do Django.** Conferir que todo `Location` devolvido pelo Admin (login, logout, salvar) é relativo. Se algum vier absoluto apontando para o Render, avaliar `USE_X_FORWARDED_HOST` com o domínio do site em `ALLOWED_HOSTS`.
- **Upload pelo rewrite.** Conferir o tamanho máximo de corpo que a Vercel aceita repassar. Se uma imagem grande falhar, registrar o limite e orientar o upload pelo endereço do Render.
- **Render acordando.** Ver se a Vercel espera cerca de 1 minuto ou devolve erro. Se devolver erro, registrar que basta recarregar.
- **Cache da Vercel.** A Vercel respeita o `Cache-Control` da origem. O Admin já manda `never_cache`, mas conferir na prática.

## LGPD e segurança

- **Nada de dado pessoal novo sai do Django.** O `/api/equipe/eu/` devolve só o nome curto de quem está logado. Os dados de Pessoa continuam só no Admin.
- **Sessão httpOnly, sem token no navegador** (decisão 8.3 preservada). O JavaScript do site não lê o cookie. Quem o repassa é o servidor do Next, e só ele.
- **Sem cache de resposta autenticada,** no Django (`never_cache`) e no Next (`cache: "no-store"`).
- **A senha passa pela Vercel.** O HTTPS termina na Vercel antes de seguir para o Render. É o mesmo provedor que já serve o site. Registrar na decisão 8.6.
- **Origem confiável fixa.** Só o endereço fixo da homologação entra em `DJANGO_CSRF_TRUSTED_ORIGINS`. Nunca `https://*.vercel.app`, que confiaria em qualquer projeto da Vercel. Por isso o login não funciona nos deploys de preview dos PRs, o que é aceito.
- **Fora do buscador:** `noindex` na página e `Disallow` no `robots.txt`.

## Critérios de aceite

**Backend (backend#24)**

- [ ] `GET /api/equipe/eu/` responde 200 para `is_staff` logado e 403 para anônimo e para usuário comum, garantido por teste
- [ ] Só autenticação por sessão nas views da equipe (Basic Auth recusado), garantido por teste
- [ ] Resposta sem cache (`never_cache`), garantido por teste
- [ ] `VisaoDaEquipe` como base para os endpoints do Relatório (backend#56 a #58)
- [ ] Item "Relatório" no menu do Admin, só para `is_staff`, apontando para o site
- [ ] Testes do menu ajustados para o item externo
- [ ] API pública sem nenhuma alteração; suíte existente passando
- [ ] `DJANGO_CSRF_TRUSTED_ORIGINS` atualizada no Render e no compose
- [ ] Decisão 8.6 no PRD Técnico, nota na 8.4 e README atualizado

**Frontend (sub-issue)**

- [ ] Rewrite de `/admin` e `/static` com `skipTrailingSlashRedirect`, sem `/api`
- [ ] Login, edição, upload e saída do Admin funcionando pelo endereço do site na homologação
- [ ] `buscarUsuarioDaEquipe` em `lib/api.ts`, sem cache e repassando só o `sessionid`
- [ ] `/equipe/relatorio` protegida: sem sessão de equipe, vai ao login e volta depois dele
- [ ] `noindex` na página; `/admin/` e `/equipe/` bloqueados no `robots.txt` de produção
- [ ] Link "Área da equipe" apontando para o `/admin/` do site
- [ ] Testes do Vitest listados acima

**Os dois**

- [ ] CI verde (back: ruff, migrations, pytest; front: lint, tsc, vitest, next build)
- [ ] Roteiro manual na homologação cumprido, com o resultado dos "Pontos a verificar" anotado no PR
- [ ] Funciona em celular e desktop
- [ ] PRs revisados por outra pessoa e ligados às issues com `Closes #N`

## Fora do escopo

- **Conteúdo do Relatório.** Indicadores, gráficos e filtros ficam nos backend#55 a #57 e frontend#66 a #70.
- **Bloquear o acesso direto ao Admin no Render.** Fica para quando houver VPS: o Django passa a ficar só na rede interna, e o único caminho para o `/admin/` passa a ser o site.
- **Domínio próprio.** Quando vier, o esquema continua o mesmo. Muda só o valor das variáveis.
- **`proxy.ts`.** A checagem fica nas páginas.
- **Login, logout ou cabeçalho de usuário no próprio Next.** Tudo continua no Admin.
- **Papéis além de `is_staff`.** Ficam com o Spike de permissões (backend#31).
- **CORS e qualquer `NEXT_PUBLIC_*`.**

## Ajustes nos cards

- **backend#24:** corrigir "pré-requisito do frontend#55" para frontend#24 e frontend#66; trocar `/painel` por `/equipe/relatorio` e `/api/painel/eu/` por `/api/equipe/eu/`; preencher Requisito/HU; colar os critérios de aceite deste PRD.
- **frontend#24 (épico):** os pré-requisitos "#59" e "#60" passam a ser backend#23 e backend#24; tirar a citação dos #56 a #58, que hoje são os cards de Autenticação pública; trocar `/painel` por `/equipe/relatorio`.
- **Sub-issue nova no `ecosol-frontend`:** "\[Spike\] Login da equipe: rewrite do Admin e rota /equipe/relatorio", como sub-issue do backend#24 (regra dos cards transversais com parte no frontend).
- **backend#58:** trocar "padrão definido no backend#24" pela referência à `VisaoDaEquipe`.

## Pontos para confirmar com a equipe

- [ ] **Pontos.** O card tem 2 pts e agora envolve os dois repositórios. Sugestão: 2 pts no backend#24 e 2 pts na sub-issue do frontend.
- [ ] **Nome do item no menu.** "Equipe → Relatório", ou só "Relatório" dentro de um grupo existente?
- [ ] **Aviso à Casa Paul Singer** sobre o novo endereço do Admin: quem avisa e quando (de preferência na Sprint Review, com a demo).
