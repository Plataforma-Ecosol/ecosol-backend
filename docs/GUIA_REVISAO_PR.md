## 0. O mal-entendido que trava todo revisor Jr
Revisar é responder três perguntas, e nenhuma delas exige senioridade:

1. **Isso faz o que o PR diz que faz?** (comparação, não julgamento)
2. **Isso quebra alguma regra escrita deste projeto?** (checklist, não intuição)
3. **Eu consigo entender isso daqui a seis meses?** (leitura, não expertise)

A regra de "ao menos uma revisão" existe no PRD (Seção 10.1) por dois motivos:
impedir que código quebrado entre, **e fazer o conhecimento circular**. Você é
metade do segundo motivo. Um PR que você não entendeu é um PR que o próximo
mantenedor também não vai entender. Isso é um achado legítimo, e é *seu* ângulo.

---

## 1. Ordem de leitura de um PR

Quase todo revisor iniciante abre a aba "Files changed" primeiro. É o pior lugar
para começar: você entra no detalhe sem ter o mapa, e acaba comentando vírgula
enquanto passa despercebida uma migration destrutiva.

A ordem que funciona:

### 1.1. Antes do diff — leia a intenção

- **A descrição do PR.** O que ele diz que muda e por quê. Se não houver
  descrição, esse já é o primeiro comentário: peça uma. O PRD exige que o PR
  descreva o que muda e por quê (Seção 10.1).
- **A seção do PRD correspondente.** Se o PR mexe no endpoint de coletivos, abra
  a Seção 9 do PRD Técnico. Se mexe no Admin, abra o `PRD_Implementacao_Django_Admin_v1.md`.
  **Este projeto tem contrato escrito.** Isso é enorme para um revisor Jr: você
  não precisa adivinhar o que é "certo", está documentado.

> Se o código diverge do PRD, existem duas possibilidades, e as duas são
> comentários válidos: ou o código está errado, ou o PRD precisa ser emendado
> **no mesmo PR**. O que não pode é divergirem em silêncio.

### 1.2. A lista de arquivos, sem abrir nenhum

Só os nomes. Já dá para formular perguntas caras:

- Mudou `rede/models/*.py` mas **não** tem nada em `rede/migrations/`? → problema.
- Mudou `rede/serializers.py` mas não tem nada em `tests/`? → problema.
- Mudou algo que o PR não menciona? → escopo. `feat: adiciona filtro por bairro`
  que também mexe em `config/settings.py` merece a pergunta "por quê?".

### 1.3. Os testes, antes do código

Contraintuitivo, e é o truque que mais acelera revisor iniciante. O teste diz
**o que o autor acredita que o código faz**. Ler `tests/test_api_coletivos.py`
antes de `rede/views.py` te dá o comportamento esperado de graça, em linguagem
de exemplo. Depois você lê o código só para conferir se ele cumpre.

Perguntas úteis nos testes:

- Existe teste para o comportamento novo, ou só para o caminho feliz?
- Existe teste para o caminho **negativo**? (neste projeto: o dado sensível
  *não* aparece; o coletivo inativo *não* é listado; o slug antigo de inativo
  responde 404)
- O teste falharia se o código estivesse errado? Um teste que passa com
  qualquer implementação não testa nada.

### 1.4. O diff, em ordem de dependência

Do fundo para a superfície — é a ordem em que um bug se propaga:

```
models/  →  migrations/  →  serializers.py  →  views.py / filters.py / urls.py  →  admin.py  →  tests/
```

### 1.5. Rode o código

**Não aprove um PR que você não rodou.** É a regra que mais compensa para quem
tem pouca experiência: você não precisa enxergar o bug no diff se a máquina
enxerga por você.

```powershell
# no seu clone, com a branch do PR
git fetch origin
git checkout <branch-do-pr>

cd C:\ecosol-fullstack\apps\ecosol-backend\infra
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend python manage.py makemigrations --check --dry-run  # "No changes detected"
docker compose run --rm --no-deps backend ruff check .                             # "All checks passed!"
docker compose run --rm backend pytest
```

E se o PR muda a API, bata no endpoint de verdade:

```powershell
docker compose up -d
curl "http://localhost:8001/api/coletivos/?page_size=2"
```

