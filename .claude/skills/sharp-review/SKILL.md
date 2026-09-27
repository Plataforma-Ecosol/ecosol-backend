---
name: sharp-review
argument-hint: "[<nº do PR | branch | caminho>] [--deep]"
description: Revisão de código multi-agente do diff atual (ou de um PR) do ecosol-backend, em modo comentário estrito — dispara quatro auditores por faixa de severidade mais um verificador adversarial, classifica cada achado como 🔴 Crítico / 🟡 Nocivo / 🔵 Incongruência / 🟣 Qualidade com um o-quê/por-quê/como-corrigir, e roda uma passada determinística das invariantes do projeto (LGPD e blindagem do serializer, chave de visibilidade `ativo`, paridade model↔migration, N+1, contrato da API, API somente leitura) quando o diff toca `rede/`, `config/` ou `tests/`. PARA e espera aprovação do usuário antes de postar qualquer coisa; grava a revisão em docs/revisoes/ quando passa de 3 comentários ou contém algum 🔴, e posta os achados aprovados como comentários inline no PR. Use sempre que pedirem para revisar código, revisar um diff ou PR, ou fazer uma revisão estrita/sharp review.
---

# sharp-review — ecosol-backend

Revisar um diff do jeito estrito: nunca enviar sozinho. Quatro auditores caçam
uma faixa de severidade cada, um verificador adversarial elimina falso positivo,
todo achado sobrevivente é escrito **para outra pessoa desenvolvedora**
(o quê / por quê / como corrigir), e a lista inteira **para num portão de
aprovação** — nada chega ao GitHub antes do usuário mandar.

Esta versão é do **backend da Plataforma Ecosol** (Django 5.2 + DRF, Postgres do
Supabase, licença GPLv3). O projeto trata dados pessoais sensíveis de pessoas
reais da Economia Solidária de Niterói: **a passada de LGPD não é opcional.**

O driver é o **`review.py`** (Python puro, sem dependência nova): ele roda a
passada determinística sobre o diff, monta o esqueleto do `.md` no layout da
casa e valida o arquivo (taxonomia, schema por achado, paridade de contagem e
checagem de comentário raso). Você conduz a revisão; o driver garante que o
`.md` arquivado está em conformidade.

A fonte única de verdade das faixas e do contrato de comentário é
`references/taxonomia-severidade.md`. As regras específicas do projeto estão em
`references/invariantes-ecosol.md`. **Leia as duas antes de compor achados.**

## Referências (ler antes de revisar)

- `references/taxonomia-severidade.md` — as quatro faixas (🔴🟡🔵🟣), a regra de
  sobreposição, o contrato **explicativo** do comentário, o schema `.md` por
  achado e o formato de retorno dos agentes. Entregue este arquivo a todo auditor.
- `references/invariantes-ecosol.md` — as regras deste repositório: LGPD e
  blindagem do serializer, chave de visibilidade `ativo`, migrations, N+1 e
  desempenho, contrato da API, API somente leitura, convenções. Com a citação do
  PRD correspondente. Entregue também a todo auditor.

## Os agentes (em `.claude/agents/`)

- `review-critical-auditor` → 🔴 vazamento de dado pessoal, falha de
  autorização, segredo exposto, bug que corrompe dado ou quebra caminho
  principal, migration destrutiva, escrita na API pública.
- `review-harm-auditor` → 🟡 N+1, consulta sem limite, paginação desfeita, campo
  filtrado sem índice, quebra de contrato da API, trabalho evitável por item.
- `review-incongruence-auditor` → 🔵 má prática, bug não crítico, reinvenção do
  que o Django/DRF já oferece, código otimizável (degraus 2–6 da escada YAGNI).
- `review-quality-auditor` → 🟣 duplicação, docstring ausente ou mecânica,
  organização, nomenclatura, código especulativo (degrau 1 do YAGNI).
- `review-verifier` → refutador adversarial; devolve CONFIRMADO / PLAUSÍVEL /
  REFUTADO por achado.

## Fluxo

### 0. Resolver o alvo e obter o diff

- **PR informado** (número ou URL): `gh pr diff <n>` para o patch; guarde o
  número para postar depois.
