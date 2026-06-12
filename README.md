# Plataforma de Denúncia e Verificação de Possíveis Notícias Falsas

## Visão geral

Este projeto propõe a criação de uma plataforma digital para receber, organizar, analisar e responder denúncias ou solicitações de verificação relacionadas a possíveis notícias falsas.

A ideia central é oferecer ao cidadão um canal simples para encaminhar conteúdos suspeitos e, ao mesmo tempo, entregar aos analistas uma estrutura organizada para examinar esses casos com apoio de tecnologia, inteligência artificial e revisão humana.

O sistema não substitui a decisão humana. Ele atua como uma etapa de apoio, capaz de acelerar a triagem inicial, reunir informações relevantes, consultar fontes públicas e apresentar uma análise preliminar. A conclusão final sobre cada caso permanece sob responsabilidade de um analista.

![workflow.png](/workflow.png)

## O que a plataforma fará

- Receber denúncias e pedidos de verificação enviados por cidadãos.
- Registrar cada solicitação com um número de protocolo.
- Identificar automaticamente o tipo de conteúdo enviado.
- Apoiar a análise com agentes especializados de inteligência artificial.
- Reunir fontes, referências e informações complementares.
- Encaminhar o caso para revisão humana.
- Registrar a conclusão final da análise.
- Retornar uma resposta ao cidadão.
- Criar uma base de conhecimento com os casos já analisados.

## Como o cidadão utiliza a plataforma

O cidadão acessa a plataforma e envia o conteúdo que deseja denunciar ou verificar. Esse conteúdo pode estar em diferentes formatos, como:

- Texto digitado ou copiado de uma mensagem.
- Imagem, como prints de conversas, cards, montagens ou publicações.
- Áudio recebido por aplicativo de mensagem.
- Link de notícia, postagem, vídeo ou página na internet.
- Combinação de mais de um desses elementos.

Após o envio, o sistema gera automaticamente um protocolo. Esse protocolo permite acompanhar e identificar a solicitação dentro da plataforma.

## Primeira etapa: registro e classificação do conteúdo

Assim que a solicitação é recebida, o sistema registra o material enviado e identifica o tipo de conteúdo.

Essa classificação é importante porque cada formato exige um tratamento diferente. Um texto pode ser analisado diretamente. Uma imagem precisa ser interpretada visualmente. Um áudio precisa ser transcrito. Um link precisa ter seu conteúdo extraído da página original.

A partir dessa identificação, a plataforma encaminha o caso para o agente mais adequado.

## Segunda etapa: atuação dos agentes especializados

A plataforma utiliza agentes especializados para realizar a primeira análise do material. Esses agentes funcionam como assistentes técnicos, cada um preparado para lidar com um tipo de conteúdo.

### Quando o conteúdo é texto

O sistema interpreta o texto enviado pelo cidadão e busca compreender qual é a afirmação principal, qual fato está sendo alegado e quais informações precisam ser verificadas.

Em seguida, realiza buscas online relacionadas ao tema. A partir dessas buscas, reúne fontes públicas, resume os conteúdos encontrados e produz uma análise preliminar sobre a possível veracidade da informação.

### Quando o conteúdo é imagem

Quando o cidadão envia uma imagem, o sistema procura identificar o que aparece nela. Isso pode incluir textos presentes na imagem, símbolos, pessoas, elementos visuais, contexto da publicação ou mensagens transmitidas pelo conteúdo.

Depois dessa interpretação, a plataforma realiza buscas relacionadas ao que foi identificado e produz uma análise preliminar semelhante à análise feita para textos.

### Quando o conteúdo é áudio

Quando o material enviado é um áudio, a plataforma primeiro realiza a transcrição automática da fala.

Depois que o áudio é transformado em texto, ele passa pelo mesmo fluxo de análise aplicado aos conteúdos textuais. O sistema identifica a afirmação principal, procura fontes relacionadas e produz uma análise preliminar.

### Quando o conteúdo é um link

Quando o cidadão envia um link, o sistema acessa a página indicada, extrai o conteúdo principal e verifica se as informações ali presentes precisam ser comparadas com outras fontes.

Se necessário, a plataforma realiza buscas complementares para verificar se o conteúdo do link está de acordo com informações públicas confiáveis.

## Terceira etapa: análise preliminar automatizada

Após o processamento inicial, o sistema organiza os resultados em um relatório preliminar. Esse relatório pode conter:

