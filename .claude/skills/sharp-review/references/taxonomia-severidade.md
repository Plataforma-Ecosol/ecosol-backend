# Taxonomia de severidade e contrato de comentário

Fonte única de verdade da `sharp-review` no **ecosol-backend**. A skill e todo
agente `review-*` citam este arquivo. Quatro faixas, uma por achado; o contrato
de comentário vale para todas.

## As quatro faixas

### 🔴 Crítico

Ameaça clara à **segurança dos dados, à privacidade das pessoas cadastradas ou à
disponibilidade** da aplicação.

- **Exposição de dado pessoal** — qualquer dado de `Pessoa` numa rota pública,
  endereço de coletivo (`logradouro`, `numero`, `complemento`, `cep`), dado
  cadastral (`cnpj`, `renda_obtida`, `historico_editais`, …), controle interno
  (`ativo`, `situacao`, `observacoes`, `nome_entrevistador`), flag de
  consentimento, ou contato sem a flag correspondente ligada. Inclui
  `fields = "__all__"` e `exclude` em serializer público (PRD 6.1).
- **Falha de autorização** — rota de escrita acessível sem sessão autenticada;
  `ModelViewSet` ou mixin de escrita na API pública (PRD 3 e 7).
- **Segredo exposto** — `SECRET_KEY`, senha, URL de banco com credencial, chave
  da AWS no código ou num `.env` commitado.
- **Bug que quebra a lógica** — código que produz resultado errado, corrompe
  dado ou derruba um caminho principal.
- **Migration destrutiva ou fora de ordem** — `RemoveField`/`DeleteModel`/
  estreitamento de tipo sem plano para os dados existentes; prefixo `000N_` que
  colide com o da `staging` (quebra o `db push`/`migrate` no merge).
- **Desempenho capaz de derrubar o serviço** — recursão sem limite, O(n²) em
  caminho quente, N+1 atravessando a requisição inteira.
- **Chave de visibilidade furada** — `ativo` exposto como parâmetro de consulta,
  ou queryset público sem `filter(ativo=True)` (emenda 10.2 do PRD).

### 🟡 Nocivo

Problema para a **base de código ou para o funcionamento** — não é ameaça
imediata de segurança ou disponibilidade, mas degrada o produto.

- Código pouco performático: consulta extra evitável, N+1 localizado, índice
  ausente implícito na forma da consulta, trabalho redundante.
- Endpoint servindo ou consultando **sem paginação**; conjunto de resultado sem
  limite; `pagination_class = None`; `max_page_size` acima de 100 (PRD 9.1).
- **Quebra de contrato da API** — campo renomeado ou removido da resposta, chave
  fora de `snake_case`, data fora de ISO 8601, envelope do DRF desfeito,
  `SEARCH_PARAM` mudado. Quebra o frontend, que é construído em paralelo.
- Risco de escala que só morde sob carga, não no caminho feliz (PRD 7: listagem
  abaixo de 500 ms).
- Comportamento novo sem teste que o cubra — em especial comportamento de
  visibilidade ou de omissão de contato.

### 🔵 Incongruência

**Má prática ou bug que não ameaça segurança nem disponibilidade.**

- Bug de lógica menor em caminho não crítico.
- Código que dá para simplificar ou otimizar sem mudar comportamento.
- **Reinvenção** — implementar à mão o que o Django, o DRF, a stdlib ou uma
  dependência já instalada oferece (degraus 2–6 da escada YAGNI abaixo).
  Exemplos deste projeto: validação manual onde caberia um validator do Django,
  paginação própria com a global já registrada, `filter()` em Python onde o ORM
  resolve, `slugify` caseiro.
- Divergência de estilo com o padrão estabelecido do repositório que o `ruff`
  não pega (organização de campos no model, ordem dos blocos, nomenclatura em
  inglês num repositório em português).

### 🟣 Qualidade de código

Prejudica a **manutenibilidade** — e neste projeto isso é requisito, não gosto:
o PRD 7 pede um sistema "compreensível e reaplicável por quem herdar o projeto".