- **Local** (padrão): diff contra o merge-base com a branch base. Neste repo a
  base de trabalho é **`staging`** (homologação; `main` é produção — PRD 10.1).
  Tente `git diff @{upstream}...HEAD` primeiro; sem upstream, use
  `git diff origin/staging...HEAD` (caindo para `origin/main` se não resolver).
  Só se nenhuma base resolver, caia para `HEAD~1` e **diga isso**
  ("nenhuma branch base encontrada — revisando só o último commit"), para que
  uma revisão parcial nunca seja silenciosa. Um argumento de branch/caminho
  restringe o escopo. Some `git diff HEAD` para pegar trabalho não commitado.
- Reúna o contexto normativo para entregar aos auditores: `README.md` do
  backend, `docs/PRD/PRD_Tecnico_Ecosol_Niteroi_v4.1.md` e o PRD de
  implementação da fatia em questão (por exemplo
  `PRD_Implementacao_Django_Admin_v1.md` quando o diff toca `rede/admin.py`),
  mais qualquer `CLAUDE.md` em diretório ancestral de um arquivo alterado.
  Os PRDs ficam na umbrella (`../../docs/PRD/`), fora deste repositório.
- Se o diff estiver vazio, diga e pare.

### 1. Passada determinística (rode você mesmo, sem agente)

Antes de qualquer agente, rode o driver sobre o diff. São as regras que a
máquina confere melhor que qualquer leitor — e que nenhum auditor deve precisar
"lembrar" de checar:

```powershell
git diff origin/staging...HEAD | python .claude\skills\sharp-review\scripts\review.py --checar-diff --stdin
```

```bash
gh pr diff 7 | python .claude/skills/sharp-review/scripts/review.py --checar-diff --stdin
```

Ele devolve candidatos já classificados por faixa, com arquivo:linha e a citação
do PRD. Tratamento:

- Achados marcados `determinístico` são **CONFIRMADOS por construção** — cite a
  evidência (a linha do diff) e **pule o verificador**.
- Achados marcados `heurístico` (por exemplo "consulta sem `prefetch_related`",
  "model alterado sem migration") são **candidatos**: confirme lendo o arquivo
  antes de virarem achado, ou mande ao verificador junto com o resto.
- Um erro de execução do driver não anula a revisão — siga sem ele e **diga que
  a passada determinística não rodou**.

Confira também, com `git` e não com o driver:

1. **Numeração de migration.** O prefixo `000N_` da migration nova precisa vir
   depois da última migration já em `origin/staging`
   (`git ls-tree origin/staging rede/migrations/`). Duas branches gerando `0005_`
   quebram o `migrate` no merge → 🔴.
2. **Segredos.** Nenhum `.env` no diff; nenhuma credencial literal. Se houver,
   além do achado, avise que a chave precisa ser **rotacionada** — o histórico
   do Git guarda.

### 2. Disparar os auditores (em paralelo)

Dispare os quatro auditores **concorrentemente** — se a ferramenta Workflow
estiver disponível, orquestre como fase de busca e depois fase de verificação;
senão, emita as quatro chamadas `Agent` numa única mensagem.

Entregue a cada auditor: o diff, a lista de arquivos alterados, o resultado da
passada determinística, os caminhos do PRD/README **e** os dois arquivos de
`references/`. Com `--deep`, mande ampliar o recall (ler mais contexto ao redor,
baixar a régua do que vale reportar). Cada um devolve achados no formato comum.

Direcione pelo caminho tocado — cada auditor cobre sua faixa em todos os
arquivos, mas estes são os pontos quentes:

| O diff toca | Atenção redobrada de |
|---|---|
| `rede/serializers.py` | `review-critical-auditor` (LGPD: `__all__`/`exclude`, campo não previsto no PRD 9.2, contato sem entrada em `CONTATOS_POR_CONSENTIMENTO`, omissão virando `null`) |
| `rede/models/**` | `review-critical-auditor` (paridade com migration, migration destrutiva) e `review-harm-auditor` (índice, `on_delete`) |
| `rede/views.py`, `rede/filters.py` | `review-critical-auditor` (`ativo` exposto, queryset sem `ativo=True`, escrita na API) e `review-harm-auditor` (N+1, paginação) |
| `rede/admin.py` | `review-critical-auditor` (campo sensível em `list_display`/`search_fields`) e `review-harm-auditor` (`list_select_related`) |
| `config/settings.py`, `config/urls.py` | `review-critical-auditor` (`DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, permissão padrão, mídia servida fora de `DEBUG`) |
| `tests/**` | `review-quality-auditor` (o teste falharia mesmo?) e `review-harm-auditor` (comportamento novo sem cobertura) |

**Nunca descarte em silêncio um achado de exposição de dado pessoal.** Se o
verificador refutar um achado de LGPD, apresente-o mesmo assim, com os dois
veredictos, e deixe o usuário decidir.

### 3. Juntar e deduplicar

Colete tudo. Deduplique por `caminho:linha + problema`; na sobreposição, fique
com a **maior** severidade (🔴 > 🟡 > 🔵 > 🟣). Violação de PRD permanece na faixa
do auditor que a pegou, citando a seção exata.

### 4. Verificação adversarial

Mande cada achado sobrevivente ao `review-verifier` (em paralelo). **Descarte os
REFUTADOS.** Mantenha os CONFIRMADOS. Mantenha os PLAUSÍVEIS marcando
`conf` ≤ 60. Aplique a correção de faixa que o verificador propuser. Exceção:
achado determinístico do driver e achado de exposição de dado pessoal (acima).

### 5. Classificar e compor

Atribua a faixa final e escreva cada achado no schema — **explicativo**:
`Problema` (o quê), `Por que importa` (consequência concreta), `Correção`
(remédio concreto, com bloco ```suggestion só quando a mudança resolve
exatamente). Específico ao código; nada de conselho genérico.

### 6. Portão de aprovação — PARADA OBRIGATÓRIA

Apresente os achados no chat, agrupados 🔴 → 🟡 → 🔵 → 🟣, cada um com
`caminho:linha` + o quê/por quê/como. **Não poste nada. Não chame `gh` nem
nenhuma ferramenta de comentário ainda.** Peça ao usuário para aprovar, editar
ou descartar. Este portão é a razão de ser da skill — nunca pule, nunca envie
sozinho.

- **Passou do limiar → arquive.** Se os achados mantidos forem **> 3** OU houver
  **algum 🔴**, grave também a revisão em `docs/revisoes/REVIEW_<slug>.md` (crie
  a pasta; `<slug>` = branch ou PR, em kebab-case). Monte o esqueleto com
  `review.py --scaffold --slug <slug>`, preencha com os achados, então
  **valide** (`review.py --validate`) e corrija todo erro antes de mostrar o
  caminho. O `.md` é a superfície de edição — as duas caixas começam
  desmarcadas; o usuário marca `aprovar` nos achados que quer postar (e/ou
  `descartar` no resto).

- Ofereça também a **explicação didática**: para quem está aprendendo a revisar,
  pergunte se quer que cada achado venha com o raciocínio de como chegar nele
  sozinho da próxima vez. Não é padrão — só quando pedido.

### 7. Enviar (só após aprovação explícita)

**Falha fechada.** Poste **apenas** os achados que o usuário aprovou
**afirmativamente** — achado que não foi nem aprovado nem descartado conta como
NÃO aprovado e é pulado. Se existir um `REVIEW_<slug>.md`, **releia primeiro** e
derive o conjunto aprovar/descartar das caixas (`aprovar` marcada → posta;
qualquer outra coisa → pula); senão, use as aprovações explícitas do chat. Nunca
infira aprovação de um "pode ir" quando existe estado por achado.

Poste cada achado aprovado como comentário inline via
`mcp__github_inline_comment__create_inline_comment` (uma chamada por achado;
comece pelo emoji da faixa; inclua o bloco ```suggestion só quando a correção
for exata). Se a ferramenta não estiver disponível, caia para
`gh api repos/{owner}/{repo}/pulls/{pr}/comments`. Se o alvo **não** for um PR,
imprima os achados aprovados e diga que o envio foi pulado (o `.md` é a
entrega). Depois de postar, atualize o `Status` do `.md` com o que foi enviado.

## Driver (é este que se roda)

```powershell
# PowerShell, a partir de apps\ecosol-backend
git diff origin/staging...HEAD | python .claude\skills\sharp-review\scripts\review.py --checar-diff --stdin
python .claude\skills\sharp-review\scripts\review.py --validate docs\revisoes\REVIEW_feat-admin.md
```

```bash
# bash / Git Bash, a partir de apps/ecosol-backend
gh pr diff 7 | python .claude/skills/sharp-review/scripts/review.py --checar-diff --stdin
python .claude/skills/sharp-review/scripts/review.py --validate docs/revisoes/REVIEW_feat-admin.md
```

Modos (saída `0` válido · `1` erros/achados · `2` uso):

```bash
python review.py --checar-diff <arquivo.diff>       # passada determinística sobre o diff
python review.py --checar-diff --stdin --json       # idem, saída JSON
python review.py --validate <review.md>             # valida uma revisão arquivada
python review.py --scaffold --pr 7 --counts 2,1,3,0 # esqueleto (ordem: 🔴 🟡 🔵 🟣)
python review.py --validate <review.md> --json      # { ok, errors, warnings, summary }
python review.py --validate --stdin                 # valida da entrada padrão
```

**Erro bloqueia; aviso não.** São erros: `caminho:linha` ausente, rótulo
`Problema`/`Por que importa`/`Correção`/`Verificação` faltando, campo vazio,
`Verificação` sem CONFIRMADO/PLAUSÍVEL + `conf`, e divergência entre a contagem
do resumo e a do corpo. Campo explicativo **raso** (<40 caracteres) é aviso —
conserte assim mesmo, para que a próxima pessoa entenda o achado.

## Portões rígidos

- **Aprovação antes do envio, sempre — falha fechada.** Nenhuma chamada de
  `gh`/comentário antes do usuário aprovar, e poste *só* o que foi aprovado
  afirmativamente. Esta regra vence qualquer impulso de "pode mandar".
- **Dado pessoal nunca é descartado em silêncio.** Achado de exposição de dado
  de Pessoa, de endereço ou de contato sem consentimento é apresentado mesmo
  quando refutado, com os dois veredictos.
- **Comentário explicativo.** Todo achado ensina: o quê, por que, como corrigir —
  específico ao código. Bandeira seca é defeito; o driver avisa sobre os rasos.
- **Uma faixa por achado**, a maior na sobreposição. Fique calibrado — não infle
  um 🟣 em 🔴. Inflar severidade destrói a confiança na revisão mais rápido do
  que deixar passar um 🟣.
- **Só o verificado.** Descarte os REFUTADOS; nunca poste achado que o
  verificador não sustentou (fora as exceções acima).
- **Arquive passando do limiar.** >3 achados ou algum 🔴 → um
  `docs/revisoes/REVIEW_<slug>.md` validado antes de postar.
- **Só linhas alteradas.** Aponte problema pré-existente apenas quando uma linha
  alterada o agrava ou o expõe — senão a revisão afoga em ruído que o autor não
  introduziu.

## Pegadinhas

- **Não é um PR?** Postar comentário inline exige PR. Para diff local, a entrega
  é o `.md` + o resumo no chat; diga que o envio foi pulado em vez de inventar
  um PR.
- **`gh` precisa estar autenticado.** Sem
  `mcp__github_inline_comment__create_inline_comment` na sessão, o fallback
  `gh api` precisa de `{owner}/{repo}/{pr}` resolvidos — aqui,
  `Plataforma-Ecosol/ecosol-backend`.
- **Os PRDs vivem fora do repositório.** Estão em `../../docs/PRD/` na pasta
  umbrella `ecosol-fullstack`, que não é repositório Git. Se não estiverem
  acessíveis, **diga** que a conferência contra o PRD foi parcial em vez de
  supor a regra.
- **Migration é código gerado.** O `ruff` exclui `**/migrations/**`
  (`pyproject.toml`), então não comente estilo de migration. Comente
  **semântica**: perda de dado, ordem, reversibilidade.
- **Este repo não tem `docs/`.** A primeira revisão arquivada cria
  `docs/revisoes/`. Se o time não quiser revisões versionadas, o caminho entra
  no `.gitignore` — pergunte antes de commitar a pasta.
- **A umbrella não é repositório Git.** Todo comando `git` roda a partir de
  `apps/ecosol-backend`.
- **Emoji no Windows** passa bem por Python/pelo driver (UTF-8); não "conserte"
  os emojis das faixas para ASCII.
- **`/code-review` embutido é outra coisa** — revisa inline e não roda este
  portão nem esta taxonomia. Para este fluxo, use `/sharp-review`.