Olhar o JSON de resposta com os próprios olhos pega vazamento de campo em dois
segundos — mais rápido que qualquer leitura de diff.

### 1.6. Só então escreva os comentários

Escrever enquanto lê produz review incoerente (você comenta algo na linha 20 que
a linha 80 já resolvia). Leia tudo, faça uma lista, depois comente.

---

## 2. Checklist das invariantes deste projeto

Esta é a parte em que um revisor Jr **empata com um sênior**, porque não é
intuição — é conferência. Percorra na ordem; as três primeiras seções bloqueiam
merge.

### A. LGPD e exposição de dados — o risco nº 1 🔴

O projeto cadastra CPF, RG, cor/raça, identidade de gênero, orientação sexual,
deficiência e renda familiar. Um vazamento aqui não é bug, é dano a pessoas
reais. É a única categoria em que vale ser chato.

- [ ] **Nenhum serializer público usa `fields = "__all__"` ou `exclude`.**
      Regra do PRD 6.1 e do docstring de `rede/serializers.py`. `exclude` é
      lista negra: o campo sensível criado amanhã entra sozinho na resposta.
- [ ] **Nenhum serializer de `Pessoa` existe.** Nenhum dado de Pessoa é público,
      em nenhuma hipótese (PRD 4.2). Um `PessoaSerializer` em `rede/serializers.py`
      é 🔴 automático, mesmo que "só use um campo".
- [ ] **Campo novo no `fields` do `ColetivoSerializer`:** ele consta na lista de
      campos públicos do PRD 9.2? Se não consta, ou o PRD é emendado no mesmo PR,
      ou o campo sai.
- [ ] **Contato novo tem entrada em `CONTATOS_POR_CONSENTIMENTO`.** Sem entrada
      no mapa, o campo sai **sempre**, com ou sem consentimento — é exatamente o
      cenário que a estrutura foi feita para evitar.
- [ ] **Nenhum destes aparece em resposta pública:** `logradouro`, `numero`,
      `complemento`, `cep`, `cnpj`, `data_inicio`, `responsavel_grupo`,
      `motivo_criacao`, `renda_obtida`, `historico_editais`, `situacao`, `ativo`,
      `nome_entrevistador`, `observacoes`, e as próprias flags
      `exibir_*_publicamente`. `bairro` é o único dado geográfico público.
- [ ] **`latitude`/`longitude` só em `PontoDeInteresse`.** Nunca em `Coletivo`
      (PRD 4.5) — a sede de um coletivo pode ser a casa de alguém.
- [ ] **A omissão continua sendo omissão.** Contato sem consentimento tem a chave
      **removida** do JSON, não devolvida como `null` ou `""` (PRD 6.2). Um
      refactor de `to_representation` que troque `dados.pop()` por
      `dados[campo] = None` quebra o contrato do frontend (`telefone?: string`)
      **e** a promessa de minimização.
- [ ] **O teste de regressão de LGPD foi estendido, não só mantido verde.** Campo
      público novo → asserção nova. A suíte é "documentação viva da promessa"
      (PRD 6.3); ela só vale se acompanhar o modelo.

### B. Visibilidade pública (`ativo`) 🔴

- [ ] **`ativo` não vira parâmetro de consulta.** Não pode entrar no
      `ColetivoFilter`, nem em `filterset_fields`, nem em `search_fields`. É a
      emenda 10.2, e o motivo está no docstring de `rede/filters.py`: exposto,
      permitiria a qualquer pessoa listar exatamente os coletivos que a equipe
      decidiu tirar do ar.
- [ ] **O queryset da view mantém `filter(ativo=True)`.** Qualquer `queryset` novo
      em view pública começa filtrado.
- [ ] **O histórico de slug não fura a regra.** `_redirecionar_slug_antigo` filtra
      `coletivo__ativo=True`. Slug antigo de coletivo inativo responde 404, não 301.

### C. Migrations e esquema 🔴/🟡

- [ ] **Mudou model → tem migration no mesmo PR.** O CI roda
      `makemigrations --check --dry-run`; se estiver vermelho, é isso.
