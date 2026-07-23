# VerificaAI

Protótipo em Python para triagem e apuração assistida de possíveis fake news. O projeto nasceu para apoiar o combate à desinformação no período eleitoral e deve evoluir depois para cenários mais amplos de verificação de fatos.

O repositório está em nome do `Ministério Público do Estado do Acre` e segue uma proposta de inovação aberta: desenvolvimento institucional com colaboração da comunidade.

![Workflow atual](workflow.png)

## Estado atual

O que existe hoje:

- execução local via terminal;
- workflow em `LangGraph`;
- roteamento entre agentes por tipo de entrada;
- agente de busca com ferramentas de data atual, descoberta de links e leitura de páginas;
- transcrição de áudio por API externa;
- síntese final estruturada da resposta;
- persistência opcional das respostas finais no Qdrant;
- geração de embeddings dense, sparse e ColBERT para busca híbrida;
- prompts separados em arquivos `.md`.

O que ainda não existe ou está incompleto:

- interface web;
- API `FastAPI`;
- persistência de casos, protocolos e revisão humana;
- processamento real de imagem;

## Como o protótipo funciona

O fluxo atual é:

1. o usuário digita uma consulta no terminal;
2. o router classifica a entrada;
3. o workflow decide quais agentes executar;
4. o agente de busca usa ferramentas externas para apuração;
5. o router sintetiza a resposta final;
6. se o Qdrant estiver configurado e disponível, a pergunta e a resposta final
   são armazenadas como um único point na collection.

O point salvo no Qdrant usa o ID do job RQ como identificador e contém:

- os vetores nomeados `dense`, `sparse` e `colbert`;
- o payload `text`, `meta`, `query`, `answer` e `sources`.

O uso do ID do job evita a criação de pontos duplicados caso uma mesma execução
seja repetida.

Hoje os agentes disponíveis são:

- `search_agent`: faz busca e leitura de fontes;
- `transcription_agent`: envia uma URL pública de áudio para transcrição e encaminha o texto ao agente de busca.

## Requisitos

- Python `3.13`
- `uv` para instalar dependências e executar o projeto
- acesso a endpoints compatíveis com OpenAI para o router e para o agente de busca
- chave da SerpAPI
- serviço HTTP para converter URL em markdown, configurado nas variáveis `FETCH_SITE_*`
- acesso à API de transcrição, configurado nas variáveis `TRANSCRIPTION_*`
- acesso a uma instância Qdrant, opcional, para persistência vetorial das respostas finais

## Configuração

1. Instale as dependências:

```bash
uv sync
```

2. Crie o arquivo `.env` a partir do `.env.example`:

```bash
cp .env.example .env
```

3. Preencha as variáveis necessárias.

Principais grupos de configuração:

- `ROUTER_*`: configuração da LLM do router.
- `SEARCH_*`: configuração da LLM do agente de busca.
- `SERPAPI_API_KEY`: busca de links.
- `FETCH_SITE_*`: leitura e conversão de páginas web.
- `TRANSCRIPTION_*`: envio do áudio, consulta de status, polling e timeout.
- `FINAL_RESULTS_*`: fila e API de destino das respostas finais.
- `QDRANT_*`: conexão, collection e modelos usados na persistência vetorial opcional.
- `*_PROMPT`: caminhos dos prompts usados pelo workflow.

Para `ROUTER_*` e `SEARCH_*`, o contrato é sempre o mesmo:

- `*_PROVIDER`: `google`, `openai` ou `vllm`
- `*_MODEL`: nome do modelo
- `*_API_KEY`: credencial do provider
- `*_BASE_URL`: endpoint do provider quando ele for OpenAI-compatible

`router` e `search` podem usar providers diferentes. Exemplo: `ROUTER_PROVIDER`
pode ser `google` enquanto `SEARCH_PROVIDER` continua como `vllm`.

Regra prática:

- `google`: use `*_PROVIDER`, `*_MODEL` e `*_API_KEY`; deixe `*_BASE_URL`
  vazio
- `openai` e `vllm`: use os quatro campos

Exemplos:

