# Documento de Arquitetura e Requisitos (PRD Técnico)

**Plataforma de Rede da Economia Solidária de Niterói**

Centro Público de Referência em Economia Solidária (Casa Paul Singer) · ITES / IFRJ Campus Niterói

**Versão:** v4.1 (implementação em andamento — scaffold do backend, ambiente Docker de desenvolvimento local, repositório/CI/proteção da main, models e conexão ao Supabase, endpoint público de Coletivos e **área administrativa no Django Admin**)

**Tipo de aplicação:** Aplicação web (frontend com renderização no servidor) + API RESTful.

**Licença:** Código aberto (GNU GPLv3).

---

## Sumário

- [0. O que mudou nesta versão](#0-o-que-mudou-nesta-versão)
- [1. Visão geral e propósito](#1-visão-geral-e-propósito)
  - [1.1. Arquitetura desacoplada (cliente-servidor)](#11-arquitetura-desacoplada-cliente-servidor)
- [2. Stack tecnológica e responsabilidades](#2-stack-tecnológica-e-responsabilidades)
  - [2.1. Frontend público — a interface de leitura](#21-frontend-público--a-interface-de-leitura)
  - [2.2. Backend — servidor, API e back-office](#22-backend--servidor-api-e-back-office)
  - [2.3. Banco de dados e armazenamento](#23-banco-de-dados-e-armazenamento)
  - [2.4. Mapa (geolocalização)](#24-mapa-geolocalização)
  - [2.5. Empacotamento e hospedagem](#25-empacotamento-e-hospedagem)
- [3. Papéis de usuário e regras de acesso](#3-papéis-de-usuário-e-regras-de-acesso)
- [4. Modelo de dados](#4-modelo-de-dados)
  - [4.1. Coletivo — o nó da rede](#41-coletivo--o-nó-da-rede)
  - [4.2. Pessoa — quem compõe o coletivo](#42-pessoa--quem-compõe-o-coletivo)
  - [4.3. Categoria / Segmento](#43-categoria--segmento)
  - [4.4. Evento](#44-evento)
  - [4.5. Ponto de Interesse — o que aparece no mapa](#45-ponto-de-interesse--o-que-aparece-no-mapa)
  - [4.6. Usuário](#46-usuário)
  - [4.7. Relações entre entidades](#47-relações-entre-entidades)
- [5. As duas interfaces](#5-as-duas-interfaces)
  - [5.1. Interface Pública (leitura, sem login)](#51-interface-pública-leitura-sem-login)
  - [5.2. Interface Administrativa (Django Admin, com login)](#52-interface-administrativa-django-admin-com-login)
  - [5.3. Fora do escopo do MVP](#53-fora-do-escopo-do-mvp)
- [6. Proteção de dados pessoais (LGPD)](#6-proteção-de-dados-pessoais-lgpd)
  - [6.1. Princípios de exposição](#61-princípios-de-exposição)
  - [6.2. Contatos por consentimento (estratégia de omissão)](#62-contatos-por-consentimento-estratégia-de-omissão)
  - [6.3. Teste de regressão como garantia viva](#63-teste-de-regressão-como-garantia-viva)
  - [6.4. A documentar antes do uso real](#64-a-documentar-antes-do-uso-real)
- [7. Requisitos não funcionais](#7-requisitos-não-funcionais)
- [8. Decisões de arquitetura (registro e justificativa)](#8-decisões-de-arquitetura-registro-e-justificativa)
  - [8.1. Next.js na parte pública](#81-nextjs-na-parte-pública)
  - [8.2. Django-cêntrico com Supabase como Postgres + Storage](#82-django-cêntrico-com-supabase-como-postgres--storage)
  - [8.3. Autenticação por sessão do Django (substitui JWT)](#83-autenticação-por-sessão-do-django-substitui-jwt)
  - [8.4. Interface 2 pelo Django Admin no MVP](#84-interface-2-pelo-django-admin-no-mvp)
  - [8.5. Docker desde o início + deploy em serviços gerenciados](#85-docker-desde-o-início--deploy-em-serviços-gerenciados)
- [9. Contrato da API pública](#9-contrato-da-api-pública)
  - [9.1. Convenções gerais](#91-convenções-gerais)
  - [9.2. Endpoints de Coletivo](#92-endpoints-de-coletivo)
    - [Parâmetros de consulta (listagem)](#parâmetros-de-consulta-listagem)
    - [Campos da resposta (Coletivo)](#campos-da-resposta-coletivo)
    - [Erros](#erros)
- [10. Fluxo de trabalho no Git, testes e integração contínua](#10-fluxo-de-trabalho-no-git-testes-e-integração-contínua)
  - [10.1. Fluxo de branches](#101-fluxo-de-branches)
  - [10.2. Padrão de commits](#102-padrão-de-commits)
  - [10.3. Testes e integração contínua (CI)](#103-testes-e-integração-contínua-ci)
- [11. Próximos passos (feito-✅/iniciado-🟨)](#11-próximos-passos-feito-iniciado-)
- [12. Status de implementação](#12-status-de-implementação)

---

# 0. O que mudou nesta versão

Esta subversão não muda decisões nem escopo — registra o andamento da construção. Já foram entregues o scaffold do backend, o ambiente Docker de desenvolvimento local, a configuração de repositório/CI/proteção da main, os models com conexão ao Supabase, o endpoint público de Coletivos e a **área administrativa no Django Admin** (Seção 11, item 4 — concluída). O detalhamento está na seção "Status de implementação". As decisões das seções de 1 a 8 permanecem válidas e inalteradas.

- **Área administrativa entregue (novo).** A Interface 2 (Seção 5.2) saiu do papel: as seis telas do back-office — Coletivo, Pessoa, Categoria, Evento, Ponto de Interesse e Usuário — estão implementadas, em português, com os blocos de campo, as chaves de visibilidade pública e a guarda de dados sensíveis descritos em 5.2. Confirma a decisão 8.4 na prática.

- **Contrato do detalhe de Coletivo por slug (correção).** A Seção 9.2 anunciava `GET /api/coletivos/{id}/`; o que foi implementado — e que passa a valer — é `GET /api/coletivos/{slug}/`, coerente com o campo slug introduzido nesta versão e com a URL do frontend. Trocar o slug pelo Admin não quebra links já publicados: o endereço antigo responde `301` para o novo.

- **`ativo` deixa de ser parâmetro de consulta (correção).** Era listado como filtro na Seção 9.2. Aceitá-lo permitiria ao público listar exatamente os coletivos que a equipe decidiu tirar do ar, esvaziando a chave de visibilidade que o Admin opera. `ativo=True` passa a ser fixo na consulta pública.

- **Contrato da API pública definido (novo).** O endpoint de Coletivos passa a ter contrato formal — paths, parâmetros de busca e filtro, paginação e erros — documentado na Seção 9. Ele serve de modelo para os demais endpoints públicos.

- **Política de LGPD na serialização (novo).** Formaliza-se a blindagem na origem e a omissão de contatos sem consentimento, com teste automatizado de regressão. Ver Seção 6.

- **Campo slug no Coletivo (novo).** Identificador textual amigável para URLs (ex.: /coletivos/sementes-do-vale), favorecendo SEO e descoberta.

- **Campos ativo e situação, independentes (novo).** "ativo" controla a visibilidade pública; "situação" é rótulo cadastral informativo. Um não afeta o outro.

- **Bairro é público; logradouro não.** Refinamento da regra de localização: o bairro dá contexto geográfico sem revelar o endereço exato.

- **Convenções de API.** Chaves em snake_case e datas em ISO 8601 (AAAA-MM-DD) como padrão de todo o projeto.

As decisões estruturais anteriores permanecem: Coletivo como unidade central; separação Pessoa × Coletivo; Next.js com renderização no servidor na parte pública; Django-cêntrico com Supabase como Postgres + Storage; dois papéis; sem transações; Interface 2 pelo Django Admin; Docker desde o início.

# 1. Visão geral e propósito

A plataforma é uma **Tecnologia Social**: uma ferramenta de código aberto, documentada em português, reaplicável e mantida de forma autônoma pelas entidades da Economia Solidária. Não é um produto entregue pronto por especialistas externos, e sim uma construção coletiva orientada às demandas reais da rede de Niterói.

O objetivo central não é apenas cadastrar dados, e sim **fortalecer a rede**. A plataforma dá visibilidade aos coletivos e permite que produtores, consumidores e os próprios coletivos se descubram por categoria, atividade ou proximidade — favorecendo a retenção de capital na economia local. A conexão acontece por **descoberta**, não por transação: o sistema mostra quem existe e como falar com eles; a negociação acontece fora da plataforma.

## 1.1. Arquitetura desacoplada (cliente-servidor)

Frontend e backend são projetos separados que se comunicam exclusivamente por HTTP (API REST, dados em JSON). Essa escolha garante:

- **Escalabilidade:** sustenta o crescimento do número de coletivos e seus dados.

- **Trabalho em equipe:** frontend e backend evoluem em paralelo, em repositórios separados, sem conflito de código.

- **Futuro mobile:** a mesma API poderá alimentar um aplicativo de celular no futuro, sem reescrita.

- **Modelo aberto:** a separação e a licença GPLv3 tornam o sistema transparente, contínuo e reaplicável por outras redes.

# 2. Stack tecnológica e responsabilidades

A stack passou por revisão item a item à luz do modelo de dados e dos objetivos. As decisões estão consolidadas aqui e detalhadas na Seção 8.

## 2.1. Frontend público — a interface de leitura

**Tecnologias:** Next.js (React) + TypeScript + Tailwind CSS.

- **Renderização no servidor (SSR/ISR):** as páginas públicas (listagem, perfil, eventos, mapa) são renderizadas no servidor, o que as torna indexáveis por buscadores e gera prévia ao compartilhar links (ex.: WhatsApp) — atendendo diretamente à visibilidade dos coletivos.

- **Camada exclusivamente pública e de leitura:** no MVP, o Next.js consome apenas endpoints GET da API. Não hospeda a área administrativa nem faz login (ver 2.2 e decisão 8.4).

- **Responsividade (mobile first):** plenamente utilizável em smartphones básicos, dado o perfil do público.

- **TypeScript e Tailwind:** tipagem que reduz erros de contrato entre tela e dados; estilo utilitário mobile-first. Como a Interface 2 é o Django Admin, provavelmente não é preciso biblioteca de componentes de formulário no MVP.

## 2.2. Backend — servidor, API e back-office

**Tecnologias:** Python + Django + Django REST Framework (DRF).

- **Autenticação e autorização:** a escrita ocorre apenas no back-office administrativo, protegido por autenticação de sessão do Django. A API pública é somente leitura e não exige login. (JWT fica registrado como evolução futura para mobile — decisão 8.3.)

- **Serialização (DRF):** converte dados em JSON e valida entradas. Os serializadores públicos declaram campos explicitamente e nunca incluem dados de Pessoa nem contatos não autorizados (ver Seção 6).

- **Endpoints:** portas do sistema — por exemplo GET /api/coletivos/. Contrato completo na Seção 9.

- **Paginação, busca e filtros:** entrega listas em páginas (20 por vez, teto de 100) e aplica busca textual e filtros (ex.: por categoria).

- **Back-office pelo Django Admin:** no MVP, a Interface 2 é o próprio Django Admin — acelera a entrega, trata dados sensíveis atrás da autenticação do Django e oferece permissões prontas (decisão 8.4).

## 2.3. Banco de dados e armazenamento

**Tecnologias:** PostgreSQL gerenciado pelo Supabase + Storage do Supabase para imagens. Arquitetura Django-cêntrica: o Django é dono do esquema, da autenticação e das permissões; sem uso de Auth, RLS ou APIs automáticas do Supabase (decisão 8.2).

- **Integridade relacional:** regras estritas — por exemplo, uma Pessoa está sempre vinculada a um Coletivo.

- **Desempenho de busca:** consultas rápidas apoiadas por índices e por consultas otimizadas (uso de select_related/prefetch_related para evitar N+1).

## 2.4. Mapa (geolocalização)

**Tecnologias:** Leaflet + OpenStreetMap (via react-leaflet), de código aberto, custo zero e sem dependência de fornecedor — alinhado à Tecnologia Social. A geocodificação de endereços (endereço → latitude/longitude) usa o Nominatim (OpenStreetMap) no momento do cadastro. O Google Maps fica como plano B documentado, caso a qualidade dos dados de Niterói no OSM se mostre insuficiente. Apenas Pontos de Interesse são georreferenciados (ver 4.5).

## 2.5. Empacotamento e hospedagem

O sistema é empacotado em Docker desde o início (Django, Next.js e Postgres como containers, orquestrados por docker-compose), o que padroniza o ambiente da equipe e torna a reaplicabilidade real. No MVP, o deploy usa serviços gerenciados (Next.js na Vercel; Django em Render/Railway; banco no Supabase), evitando trabalho de infraestrutura. Auto-hospedagem em servidor próprio (VPS) fica viável no futuro sem retrabalho (decisão 8.5).

# 3. Papéis de usuário e regras de acesso

Dois papéis nesta fase. Não há autocadastro público: pessoas e coletivos são cadastrados exclusivamente pela equipe do Centro Público.

| **Papel** | **O que pode fazer** |
|---|---|
| Administrador (Centro Público / Casa Paul Singer) | Acesso completo ao back-office (Django Admin): cadastrar, editar e remover Pessoas, Coletivos, Categorias, Eventos e Pontos de Interesse; definir o que é público em cada coletivo; registrar situação e histórico de editais. |
| Público Geral (coletivos, consumidores, interessados) | Somente leitura da interface pública: navegar e buscar coletivos por categoria, ver o perfil público, consultar o mapa de pontos da ES e a agenda de eventos. Não faz login e não vê nenhum dado pessoal. |

O login serve essencialmente para separar quem entra no back-office. Toda rota de escrita exige autenticação de sessão do Django; a API pública expõe somente leitura (AllowAny).

# 4. Modelo de dados

O modelo nasce da normalização da planilha de cadastro atual, que misturava dados de pessoa e de coletivo em uma única linha. As entidades principais são Pessoa, Coletivo, Categoria, Evento e Ponto de Interesse.

## 4.1. Coletivo — o nó da rede

Unidade central e única entidade exibida na listagem pública. Um coletivo agrupa uma ou mais pessoas/empreendimentos.

- **Identificação pública:** nome; slug (identificador textual para URL, ex.: sementes-do-vale); descrição; bairro (público); site.

- **Contatos com visibilidade condicional:** telefone, e-mail, Instagram — cada um com uma flag "exibir publicamente?" (exibir_telefone_publicamente, etc.). Ver Seção 6.

- **Dados cadastrais (uso administrativo):** CNPJ, data de início, responsável pelo grupo, motivo de criação, renda obtida, histórico de editais (se contemplado e em que ano).

- **Endereço/logradouro completo:** uso administrativo — nunca exibido publicamente (apenas o bairro é público).

- **ativo (booleano):** controla a visibilidade na interface pública. Por padrão, a API lista apenas coletivos ativos.

- **situação (texto):** rótulo cadastral informativo (ex.: "regular", "em transição"), preenchido pelo administrador, sem trava automática. É independente de "ativo": um coletivo pode estar "em transição" e ainda assim ativo e visível.

- **Categorias:** um coletivo pode se enquadrar em várias (ver 4.3).

- **Metadados:** criado_em, atualizado_em, nome do entrevistador, observações.

**Regra de negócio (verificação humana, não do software):** na ES de Niterói, um coletivo válido tem no mínimo 3 pessoas e é interfamiliar (ao menos duas famílias distintas). A verificação é feita pela equipe do Centro Público antes do cadastro. O sistema não implementa essa validação — se o administrador cadastrou, o coletivo é considerado válido. Por isso "família" não é uma entidade do modelo.

## 4.2. Pessoa — quem compõe o coletivo

Representa cada indivíduo cadastrado. Toda pessoa pertence a um coletivo. Nenhum dado de pessoa é exibido na interface pública, em nenhuma hipótese.

- **Identificação:** nome, nome social, data de nascimento, CPF, RG, RNE/CRNM, naturalidade, estado civil.

- **Contato:** e-mail, Instagram, Facebook, site, telefone (preferência com WhatsApp).

- **Endereço:** CEP, logradouro, bairro, município, estado.

- **Escolaridade.**

- **Empreendimento individual, caso tenha:** atributo da pessoa (não é entidade de rede própria). Reflete a transição de empreendedores individuais para dentro de coletivos.

- **Bloco socioeconômico e de identidade (dados sensíveis):** cor/raça (autodeclaração), sexo, identidade de gênero, orientação sexual, pessoa com deficiência e qual, renda familiar, rede de proteção social, participação em programas sociais / transferência de renda. Ver Seção 6.

## 4.3. Categoria / Segmento

Classifica os coletivos (artesanato, alimentação, agroecologia, serviços, etc.). Relação muitos-para-muitos com Coletivo. Campos: id, nome, slug. É o principal eixo de busca e filtro público.

## 4.4. Evento

Agenda da ES divulgada na interface pública (feiras, encontros, formações). Mantido pelo administrador. Segue o mesmo padrão de endpoint público de leitura (ver anexo da Seção 9).

## 4.5. Ponto de Interesse — o que aparece no mapa

Entidade separada do Coletivo. O mapa não mostra onde os coletivos ficam; mostra locais de referência da ES. É a **única entidade autorizada a ser georreferenciada** publicamente.

- Órgãos da Economia Solidária; lojas físicas; feiras do Circuito Araribóia.

- Eventualmente, um coletivo com ponto físico próprio de comercialização.

- **Geolocalização (latitude/longitude) vive aqui** — não no Coletivo. Cadastrada pelo administrador.

## 4.6. Usuário

Modelo de usuário customizado do Django para os papéis (Administrador e Público Geral). Como não há autocadastro, na prática as contas com login são as da equipe administrativa.

## 4.7. Relações entre entidades

- Uma Pessoa pertence a um Coletivo; um Coletivo tem muitas Pessoas.

- Um Coletivo tem uma ou mais Categorias; uma Categoria classifica muitos Coletivos (M2M).

- Um Ponto de Interesse é independente do Coletivo (pode, opcionalmente, referenciá-lo no caso de venda física).

- Eventos são independentes, mantidos pelo administrador.

- **Futuro (fora do MVP):** registro de conexões/parcerias entre coletivos, como entidade própria.

# 5. As duas interfaces

A aplicação abre na interface pública. O login leva a equipe do Centro Público à área administrativa (Django Admin). A interface pública lê os dados cadastrados na administrativa.

## 5.1. Interface Pública (leitura, sem login)

- Página inicial de apresentação da rede.

- Listagem de coletivos com busca textual e filtro por categoria e bairro.

- **Perfil público do coletivo:** exibe nome, categoria, descrição, bairro, site e os contatos autorizados. Nenhum dado de pessoa; nenhum logradouro/localização exata.

- Mapa dos Pontos de Interesse (órgãos, lojas, feiras do Araribóia).

- Agenda de eventos da ES.

## 5.2. Interface Administrativa (Django Admin, com login)

Implementada (ver Seção 12). Fica em `/admin/`, inteiramente em português, e substitui o tratamento de dados atual (planilha) por um cadastro estruturado. Não há autocadastro: a conta inicial é criada por linha de comando e as demais, pela própria equipe, na tela de Usuários.

| Tela | O que se administra |
|---|---|
| **Coletivos** | Campos agrupados em blocos (identificação pública, contatos, dados cadastrais, endereço, controle, metadados); "ativo" editável direto na listagem; categorias por seletor duplo; listas somente leitura de quem compõe o coletivo e dos endereços anteriores. |
| **Pessoas** | Cerca de 25 campos em blocos, com o bloco socioeconômico recolhido e rotulado como sensível; vínculo com o coletivo por autocompletar. |
| **Categorias** | Slug preenchido a partir do nome; coluna com o número de coletivos de cada categoria. |
| **Eventos** | Galeria de imagens de divulgação em linha, com miniatura; navegação por data. |
| **Pontos de Interesse** | Latitude/longitude em graus decimais, imagem de capa e vínculo opcional com um coletivo. |
| **Usuários** | Contas da equipe, no formulário padrão do Django (senha em hash, fieldsets de permissão). |

**As chaves de visibilidade que o Admin opera.** A API pública apenas obedece ao que se define aqui:

- **ativo** decide se o coletivo existe para o público — desligar tira da listagem e faz o detalhe responder 404.

- **situação** é rótulo cadastral informativo e independente de "ativo".

- **exibir_*_publicamente** decide, contato a contato, se telefone, e-mail e instagram saem no JSON. Por isso cada contato aparece imediatamente acima da sua flag, no mesmo bloco — nunca um longe do outro.

- **Editar o slug** troca o endereço público sem quebrar links: o endereço antigo é registrado sozinho e passa a responder 301 para o novo.

**Minimização dentro do próprio back-office.** Os campos do bloco socioeconômico e de identidade de Pessoa são editáveis na ficha, mas nunca viram coluna, filtro ou campo de busca da listagem: filtrar pessoas por cor/raça, identidade de gênero ou orientação sexual transformaria o cadastro em ferramenta de segmentação por atributo protegido. Há teste automatizado bloqueando isso (ver 6.3).

## 5.3. Fora do escopo do MVP

- Qualquer transação: escambo, moeda social Araribóia, pagamentos.

- Autocadastro de pessoas ou coletivos pelo público.

- Registro formal de conexões/parcerias entre coletivos.

- Mensageria entre coletivos dentro da plataforma.

- Exibição pública de logradouro/localização exata de coletivos.

# 6. Proteção de dados pessoais (LGPD)

O cadastro reúne dados pessoais e sensíveis (cor/raça, identidade de gênero, orientação sexual, dados de saúde/deficiência, situação socioeconômica). A proteção de dados é requisito de projeto, garantido inclusive na camada de serialização da API.

## 6.1. Princípios de exposição

- **Blindagem na origem:** campos sensíveis não são sequer declarados no serializer público — mais seguro do que filtrar em tempo de execução, pois um refactor futuro não reintroduz o vazamento por acidente. Serializers usam sempre campos explícitos, nunca `fields = '__all__'`.

- **Segregação por padrão:** nenhum dado de Pessoa é exposto em rota pública; a interface pública opera apenas sobre o subconjunto público do Coletivo.

- **Bairro sim, logradouro não:** o bairro é público (contexto geográfico); o logradouro completo do coletivo é blindado, pois a sede pode ser a casa de alguém.

## 6.2. Contatos por consentimento (estratégia de omissão)

Cada contato (telefone, email, instagram) só entra na resposta se a flag de consentimento correspondente for verdadeira. Sem consentimento, **a chave é omitida** da resposta JSON — não retorna como null.

**Por que omitir a chave em vez de retornar null:** retornar null ainda comunica que "existe um dado aqui, mas foi escondido". Omitir a chave é a aplicação prática da minimização de dados: o consumidor da API não recebe sequer o indício de que há um dado. No frontend, isso se reflete em tipos TypeScript opcionais (`telefone?: string`), e não `string | null`.

## 6.3. Teste de regressão como garantia viva

Um teste automatizado verifica que (a) contatos sem consentimento são omitidos, (b) contatos com consentimento aparecem e (c) endereço e dados sensíveis nunca são serializados. Num projeto aberto, esse teste é documentação viva da promessa de privacidade: qualquer contribuição que exponha um campo sensível quebra a suíte antes de chegar à produção. O teste integra o CI (ver Seção 10).

A mesma garantia existe do lado do back-office: um teste irmão verifica que nenhum atributo do bloco socioeconômico e de identidade de Pessoa virou coluna, filtro ou campo de busca da listagem do Admin (5.2). Os dois testes cobrem as duas superfícies por onde um dado sensível poderia escapar — a resposta da API e a listagem administrativa.

## 6.4. A documentar antes do uso real

Base legal do tratamento, política de retenção e procedimento para solicitações de titulares (acesso, correção, exclusão).

# 7. Requisitos não funcionais

- **Responsividade (mobile first):** plenamente utilizável em smartphones básicos.

- **Segurança de endpoints:** nenhuma rota de escrita acessível sem sessão autenticada de administrador; a API pública é somente leitura.

- **Desempenho e escala:** listagens respondem em menos de 500 ms, apoiadas por paginação (teto de 100 itens), índices e consultas sem N+1. Adotados como boa prática para escalar com folga conforme a ES de Niterói cresça — não por já haver alto volume. Evita-se sobre-engenharia.

- **Descoberta / SEO:** páginas públicas indexáveis e com prévia de link, via renderização no servidor; URLs por slug.

- **Documentação em português e abertura (GPLv3):** sistema compreensível e reaplicável por quem herdar o projeto.

- **Independência de fornecedor:** nenhum componente essencial deve prender o projeto a um fornecedor (ver 8.2 e 8.5).

- **Reaplicabilidade via Docker:** outra rede de ES deve subir o sistema com um comando, sem instalação manual.

# 8. Decisões de arquitetura (registro e justificativa)

## 8.1. Next.js na parte pública

**Decisão:** Next.js com renderização no servidor para a parte pública; frontend único consumindo a API do Django.

**Motivo:** a descoberta é o propósito da plataforma. Uma aplicação puramente client-side não é bem indexada nem gera prévia de link, o que enfraqueceria a visibilidade. Com renderização no servidor, cada coletivo vira uma página real, indexável e compartilhável.

**Custo assumido:** um runtime a mais (Node.js sempre ativo, além de Django e Postgres), maior aprendizado e um piso de manutenção mais alto — compensados por documentação forte, em vez de migrar de SPA depois (o que exigiria reescrever boa parte do frontend).

## 8.2. Django-cêntrico com Supabase como Postgres + Storage

**Decisão:** arquitetura centrada no Django; Supabase apenas como Postgres gerenciado e armazenamento de arquivos.

**Motivo:** Supabase e Django/DRF se sobrepõem (auth, API automática, RLS). Usar ambos "cheios" criaria duas fontes de verdade e dois sistemas de permissão. Concentrar esquema, autenticação e regra no Django deixa tudo em um lugar só, ensinável, e permite aproveitar o Django Admin.

**Divisão de responsabilidades:**

- **Supabase = Postgres gerenciado + Storage.** Sem Auth, RLS, PostgREST ou Edge Functions do Supabase.

- **Esquema = migrations do Django, sempre.** Ninguém edita tabela pelo painel do Supabase; toda mudança passa por migration.

- **Conexão:** a aplicação usa o pooler; as migrations, a conexão direta. O modo de transação do pooler tem atrito conhecido com prepared statements do Django — é configuração, a confirmar na documentação vigente do Supabase.

- **Imagens:** Storage compatível com S3, integrado via django-storages, com upload passando pelo Django.

- **Isolamento de acesso:** pela camada de permissões do Django, não por RLS (que seria ignorado, pois o Django conecta com papel privilegiado). Documentar para não gerar falsa sensação de proteção.

**Benefício colateral:** o Supabase vira commodity; trocá-lo é apontar para outro Postgres, sem reescrever autenticação ou regras.

## 8.3. Autenticação por sessão do Django (substitui JWT)

**Decisão:** autenticação de sessão nativa do Django/DRF (cookie httpOnly) no lugar de JWT.

**Motivo:** a escrita é só de administrador e o público não faz login. Guardar JWT no navegador expõe o token a roubo via XSS e exige lógica de refresh — complexidade para um problema (mobile) que ainda não existe. A sessão httpOnly é mais simples e segura para web.

**Observação:** diverge do JWT citado no artigo (que descreve intenção, projeto em andamento). JWT permanece como evolução futura para mobile, adicionável sem retrabalho.

## 8.4. Interface 2 pelo Django Admin no MVP

**Decisão:** no MVP, a área administrativa é o Django Admin, não uma aplicação React customizada.

**Motivo:** Pessoa tem cerca de 25 campos (vários sensíveis) e há CRUD completo de Coletivo, Categoria, Evento e Ponto de Interesse. O Django Admin entrega isso praticamente de graça, com autenticação e permissões prontas — protegendo o prazo. Administração customizada fica para a v2.

**Consequência coerente:** com a Interface 2 no Django Admin, o Next.js fica só com a leitura pública e a autenticação vive inteira no Django (reforça 8.3).

## 8.5. Docker desde o início + deploy em serviços gerenciados

**Decisão:** empacotar em Docker desde o início e, no MVP, fazer deploy em serviços gerenciados.

**Motivo:** Docker padroniza o ambiente da equipe e torna a reaplicabilidade concreta (subir em outra cidade vira um comando). Serviços gerenciados (Vercel para o Next.js; Render/Railway para o Django; Supabase para o banco) tiram o trabalho de infraestrutura durante o MVP.

**Benefício futuro:** por já estar em Docker, migrar para VPS e auto-hospedagem é possível sem reescrever nada.

**Nota (decisão consciente):** a Vercel é serviço comercial com limites de plano — caminho de menor atrito para o MVP, mas o mesmo container do Next.js pode rodar numa VPS caso o projeto queira 100% de independência de fornecedor no futuro.

# 9. Contrato da API pública

Esta seção define o contrato do primeiro endpoint público (Coletivos), que serve de **modelo para os demais** (Eventos, Pontos de Interesse). Todo endpoint público é somente leitura (GET).

## 9.1. Convenções gerais

- Chaves em snake_case; datas em ISO 8601 (AAAA-MM-DD).

- Respostas de lista usam o envelope de paginação do DRF: count, next, previous, results.

- Paginação: page_size padrão 20, máximo 100.

- Serializers declaram campos explicitamente; contatos seguem a omissão por consentimento (Seção 6).

## 9.2. Endpoints de Coletivo

| **Método e path** | **Descrição** | **Permissão** |
|---|---|---|
| GET /api/coletivos/ | Lista paginada de coletivos ativos. | Público (AllowAny) |
| GET /api/coletivos/{slug}/ | Detalhe de um coletivo, buscado pelo slug. | Público (AllowAny) |

O detalhe é buscado pelo **slug**, e não pelo id: é ele a identidade pública do coletivo e é ele que aparece na URL do frontend. Um slug antigo (registrado automaticamente quando a equipe edita o slug no Admin) responde **301** para a URL canônica, preservando os links já publicados. A regra de visibilidade não é furada por esse caminho: slug antigo de coletivo inativo responde 404, como qualquer slug inexistente.

### Parâmetros de consulta (listagem)

| **Parâmetro** | **Tipo** | **Descrição** | **Obrig.** |
|---|---|---|---|
| q | string | Busca textual em nome e descrição (case-insensitive). | Não |
| categoria | int | Filtra pelo id de uma Categoria (M2M). | Não |
| bairro | string | Filtra por bairro (valor público, não o logradouro). | Não |
| ordering | string | nome, -nome, criado_em, -criado_em. Padrão: nome. | Não |
| page | int | Número da página (default 1). | Não |
| page_size | int | Itens por página (default 20, máx. 100). | Não |

**ativo não é parâmetro de consulta.** A listagem pública é sempre `ativo=True`, fixo. Aceitá-lo como filtro permitiria ao público pedir justamente os coletivos que a equipe do Centro Público decidiu tirar do ar, esvaziando a chave de visibilidade operada no Admin (5.2).

### Campos da resposta (Coletivo)

Institucionais: id, nome, slug, descricao, bairro, site. Relacionamento: categorias (lista, cada uma com id/nome/slug). Datas: criado_em, atualizado_em. Contatos condicionais (só com consentimento, senão a chave é omitida): telefone, email, instagram.

### Erros

| **Código** | **Quando ocorre** |
|---|---|
| 400 | Tipo inválido em parâmetro (ex.: categoria=texto onde se espera número). |
| 404 | Recurso inexistente, ou página fora da faixa (comportamento nativo do DRF). |

O padrão deste endpoint (serializer explícito, omissão de contato, otimização anti-N+1 e teste de LGPD) replica-se em GET /api/eventos/ e GET /api/pontos-de-interesse/ — sendo que Pontos de Interesse expõem, sim, latitude/longitude, por serem a única entidade georreferenciada.

# 10. Fluxo de trabalho no Git, testes e integração contínua

## 10.1. Fluxo de branches

- **Branch principal protegida:** a main não recebe push direto; só entra código via pull request revisado e aprovado.

- **Branch de homologação:** todas as alterações passam pela staging — o ambiente beta, com deploy próprio, assim como a main.

- **Branches por tarefa, com padrão de nome:** feat/, fix/, docs/, refactor/, test/. Exemplo: feat/cadastro-coletivo.

- **Pull request com revisão obrigatória:** ao menos uma revisão antes do merge; o PR descreve o que muda e por quê. Alterações visuais devem incluir evidências (screenshots).

## 10.2. Padrão de commits

- **Conventional Commits:** mensagens no formato tipo: descrição (ex.: feat: adiciona filtro por categoria). Simples, legível e permite histórico e changelog automáticos.

## 10.3. Testes e integração contínua (CI)

- **Conjunto mínimo de testes:** núcleo que cubra models, serializadores e as principais rotas — incluindo o teste de regressão de LGPD (Seção 6.3).

- **GitHub Actions:** a cada pull request, o CI roda os testes; PR com teste quebrado não pode ser mesclado em main nem staging. Assim, código quebrado — ou um vazamento de dado sensível — não entra no projeto.

# 11. Próximos passos (feito-✅/iniciado-🟨)

1. **Backend primeiro:** iniciar o Django, conectar ao Postgres do Supabase e criar os Models (Pessoa, Coletivo com slug/ativo/situação, Categoria, Evento, Ponto de Interesse). ✅

2. **Implementar o endpoint de Coletivos:** Seção 9, com o teste de regressão de LGPD. ✅

3. **Configurar os repositórios** no GitHub (organização + repositórios separados) sob GPLv3, com as regras de branch e o CI da Seção 10. ✅

4. **Área administrativa a partir do Django Admin,** substituindo a planilha por um cadastro estruturado. ✅

5. **Frontend público em Next.js:** listagem, perfil por slug, mapa (Leaflet/OSM) e eventos, com renderização no servidor.

6. **Replicar o padrão de endpoint** para Eventos e Pontos de Interesse.

7. **Meta:** Produto Mínimo Viável previsto para agosto, com frontend, API e backend integrados.

# 12. Status de implementação

Esta seção registra o que já foi construído, sem alterar as decisões e o escopo definidos nas seções anteriores. Serve como um retrato do progresso: os itens ainda não desenvolvidos permanecem como planejado.

- Repositório do backend criado e versionado, sob licença GPLv3, com README e .gitignore. (Atende parte da Seção 11, item 3.)

- Ambiente de desenvolvimento em Docker: o docker-compose (pasta infra/) sobe, com um único comando (docker compose up --build), um Postgres 16 isolado em container e o backend Django. O ambiente local não toca o Supabase — o Postgres gerenciado do Supabase segue reservado para a integração real, no próximo passo.

- O backend Django sobe na porta 8001 no ambiente local do docker-compose, com a DATABASE_URL apontando para o Postgres do próprio compose. (Detalhe operacional do ambiente da Seção 2.5.)

- Conexão real ao Postgres do Supabase e criação dos Models (Pessoa; Coletivo com slug/ativo/situação; Categoria; Evento; Ponto de Interesse). (Seção 11, item 1.)

- Integração contínua (GitHub Actions): workflow de CI com o job de testes ("test"), executado automaticamente a cada pull request. (Seção 10.3.)

- Proteção da branch main ativa no GitHub: exige pull request e a aprovação do check de CI ("test" verde) antes do merge; sem push direto. (Seção 10.1.)

- Fluxo de trabalho em uso: branches por tarefa e Conventional Commits, conforme a Seção 10.

- Endpoint de Coletivos conforme o contrato da Seção 9, com o teste de regressão de LGPD da Seção 6.3. (Seção 11, item 2.) Inclui o histórico de slug: trocar o slug de um coletivo gera o registro do endereço anterior, que passa a responder 301 para o novo.

- Área administrativa no Django Admin, em `/admin/`, com as seis telas descritas em 5.2 — Coletivo, Pessoa, Categoria, Evento, Ponto de Interesse e Usuário. (Seção 11, item 4.) O detalhamento da fatia está em `docs/PRD/PRD_Implementacao_Django_Admin_v1.md`.

- Armazenamento de imagens configurado para o Supabase Storage via django-storages (`DJANGO_USE_S3`), usado pela galeria de Evento e pela capa de Ponto de Interesse. Com a flag desligada, os uploads vão para `media/` e são servidos pelo Django enquanto `DEBUG=True`. (Seção 8.2.)

- Suíte de testes com 63 casos, verde e bloqueante no CI: regressão de LGPD do serializer (17), telas e guardas do Admin (25), models (8), histórico de slug (11) e fumaça (2). O CI roda lint (ruff), checagem de paridade entre models e migrations, e os testes, em todo pull request.

Em detalhe/próximo

- **Replicar o padrão de endpoint para Eventos e Pontos de Interesse** (Seção 11, item 6). Os dois já têm model, migration e tela de administração; falta a camada pública — serializer explícito, viewset somente leitura, filtros e o teste de exposição. É o que destrava o mapa e a agenda no frontend.

Ainda não iniciado:

- Frontend público em Next.js (Seção 11, item 5).

Pendências operacionais (não de código)

- **Reativar o projeto no Supabase.** A instância referenciada no `.env` está fora do ar — o host do projeto não resolve e tanto o Postgres (pooler e conexão direta) quanto o Storage recusam conexão. O desenvolvimento local segue normal, no Postgres em container do docker-compose; o que está parado é a validação contra o ambiente real e o upload de imagens.

- **Documentar a base legal do tratamento**, a política de retenção e o procedimento para solicitações de titulares (Seção 6.4) — obrigatório antes do primeiro cadastro com dado real de pessoa.