- [ ] **Nenhum `CREATE TABLE`/`ALTER TABLE` fora de migration.** "Esquema =
      migrations do Django, sempre. Ninguém edita tabela pelo painel do Supabase"
      (PRD 8.2). Se o PR menciona ter mexido no painel, isso é um achado.
- [ ] **Numeração sem colisão.** Duas branches abertas em paralelo geram duas
      `0005_*.py`; o merge das duas quebra o `migrate`. Confira o número da
      migration nova contra o que já está na `staging`.
- [ ] **Migration destrutiva vem com justificativa.** `RemoveField`, `DeleteModel`,
      ou `AlterField` que estreita tipo/tamanho (`max_length` de 200 → 100)
      **perde dado em produção**. Isso não é um "nit": peça no PR o que acontece
      com os registros existentes.
- [ ] **`null=True` num campo que já tem dados** exige default ou migration de
      dados. O Django pergunta isso no `makemigrations`; se o autor respondeu no
      automático, vale conferir.
- [ ] **Sem `RunPython` sem `reverse_code`** — migration de dados irreversível
      trava rollback.

### D. Desempenho e escala 🟡

O PRD 7 pede listagem abaixo de 500 ms, com paginação, índices e sem N+1.

- [ ] **Sem N+1.** Relação percorrida na serialização precisa de
      `prefetch_related` (M2M / reverse FK, como `categorias`) ou
      `select_related` (FK / OneToOne, como `coletivo`). O padrão está em
      `ColetivoViewSet.queryset`.
- [ ] **N+1 no Admin também conta.** `list_display` que mostra um campo de FK sem
      `list_select_related` faz uma query por linha da listagem. Vale para o PR
      do Django Admin que está por vir.
- [ ] **Paginação preservada.** É global (`config.settings.REST_FRAMEWORK`), então
      o risco aqui é o inverso: uma view que declara `pagination_class = None`,
      ou um `max_page_size` acima de 100, desfaz a proteção.
- [ ] **Campo novo de filtro/ordenação tem `db_index=True`?** `bairro` e `ativo`
      têm. Um filtro novo sobre campo sem índice é 🟡 — não erra o resultado,
      erra o tempo.
- [ ] **Nada de trabalho por item em loop.** Query, `save()` ou chamada externa
      dentro de `for` sobre queryset é o formato clássico do problema.

### E. Contrato da API 🟡

Quebrar contrato quebra o frontend, que está sendo construído em paralelo.

- [ ] Chaves em `snake_case`, datas em ISO 8601 (PRD 9.1).
- [ ] Envelope do DRF preservado: `count`, `next`, `previous`, `results`.
- [ ] Busca textual continua sendo `q` (`SEARCH_PARAM` em settings), não `search`.
- [ ] **Renomear ou remover campo de resposta é breaking change.** Precisa estar
      na descrição do PR e no PRD.
- [ ] Erros seguem a tabela: tipo inválido → 400; inexistente ou página fora da
      faixa → 404. Um `try/except` novo engolindo exceção pode transformar 400
      em 200 com lista vazia — sutil e ruim.
- [ ] O README documenta a rota nova. Este projeto é Tecnologia Social; a
      documentação em português é requisito (PRD 7), não cortesia.

### F. Segurança e permissões 🔴

- [ ] **Nenhuma rota de escrita na API pública.** Só `ReadOnlyModelViewSet`. Um
      `ModelViewSet`, um `mixins.CreateModelMixin` ou um `@action(methods=["post"])`
      em `rede/views.py` é 🔴 — contraria o PRD 3 e 7. Escrita vive no Admin,
      atrás de sessão autenticada.
- [ ] **`permission_classes` declarado explicitamente** em view pública nova. O
      padrão global já permitiria, mas o projeto exige a declaração (ver docstring
      de `ColetivoViewSet`).
- [ ] **Nenhum segredo no diff.** Nada de `SECRET_KEY`, senha, URL de banco com
      credencial ou chave da AWS em código. Se apareceu, além de comentar: a chave
      precisa ser **rotacionada**, porque o histórico do Git guarda.
- [ ] **`.env` não commitado.** Só `.env.example`, com placeholders.
- [ ] **`DEBUG` não vira `True` por default.** `DEBUG=True` em produção expõe
      stack trace e settings.
