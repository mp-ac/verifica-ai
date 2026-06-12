# DenuncIAI

Protótipo em Python para triagem e apuração assistida de possíveis fake news. O projeto nasceu para apoiar o combate à desinformação no período eleitoral e deve evoluir depois para cenários mais amplos de verificação de fatos.

O repositório está em nome do `Ministério Público do Estado do Acre` e segue uma proposta de inovação aberta: desenvolvimento institucional com colaboração da comunidade.

![Workflow atual](workflow.png)

## Estado atual

O que existe hoje:

- execução local via terminal;
- workflow em `LangGraph`;
- roteamento entre agentes por tipo de entrada;
- agente de busca com ferramentas de data atual, descoberta de links e leitura de páginas;
- síntese final estruturada da resposta;
- prompts separados em arquivos `.md`.

O que ainda não existe ou está incompleto:

- interface web;
- API `FastAPI`;
- persistência de casos, protocolos e revisão humana;
- processamento real de imagem;
- transcrição real de áudio.

Importante: a tool de transcrição em [src/tools/audio_transcription.py](/Users/carneiro/Projetos/mpac/denunciai.mpac.mp.br/src/tools/audio_transcription.py:1) ainda é um stub e retorna um exemplo fixo.

## Como o protótipo funciona

O fluxo atual é:

1. o usuário digita uma consulta no terminal;
2. o router classifica a entrada;
3. o workflow decide quais agentes executar;
4. o agente de busca usa ferramentas externas para apuração;
5. o router sintetiza a resposta final.

Hoje os agentes disponíveis são:

- `search_agent`: faz busca e leitura de fontes;
- `transcription_agent`: recebe referência de áudio, mas ainda usa transcrição mockada.

## Requisitos

- Python `3.13`
- `uv` para instalar dependências e executar o projeto
- acesso a endpoints compatíveis com OpenAI para o router e para o agente de busca
- chave da SerpAPI
- serviço HTTP para converter URL em markdown, configurado nas variáveis `FETCH_SITE_*`

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

- `ROUTER_*`: modelo e endpoint usados pelo router.
- `SEARCH_*`: modelo e endpoint usados pelo agente de busca.
- `SERPAPI_API_KEY`: busca de links.
- `FETCH_SITE_*`: leitura e conversão de páginas web.
- `*_PROMPT`: caminhos dos prompts usados pelo workflow.

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

## Limitações atuais

- o projeto ainda depende de serviços externos para LLM e leitura de páginas;
- a transcrição de áudio ainda não é real;
- a execução atual é voltada a teste manual, não a produção;
- os imports e o ponto de entrada ainda estão em transição para uma estrutura mais preparada para múltiplas interfaces;
- o README descreve o estado atual do protótipo, não a visão completa já pretendida para a plataforma final.

## Roadmap curto

- transformar a transcrição em integração real;
- reduzir acoplamento da interface CLI;
- evoluir o núcleo atual para suportar também uma camada `FastAPI`;
- adicionar testes automatizados;
- documentar melhor fluxo de contribuição.

## Licença

Este projeto está licenciado sob a `GNU Affero General Public License v3.0` (`AGPL-3.0`). Veja o arquivo [LICENSE](/Users/carneiro/Projetos/mpac/denunciai.mpac.mp.br/LICENSE) para mais detalhes.

Titular institucional do projeto: `Ministério Público do Estado do Acre`.
