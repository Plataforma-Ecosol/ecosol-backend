# PRD — Saiba mais: modelo de seções por subgrupo

16/11/2026 · Jean Macedo

## Contexto e objetivo

A página "Saiba mais" do site é uma página só, com o conteúdo fixo em `ecosol-frontend/src/lib/casa.ts`. Qualquer correção de texto precisa de um desenvolvedor e de um deploy. A equipe da Casa Azul quer editar esse conteúdo pelo Admin, e o site vai separá-lo em três subgrupos: Casa Azul, Economia Solidária e ITES/IFRJ.

Este PRD cobre o primeiro passo: o model que guarda as seções de cada subgrupo, a migration e a carga do conteúdo que já existe. É a base das outras tarefas da história: o Admin (#62) edita estas seções, o endpoint (#63) as publica, e o frontend (#75) as consome.

**História (backend#60):** como integrante da equipe da Casa Azul, quero editar pelo Admin os textos do Saiba mais (Casa Azul, Economia Solidária e ITES/IFRJ) para manter as informações atualizadas sem depender dos desenvolvedores.

- **Issue:** [backend#61 — \[Modelagem\] Saiba mais: modelo de seções por subgrupo · 3 pts](https://github.com/Plataforma-Ecosol/ecosol-backend/issues/61) (Sprint 3, Release R3)
- **História mãe:** [backend#60 — Conteúdo do Saiba mais editável pelo Admin · 8 pts](https://github.com/Plataforma-Ecosol/ecosol-backend/issues/60)
- **Depois desta:** backend#62 (Admin) e backend#63 (endpoint). No frontend, a #72 (rotas dos subgrupos) usa os mesmos valores de subgrupo, e a #75 consome a API.
- **PRDs anteriores:** "Página Saiba mais com contato da Casa Paul Singer" (`ecosol-frontend/docs/PRD/PRD_Pagina_Saiba_Mais_e_Contato_da_Casa_v1.md`), que define o conteúdo atual; e o padrão de imagem com nome único no bucket da foto do coletivo (PR #19).
- **Escopo:** só o backend. Model, migration de esquema, migration de dados e testes. Nenhuma mudança em Admin, serializer, endpoint ou frontend.
- **Ponto de partida:** a `staging` em `89ab9b2` (PR #54). A última migration é a `0005_coletivo_foto`.
- **Entrega:** uma branch (`feat/saiba-mais-modelo-secoes`) e um PR para a `staging`, com este PRD e a implementação juntos.

## Decisões de 16/11

- **Desenvolver antes da aprovação da Casa.** A Casa demora a mandar textos e aprovações. O conteúdo inicial vem do que já está no ar, mais um texto curto sobre a ITES escrito pelo time. Tudo fica editável pela própria Casa quando o Admin (#62) entrar, e o resultado é mostrado a ela depois (ver "O que mostrar à Casa").
- **Um model de seções, e não um model por subgrupo.** Os três subgrupos têm a mesma forma: uma lista ordenada de blocos com título, texto e imagem opcional. O subgrupo é um campo com três valores fixos.
- **Subgrupos fixos em `TextChoices`, e não uma tabela.** A #72 cria uma rota no frontend para cada subgrupo. Um subgrupo novo pediria rota, navegação e SEO novos, então não faz sentido a equipe criá-lo pelo Admin. Os valores já são os slugs das rotas: `casa-azul`, `economia-solidaria` e `ites-ifrj`.
- **Slug único no projeto inteiro, e não só dentro do subgrupo.** É o que a issue pede, e o endpoint de detalhe (#63) busca pelo slug sozinho, sem precisar do subgrupo na URL da API.
- **Texto simples, sem HTML nem Markdown.** O frontend já mostra os textos da Casa com `whitespace-pre-line`: linha em branco separa parágrafos. Aceitar HTML exigiria sanitizar a entrada para não abrir espaço para XSS; Markdown exigiria um renderizador no frontend. Se a Casa pedir negrito ou link no meio do texto, isso vira outro card.
- **Seção nova nasce despublicada.** `publicado` começa em `False`: a equipe escreve, revisa e só então publica. As seções da carga inicial já entram publicadas, para o site não ficar vazio no dia da troca.
- **Imagem com o mesmo cuidado da foto do coletivo.** Nome único no bucket, limite de 5 MB e descrição obrigatória quando houver imagem (é o `alt` que o leitor de tela lê).
- **Os contatos da Casa ficam fora deste model.** Telefone, e-mail, redes, endereço e horário são dados estruturados, com regras próprias (o telefone tem um número para exibir e outro para discar, por exemplo). O desenho de um model `Instituicao` de registro único para eles já existe no PRD do frontend, na seção "Próximo passo: edição pelo Admin". Até esse card existir, os contatos continuam em `casa.ts`.

## O model

### Arquivo e exportação

Arquivo novo: `rede/models/secao_saiba_mais.py`. A classe é reexportada em `rede/models/__init__.py`, no import e no `__all__`, como as outras.

### Campos

| Campo | Tipo | Regra |
|---|---|---|
| `subgrupo` | `CharField(max_length=30, choices=Subgrupo.choices, db_index=True)` | Obrigatório. `casa-azul`, `economia-solidaria` ou `ites-ifrj` |
| `titulo` | `CharField(max_length=200)` | Obrigatório. Vira o `<h2>` da seção no site |
| `slug` | `SlugField(max_length=220, unique=True)` | Obrigatório e único no projeto |
| `texto` | `TextField()` | Obrigatório. Texto simples; linha em branco separa parágrafos |
| `imagem` | `ImageField(upload_to=caminho_da_imagem, null=True, blank=True, validators=[validar_tamanho_da_foto])` | Opcional. Até 5 MB, em `saiba-mais/<uuid>.<ext>` no bucket |
| `imagem_descricao` | `CharField(max_length=200, blank=True)` | Obrigatória quando há imagem |
| `ordem` | `PositiveIntegerField(default=0)` | Posição dentro do subgrupo; menor vem primeiro |
| `publicado` | `BooleanField(default=False)` | Só seção publicada vai para a API (#63) |
| `criado_em` | `DateTimeField(auto_now_add=True)` | |
| `atualizado_em` | `DateTimeField(auto_now=True)` | |

### Código proposto

```python
"""Seção da página "Saiba mais", editável pela equipe no Admin."""
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models

from rede.models.coletivo import validar_tamanho_da_foto


def caminho_da_imagem(instancia, nome_original):
    """Nome único no bucket: `saiba-mais/<uuid>.<ext>`.

    Mesmo motivo da foto do coletivo: com `AWS_S3_FILE_OVERWRITE` no padrão
    `True`, duas seções que enviassem `foto.jpg` gravariam a mesma chave.

    Fica no nível do módulo para a migration conseguir referenciá-la.
    """
    extensao = Path(nome_original).suffix.lower()
    return f"saiba-mais/{uuid.uuid4().hex}{extensao}"


class SecaoSaibaMais(models.Model):
    """Um bloco de conteúdo de um dos subgrupos do "Saiba mais".

    Conteúdo institucional e público: nunca dado pessoal. Contatos da Casa
    (telefone, e-mail, endereço, horário) não moram aqui.
    """

    class Subgrupo(models.TextChoices):
        # Os valores são os slugs das rotas do frontend (/saiba-mais/<valor>).
        CASA_AZUL = "casa-azul", "Casa Azul"
        ECONOMIA_SOLIDARIA = "economia-solidaria", "Economia Solidária"
        ITES_IFRJ = "ites-ifrj", "ITES/IFRJ"

    subgrupo = models.CharField(
        "subgrupo", max_length=30, choices=Subgrupo.choices, db_index=True,
    )
    titulo = models.CharField("título", max_length=200)
    slug = models.SlugField(
        "slug", max_length=220, unique=True,
        help_text="Identifica a seção na API (ex.: quem-somos).",
    )
    texto = models.TextField(
        "texto",
        help_text="Texto simples. Deixe uma linha em branco entre os parágrafos.",
    )
    imagem = models.ImageField(
        "imagem", upload_to=caminho_da_imagem, null=True, blank=True,
        validators=[validar_tamanho_da_foto],
        help_text="Opcional. Até 5 MB.",
    )
    imagem_descricao = models.CharField(
        "descrição da imagem", max_length=200, blank=True,
        help_text="O que a imagem mostra. É o texto lido por quem usa leitor de tela.",
    )
    ordem = models.PositiveIntegerField(
        "ordem", default=0, help_text="Menor número aparece primeiro no subgrupo.",
    )
    publicado = models.BooleanField(
        "publicado", default=False,
        help_text="Só seções publicadas aparecem no site.",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "seção do Saiba mais"
        verbose_name_plural = "seções do Saiba mais"
        # Os valores de `subgrupo` em ordem alfabética coincidem com a ordem
        # do menu (casa-azul, economia-solidaria, ites-ifrj). O `id` no fim
        # desempata seções com a mesma `ordem`.
        ordering = ["subgrupo", "ordem", "id"]

    def __str__(self):
        return self.titulo

    def clean(self):
        super().clean()
        if self.imagem and not self.imagem_descricao.strip():
            raise ValidationError(
                {"imagem_descricao": "Descreva a imagem para quem usa leitor de tela."}
            )
```

`__str__` vem antes do `clean()` porque o ruff do projeto aplica a regra DJ012 (ordem do guia de estilo do Django).

**Sobre o validador reaproveitado:** `validar_tamanho_da_foto` vem de `rede/models/coletivo.py` e a mensagem dele fala em "foto" ("A foto tem 6,2 MB. O limite é 5 MB."). Serve para a imagem da seção sem mudança. Se um terceiro model precisar dele, vale movê-lo para um módulo comum; com dois usos, não compensa.

**Sobre a `ordem`:** não há restrição de unicidade entre `subgrupo` e `ordem`. Com ela, reordenar duas seções no Admin exigiria um valor temporário para não colidir no meio da troca. O empate é resolvido pelo `id` no `ordering`, como na `OrdenacaoEstavel` da API.

## Migrations

### `0006_secaosaibamais` (esquema)

Gerada com `makemigrations rede`, sem edição manual.

### `0007_conteudo_inicial_saiba_mais` (dados)

Criada com `makemigrations rede --empty --name conteudo_inicial_saiba_mais` e preenchida à mão com `RunPython(criar, remover)`.

- Usa `apps.get_model("rede", "SecaoSaibaMais")`, nunca o import direto do model.
- **Ida:** `get_or_create` pelo `slug`, com os outros campos em `defaults`. Rodar de novo não duplica nada e não sobrescreve um texto que a equipe já tenha editado.
- **Volta:** apaga as seções pelos três slugs da carga. Serve para desfazer no ambiente local; em produção não há motivo para voltar.
- As três seções entram com `publicado=True`, `ordem=1` e sem imagem.

| Subgrupo | Título | Slug | Texto | Origem |
|---|---|---|---|---|
| `casa-azul` | Quem somos | `quem-somos` | `CASA.quem_somos`, copiado exatamente de `casa.ts` | Já está no ar desde 13/10 |
| `economia-solidaria` | A Rede de Economia Solidária de Niterói | `rede-de-economia-solidaria` | `CASA.sobre_a_rede`, copiado exatamente de `casa.ts` | Já está no ar desde 13/10 |
| `ites-ifrj` | A ITES | `a-ites` | Texto abaixo | **Novo, escrito pelo time** |

Texto da seção `a-ites`:

> A ITES é a Incubadora Tecnológica de Empreendimentos Solidários do IFRJ Campus Niterói. Ela apoia a criação e o fortalecimento de empreendimentos da economia solidária e desenvolve esta plataforma junto com a Casa da Economia Solidária Paul Singer, com apoio do CNPq pelo programa PIBITI.

O crédito de licença (GPLv3), o link para o GitHub e o endereço do ITES continuam fixos no frontend, como o PRD do Saiba mais já decidiu. Não entram nesta seção.

**Os textos são copiados para dentro da migration**, e não importados de algum lugar. Migration precisa continuar igual para sempre, mesmo que o `casa.ts` mude ou seja apagado.

## Requisitos de implementação

1. Model `SecaoSaibaMais` em `rede/models/secao_saiba_mais.py`, com os campos, o `clean()` e o `ordering` acima.
2. Reexportar em `rede/models/__init__.py`.
3. Migrations `0006` (esquema) e `0007` (dados), nessa ordem. Se outra branch criar uma `0006` antes deste PR entrar, renumerar e ajustar a dependência antes do merge.
4. Atualizar o PRD Técnico v4.1, Seção 4 (Modelo de dados), com um item curto sobre a seção do Saiba mais: o que é, os três subgrupos e que não guarda dado pessoal.
5. Nenhum registro no Admin, serializer ou URL neste PR. A seção só aparece para a equipe com a #62.
6. Comandos do Django sempre pelo compose (`docker compose exec backend ...`), porque o `.env` do host aponta para o Supabase de produção.

## Testes

Arquivo novo `tests/test_saiba_mais_models.py`, no estilo do `tests/test_models.py` (um teste por regra, com docstring dizendo qual).

**A carga inicial está no banco de teste**, porque a suíte roda as migrations. Os testes de ordenação filtram só as seções que eles mesmos criam; sem isso, as três seções da carga entrariam na conta.

1. Slug duplicado levanta `IntegrityError`, mesmo em subgrupos diferentes.
2. `publicado` começa `False` numa seção criada sem informar o campo.
3. A listagem padrão sai na ordem subgrupo, `ordem`, `id`: criar fora de ordem e conferir.
4. Com a mesma `ordem`, a seção criada antes vem primeiro.
5. `full_clean()` recusa subgrupo fora das três opções.
6. `clean()` recusa imagem sem descrição e aceita imagem com descrição. Usar `SimpleUploadedFile` sem salvar, para não gravar no storage.
7. `caminho_da_imagem` gera `saiba-mais/<32 hex>.<ext>`, com a extensão em minúsculas e um nome diferente a cada chamada.
8. A carga inicial existe no banco de teste (que roda as migrations): três seções publicadas, uma por subgrupo, com os slugs `quem-somos`, `rede-de-economia-solidaria` e `a-ites`.

**Verificação manual da volta da migration**, no compose: `migrate rede 0006` apaga as três seções, e `migrate rede` as cria de novo.

**CI:** o passo `makemigrations --check --dry-run` precisa continuar passando, o que confirma que as migrations estão em dia com o model.

## LGPD

- **Conteúdo institucional, sem dado pessoal.** Nenhum campo do model guarda dado de pessoa, e a ajuda dos campos diz isso.
- **Mesma regra do `casa.ts` para o texto:** só canais institucionais. Nada de celular, e-mail pessoal ou nome de alguém da equipe da Casa no texto de uma seção. Isso vai como aviso na tela do Admin (#62).
- **Imagem com pessoas:** como na foto do coletivo, a equipe só envia a imagem com autorização de uso de imagem de quem aparece nela.
- **Público por natureza:** o que for publicado vai para o site. Por isso a seção nasce despublicada.

## Critérios de aceite

Da issue #61:
- [ ] Subgrupo (Casa Azul, Economia Solidária, ITES/IFRJ), título, slug único, texto, imagem opcional (Supabase Storage), ordem e publicado
- [ ] Migration criada e paridade de migrations no CI passando
- [ ] Data migration com o conteúdo atual da página Saiba mais

Deste PRD:
- [ ] Descrição obrigatória quando houver imagem
- [ ] Imagem com nome único em `saiba-mais/` e limite de 5 MB
- [ ] Seção nova nasce despublicada; as da carga inicial, publicadas
- [ ] Data migration idempotente e com volta
- [ ] Os 8 testes da seção "Testes" passando, e a suíte inteira verde
- [ ] PRD Técnico, Seção 4, atualizado

## Fora do escopo

- **Admin das seções:** backend#62.
- **Endpoint público:** backend#63.
- **Contatos da Casa editáveis** (model `Instituicao`): não tem issue ainda. Ver "Pontos para conferir".
- **Formatação no texto** (negrito, links, listas): só se a Casa pedir, em outro card.
- **Subgrupo novo pelo Admin:** depende de rota nova no frontend, então continua sendo mudança de código.
- **Qualquer mudança no frontend.**

## O que mostrar à Casa

Quando o Admin (#62) estiver em homologação, mandar para a Casa, numa mensagem só:

1. O texto novo da seção **"A ITES"**, para ela corrigir direto no Admin se quiser.
2. Os nomes dos subgrupos como aparecem no site: **"Casa Azul", "Economia Solidária" e "ITES/IFRJ"**. A Casa prefere "Casa Azul" ou "Casa Paul Singer" no menu?
3. O convite para escrever as seções que faltam, principalmente a de **Economia Solidária**, que hoje só tem o texto sobre a Rede.

## Pontos para conferir com a equipe

- **Contatos da Casa no Admin.** O critério "conteúdo atual migrado para o banco" da #60 é atendido só para os textos. Os contatos continuam em `casa.ts`. Se a equipe quiser fechar a #60 com os contatos editáveis também, falta uma issue para o model `Instituicao` (sugestão: "[Backend] Dados da Casa editáveis no Admin · 3 pts", como no PRD do frontend).
- **Seção "A ITES" e o crédito fixo do frontend.** O crédito da licença e do GitHub continua no código do frontend. A #74 precisa decidir se ele fica na página do subgrupo ITES/IFRJ, logo abaixo das seções, ou no rodapé do Saiba mais.
