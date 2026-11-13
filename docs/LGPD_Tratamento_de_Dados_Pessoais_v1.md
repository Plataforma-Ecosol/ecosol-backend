# LGPD — Tratamento de dados pessoais

**Projeto:** Plataforma de Rede da Economia Solidária de Niterói
**Centro Público de Referência em Economia Solidária (Casa Paul Singer) · ITES / IFRJ Campus Niterói**

| | |
|---|---|
| **Documento** | Base legal do tratamento, política de retenção e procedimento para pedidos de titulares |
| **Versão** | 1.0 — **rascunho, a validar com a Casa Paul Singer** |
| **Data** | 29/10/2026 |
| **Deriva de** | PRD Técnico v4.1 (Seções 4.1, 4.2, 6 e 11.1) · Cartão do Trello "[LGPD] Documentar base legal, retenção e direitos dos titulares" (Sprint 1) |
| **Escopo** | O que a plataforma guarda sobre pessoas, com que fundamento, por quanto tempo e como atender quem pede acesso, correção ou exclusão |

> **Como ler este documento.** Os itens marcados como **fato** descrevem o sistema como ele está no código. Os marcados como **proposta** são sugestões da equipe técnica e só valem depois de aprovados pela Casa Paul Singer. Este texto não substitui orientação jurídica: a base legal, em especial, deve passar pelo encarregado de dados da Casa e por quem responda juridicamente por ela.

**Condição de uso (PRD 6.4):** nenhum dado real de pessoa entra no sistema antes de as Seções 3, 4 e 5 serem aprovadas e as pendências da Seção 7 marcadas como "antes do primeiro cadastro" estarem resolvidas.

---

## Sumário