- Código duplicado.
- **Docstring ausente, ou docstring que só descreve a mecânica.** O padrão desta
  base é explicar a *decisão* ("por que omitir a chave em vez de retornar
  `null`"), não repetir o nome da função. Código novo sem isso destoa.
- Organização fraca, nomenclatura ruim, código morto, abstração vazando.
- Comentário/docstring em inglês num repositório documentado em português.
- **Código especulativo** (YAGNI, degrau 1) — abstração com uma implementação
  só, configuração para valor que nunca muda, andaime "para depois",
  flexibilidade que ninguém usa. O PRD 7 diz explicitamente "evita-se
  sobre-engenharia".

**Regra de sobreposição:** se um achado cabe em mais de uma faixa, fique com a
**maior** severidade (🔴 > 🟡 > 🔵 > 🟣). Deduplique por `caminho:linha + problema`.

**Regra de calibração:** inflar severidade destrói a confiança na revisão mais
rápido do que deixar passar um 🟣. Um 🔴 significa "isso não pode entrar na
`staging`". Se você não defenderia isso numa conversa, não é 🔴.

## Escada YAGNI (todo auditor aplica)

Para cada bloco adicionado, pergunte em que degrau ele deveria ter parado.
Código que aterrissa num degrau mais baixo do que poderia é um achado — e a
correção **nomeia o degrau mais alto**.

1. **Isso precisa existir?** Necessidade especulativa → não deveria existir. → 🟣
2. **Já existe nesta base?** Reimplementa helper/padrão existente → reuse.
   → 🔵 (cópia-e-cola pura continua 🟣)
3. **O Django/DRF já faz?** `slugify`, validators, `TextChoices`,
   `CheckConstraint`, `PageNumberPagination`, `SearchFilter`, `OrderingFilter`,
   `django_filters` → use. → 🔵
4. **O banco resolve melhor?** Constraint/índice no banco em vez de checagem em
   Python; `on_delete` correto em vez de limpeza manual. → 🔵
5. **Dependência já instalada resolve?** `django-filter`, `django-storages`,
   `Pillow`, `django-environ` já estão no `requirements.txt`. Implementar à mão
   — ou adicionar dependência *nova* — em vez de usar. → 🔵
6. **Daria uma linha?** Indireção desnecessária em cima de um one-liner. → 🔵
7. Só então código sob medida se justifica — e apenas o mínimo que funciona.

Nunca troque por minimalismo: validação de entrada em fronteira de confiança,
tratamento de erro que evita perda de dado, medidas de segurança, blindagem de
dado pessoal, acessibilidade básica.

A correção precisa citar a alternativa concreta (o caminho do helper existente,
a API do Django/DRF, a dependência já instalada) — "isso está
sobre-engenheirado" sozinho não é achado.

## Contrato de comentário (vale para todo achado)

O comentário é lido por **outra pessoa desenvolvedora**, então todo achado
precisa ser **explicativo** — ensina, não só sinaliza. Cada achado declara:

1. **O quê** — o problema em linguagem simples, específico a *este* código
   (nomeie o símbolo/linha, não a categoria genérica).
2. **Por que importa** — a consequência concreta: o que quebra, vaza, fica lento
   ou confunde, e sob quais condições.
3. **Como corrigir** — remédio concreto. Inclua bloco ` ```suggestion ` **apenas
   quando a mudança for exata** e resolver o problema por inteiro.

Regras:

- Cite `caminho:linha` exato. Para violação de norma, **cite a seção do PRD ou a
  regra do docstring** e a linha que a quebra.
- Seja específico — nada de conselho genérico que um linter daria, nada de
  "considere as boas práticas".
- Só marque **linhas alteradas/adicionadas** do diff, a menos que uma linha
  alterada claramente quebre ou exponha código pré-existente.
- Não comente estilo que o `ruff` já reprova (`E`, `F`, `I`, `UP`, `B`, `DJ`,
  line-length 100), nem estilo de arquivo em `rede/migrations/` (excluído do
  lint por ser código gerado).
- Uma pessoa sênior não deve revirar os olhos. Se é implicância sem
  consequência, descarte.
- Em dúvida genuína, **formule como pergunta** em vez de afirmação. Uma pergunta
  específica ("isso não faz uma query por evento no loop?") é melhor revisão do
  que uma afirmação errada.

## Schema `.md` por achado

A forma que a skill escreve e que `review.py --validate` verifica:

```
### N.M <título> — `caminho/do/arquivo.py:LINHA`
**Problema:** <o quê — específico a este código>
**Por que importa:** <consequência concreta>
**Correção:** <como — remédio concreto; bloco ```suggestion quando exato>
**Verificação:** CONFIRMADO|PLAUSÍVEL · conf <0-100>
- [ ] aprovar   - [ ] descartar
```

## Formato de retorno do agente (o que cada auditor `review-*` devolve)

```
[<🔴|🟡|🔵|🟣>] caminho/do/arquivo.py:LINHA — <título>
   O quê: <descrição específica>
   Por quê: <consequência concreta>
   Correção: <remédio concreto; diga se é possível uma mudança exata de código>
   Regra: <seção do PRD / regra do docstring violada, quando houver>
   Conf: <0-100>
```

Termine com `Veredicto: <n> achados (<sua-faixa><n>)` ou `Veredicto: limpo`. Um
auditor de faixa única reporta só a contagem da própria faixa; a forma com os
quatro emojis `(🔴<a> 🟡<b> 🔵<c> 🟣<d>)` é o vocabulário que a skill usa depois de
juntar todos.
