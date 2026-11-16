# PRD — Saiba mais: edição das seções no Admin (Unfold)

16/11/2026 · Jean Macedo

## Contexto e objetivo

A #61 criou o model `SecaoSaibaMais`, com as três seções iniciais já no banco, mas ninguém da equipe consegue vê-las nem editá-las: o model não está registrado no Admin. Este PRD cobre essa tela, a segunda tarefa da história #60. É a partir dela que a Casa Azul passa a corrigir os textos do Saiba mais sem depender de desenvolvedor.

**História (backend#60):** como integrante da equipe da Casa Azul, quero editar pelo Admin os textos do Saiba mais (Casa Azul, Economia Solidária e ITES/IFRJ) para manter as informações atualizadas sem depender dos desenvolvedores.

- **Issue:** [backend#62 — \[Admin\] Saiba mais: edição das seções no Unfold · 2 pts](https://github.com/Plataforma-Ecosol/ecosol-backend/issues/62) (Sprint 3, Release R3)
- **História mãe:** [backend#60](https://github.com/Plataforma-Ecosol/ecosol-backend/issues/60)
- **Depende de:** backend#61 (model), em revisão no PR #64.
- **PRDs anteriores:** "Saiba mais: modelo de seções por subgrupo" (`docs/PRD/PRD_Saiba_Mais_Secoes_por_Subgrupo_v1.md`) e "Admin com Unfold e identidade visual da Casa Azul" (`docs/PRD/PRD_Admin_Unfold_e_Identidade_Casa_Azul_v1.md`), que define o tema, o menu montado à mão e as guardas dos testes.
- **Escopo:** só o backend. `rede/admin.py`, o menu do Unfold em `config/settings.py`, testes e README. Nenhuma mudança em model, migration, serializer ou endpoint.
- **Ponto de partida:** a branch `feat/saiba-mais-modelo-secoes` (PR #64).
- **Entrega:** a branch `feat/saiba-mais-admin` e um PR com este PRD e a implementação. **Base do PR: `feat/saiba-mais-modelo-secoes` (#64)**, porque o Admin precisa do model. Quando o #64 entrar e a branch dele for apagada no merge, o GitHub troca a base para `staging` sozinho.

## Decisões de 16/11

- **Reordenar arrastando, com o recurso nativo do Unfold.** O Unfold 0.110 tem lista ordenável (`ordering_field`): a equipe arrasta as linhas e salva. É exatamente o "ordenação das seções dentro do subgrupo" da issue, sem pacote novo nem JavaScript próprio. O campo `ordem` some da lista (`hide_ordering_field`) e continua no formulário de edição.
- **Arrastar funciona com a ordem do model, que começa pelo subgrupo.** Ao soltar uma linha, o Unfold renumera a `ordem` de todas as linhas da página: 0, 1, 2… Como a lista sai ordenada por subgrupo e depois por `ordem`, a sequência dentro de cada subgrupo é preservada. Arrastar uma seção para o meio de outro subgrupo não muda o subgrupo dela: depois de salvar, ela volta para o grupo dela, na nova posição relativa. Para trocar de subgrupo, edita-se a seção.
- **Sem ordenar pelo cabeçalho das colunas (`sortable_by = ()`).** Se a equipe ordenasse a lista por título e depois arrastasse, a renumeração seguiria a ordem do título e embaralharia as seções. Sem cabeçalho clicável, a lista está sempre na ordem real do site.
- **Tudo numa página só (`list_per_page = 100`).** O Unfold renumera só as linhas visíveis. Com paginação, arrastar na página 2 daria números repetidos com a página 1. Cem seções é muito mais do que o Saiba mais vai ter.
- **`publicado` editável direto na lista**, como o `ativo` do coletivo. Publicar e despublicar é a operação mais frequente depois de editar o texto.
- **Slug preenchido a partir do título** (`prepopulated_fields`), como em Coletivo, Categoria e Evento. A ajuda do formulário avisa para não trocá-lo depois de publicado, porque o detalhe da API (#63) usa o slug.
- **Item novo no menu, num grupo próprio "Site".** O menu é montado à mão em três grupos (Cadastros, Agenda e mapa, Acesso), e um model registrado fora do menu quebra o teste `test_menu_cobre_todo_model_registrado`. O Saiba mais não é cadastro de rede nem agenda; é conteúdo do site, e o grupo novo deixa lugar para o que vier depois (o model `Instituicao` dos contatos da Casa, por exemplo).
- **Avisos no próprio formulário.** As regras que a equipe precisa lembrar na hora de escrever (texto simples, só canais institucionais, autorização de uso de imagem, descrição da imagem) ficam na `description` de cada bloco, como no bloco "Foto" do coletivo.
- **Permissões sem mudança.** No MVP há um papel só (Administrador, com acesso completo), então quem já usa o Admin passa a ver a tela nova sem configuração. O item do menu segue a regra de sempre: só aparece para quem pode ver o model.

## A tela

### Lista

| Configuração | Valor | Por quê |
|---|---|---|
| `list_display` | `titulo`, `subgrupo`, `publicado`, `atualizado_em` | O que a equipe precisa ver para achar a seção e saber se está no ar |
| `list_editable` | `publicado` | Publicar e despublicar sem abrir a seção |
| `list_filter` | `subgrupo`, `publicado` | Critério da issue |
| `search_fields` | `titulo`, `texto` | Achar a seção por uma frase do texto |
| `ordering_field` | `ordem` | Arrastar para reordenar |
| `hide_ordering_field` | `True` | O número da ordem não precisa aparecer; a posição na lista já diz tudo |
| `sortable_by` | `()` | Ver "Decisões" |
| `list_per_page` | `100` | Ver "Decisões" |

### Formulário

| Bloco | Campos | Texto de ajuda do bloco (`description`) |
|---|---|---|
| Conteúdo | `subgrupo`, `titulo`, `slug`, `texto` | "Texto simples: deixe uma linha em branco entre os parágrafos. Use só canais institucionais da Casa: nada de celular, e-mail pessoal ou nome de alguém da equipe. Evite trocar o slug de uma seção já publicada." |
| Imagem | `imagem`, `previa_da_imagem`, `imagem_descricao` | "Opcional. Só envie com autorização de uso de imagem das pessoas que aparecem nela. Na descrição, diga o que a imagem mostra: ela é lida por quem usa leitor de tela." |
| Publicação | `publicado`, `ordem` | "Seção nova começa despublicada. Marque "publicado" quando o texto estiver revisado. A ordem também pode ser ajustada arrastando as linhas na lista." |
| Registro | `criado_em`, `atualizado_em` (só leitura) | — |

`previa_da_imagem` é a mesma miniatura do `previa_da_foto` do coletivo: travessão sem imagem, `<img>` de 120 px de altura com a imagem salva.

A validação "imagem sem descrição" já vem do `clean()` do model (#61). O Admin chama `full_clean()` ao salvar, então o erro aparece no campo de descrição sem código novo.

### Código proposto

```python
@admin.register(SecaoSaibaMais)
class SecaoSaibaMaisAdmin(ModelAdmin):
    """Conteúdo da página "Saiba mais", por subgrupo.

    A equipe reordena arrastando as linhas (`ordering_field` do Unfold). O
    Unfold renumera a `ordem` das linhas visíveis, na ordem em que estão; por
    isso a lista não pode ser reordenada pelo cabeçalho (`sortable_by`) nem
    paginada (`list_per_page`), senão a renumeração embaralharia as seções.
    """

    list_display = ("titulo", "subgrupo", "publicado", "atualizado_em")
    list_editable = ("publicado",)
    list_filter = ("subgrupo", "publicado")
    search_fields = ("titulo", "texto")
    prepopulated_fields = {"slug": ("titulo",)}
    readonly_fields = ("previa_da_imagem", "criado_em", "atualizado_em")
    ordering_field = "ordem"
    hide_ordering_field = True
    sortable_by = ()
    list_per_page = 100

    fieldsets = (...)  # os quatro blocos da tabela acima

    @admin.display(description="prévia")
    def previa_da_imagem(self, obj):
        if not obj.pk or not obj.imagem:
            return "—"
        return format_html('<img src="{}" style="height: 120px;" />', obj.imagem.url)
```

### Menu

Em `UNFOLD["SIDEBAR"]["navigation"]`, um quarto grupo, depois de "Agenda e mapa" e antes de "Acesso":

```python
{
    "title": "Site",
    "items": [
        _item("Saiba mais", "info", "rede", "secaosaibamais"),
    ],
},
```

O ícone `info` é do Material Symbols, a mesma família dos outros itens.

## Requisitos de implementação

1. `SecaoSaibaMaisAdmin` em `rede/admin.py`, numa seção própria (`# --- Saiba mais ---`), depois de Pontos de interesse, herdando do `ModelAdmin` do Unfold.
2. Grupo "Site" no menu, em `config/settings.py`.
3. README, seção do Admin: o menu passa a ter quatro grupos (Cadastros, Agenda e mapa, Site, Acesso), e "O que se administra" ganha o Saiba mais.
4. Se o Unfold trouxer algum texto novo sem tradução (o arrastar, por exemplo), `tests/test_identidade_admin.py` aponta, e a tradução entra em `locale/pt_BR/LC_MESSAGES/django.po`, com o `.mo` recompilado como o README explica.
5. Comandos do Django sempre pelo compose (`docker compose exec backend ...`).

## Testes

**Já cobertos pelas guardas existentes**, desde que o fixture `registros` de `tests/test_admin.py` ganhe a chave `secaosaibamais` (pode usar a seção `quem-somos`, que a carga inicial já criou):
- a lista, o formulário de adição e o de edição abrem (200);
- a tela herda do Unfold;
- o menu cobre todo model registrado, e o item novo abre.

**Novos**, em `tests/test_admin.py`, numa seção `# --- Saiba mais (card 62) ---`:

1. O filtro por subgrupo na lista mostra só as seções daquele subgrupo.
2. Salvar a lista com a `ordem` trocada (o POST que o arrastar gera) grava a nova ordem: duas seções do mesmo subgrupo invertidas saem invertidas na consulta.
3. Desmarcar `publicado` pelo formset da lista despublica a seção, e marcar publica de novo (mesmo molde do teste do `ativo` do coletivo).
4. Salvar pelo formulário uma seção com imagem e sem descrição volta com erro no campo `imagem_descricao` e não grava nada. A imagem do teste é o `PNG_MINIMO` de `tests/helpers.py`, o mesmo dos testes da API; o storage do teste já é temporário (`tests/conftest.py`).
5. O formulário de edição mostra os avisos de LGPD e de imagem ("canais institucionais" e "autorização de uso de imagem").
6. A configuração que protege a reordenação está no lugar: `ordering_field == "ordem"`, `sortable_by == ()` e `list_per_page >= 100`. Uma mudança nisso quebraria o arrastar sem erro nenhum, então o teste explica o motivo na docstring.

## Conferência manual

No compose (`http://localhost:8001/admin/`), com o usuário local:

1. O menu mostra o grupo "Site" com "Saiba mais", e a lista abre com as três seções da carga, na ordem Casa Azul, Economia Solidária, ITES/IFRJ.
2. Criar duas seções em Casa Azul, arrastar uma para cima da outra, salvar e conferir que a ordem ficou.
3. Arrastar uma seção para o meio de outro subgrupo e salvar: ela volta ao subgrupo dela.
4. Filtrar por subgrupo e por publicado.
5. Enviar uma imagem sem descrição: o erro aparece no campo.
6. Celular: modo responsivo do navegador em 360 px. A lista e o formulário precisam ser usáveis; o arrastar no toque fica registrado como observação se não funcionar bem, já que a ordem também pode ser editada no formulário.

## LGPD

- **Nenhum dado pessoal novo.** A tela edita conteúdo institucional.
- **O aviso de "só canais institucionais" fica no formulário**, onde a equipe escreve, e não só neste PRD. É a mesma regra do `casa.ts`.
- **Autorização de uso de imagem**, como na foto do coletivo.
- **Publicar é decisão da equipe:** a seção nasce despublicada e só vai para o site quando alguém marca "publicado".

## Critérios de aceite

Da issue #62:
- [ ] Lista filtrável por subgrupo e por publicado
- [ ] Ordenação das seções dentro do subgrupo
- [ ] Visual seguindo a identidade já aplicada no Admin

Deste PRD:
- [ ] Reordenar arrastando, sem cabeçalho clicável e sem paginação
- [ ] `publicado` editável na lista
- [ ] Slug preenchido a partir do título
- [ ] Avisos de texto simples, canais institucionais e uso de imagem no formulário
- [ ] Erro claro para imagem sem descrição
- [ ] Grupo "Site" no menu
- [ ] README atualizado
- [ ] Os 6 testes novos passando, e a suíte inteira verde

## Fora do escopo

- **Endpoint público:** backend#63.
- **Contatos da Casa** (model `Instituicao`): sem issue ainda.
- **Editor de texto rico**: o texto continua simples (decisão da #61).
- **Pré-visualizar a seção como ela fica no site:** depende do frontend.
- **Histórico de versões do texto:** o Admin já registra quem mudou e quando; guardar o texto anterior seria outro card.

## Depois do merge: o que mostrar à Casa

Com esta tela em homologação, mandar para a Casa a mensagem prevista no PRD da #61: o link do Admin, o texto novo da seção "A ITES" para revisão, a pergunta sobre os nomes dos subgrupos no menu do site e o convite para escrever as seções que faltam.

## Pontos para conferir com a equipe

- **O nome do grupo no menu.** "Site" é curto e deixa espaço para o que vier; "Conteúdo do site" é mais explícito. Escolher antes do merge.
- **Arrastar no celular.** O Unfold usa o Alpine Sort, que aceita toque, mas a lista é larga. Se não funcionar bem em 360 px, a ordem continua editável no formulário.