- [1. Papéis](#1-papéis)
- [2. Inventário de dados pessoais](#2-inventário-de-dados-pessoais)
- [3. Base legal do tratamento](#3-base-legal-do-tratamento)
- [4. Política de retenção](#4-política-de-retenção)
- [5. Pedidos de titulares](#5-pedidos-de-titulares)
- [6. Garantias técnicas já implementadas](#6-garantias-técnicas-já-implementadas)
- [7. Pendências](#7-pendências)
- [8. Perguntas para a Casa Paul Singer](#8-perguntas-para-a-casa-paul-singer)

---

# 1. Papéis

| **Papel na LGPD** | **Quem** | **Situação** |
|---|---|---|
| Controlador (art. 5º, VI) | Casa Paul Singer — quem decide o que se coleta e para quê | **Fato.** |
| Encarregado / DPO (art. 41) | Casa Paul Singer | **Fato.** Falta nomear a pessoa e o contato que a Casa vai divulgar (Seção 8). |
| Equipe de desenvolvimento | ITES / IFRJ — constrói e mantém a plataforma | **Fato.** Não decide sobre os dados. Como a equipe tem acesso técnico ao banco de produção, atua como operadora: só mexe nos dados reais quando a Casa pede ou para manutenção, e o acesso fica restrito a quem precisa. |
| Operadores (art. 5º, VII) | Supabase (banco e Storage), Render (backend), Vercel (frontend) | **Fato** quanto aos serviços usados. Os três processam dados por conta do controlador. |
| Titulares | Pessoas cadastradas; responsáveis e contatos de coletivos; usuários do Admin | **Fato.** O público do site não faz login e não tem cadastro. |

---

# 2. Inventário de dados pessoais

**Fato.** Levantado dos models em `rede/models/`. Só a equipe do Centro Público cadastra; não há autocadastro (PRD 3).

## 2.1. Pessoa (`rede/models/pessoa.py`) — nunca exibida publicamente

| **Bloco** | **Campos** | **Natureza** |
|---|---|---|
| Identificação | nome, nome social, data de nascimento, CPF, RG, RNE/CRNM, naturalidade, estado civil | Pessoal |
| Contato | e-mail, Instagram, Facebook, site, telefone | Pessoal |
| Endereço | CEP, logradouro, bairro, município, estado | Pessoal |
| Formação e trabalho | escolaridade, empreendimento individual | Pessoal |
| Socioeconômico e identidade | cor/raça, sexo, identidade de gênero, orientação sexual, pessoa com deficiência e qual, renda familiar, rede de proteção social, participação em programas sociais | **Sensível** (art. 5º, II): origem racial, vida sexual, saúde. Renda e programas sociais não são sensíveis pela lei, mas recebem o mesmo cuidado. |
| Metadados | criado em, atualizado em | Técnico |

## 2.2. Coletivo (`rede/models/coletivo.py`) — parte pública, parte administrativa

| **Campo** | **Por que é dado pessoal** | **Exibição** |
|---|---|---|
| telefone, e-mail, Instagram | Em coletivo pequeno, costumam ser o contato pessoal de alguém | Pública **só** com a flag `exibir_*_publicamente` marcada |
| responsável pelo grupo | Nome de pessoa | Administrativa |
| logradouro, número, complemento, CEP | A sede pode ser a casa de alguém | Administrativa (só o bairro é público) |
| nome do entrevistador | Nome de pessoa da equipe | Administrativa |
| foto | Pode mostrar pessoas | Pública |
| observações, motivo de criação | Texto livre: pode conter qualquer coisa | Administrativa |

## 2.3. Outros lugares onde há dado pessoal

| **Onde** | **O que fica** |
|---|---|
| Usuário do Admin (`rede/models/usuario.py`) | Nome, e-mail e senha (com hash) da equipe |
| Histórico do Admin (`django_admin_log`) | Para cada criação, edição ou exclusão: quem fez, quando, e o **nome** do registro (o `__str__` da Pessoa é o nome social ou o nome). O nome **continua lá depois que a pessoa é excluída**. |
| Sessões (`django_session`) | Sessão de login da equipe |
| Logs do Render e da Vercel | Requisições e erros; podem trazer IP de quem visita o site |
| Backups do Supabase | Cópia do banco, conforme o plano contratado |

---

# 3. Base legal do tratamento

**Proposta.** Cada finalidade precisa de uma base legal. Para dado comum, as bases estão no art. 7º; para dado sensível, só valem as do art. 11, que são mais restritas.

| **Finalidade** | **Dados** | **Base legal proposta** | **Observação** |
|---|---|---|---|
| Cadastrar a pessoa como integrante de um coletivo e acompanhar a rede | Identificação, contato, endereço, escolaridade, empreendimento | Execução de políticas públicas (art. 7º, III), **se** o Centro Público for reconhecido como executor de política pública de economia solidária; senão, consentimento (art. 7º, I) | Depende da natureza jurídica da Casa (Seção 8, pergunta 1) |
| Diagnóstico socioeconômico e de identidade da rede, incluindo os gráficos pedidos (PRD 11.1) | Bloco socioeconômico e de identidade | **Consentimento específico e destacado** (art. 11, I), separado do restante do cadastro, com opção "prefiro não informar" em cada campo | É a base mais segura para dado sensível autodeclarado. Os gráficos usam só números agregados e anonimizados |
| Mostrar contatos do coletivo no site | Telefone, e-mail e Instagram do coletivo | Consentimento (art. 7º, I), registrado pelas flags `exibir_*_publicamente` | Já implementado (Seção 6) |
| Divulgar o coletivo no site | Nome, descrição, bairro, foto | Execução de política pública ou consentimento, como na primeira linha | Fotos com pessoas pedem autorização de uso de imagem |
| Dar acesso ao Admin à equipe | Dados da conta | Legítimo interesse do controlador (art. 7º, IX) — segurança e controle de acesso | |

**Consequências para o atendimento, já valendo como proposta:**
- Os campos sensíveis são opcionais. Recusar não impede o cadastro da pessoa nem do coletivo.
- O consentimento precisa ficar registrado (quem, quando, para o quê, qual versão do termo). Hoje o sistema não registra isso (Seção 7).
- A pessoa pode revogar o consentimento a qualquer momento (art. 8º, §5º). A revogação apaga os dados que dependiam dele (Seção 5).

---

# 4. Política de retenção

**Proposta.** Os prazos abaixo são o ponto de partida para a conversa com a Casa. Quando o prazo vence, o dado é **excluído** ou **anonimizado** (o registro fica, sem nada que identifique a pessoa).

| **Dado** | **Fica guardado enquanto** | **Depois disso** |
|---|---|---|
| Pessoa: identificação, contato, endereço | A pessoa integrar um coletivo ativo na rede | Excluído **2 anos** depois de a pessoa sair do coletivo ou de o coletivo ficar inativo, salvo obrigação de guarda (prestação de contas de edital, por exemplo) |
| Pessoa: bloco socioeconômico e de identidade | Valer o consentimento | Excluído na revogação ou junto com o cadastro. Para estatística histórica, só números agregados e anonimizados |
| CPF, RG, RNE/CRNM | Houver uso concreto (edital, convênio, prestação de contas) | Excluído quando o uso acabar. Se não houver uso concreto, **não coletar** (Seção 8, pergunta 3) |
| Contatos e endereço do coletivo, responsável pelo grupo | O coletivo estiver ativo | Excluídos **2 anos** depois de o coletivo ficar inativo. Nome, categorias e bairro podem ficar como histórico da rede |
| Histórico do Admin (`django_admin_log`) | **1 ano** | Excluído. Quando uma pessoa é excluída a pedido, as linhas com o nome dela saem junto |
| Conta de usuário do Admin | A pessoa fizer parte da equipe | Desativada no desligamento e excluída **6 meses** depois |
| Sessões | Expiração da sessão | Limpeza periódica (`clearsessions`) |
| Logs do Render e da Vercel | O que o plano de cada serviço guarda | Sem ação; conferir o prazo de cada um (Seção 7) |
| Backups do Supabase | O ciclo de backup do plano | Dado excluído no banco some dos backups quando o ciclo vira; o titular é avisado desse prazo |

---

# 5. Pedidos de titulares

**Proposta.** Como atender os direitos do art. 18 com o sistema como ele está.

## 5.1. Canal e identificação

1. **Canal único:** um e-mail da Casa (a definir) e atendimento presencial. O canal aparece na página pública de privacidade.
2. **Confirmar que quem pede é o titular** antes de mostrar ou mudar qualquer dado: conferir pessoalmente ou pedir um dado que só ele saiba, sem pedir documento novo além do necessário.
3. **Registrar o pedido:** data, tipo, quem atendeu e data da resposta. Uma planilha da Casa basta no começo. O registro não guarda os dados pessoais pedidos, só o fato do pedido.

## 5.2. Prazos

- **Confirmação de que há dados e acesso simplificado:** na hora, se for presencial (art. 19, I).
- **Declaração completa:** até **15 dias** (art. 19, II).
- **Correção, exclusão e revogação:** proposta de até **15 dias**, alinhado ao prazo acima.

## 5.3. Como executar cada pedido

| **Pedido** | **Como fazer hoje** |
|---|---|
| Acesso | Abrir a ficha da Pessoa no Admin e entregar o conteúdo ao titular. Não há exportação automática (Seção 7) |
| Correção | Editar a ficha no Admin |
| Exclusão | Excluir a Pessoa no Admin e apagar do `django_admin_log` as linhas com o nome dela. Avisar o titular de que a cópia nos backups some no fim do ciclo (Seção 4) |
| Revogação do consentimento do bloco sensível | Apagar os campos do bloco socioeconômico e de identidade na ficha. O resto do cadastro continua, se tiver outra base legal |
| Contatos públicos de coletivo | Desmarcar a flag `exibir_*_publicamente`; o contato some da API na hora |
| Informação sobre compartilhamento | Responder que os dados ficam com os operadores da Seção 1 e não são compartilhados com terceiros |

> **Cuidado ao excluir:** `Pessoa.coletivo` usa `on_delete=PROTECT`. Um coletivo com pessoas não pode ser excluído; as pessoas saem primeiro. Isso é proposital (evita apagar gente por acidente) e não atrapalha a exclusão de uma pessoa sozinha.

---

# 6. Garantias técnicas já implementadas

**Fato.** Descritas no PRD Técnico v4.1, Seção 6.

- **Blindagem na origem:** nenhum serializer público declara campo de Pessoa nem endereço de Coletivo; serializers nunca usam `fields = '__all__'`.
- **Contatos por consentimento:** sem a flag marcada, a chave é omitida do JSON.
- **Minimização no Admin:** campos do bloco sensível nunca viram coluna, filtro ou busca da listagem de Pessoas.
- **Testes de regressão no CI:** um teste quebra a suíte se a API expuser dado sensível ou contato sem consentimento; outro, se a listagem do Admin expuser o bloco sensível.
- **Sem cadastro público:** quem visita o site não faz login e não fornece dado nenhum.

---

# 7. Pendências

| **Pendência** | **Quando** |
|---|---|
| Aprovar as Seções 3, 4 e 5 com a Casa Paul Singer e nomear a pessoa encarregada | **Antes do primeiro cadastro** |
| Registrar o consentimento da Pessoa (data, versão do termo, finalidades aceitas). Hoje não há campo para isso | **Antes do primeiro cadastro** |
| Termo de consentimento em papel ou formulário, com o bloco sensível em destaque e separado | **Antes do primeiro cadastro** |
| Conferir se os servidores do Supabase, Render e Vercel ficam fora do Brasil e registrar a transferência internacional (art. 33) | **Antes do primeiro cadastro** |
| Página pública de privacidade, a partir deste documento | Cartão já no backlog |
| Campo de saída da pessoa ou de inativação do coletivo com data, para os prazos da Seção 4 poderem ser cumpridos | Antes do primeiro prazo vencer |
| Comando de manutenção que aplica a retenção: anonimiza e exclui o que venceu, limpa `django_admin_log` e sessões | Antes do primeiro prazo vencer |
| Exportação dos dados de uma Pessoa (ação no Admin) para responder pedidos de acesso | Quando o volume de pedidos justificar |
| Conferir o prazo de logs do Render e da Vercel e o ciclo de backup do Supabase no plano usado | Antes do primeiro cadastro |
| Desenho de privacidade dos gráficos socioeconômicos (PRD 11.1): só números agregados, com mínimo de pessoas por grupo para ninguém ser identificado | Antes de começar os gráficos |

---

# 8. Perguntas para a Casa Paul Singer

1. **O Centro Público executa uma política pública formal** (convênio, programa municipal ou federal)? A resposta define se a base do cadastro é política pública ou consentimento.
2. **Quem, na Casa, é a pessoa encarregada** dos dados, e qual contato dela vai ser divulgado?
3. **Para que servem CPF, RG e RNE/CRNM?** Se nenhum edital ou prestação de contas exige, a proposta é parar de coletar.
4. **Há obrigação de guardar o cadastro** por algum prazo, por edital, convênio ou prestação de contas?
5. **Os gráficos socioeconômicos** são para gestão interna da Casa ou para divulgação? Cada uso pede uma base legal e um cuidado diferente.
6. **Os prazos da Seção 4** (2 anos depois da saída, 1 ano de histórico do Admin) fazem sentido para o trabalho da Casa?
7. **Qual e-mail** vai receber os pedidos de titulares?