```env
ROUTER_PROVIDER=google
ROUTER_MODEL=gemini-2.5-flash
ROUTER_API_KEY=sua_chave_google
ROUTER_BASE_URL=
```

```env
SEARCH_PROVIDER=vllm
SEARCH_MODEL=Qwen/Qwen3-14B-FP8
SEARCH_API_KEY=sua_chave_vllm
SEARCH_BASE_URL=https://seu-endpoint/v1
```

### Qdrant

A integração com o Qdrant é opcional. Quando configurada, a aplicação verifica
se a collection existe durante a inicialização e a cria quando necessário. Se a
conexão ou a gravação falhar, o erro é registrado nos logs e o fluxo principal
continua normalmente.

Exemplo de configuração:

```env
QDRANT_DENSE_MODEL="intfloat/multilingual-e5-large"
QDRANT_SPARSE_MODEL="Qdrant/bm25"
QDRANT_COLBERT_MODEL="colbert-ir/colbertv2.0"
QDRANT_MAX_TOKENS=1024
QDRANT_COLLECTION_NAME="verifica-ai"
QDRANT_API_URL="https://seu-qdrant"
QDRANT_API_KEY="sua-chave"
QDRANT_API_PORT=443
```

Cada resposta final é persistida como um único point. A pergunta e a resposta
são usadas para gerar os embeddings dense, sparse e ColBERT, enquanto as fontes
e os demais dados permanecem disponíveis no payload.

### Entrega dos resultados finais

Ao concluir uma análise, o worker principal enfileira a entrega da resposta para
a API configurada em `FINAL_RESULTS_API_URL`. A fila `final-results` é consumida
por um worker dedicado e repete requisições que falharem conforme os intervalos
definidos em `FINAL_RESULTS_RETRY_INTERVALS_SECONDS`.

```env
FINAL_RESULTS_QUEUE_NAME="final-results"
FINAL_RESULTS_JOB_TIMEOUT_SECONDS=60
FINAL_RESULTS_RESULT_TTL_SECONDS=86400
FINAL_RESULTS_FAILURE_TTL_SECONDS=604800
FINAL_RESULTS_RETRY_INTERVALS_SECONDS="10,30,60,300,900"
FINAL_RESULTS_API_URL="http://laravel:8002/api/v1/final-results"
FINAL_RESULTS_API_TOKEN="seu-token"
FINAL_RESULTS_API_TIMEOUT_SECONDS=15
```

O `endpoint` deve aceitar autenticação Bearer e tratar `task_id` de forma
idempotente para que novas tentativas não criem resultados duplicados.

## Execução local

Com o ambiente configurado:

```bash
uv run python src/main.py
```

O programa abrirá um prompt no terminal:

```text
O que você quer procurar?
```

Depois disso, o workflow imprime as fases do processamento e a resposta final estruturada.

## Dependências

Para permitir que o agente acesse URLs encontradas, você pode usar este projeto: [https://github.com/mp-ac/link_para_markdown](https://github.com/mp-ac/link_para_markdown)

## Limitações atuais

- o projeto ainda depende de serviços externos para LLM e leitura de páginas;
- a transcrição depende de uma API externa e de uma URL de áudio acessível por ela;
- a execução atual é voltada a teste manual, não a produção;
- os imports e o ponto de entrada ainda estão em transição para uma estrutura mais preparada para múltiplas interfaces;
- a persistência no Qdrant é complementar e não substitui um banco transacional;
- os modelos de embedding podem ser baixados e carregados no primeiro uso, exigindo espaço em disco e memória;
- o README descreve o estado atual do protótipo, não a visão completa já pretendida para a plataforma final.

## Roadmap curto

- reduzir acoplamento da interface CLI;
- evoluir o núcleo atual para suportar também uma camada `FastAPI`;
- adicionar testes automatizados;
- documentar melhor fluxo de contribuição.

## Licença

Este projeto está licenciado sob a `GNU Affero General Public License v3.0` (`AGPL-3.0`). Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

Titular institucional do projeto: `Ministério Público do Estado do Acre`.