- [ ] Nada de SQL cru concatenado com entrada do usuário (`.raw()`, `.extra()`).
      O ORM parametriza; concatenação não.

### G. Convenções e manutenibilidade 🟣

- [ ] `ruff check .` limpo (o CI já garante — não gaste comentário com estilo que
      o linter pega).
- [ ] **Docstring explicando o *porquê*.** Este repositório tem um padrão de
      documentação incomumente alto: os docstrings explicam decisão, não mecânica
      ("por que omitir a chave em vez de retornar null"). Código novo sem isso
      destoa, e vale comentar — é o que torna o projeto reaplicável.
- [ ] Português nos docstrings, comentários e `verbose_name`.
- [ ] Conventional Commits (`feat:`, `fix:`, `test:`, `refactor:`, `chore:`, `docs:`).
- [ ] Sem código especulativo: abstração com uma implementação só, parâmetro que
      ninguém passa, `if` para um caso que não existe. O PRD 7 diz explicitamente
      "evita-se sobre-engenharia".
- [ ] Sem `print()` esquecido, sem código comentado, sem `TODO` sem dono.

---

## 3. Como escrever o comentário

A diferença entre um review útil e um review chato não está no que se acha —
está em como se escreve.

### A forma: o quê / por quê / como

```
🔴 `rede/serializers.py:58`

**O quê:** `EventoSerializer` usa `fields = "__all__"`.

**Por quê importa:** o PRD 6.1 proíbe — `__all__` é lista branca automática. Hoje
o model `Evento` não tem campo sensível, mas o dia em que alguém adicionar
`observacoes_internas` ao model, ele entra na resposta pública sozinho, sem
ninguém revisar. É exatamente o refactor distraído que a regra existe para pegar.

**Como corrigir:** declarar a lista explícita, como em `ColetivoSerializer`:

```suggestion
        fields = ["id", "titulo", "slug", "descricao", "data_inicio",
                  "data_fim", "local", "bairro", "link"]
```
```

Três coisas fazem esse comentário funcionar: cita `arquivo:linha`, cita a regra
escrita (o autor não precisa acreditar na sua palavra), e propõe o conserto.

### Marque o peso de cada comentário

Sem isso, o autor não sabe o que bloqueia e o que é gosto. Use prefixo:

| Prefixo | Significa | Bloqueia? |
|---|---|---|
| `bloqueia:` | precisa mudar antes do merge | sim |
| `sugestão:` | melhoraria, mas não impede | não |
| `nit:` | detalhe pequeno, fique à vontade para ignorar | não |
| `dúvida:` | não entendi, me explica | depende da resposta |
| `elogio:` | isso ficou bom | não |

`elogio:` não é enfeite. Review que só aponta erro treina o time a temer review.

### Perguntar > afirmar (principalmente quando você não tem certeza)

Comparar:

> ❌ "Isso aqui gera N+1."
> ✅ "dúvida: `evento.imagens.all()` dentro do loop do serializer não faz uma
> query por evento? Vi que em `ColetivoViewSet` a gente resolve isso com
> `prefetch_related`. É o mesmo caso ou tem algo diferente aqui?"

A segunda versão é **melhor review**, não mais fraca. Se você estiver certo, o
autor conserta igual. Se estiver errado, você aprendeu sem custo social — e a
resposta dele fica registrada no PR, virando documentação. Como Jr, esse formato
é sua ferramenta mais poderosa: transforma cada review numa aula.

### O que não comentar

- Estilo que o ruff já reprova. Redundante.
- Preferência pessoal sem consequência ("eu teria feito com list comprehension").
- Coisas fora do diff, a menos que uma linha alterada quebre código pré-existente.
  Senão o review vira lista de desejos e o autor para de ler.
- Reescrever a arquitetura no comentário. Se a discordância é grande, é conversa,
  não thread de PR.

---

## 4. Quando aprovar, quando bloquear, quando dizer "não sei"

| Situação | Ação |
|---|---|
| Entendi tudo, checklist passou, rodei local, testes cobrem o novo | **Approve** |
| Tem 🔴 ou 🟡 | **Request changes**, com o que precisa mudar |
| Só 🔵/🟣 e o autor é experiente | **Approve** com comentários não bloqueantes |
| Não entendi uma parte central | **Comment**, com a dúvida. Não aprove nem bloqueie ainda |
| Está fora da sua capacidade de avaliar | **Comment**, dizendo isso explicitamente |