- O conteúdo original enviado pelo cidadão.
- O tipo de conteúdo identificado.
- As fontes consultadas.
- Resumos das informações encontradas.
- Pontos que confirmam ou contradizem a informação analisada.
- Uma conclusão inicial sugerida pelo sistema.
- Observações úteis para o analista humano.

Essa etapa reduz o trabalho repetitivo da equipe, pois antecipa a coleta de informações e apresenta os principais elementos para revisão.

## Quarta etapa: revisão humana

Todos os casos analisados pela plataforma são encaminhados para uma área de revisão humana.

Nessa área, o analista pode consultar o conteúdo original, verificar as fontes utilizadas pelo sistema, revisar os resumos, avaliar a conclusão preliminar e registrar a decisão final.

Essa etapa é essencial para garantir responsabilidade, controle institucional e segurança na análise. A inteligência artificial auxilia o trabalho, mas não decide sozinha.

## Quinta etapa: resposta ao cidadão

Depois que o analista registra a decisão final, a plataforma envia uma resposta ao cidadão utilizando o protocolo gerado no momento da solicitação.

A resposta pode informar, por exemplo, se o conteúdo foi considerado falso, verdadeiro, impreciso, fora de contexto ou inconclusivo, conforme os critérios definidos pela instituição.

## Base de conhecimento e reaproveitamento de análises

Com o passar do tempo, a plataforma passa a formar uma base de conhecimento com os conteúdos já analisados.

Essa base permite que novos casos sejam comparados com casos anteriores. Quando um cidadão envia um conteúdo semelhante a outro já verificado, o sistema pode identificar essa similaridade e indicar que já existe uma análise relacionada.

Isso tende a reduzir o tempo de resposta, evitar retrabalho e aumentar a eficiência da equipe responsável pela verificação.

## Transparência e proposta open source

O projeto possui proposta open source. Isso significa que o código-fonte da aplicação e a base de conhecimento construída a partir das análises podem ser disponibilizados de forma aberta, conforme as regras institucionais definidas.

Essa abordagem favorece a transparência, permite auditoria pública, estimula colaboração técnica e facilita que outras instituições possam adaptar ou aprimorar a solução.

## Resumo do fluxo do projeto

1. O cidadão envia um conteúdo suspeito.
2. O sistema gera um protocolo.
3. A plataforma identifica o tipo de conteúdo enviado.
4. Um agente especializado processa o material.
5. O sistema consulta fontes e monta uma análise preliminar.
6. Um analista humano revisa o caso.
7. A decisão final é registrada.
8. O cidadão recebe a resposta da verificação.

## Organização do código

Atualmente, o código do projeto está organizado para separar melhor as responsabilidades entre entrada da aplicação, fluxo do router, agentes, ferramentas e utilitários.

### Estrutura principal

- `src/main.py`: ponto de entrada da execução local via terminal. Recebe a pergunta do usuário, executa o workflow e exibe as etapas do processamento.
- `src/graph/workflow.py`: define e compila o fluxo principal com LangGraph.
- `src/graph/state.py`: concentra os tipos e o estado compartilhado pelo workflow, como query original, classificações, resultados e resposta final.
- `src/graph/nodes.py`: reúne os nós do router, como classificação da pergunta, roteamento para agentes e síntese da resposta final.
- `src/agents/search_agent.py`: define o agente de busca responsável por usar ferramentas e produzir a apuração inicial.
- `src/tools/`: contém as ferramentas utilizadas pelos agentes, como busca de links, leitura de URLs e data atual.
- `src/llms.py`: centraliza a configuração dos modelos usados pelo router e pelos agentes.
- `src/util.py`: reúne utilitários compartilhados, como carregamento de prompts.
- `prompts/`: armazena os prompts em arquivos `.md`, facilitando manutenção e ajuste fora do código Python.

### Objetivo dessa organização

Essa separação permite evoluir o projeto com mais clareza. Novos agentes podem ser adicionados sem concentrar toda a lógica em um único arquivo, e o fluxo do router pode crescer sem misturar configuração de modelo, tools, prompts e interface de terminal no mesmo lugar.

## Tecnologias envolvidas

* Docker
* Laravel
* FastAPI
* PostgreSQL
* Redis/RQ
* Qdrant
* MinIO
* LangChain
* LangGraph
* LangSmith
* Whisper
* Docling
* SerpAPI

## Licença

Este projeto é disponibilizado sob a licença `GNU Affero General Public License v3.0` (`AGPL-3.0`).

---
