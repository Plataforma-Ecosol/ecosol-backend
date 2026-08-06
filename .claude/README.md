# `.claude/` — configuração do Claude Code neste repositório

Versionada de propósito: a régua de revisão é do projeto, não de uma pessoa.

```
.claude/
├── agents/                       # subagentes usados pela sharp-review
│   ├── review-critical-auditor.md      🔴 LGPD, autorização, segredo, migration destrutiva
│   ├── review-harm-auditor.md          🟡 N+1, paginação, índice, contrato da API
│   ├── review-incongruence-auditor.md  🔵 má prática, bug menor, reinvenção (YAGNI 2–6)
│   ├── review-quality-auditor.md       🟣 duplicação, docstring, código especulativo
│   └── review-verifier.md              refutador adversarial
└── skills/
    └── sharp-review/
        ├── SKILL.md              o fluxo da revisão
        ├── references/
        │   ├── taxonomia-severidade.md   as quatro faixas e o contrato de comentário
        │   └── invariantes-ecosol.md     as regras deste repo, com citação do PRD
        └── scripts/
            └── review.py         driver: --checar-diff, --scaffold, --validate
```

## Como usar

Na raiz de `apps/ecosol-backend`, dentro do Claude Code:

```
/sharp-review 7          # revisa o PR #7
/sharp-review            # revisa a branch atual contra origin/staging
/sharp-review 7 --deep   # recall mais alto, para PR grande ou sensível
```

A skill **para** antes de postar qualquer comentário e espera aprovação item a
item. Nada vai para o GitHub sem você mandar.

## O driver sozinho

A camada mecânica roda sem a skill, e é útil até no seu próprio PR antes de
abrir:

```powershell
git diff origin/staging...HEAD | python .claude\skills\sharp-review\scripts\review.py --checar-diff --stdin
```

Python puro, sem dependência nova. Passa no `ruff check .` do CI.

## Guia de revisão

Como revisar um PR neste projeto — ordem de leitura, checklist das invariantes,
como escrever comentário: `docs/GUIA_REVISAO_PR.md`.