Sobre a última linha — ela é a mais importante deste guia:

> **"Revisei os itens A–G do checklist e está tudo ok. A lógica de transação em
> `save()` eu não tenho experiência para avaliar com segurança — @fulano,
> consegue dar uma olhada nessa parte?"**

Isso é um review honesto e profissional. É infinitamente melhor que um "LGTM 👍"
que finge cobertura que não houve. Aprovar no escuro é o único erro realmente
grave que um revisor Jr pode cometer, porque destrói o valor da regra de revisão
obrigatória — e ninguém fica sabendo.

---

## 5. Usando a skill `sharp-review` sem terceirizar o julgamento

A skill está instalada em `.claude/skills/sharp-review/`. Ela roda quatro
auditores em paralelo, um verificador adversarial que descarta falso positivo, e
uma passada determinística das invariantes deste projeto. Mas ela **para** antes
de postar qualquer coisa, e espera você aprovar item a item.

Esse gate não é burocracia — é o desenho todo. Três regras de uso:

1. **Rode a skill depois da sua própria leitura, não antes.** Se você ler o
   relatório dela primeiro, sua atenção fica ancorada no que ela achou e você
   para de enxergar o resto. Faça sua passada, anote o que viu, *depois* rode e
   compare. A diferença entre as duas listas é o seu progresso medido, PR a PR.

2. **Nunca poste um comentário que você não sabe explicar.** Se a skill levantar
   algo que você não entendeu, pergunte a ela antes ("me explica por que isso é
   N+1 aqui"). Se ainda assim não estiver claro, descarte. Um comentário que você
   não consegue defender quando o autor responde queima sua credibilidade — e a
   credibilidade é o capital do revisor.

3. **A assinatura é sua.** O PR é aprovado pelo seu usuário, não pelo modelo. A
   skill acha candidatos; você decide o que é achado.

Uso típico:

```
/sharp-review 7          # revisa o PR #7
/sharp-review            # revisa a branch atual contra origin/staging
/sharp-review 7 --deep   # recall mais alto, para PR grande ou sensível
```

---

## 6. Seus primeiros cinco PRs

Um plano concreto para sair da insegurança sem fingir experiência:

1. **PR 1** — só o checklist da Seção 2, itens A, B e C. Nada mais. Se passar,
   aprove. Você já cobriu o que este projeto tem de mais crítico.
2. **PR 2** — checklist + ler os testes antes do código. Comente uma dúvida real,
   mesmo que se revele boba.
3. **PR 3** — checklist + rodar local. Compare o JSON da resposta com a tabela do
   PRD 9.2, campo por campo.
4. **PR 4** — faça sua revisão completa, depois rode a `sharp-review`. Anote o que
   ela achou e você não. Esse delta é seu plano de estudo.
5. **PR 5** — releia seus quatro reviews anteriores. Os padrões que se repetem
   viram itens novos em `references/invariantes-ecosol.md`.

Depois de uns dez PRs, você vai reparar que passou a ver certas coisas antes de
abrir o checklist. É assim que a experiência se forma — por repetição
estruturada, não por tempo passado.

---

## Referências rápidas

| Preciso conferir | Onde está escrito |
|---|---|
| O que é público no Coletivo | PRD Técnico §9.2 e `rede/serializers.py` |
| Regras de LGPD | PRD Técnico §6 |
| Por que `ativo` não é filtro | PRD Técnico §10.2 (emenda) e `rede/filters.py` |
| Contrato da API (params, erros) | PRD Técnico §9 e README do backend |
| Requisitos de desempenho | PRD Técnico §7 |
| Fluxo de branch e commits | PRD Técnico §10 |
| Regras do Django Admin | `PRD_Implementacao_Django_Admin_v1.md` §4 e §7 |
| Severidades da revisão | `.claude/skills/sharp-review/references/taxonomia-severidade.md` |
| Invariantes verificáveis | `.claude/skills/sharp-review/references/invariantes-ecosol.md` |
