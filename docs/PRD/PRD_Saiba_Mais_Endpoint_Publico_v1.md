# PRD: endpoint público das seções do Saiba mais

16/11/2026 · Jean Macedo

## Contexto e objetivo

A #61 criou o model `SecaoSaibaMais` com as três seções iniciais, e a #62 deu à equipe a tela do Admin para escrever, publicar e reordenar as seções. Falta o site ler esse conteúdo. Este PRD cobre o endpoint público somente leitura que entrega as seções publicadas. É a última tarefa de backend da história #60, e é dele que a frontend#75 depende para trocar o texto fixo da página pelo do banco.

**História (backend#60):** como integrante da equipe da Casa Azul, quero editar pelo Admin os textos do Saiba mais (Casa Azul, Economia Solidária e ITES/IFRJ), para manter as informações atualizadas sem depender dos desenvolvedores. Critério da história atendido aqui: "API pública devolve só o que está publicado".

- **Issue:** [backend#63: \[Backend\] Saiba mais: endpoint público das seções · 3 pts](https://github.com/Plataforma-Ecosol/ecosol-backend/issues/63) (Release R3)
- **História mãe:** [backend#60](https://github.com/Plataforma-Ecosol/ecosol-backend/issues/60)
- **Depende de:** backend#61 (model), em revisão no PR #64. Não depende do Admin (#62, PR #65).
- **Quem consome:** frontend#75 (páginas buscam as seções com ISR) e frontend#72 (rotas `/saiba-mais/<subgrupo>` e página índice).
- **PRDs anteriores:**
  - "Saiba mais: modelo de seções por subgrupo" (`docs/PRD/PRD_Saiba_Mais_Secoes_por_Subgrupo_v1.md`);
  - "Saiba mais: edição das seções no Admin" (`docs/PRD/PRD_Saiba_Mais_Admin_das_Secoes_v1.md`);
  - "Endpoint de Coletivos" (`docs/PRD/PRD_Implementacao_Endpoint_Coletivos_v1.md`), que define o padrão dos endpoints públicos.
- **Escopo:** só o backend: serializer, view, rota, testes, o README e uma frase no PRD técnico. Nenhuma mudança em model, migration ou Admin.
- **Ponto de partida:** a branch `feat/saiba-mais-modelo-secoes` (PR #64).
- **Entrega:** a branch `feat/saiba-mais-endpoint` e um PR com este PRD e a implementação.
  - **Base do PR: `feat/saiba-mais-modelo-secoes` (#64)**, porque o endpoint precisa do model e só dele.
  - O #65 (Admin) e este PR ficam independentes entre si. Quando o #64 entrar e a branch dele for apagada no merge, o GitHub troca a base dos dois para `staging` sozinho.

## Decisões de 16/11

- **Duas rotas:**
  - `GET /api/saiba-mais/`: a listagem, agrupada por subgrupo;
  - `GET /api/saiba-mais/{slug}/`: o detalhe de uma seção.

  O prefixo é o mesmo da rota do site (`/saiba-mais`), como `coletivos` e `eventos`.
- **A listagem vem agrupada, e não no envelope paginado.**
  - **O que a issue pede:** "Listagem agrupada por subgrupo".
  - **Como o site usa:** a página índice (frontend#72) mostra os três subgrupos, e cada página de subgrupo mostra todas as seções dele de uma vez.
  - **Por que sem paginação:** o Saiba mais tem poucas seções, e o Admin já supõe menos de 100 (`list_per_page = 100`). Paginar obrigaria o site a percorrer páginas para montar um texto que é um bloco só.
  - **Precedente:** é a mesma exceção dos endpoints de `/api/filtros/`, que também não são lista paginada.
  - **Formato:** um objeto com a chave `subgrupos`, e não uma lista solta. Assim, um campo novo no futuro não quebra o cliente.
- **Os três subgrupos vêm sempre, na ordem do menu**, mesmo sem seção publicada. Nesse caso, `secoes` vem vazio.
  - **Ordem:** a dos `choices` do model (Casa Azul, Economia Solidária, ITES/IFRJ), e não uma ordem alfabética que só coincide com ela hoje.
  - **Contrato estável:** os subgrupos são fixos no model, e o site não precisa tratar a falta de uma chave.
  - **O que fazer com o subgrupo vazio** (esconder o card, mostrar o texto fixo) é decisão do frontend (frontend#75).
  - **Nome de exibição** (`nome`): vem do backend, para o rótulo existir num lugar só.
- **Só o que está publicado, na ordem do Admin:**
  - **Filtro fixo:** `publicado=True` é filtro fixo do queryset, como o `ativo=True` das outras rotas. Não é parâmetro da URL.
  - **Ordem:** dentro de cada subgrupo, as seções vêm por `ordem` e depois por `id`. É a mesma regra do model e da lista do Admin, então o site mostra o que a equipe arrumou arrastando.
- **Sem busca, sem filtro e sem `ordering` na URL.** A view desliga os filtros globais da API (`filter_backends = []`).
  - **`?ordering=` desfaria a ordem do Admin**, e quem ordena o Saiba mais é a equipe.
  - **`?subgrupo=` ficou de fora de propósito.** Com uma URL só, o ISR do Next guarda uma entrada de cache só, e todas as páginas do Saiba mais revalidam juntas. Separar por subgrupo multiplicaria as entradas para economizar poucos kilobytes.
  - **Parâmetro desconhecido é ignorado**, como no resto da API.
- **Detalhe por slug, sem `301` de slug antigo.**
  - **Por que pelo slug:** é a identidade pública da seção, e é único no projeto (decisão da #61). A URL da API dispensa o subgrupo.
  - **Seção que não deve aparecer:** a despublicada e a inexistente respondem `404` do mesmo jeito, como o coletivo inativo.
  - **Por que sem histórico de slugs:** ele existe no Coletivo porque o perfil dele circula em cartaz e WhatsApp. A seção do Saiba mais não é página própria do site, é um bloco dentro da página do subgrupo. O Admin já avisa para não trocar o slug depois de publicado.
- **Um serializer só, para a listagem e para o detalhe.** Dentro de `secoes` cada seção repete o `subgrupo`. É redundante, mas o frontend declara um tipo só.
- **Campos da seção:**
  - **O que sai:** `id`, `slug`, `subgrupo`, `titulo`, `texto`, `imagem`, `imagem_descricao`, `atualizado_em`.
  - **`publicado` não sai:** pela regra do `ativo`, ele é a chave de visibilidade e nunca vai na resposta.
  - **`ordem` não sai:** a posição na lista já é a ordem. Expor o número convidaria o cliente a reordenar por conta própria.
  - **`criado_em` não sai:** o site não tem uso para ele.
  - **`atualizado_em` sai:** serve para o "atualizado em" e para o `dateModified` dos dados estruturados, se o frontend quiser.
- **Imagem como a foto do coletivo:**
  - sem arquivo, `imagem` vem `null`;
  - com arquivo, vem a URL absoluta (no Supabase Storage em homologação e produção);
  - `imagem_descricao` vem como texto e pode vir vazia quando não há imagem. Com imagem, o `clean()` do model garante que ela existe.
- **Uma query só na listagem.** As seções são lidas de uma vez e agrupadas em Python. Não há relacionamento para causar N+1. Um teste trava essa contagem.
- **Sem cache no backend.** Quem guarda é o ISR do frontend (frontend#75), como nas outras rotas. Despublicar uma seção no Admin some do site na próxima revalidação.

## Contrato

### `GET /api/saiba-mais/`

```json
{
  "subgrupos": [
    {
      "slug": "casa-azul",
      "nome": "Casa Azul",
      "secoes": [
        {
          "id": 1,
          "slug": "quem-somos",
          "subgrupo": "casa-azul",
          "titulo": "Quem somos",
          "texto": "A Casa Paul Singer é o Centro Público...\n\nNo espaço...",
          "imagem": null,
          "imagem_descricao": "",
          "atualizado_em": "2026-11-16T10:00:00-03:00"
        }
      ]
    },
    { "slug": "economia-solidaria", "nome": "Economia Solidária", "secoes": [ ... ] },
    { "slug": "ites-ifrj", "nome": "ITES/IFRJ", "secoes": [] }
  ]
}
```

- **Os três itens de `subgrupos` vêm sempre**, nesta ordem. O `slug` de cada um é o mesmo valor do campo `subgrupo` da seção e o mesmo da rota do site.
- **`secoes`:** só as publicadas, por `ordem` e depois por `id`. Pode vir vazio.
- **`texto`:** simples, sem HTML nem Markdown. Os parágrafos vêm separados por linha em branco (`\n\n`). O frontend mostra o texto com `whitespace-pre-line`.

### `GET /api/saiba-mais/{slug}/`

Uma seção, com as mesmas chaves de um item de `secoes`. Seção despublicada ou inexistente → `404`.

### Erros e métodos

- `POST`, `PUT`, `PATCH` e `DELETE` nas duas rotas → `405`, como em toda a API.
- Não há `400`, porque a listagem não aceita parâmetro.

### Tipo para o frontend (sugestão para a frontend#75)

```ts
type Subgrupo = "casa-azul" | "economia-solidaria" | "ites-ifrj";

type SecaoSaibaMais = {
  id: number;
  slug: string;
  subgrupo: Subgrupo;
  titulo: string;
  texto: string;
  imagem: string | null;
  imagem_descricao: string;
  atualizado_em: string;
};

type SaibaMais = {
  subgrupos: { slug: Subgrupo; nome: string; secoes: SecaoSaibaMais[] }[];
};
```

## Código proposto

### Serializer (`rede/serializers.py`)

```python
class SecaoSaibaMaisSerializer(serializers.ModelSerializer):
    """Seção do Saiba mais como ela aparece na API pública.

    Lista explícita, como todo serializer público. `publicado` não sai pela
    mesma regra do `ativo`; `ordem` não sai porque a posição na lista já é a
    ordem definida no Admin.
    """

    class Meta:
        model = SecaoSaibaMais
        fields = [
            "id",
            "slug",
            "subgrupo",
            "titulo",
            "texto",
            "imagem",
            "imagem_descricao",
            "atualizado_em",
        ]
```

### View (`rede/views.py`)

```python
class SecaoSaibaMaisViewSet(ReadOnlyModelViewSet):
    """Seções publicadas do Saiba mais: listagem agrupada e detalhe por slug.

    A listagem não usa o envelope paginado: são poucas seções, e o site precisa
    de todas de uma vez. Os três subgrupos vêm sempre, na ordem dos `choices`,
    mesmo sem seção publicada. Sem busca, filtro nem `ordering` na URL: a ordem
    é a que a equipe definiu no Admin.
    """

    permission_classes = [AllowAny]
    lookup_field = "slug"
    queryset = SecaoSaibaMais.objects.filter(publicado=True).order_by("ordem", "id")
    serializer_class = SecaoSaibaMaisSerializer
    pagination_class = None
    filter_backends = []

    def list(self, request, *args, **kwargs):
        secoes = self.get_serializer(self.get_queryset(), many=True).data
        return Response({
            "subgrupos": [
                {
                    "slug": valor,
                    "nome": rotulo,
                    "secoes": [s for s in secoes if s["subgrupo"] == valor],
                }
                for valor, rotulo in SecaoSaibaMais.Subgrupo.choices
            ],
        })
```

- **O `order_by` é explícito:** a ordem por `ordem` e `id` não depende do `Meta.ordering` do model. O agrupamento segue os `choices` e não a ordem do banco.
- **A rota (`rede/urls.py`) entra no mesmo router das outras:**

  ```python
  router.register("saiba-mais", SecaoSaibaMaisViewSet, basename="secao-saiba-mais")
  ```

## Requisitos de implementação

1. **Código e rota:** `SecaoSaibaMaisSerializer` em `rede/serializers.py`, `SecaoSaibaMaisViewSet` em `rede/views.py` e a rota em `rede/urls.py`, cada um numa seção própria (`# --- Saiba mais ---`).
2. **Docstrings dos módulos:**
   - `rede/urls.py` passa a dizer que há quatro recursos no router;
   - a docstring de `rede/serializers.py` não muda, porque a regra do `ativo` já cobre "todos os serializers públicos".
3. **README, seção "API pública":**
   - duas linhas novas na tabela de rotas;
   - uma subseção "Saiba mais" com o formato agrupado, os campos e as regras: só publicado, ordem do Admin, sem paginação nem parâmetros e `404` para seção despublicada;
   - no parágrafo inicial da seção, a ressalva de que o Saiba mais e os filtros não usam o envelope paginado.
4. **PRD técnico (`docs/PRD/PRD_Tecnico_Ecosol_Niteroi_v4.1.md`):** a Seção 4.8 ganha uma frase com as rotas e o link para este PRD.
5. **Comandos do Django:** sempre pelo compose (`docker compose exec backend ...`).

## Testes

Num arquivo novo, `tests/test_api_saiba_mais.py`, no molde de `tests/test_api_pontos.py`.

A carga inicial (migration 0007) já cria três seções publicadas, uma por subgrupo, e o pytest-django aplica as migrations. Os testes contam com elas ou as apagam no começo, e precisam dizer qual das duas coisas fazem.

1. **Envelope:** a listagem responde `200` com `subgrupos`, três itens, na ordem Casa Azul, Economia Solidária, ITES/IFRJ, cada um com `slug`, `nome` e `secoes`. Não há `count`, `next` nem `results`.
2. **Carga inicial:** `quem-somos`, `rede-de-economia-solidaria` e `a-ites` aparecem, cada uma no seu subgrupo.
3. **Despublicada:** some da listagem, e o detalhe dela responde `404`.
4. **Subgrupo sem seção publicada:** vem na lista com `secoes: []`.
5. **Ordem do Admin:**
   - dentro do subgrupo, vale `ordem` e, no empate, `id`;
   - `?ordering=-ordem` e `?q=` não mudam a resposta.
6. **Chaves do contrato:** a seção tem exatamente as chaves combinadas, e `publicado`, `ordem` e `criado_em` não aparecem nem na lista nem no detalhe.
7. **Sem paginação:** com 25 seções publicadas num subgrupo, as 25 vêm, sem paginação e ignorando `?page_size=`.
8. **Detalhe:**
   - por slug, responde `200` com as chaves do contrato;
   - um slug inexistente responde `404`.
9. **Imagem:** sem arquivo vem `null`; com arquivo vem uma URL absoluta. Usa o `PNG_MINIMO` de `tests/helpers.py`, e o storage do teste já é temporário.
10. **Somente leitura:** `POST`, `PUT`, `PATCH` e `DELETE` respondem `405`.
11. **Uma query:** a listagem faz uma query só (`django_assert_num_queries(1)`), com várias seções nos três subgrupos.

## Conferência manual

No compose, com o backend em `http://localhost:8001`:

1. **Listagem:** `http://localhost:8001/api/saiba-mais/` no navegador mostra a página do DRF com os três subgrupos e as três seções da carga.
2. **Despublicar:** desmarcar "publicado" de uma seção no Admin e recarregar. Ela some da listagem, e `/api/saiba-mais/<slug>/` responde `404`.
3. **Reordenar:** criar uma segunda seção em Casa Azul, publicá-la e arrastá-la para cima no Admin. A listagem passa a trazê-la primeiro.
4. **Imagem:** enviar uma imagem numa seção. `imagem` passa a trazer a URL, e ela abre.
5. **Escrita:** `curl -X POST http://localhost:8001/api/saiba-mais/` responde `405`.

Os passos 2 a 4 usam o Admin da #62. Sem o PR #65 na mesma base, dá para fazer as mesmas mudanças pelo `shell` do Django no container.

## LGPD

- **Nenhum dado pessoal sai daqui:**
  - a seção é conteúdo institucional;
  - o serializer tem lista explícita de campos;
  - um teste trava as chaves.
- **A equipe decide o que vai ao ar:** só a seção marcada como "publicado" vai para a API. A flag não aparece na resposta, e a seção despublicada responde como inexistente.
- **Uso de imagem:** a imagem pública segue a regra de autorização de uso de imagem, avisada no formulário do Admin (#62).

## Critérios de aceite

Da issue #63:
- [ ] Listagem agrupada por subgrupo e detalhe por slug
- [ ] Só seções publicadas, na ordem definida no Admin
- [ ] Documentado no README (seção "API pública")
- [ ] Testes de listagem, detalhe e seção despublicada

Deste PRD:
- [ ] Três subgrupos sempre presentes, na ordem do menu
- [ ] Sem paginação, busca, filtro nem `ordering` na URL
- [ ] `publicado`, `ordem` e `criado_em` fora da resposta
- [ ] `imagem` com URL absoluta ou `null`
- [ ] Listagem em uma query
- [ ] PRD técnico atualizado
- [ ] Os 13 testes novos passando, e a suíte inteira verde

## Fora do escopo

- **Consumir a API no site:** frontend#75 (ISR e fallback para o texto fixo).
- **Rotas dos subgrupos e página índice:** frontend#72.
- **Filtro `?subgrupo=`:** ver "Decisões". Se um dia fizer falta, é aditivo e não quebra o contrato.
- **Histórico de slugs e `301`:** ver "Decisões".
- **Contatos da Casa** (model `Instituicao`): ainda sem issue. Continuam no `casa.ts`.
- **Texto rico** (HTML ou Markdown): o texto continua simples, por decisão da #61.

## Pontos para conferir com a equipe

- **Subgrupo vazio no site.** O backend sempre manda os três. Falta decidir na frontend#75 se um subgrupo sem seção publicada esconde o card do índice ou mostra o texto fixo.
- **Ordem dos merges.** O #65 e este PR saem os dois da branch do #64 e não mexem nos mesmos arquivos de código.
  - **Arquivos de código:** o #65 mexe em `admin.py` e `settings.py`; este PR, em `serializers.py`, `views.py` e `urls.py`.
  - **Arquivos em comum:** só o `README.md`, em seções diferentes (Admin e API pública), e o fixture `registros` não muda aqui.
  - **Resultado:** a ordem entre os dois não importa, desde que o #64 entre primeiro.
