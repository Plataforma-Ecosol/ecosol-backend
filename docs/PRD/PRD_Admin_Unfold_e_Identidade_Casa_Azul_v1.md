# PRD — Admin com Unfold e identidade visual da Casa Azul

16/10/2026 · Jean Macedo

## Contexto e objetivo

O site público já tem a cara da Casa Azul: paleta, logo, fonte dos títulos, componentes e a página "Saiba mais". A área administrativa, onde a equipe da Casa Paul Singer passa a maior parte do tempo, continua com o visual padrão do Django: cinza, em inglês em alguns pontos, sem logo e com um link "Ver o site" que leva a uma página 404. Para quem usa as duas telas, parecem dois sistemas diferentes.

Este PRD junta os dois cards que resolvem isso, porque um é a base do outro e os dois mexem nos mesmos arquivos: o card 70 troca o tema do Admin pelo Unfold sem mudar nenhuma regra, e o card 71 aplica a identidade da Casa Azul sobre esse tema.

**História:** como membro da equipe da Casa Paul Singer, quero que a área administrativa tenha a mesma cara do site público, em português e fácil de navegar, para reconhecer que é a mesma plataforma e achar rápido o que preciso cadastrar.

- **Cards:**
  - [\[Admin\] Integrar o Unfold ao Django Admin atual · 3 pts](https://trello.com/c/S1MINmj7/70-admin-integrar-o-unfold-ao-django-admin-atual-3-pts) (Em Andamento)
  - [\[Admin\] Identidade visual da Casa Azul no Admin · 2 pts](https://trello.com/c/mtbKqBUl/71-admin-identidade-visual-da-casa-azul-no-admin-2-pts) (Em Andamento)
- **Origem:** decisão sobre a área da Casa Paul Singer (cards #68 e #69): CRUD no Django Admin com Unfold, sem muita complexidade; insights e interações numa página Next separada.
- **PRDs anteriores:** Django Admin v1 (`docs/PRD/PRD_Implementacao_Django_Admin_v1.md`), homologação v1 (WhiteNoise e `collectstatic`), e no frontend os PRDs de paleta, logo e base visual (`ecosol-frontend/docs/PRD/`). As cores e os arquivos da logo vêm de lá.
- **Escopo:** só o backend (`apps/ecosol-backend`). Nenhuma mudança em model, migration, serializer ou endpoint. O frontend só cede arquivos de imagem.
- **Ponto de partida:** a `staging` com o PR #19 (foto do coletivo) mesclado. A branch `feat/filtros-combinados` não mexe no Admin, então não deve haver conflito.
- **Entrega:** uma branch e um PR para os dois cards, com um commit por card. Total de 5 pontos.

## Decisões de 16/10

- **Os dois cards num PR só.** O 71 depende do 70 e os dois editam `settings.py` e `admin.py`. Separar geraria dois PRs seguidos nos mesmos arquivos. Os commits continuam separados, um por card, para a revisão.
- **Tema claro fixo (`"THEME": "light"`).** É a mesma decisão do frontend (PR #7: um tema só, claro). O Unfold tem modo escuro e um seletor de tema; fixar o claro tira o seletor e evita testar duas paletas.
- **As cores saem dos mesmos hex do `globals.css`.** O backend guarda os hex exatamente como no frontend e converte para `oklch()` na carga das settings, porque é o formato que a documentação do Unfold usa. Assim a comparação entre os dois repositórios é de texto igual a texto igual.
- **`primary` é a escala azul; `base` é a escala neutra quente (stone).** O Unfold só tem duas escalas de cor. O texto do site já é `#1C1917` (stone-900), e o neutro quente conversa com o bege melhor que o cinza azulado padrão do Unfold.
- **Bege entra pela tela de login; dourado fica de fora do tema.** Ver "Onde entram o bege e o dourado". Este é o principal ponto para confirmar com a equipe.
- **Logo e favicons são cópias dos arquivos do frontend**, em `rede/static/rede/marca/`. Quando a Casa Azul mandar o SVG ou o PNG grande, a troca é feita nos dois repositórios.
- **"Ver site público" vem de variável de ambiente** (`DJANGO_URL_SITE_PUBLICO`), como o link "Área da equipe" do frontend usa `NEXT_PUBLIC_ADMIN_URL` (card #72). O backend e o site ficam em domínios diferentes.
- **Grupos também passam para o Unfold.** O `Group` do Django aparece no Admin mesmo sem estar entre as 6 telas do card. Sem registrar de novo com o Unfold, essa tela ficaria sem estilo. Ele vai para o grupo "Acesso" do menu.
- **WhiteNoise já existe** (PR #17, homologação). O card 70 diz que não há, mas o texto é anterior a esse PR. O `collectstatic` do `Dockerfile` e do CI já empacota os estáticos do Unfold; falta só um teste que prove isso.
- **Nenhum template sobrescrito, nenhum CSS próprio.** Tudo por `UNFOLD` no `settings.py` e pelas classes do Unfold no `admin.py`.

## Parte 1 — Unfold no lugar do tema padrão (card 70)

O CRUD continua o mesmo: os mesmos campos, blocos, filtros, buscas, inlines e permissões. Muda só a classe de onde cada tela herda.

### Dependência

- `django-unfold` no `requirements.txt`, fixado na versão menor instalada: `django-unfold~=0.N.0`, com `N` a versão do dia. O Unfold ainda está em 0.x e lança versões quase toda semana, então um `>=` solto pode trazer mudança de comportamento num deploy qualquer. Antes de fixar, conferir nas notas da versão que ela suporta Django 5.2.
- Licença MIT, compatível com a GPLv3 do projeto.

### `INSTALLED_APPS`

`"unfold"` antes de `"django.contrib.admin"`. É isso que faz os templates do Unfold valerem no lugar dos do Admin. Nenhum `unfold.contrib.*` nesta entrega: filtros, formulários e inlines especiais não são usados.

### `rede/admin.py`

| Hoje | Passa a ser |
| --- | --- |
| `admin.ModelAdmin` (Categoria, Coletivo, Pessoa, Evento, Ponto de Interesse) | `unfold.admin.ModelAdmin` |
| `admin.TabularInline` (pessoas, slugs anteriores, imagens do evento) | `unfold.admin.TabularInline` |
| `UsuarioAdmin(UserAdmin)` | `UsuarioAdmin(UserAdmin, ModelAdmin)` com os formulários do Unfold |
| `Group` com o `GroupAdmin` do Django | `GrupoAdmin(BaseGroupAdmin, ModelAdmin)` |
| `site_header` e `site_title` no topo do arquivo | Saem daqui e vão para `UNFOLD` (Parte 2) |

O `UsuarioAdmin` continua herdando de `UserAdmin` primeiro. É o que preserva o hash da senha e o cadastro em duas etapas (o teste 5 do `test_admin.py` existe para isso). O Unfold entra como segunda base e traz os formulários estilizados:

```python
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from unfold.admin import ModelAdmin, TabularInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


# O Django registra o Group sozinho, com a classe dele. Registrar de novo com
# o Unfold é o que dá a esta tela o mesmo visual das outras.
admin.site.unregister(Group)


@admin.register(Group)
class GrupoAdmin(BaseGroupAdmin, ModelAdmin):
    """Grupos de permissão. Sem uso no MVP (papel único), mas a tela existe."""
```

As docstrings e comentários atuais continuam. O `index_title = "Administração"` pode ficar no `admin.py`: o Unfold não tem chave própria para ele.

### O que conferir na tela, um por um

Os testes de fumaça só provam que cada tela abre. Estas partes têm comportamento próprio e precisam de uma olhada no navegador depois da troca:

- Coletivo: `ativo` editável na listagem, categorias com `filter_horizontal`, prévia da foto, os dois inlines somente leitura com o link "abrir ficha".
- Pessoa: autocomplete de coletivo e o bloco de dados sensíveis **recolhido** (classe `collapse`) com o aviso em destaque.
- Evento: `date_hierarchy`, galeria com prévia das imagens e upload.
- Ponto de Interesse: autocomplete de coletivo e upload da capa.
- Usuário: adicionar (duas etapas), editar e trocar a senha.

Se algum desses itens perder o comportamento com o Unfold, ajustar só no `admin.py`, sem template.

## Parte 2 — Identidade da Casa Azul (card 71)

### Cores

Um módulo novo, `config/identidade.py`, guarda as escalas em hex e a conversão. As settings só leem dele.

```python
"""Cores da Casa Paul Singer na área administrativa.

Os hex são os mesmos do `@theme` de `ecosol-frontend/src/app/globals.css`.
Mudou uma escala lá, muda aqui também (o comentário do globals.css pede o
mesmo no sentido contrário).
"""
import math

DEGRAUS = ("50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950")

# Azul da marca no degrau 800 (#33469B), como no frontend.
AZUL = dict(zip(DEGRAUS, (
    "#F4F7FE", "#E4EAFA", "#CFD9F6", "#B0C1F1", "#869EEB", "#6882DD",
    "#536AC3", "#4359B0", "#33469B", "#2C3C77", "#182143",
)))

# Neutro quente (stone do Tailwind). O texto do site é o 900 (#1C1917).
NEUTRO = dict(zip(DEGRAUS, (
    "#FAFAF9", "#F5F5F4", "#E7E5E4", "#D6D3D1", "#A8A29E", "#78716C",
    "#57534E", "#44403C", "#292524", "#1C1917", "#0C0A09",
)))


def hex_para_oklch(cor: str) -> str:
    """Converte "#RRGGBB" para "oklch(L% C H)", o formato das cores do Unfold."""
    ...  # sRGB -> linear -> OKLab -> OKLCh (fórmulas de Björn Ottosson)


def escala_oklch(escala: dict[str, str]) -> dict[str, str]:
    return {degrau: hex_para_oklch(cor) for degrau, cor in escala.items()}
```

A conversão segue as fórmulas públicas do OKLab, com `L` em porcentagem e uma casa, `C` com três casas e `H` com uma. Cor sem croma (branco, preto) sai com `C` e `H` zerados. Valores de referência, já calculados, para conferir a função e os testes:

| Degrau | Azul (hex) | Azul (oklch) | Neutro (hex) | Neutro (oklch) |
| --- | --- | --- | --- | --- |
| 50 | `#F4F7FE` | `oklch(97.6% 0.010 267.4)` | `#FAFAF9` | `oklch(98.5% 0.001 106.4)` |
| 500 | `#6882DD` | `oklch(62.8% 0.140 270.0)` | `#78716C` | `oklch(55.3% 0.012 58.1)` |
| 600 | `#536AC3` | `oklch(55.1% 0.140 270.3)` | `#57534E` | `oklch(44.4% 0.010 73.6)` |
| 800 | `#33469B` | `oklch(42.9% 0.140 270.0)` | `#292524` | `oklch(26.8% 0.006 34.3)` |
| 900 | `#2C3C77` | `oklch(37.6% 0.102 269.5)` | `#1C1917` | `oklch(21.6% 0.006 56.0)` |

Branco (`#FFFFFF`) sai `oklch(100.0% 0.000 0.0)`.

No `UNFOLD["COLORS"]` entram só `base` e `primary`. O grupo `font` fica no padrão do Unfold, que já aponta para a escala `base`. Se a versão instalada exigir o dicionário completo, copiar o `font` padrão da documentação sem mudar os valores.

**Atenção ao degrau dos botões.** No site, botão e link usam o azul da marca (`#33469B`, degrau 800). Se o Unfold usar o degrau 600 nos botões, o Admin vai ficar com um azul mais claro (`#536AC3`). Os dois passam no contraste, mas a diferença aparece lado a lado. Conferir na primeira tela; se incomodar, é ponto para confirmar (ver o fim do documento), sem mexer nos valores da escala.

### Onde entram o bege e o dourado

O card pede azul, bege e dourado no `UNFOLD["COLORS"]`, mas o Unfold só tem as escalas `base` e `primary`. Não há lugar para uma terceira cor sem CSS próprio, e o card também pede "só configuração".

- **Bege:** entra na tela de login, pela imagem lateral do Unfold (`LOGIN["image"]`). A imagem de partida é a `opengraph-image.png` do frontend, que já é o círculo da logo sobre fundo `bege` (1200×630). Se o recorte da tela de login cortar o círculo, gerar uma versão vertical (por exemplo 800×1200) com o círculo no centro, sobre o mesmo bege.
- **Dourado:** fica de fora do tema nesta entrega. No site ele já é só detalhe (borda, divisor), nunca cor principal, e forçá-lo no Admin pediria uma folha de estilo própria, que o card 71 exclui.

### Logo e favicons

Arquivos em `rede/static/rede/marca/`, copiados do frontend. O `collectstatic` encontra a pasta sozinho (o app `rede` já está em `INSTALLED_APPS`).

| Arquivo | Origem no frontend | Uso no Admin |
| --- | --- | --- |
| `logo.png` | `public/brand/logo.png` (círculo recortado, 118×118, transparente) | `SITE_ICON`: topo do menu lateral e tela de login |
| `icon.png` | `src/app/icon.png` (512×512) | Favicon |
| `apple-icon.png` | `src/app/apple-icon.png` (180×180) | Ícone no iPhone |
| `favicon.ico` | `src/app/favicon.ico` | Favicon para navegadores antigos |
| `login.png` | `src/app/opengraph-image.png` (1200×630, fundo bege) | `LOGIN["image"]` |

Sobre o fundo branco do menu, o círculo branco da logo some na borda e fica só o retrato. É aceitável para um ícone de 32 a 40 px e não pede contorno. Registrar no PR como ficou.

### Títulos

| Chave | Valor | Onde aparece |
| --- | --- | --- |
| `SITE_TITLE` | "Área da equipe · Casa Paul Singer" | Aba do navegador |
| `SITE_HEADER` | "Casa Paul Singer" | Topo do menu lateral, ao lado da logo |
| `SITE_SUBHEADER` | "Área da equipe" | Abaixo do nome |

"Casa Paul Singer" é o mesmo nome curto do cabeçalho do site. "Área da equipe" é o mesmo texto do link do rodapé do site (card #72): quem clica lá chega numa tela com o mesmo nome.

### Menu lateral

`show_all_applications: False` e a navegação montada à mão, em português, com `show_search: True`. Cada item só aparece para quem tem a permissão de ver o model.

| Grupo | Itens (ícone Material Symbols) |
| --- | --- |
| Cadastros | Coletivos (`groups`), Pessoas (`person`), Categorias (`sell`) |
| Agenda e mapa | Eventos (`event`), Pontos de interesse (`location_on`) |
| Acesso | Usuários (`manage_accounts`), Grupos (`admin_panel_settings`) |

Com `show_all_applications` desligado, um model registrado e esquecido no menu some da navegação. Um teste garante que todo model registrado tem item no menu (ver "Testes").

### Link para o site público

Hoje o link padrão do Admin aponta para `/` do próprio backend, que não tem rota e devolve 404. Com a variável nova:

- `SITE_URL` recebe a URL do site público, e o link padrão passa a funcionar.
- `SITE_DROPDOWN` ganha o item "Ver site público" (ícone `open_in_new`), com a mesma URL.

| Ambiente | `DJANGO_URL_SITE_PUBLICO` |
| --- | --- |
| Local e CI | sem definir (padrão `http://localhost:3000`) |
| Homologação (Render) | `https://ecosol-frontend.vercel.app` |
| Produção | a URL do domínio, quando existir |

### Como fica o `settings.py`

```python
from django.templatetags.static import static
from django.urls import reverse_lazy

from config.identidade import AZUL, NEUTRO, escala_oklch

# --- Área administrativa (Unfold) -------------------------------------------
# Site público em outro domínio (Vercel). Sem a variável, vale o Next local.
URL_SITE_PUBLICO = env("DJANGO_URL_SITE_PUBLICO", default="http://localhost:3000")


def _marca(arquivo):
    """Caminho estático de um arquivo da marca, resolvido a cada requisição."""
    return lambda request: static(f"rede/marca/{arquivo}")


def _item(titulo, icone, app, model):
    """Item do menu lateral, visível só para quem pode ver o model."""
    return {
        "title": titulo,
        "icon": icone,
        "link": reverse_lazy(f"admin:{app}_{model}_changelist"),
        "permission": lambda request: request.user.has_perm(f"{app}.view_{model}"),
    }


UNFOLD = {
    "SITE_TITLE": "Área da equipe · Casa Paul Singer",
    "SITE_HEADER": "Casa Paul Singer",
    "SITE_SUBHEADER": "Área da equipe",
    "SITE_URL": URL_SITE_PUBLICO,
    "SITE_ICON": {"light": _marca("logo.png"), "dark": _marca("logo.png")},
    "SITE_FAVICONS": [
        {"rel": "icon", "sizes": "any", "type": "image/x-icon", "href": _marca("favicon.ico")},
        {"rel": "icon", "sizes": "512x512", "type": "image/png", "href": _marca("icon.png")},
        {"rel": "apple-touch-icon", "sizes": "180x180", "type": "image/png", "href": _marca("apple-icon.png")},
    ],
    "SITE_DROPDOWN": [
        {"icon": "open_in_new", "title": "Ver site público", "link": URL_SITE_PUBLICO},
    ],
    # Um tema só, claro, como o site (frontend, PR #7). Tira o seletor de tema.
    "THEME": "light",
    "LOGIN": {"image": _marca("login.png")},
    "COLORS": {"base": escala_oklch(NEUTRO), "primary": escala_oklch(AZUL)},
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Cadastros",
                "items": [
                    _item("Coletivos", "groups", "rede", "coletivo"),
                    _item("Pessoas", "person", "rede", "pessoa"),
                    _item("Categorias", "sell", "rede", "categoria"),
                ],
            },
            {
                "title": "Agenda e mapa",
                "items": [
                    _item("Eventos", "event", "rede", "evento"),
                    _item("Pontos de interesse", "location_on", "rede", "pontodeinteresse"),
                ],
            },
            {
                "title": "Acesso",
                "items": [
                    _item("Usuários", "manage_accounts", "rede", "usuario"),
                    _item("Grupos", "admin_panel_settings", "auth", "group"),
                ],
            },
        ],
    },
}
```

O `lambda` dentro de `_item` captura `app` e `model` como argumentos da função, então cada item tem a sua permissão (sem o erro clássico de `lambda` em laço). Os nomes de chave seguem a documentação do Unfold na versão fixada; se alguma tiver mudado, ajustar o nome e registrar no PR.

## Requisitos de implementação

Uma branch criada pelo desenvolvedor a partir da `staging`. Commits com aval do desenvolvedor, sem trailer de coautoria.

**Commit do card 70**

1. `django-unfold~=0.N.0` no `requirements.txt` (versão menor fixada, Django 5.2 conferido nas notas da versão).
2. `"unfold"` antes de `"django.contrib.admin"` no `INSTALLED_APPS`.
3. `rede/admin.py`: `ModelAdmin` e `TabularInline` do Unfold nas 5 telas e nos 3 inlines; `UsuarioAdmin(UserAdmin, ModelAdmin)` com os formulários do Unfold; `Group` registrado de novo com `GrupoAdmin`.
4. Testes do card 70 (ver "Testes"), com todos os testes atuais de `test_admin.py` passando sem alteração.
5. Conferência manual da lista "O que conferir na tela, um por um", no ambiente local (`docker compose up --build`).

**Commit do card 71**

6. `config/identidade.py` com `AZUL`, `NEUTRO`, `hex_para_oklch` e `escala_oklch`.
7. Arquivos da marca em `rede/static/rede/marca/` (tabela "Logo e favicons").
8. Bloco `UNFOLD` no `settings.py` e `URL_SITE_PUBLICO` lida de `DJANGO_URL_SITE_PUBLICO`. Remover `site_header` e `site_title` do `admin.py`.
9. `DJANGO_URL_SITE_PUBLICO` no `.env.example`, com comentário, e na tabela "Variáveis do Render" do README.
10. README, seção "Área administrativa": uma frase sobre o Unfold e o menu em grupos; este PRD na tabela de documentação.
11. Testes do card 71 (ver "Testes").

**Fechamento**

12. `ruff check .`, `makemigrations --check --dry-run`, `pytest` e `collectstatic` verdes (os mesmos passos do CI). Build do Docker também.
13. No Render (homologação), cadastrar `DJANGO_URL_SITE_PUBLICO=https://ecosol-frontend.vercel.app` antes do merge na `staging`.
14. Depois do deploy em homologação: login, uma edição em cada tela e uma troca de senha. Capturas de tela da tela de login, da listagem de Coletivos e do formulário de Pessoa no PR.
15. O desenvolvedor abre o PR com o `template_pr.md`, cola o link nos dois cards e move os dois para Code Review.

## Testes

Os testes atuais continuam como estão, principalmente os de LGPD (6 e 6b) e o 5 (`UsuarioAdmin` é um `UserAdmin`). Nenhum deles deve ser afrouxado para passar.

**Card 70, em `tests/test_admin.py`**

- **Toda tela herda do Unfold:** para cada classe em `admin.site._registry` (incluindo o `Group`), `isinstance(..., unfold.admin.ModelAdmin)`. Pega a tela nova que alguém registrar no futuro com a classe do Django.
- **Todo inline herda do Unfold:** para cada classe registrada, cada item de `inlines` é subclasse do `TabularInline` (ou `StackedInline`) do Unfold.
- **Formulários de usuário do Unfold:** `form`, `add_form` e `change_password_form` do `UsuarioAdmin` são as classes de `unfold.forms`.
- **Troca de senha continua com hash:** abrir `admin:rede_usuario_password_change` (200), enviar uma senha nova e conferir `check_password` verdadeiro e o campo `password` diferente do texto enviado.
- **Telas do Grupo abrem:** listagem e adição de `auth.Group` respondem 200 (os testes de fumaça atuais só cobrem o app `rede`).

**Card 70, em `tests/test_prontidao_deploy.py`**

- **Estáticos do Unfold sem `DEBUG`:** no mesmo molde de `test_admin_serve_css_sem_debug`, rodar o `collectstatic` num `tmp_path`, achar um `.css` qualquer dentro de `unfold/` e pedir pelo cliente com resposta 200. Procurar o arquivo, em vez de fixar o nome, evita quebrar o teste a cada versão do Unfold.

**Card 71, em `tests/test_identidade_admin.py` (novo)**

- **Conversão de cor:** `hex_para_oklch("#FFFFFF") == "oklch(100.0% 0.000 0.0)"` e `hex_para_oklch("#33469B") == "oklch(42.9% 0.140 270.0)"`; aceita hex em minúsculas.
- **Escalas completas e iguais ao frontend:** `AZUL` e `NEUTRO` têm os 11 degraus; `AZUL["800"] == "#33469B"`; `UNFOLD["COLORS"]["primary"] == escala_oklch(AZUL)`.
- **Tema claro fixo:** `UNFOLD["THEME"] == "light"`.
- **Arquivos da marca existem:** `finders.find("rede/marca/<arquivo>")` não é `None` para os cinco arquivos.
- **Login com a marca:** anônimo em `admin:login` recebe 200 com `rede/marca/logo.png`, o favicon e "Área da equipe" no HTML.
- **Início com o link do site público:** logado em `admin:index`, o HTML traz `settings.URL_SITE_PUBLICO` e "Ver site público".
- **Menu cobre todo model registrado:** o conjunto de links do `SIDEBAR` é igual ao conjunto das `changelist` de todos os models em `admin.site._registry`. Um model novo sem item no menu quebra o teste em vez de sumir da navegação.
- **Itens do menu abrem:** para cada item, `GET` como superusuário responde 200.
- **Permissão do menu:** um usuário da equipe só com `view_coletivo` vê o item "Coletivos" e não vê "Pessoas" (chamar a `permission` de cada item com um `request` do `RequestFactory`).

## Acessibilidade e celular

- **Contraste (WCAG AA, 4,5 para texto):** texto padrão do Unfold no neutro 700 (`#44403C`) sobre branco dá 10,3; texto sutil no 500 (`#78716C`) dá 4,8 sobre branco e 4,6 sobre o neutro 50; texto branco sobre azul 600 (`#536AC3`) dá 5,0 e sobre azul 800 (`#33469B`) dá 8,4. Todos passam. Se a revisão visual mostrar texto em outro degrau, medir antes de aprovar.
- **Português:** os títulos, o menu e os rótulos dos models já estão em português. Conferir se os textos próprios do Unfold (botões, busca do menu, filtros) aparecem traduzidos com `LANGUAGE_CODE = "pt-br"`. O que faltar fica anotado no PR, sem tradução própria nesta entrega.
- **Celular (360 px):** o Unfold tem menu recolhível. Conferir login, listagem de Coletivos e formulário de Pessoa nessa largura, sem rolagem horizontal fora das tabelas.
- **Teclado:** foco visível no menu lateral, no formulário de login e nos botões de salvar.

## LGPD

- **Nada muda no que o Admin mostra.** Os mesmos campos, nos mesmos blocos. O bloco socioeconômico de Pessoa continua recolhido e fora de coluna, filtro e busca, garantido pelos testes 6 e 6b.
- **Menu por permissão.** Os itens seguem a permissão de ver cada model, o que já prepara o Spike de permissões por papel: quem não pode ver Pessoa não vê nem o item.
- **Sem recurso de terceiros no Admin.** Conferir na aba Rede do navegador que o Admin não carrega fonte, ícone ou script de domínio externo. A tela de Pessoa tem dado sensível, e nenhum terceiro deve receber a visita a ela.

## Critérios de aceite

**Card 70**

- [ ] `django-unfold` no `requirements.txt` com a versão menor fixada, e `"unfold"` antes de `"django.contrib.admin"`
- [ ] As 6 telas (Coletivo, Pessoa, Categoria, Evento, Ponto de Interesse, Usuário), a de Grupos e os 3 inlines herdando das classes do Unfold, garantido por teste
- [ ] `UsuarioAdmin` herdando de `UserAdmin` e do `ModelAdmin` do Unfold, com os formulários de senha do Unfold e a troca de senha gravando hash
- [ ] Todos os testes de `tests/test_admin.py` passando sem alteração, incluindo os de LGPD
- [ ] Estáticos do Unfold servidos pelo WhiteNoise sem `DEBUG`, garantido por teste, e funcionando na homologação
- [ ] Comportamentos da lista "O que conferir na tela" funcionando
- [ ] Nenhum template sobrescrito

**Card 71**

- [ ] Escalas azul e neutra em `UNFOLD["COLORS"]`, a partir dos mesmos hex do `globals.css` do frontend
- [ ] Tema claro fixo, sem seletor de tema
- [ ] Logo da Casa Azul no menu lateral e na tela de login; favicon e ícone Apple
- [ ] Bege na tela de login (imagem lateral)
- [ ] Títulos em português: "Área da equipe · Casa Paul Singer" na aba, "Casa Paul Singer" e "Área da equipe" no topo do menu
- [ ] Menu lateral em três grupos (Cadastros, Agenda e mapa, Acesso), com item por permissão e teste cobrindo todo model registrado
- [ ] "Ver site público" no topo levando ao site, com a URL vinda de `DJANGO_URL_SITE_PUBLICO` (configurada no Render)
- [ ] Só configuração no `settings.py` e no `admin.py`, sem template nem CSS próprio

**Os dois**

- [ ] Ruff, migrations em dia, pytest e `collectstatic` verdes; build do Docker verde
- [ ] Funciona em celular (360 px) e desktop
- [ ] Capturas de tela no PR e os dois cards com o link do PR

## Fora do escopo

- **Dashboard, gráficos e páginas próprias no Admin.** Insights vão para a página Next (card #69).
- **Template sobrescrito ou CSS próprio.** Inclui o dourado no tema (ver "Pontos para confirmar").
- **Contribs do Unfold** (filtros especiais, `import_export` e afins).
- **Tradução dos textos internos do Unfold.** Só anotar o que estiver em inglês.
- **Logo maior ou em SVG.** Depende da Casa Azul; quando chegar, troca nos dois repositórios.
- **Permissões por papel.** O menu já respeita permissão, mas os papéis continuam os mesmos do MVP.

## Pontos para confirmar com a equipe

- [ ] **Dourado fora do tema do Admin.** Aceitar assim, ou abrir um card pequeno para uma folha de estilo (`UNFOLD["STYLES"]`) com o dourado em detalhes (divisor do topo, borda da tela de login)?
- [ ] **Tom do azul nos botões.** Se o Unfold usar o degrau 600, os botões do Admin ficam mais claros que os do site. Aceitar, ou estudar o ajuste na revisão visual?
- [ ] **Nome "Área da equipe"** na aba e no topo do menu, igual ao link do rodapé do site.
- [ ] **Grupos no menu.** Hoje não são usados (papel único). Deixar visível em "Acesso" ou esconder até o Spike de permissões?
