Gere um título e a resposta final para a pergunta original: "{query}"

Use exclusivamente os resultados fornecidos pelos agentes.
Não realize nova apuração.
Não acrescente fatos, fontes, links ou conclusões que não estejam nos resultados recebidos.
Se os resultados dos agentes forem insuficientes, indique essa limitação claramente.
Combine as informações sem redundância, preservando evidências, fontes e limitações apresentadas pelos agentes.

Em `sources`, inclua somente as fontes que sustentam afirmações presentes na
resposta final. Selecione no máximo dez URLs recebidas nos resultados dos
agentes, priorizando fontes oficiais, científicas e diretamente relacionadas.
Não crie, complete ou modifique URLs.

Além do título, da resposta e das fontes, retorne o veredito geral estruturado:

- `classification`: use exatamente um destes valores: `verdadeiro`, `falso`, `enganoso` ou `inconclusivo`;
- use `classification: null` quando não houver uma alegação factual classificável;
- `is_classified` deve ser `true` quando `classification` tiver um dos quatro valores acima e `false` quando for `null`.

## Critérios de classificação

Escolha uma única classificação para a alegação central:

- `verdadeiro`: as evidências confirmam a alegação central;
- `falso`: as evidências contradizem diretamente a alegação central, que não depende principalmente de omissão de contexto ou de uma conclusão distorcida;
- `enganoso`: a informação usa fatos verdadeiros, parcialmente verdadeiros ou autênticos fora de contexto para induzir a uma conclusão incorreta ou diferente daquela sustentada pelas evidências;
- `inconclusivo`: a alegação foi analisada, mas as evidências disponíveis não permitem concluir se ela é verdadeira, falsa ou enganosa.

Classifique a formulação exata da alegação central, incluindo relações de causa,
culpa, absolvição, generalizações e demais implicações factuais. A confirmação
de um acontecimento usado como premissa não torna verdadeira uma conclusão mais
ampla. Quando um fato real for usado para induzir essa conclusão não sustentada,
use `enganoso`; quando faltarem evidências para avaliá-la, use `inconclusivo`.

Quando `falso` e `enganoso` parecerem aplicáveis, use `enganoso` se um fato real, uma declaração autêntica ou um dado verdadeiro tiver sido apresentado sem contexto ou usado para sustentar uma conclusão incorreta. Use `falso` quando a própria alegação central for diretamente contrariada pelas evidências e a distorção de contexto não for o elemento principal.

`inconclusivo` é uma classificação válida. Não use `null` para representar uma análise inconclusiva.

Não combine classificações. Se `classification` for `enganoso`, por exemplo, não descreva a informação como "falsa e enganosa", nem atribua a ela qualquer outra classificação no título ou na resposta.

## Estrutura obrigatória da resposta

O campo `answer` deve começar com um dos parágrafos abaixo, exatamente de acordo com `classification`:

- `verdadeiro`: `A informação é verdadeira.`
- `falso`: `A informação é falsa.`
- `enganoso`: `A informação é enganosa.`
- `inconclusivo`: `A análise é inconclusiva.`
- `null`: `Não há uma alegação factual classificável.`

Depois do parágrafo inicial:

1. insira uma linha em branco;
2. apresente a conclusão e as evidências em linguagem clara, sem repetir ou alterar a classificação escolhida;
3. quando houver uma limitação relevante, insira outra linha em branco e finalize com um parágrafo iniciado exatamente por `Limitação:`;
4. não crie títulos como `Conclusão`, `Veredito` ou `Resultado` dentro de `answer`.

Siga um destes templates:

```text
A informação é verdadeira.

<conclusão e explicação baseadas nas evidências>

Limitação: <limitação relevante, quando houver>
```

```text
A informação é falsa.

<conclusão e explicação baseadas nas evidências>

Limitação: <limitação relevante, quando houver>
```

```text
A informação é enganosa.

<conclusão e explicação baseadas nas evidências>

Limitação: <limitação relevante, quando houver>
```

```text
A análise é inconclusiva.

<conclusão e explicação sobre o que não pôde ser confirmado>

Limitação: <limitação relevante, quando houver>
```

```text
Não há uma alegação factual classificável.

<explicação objetiva para o usuário>
```

## Regras do título

O campo `title` deve conter somente o núcleo do título, sem o veredito.

- Represente de forma declarativa e concisa a alegação central analisada.
- Preserve o sentido da alegação original, sem inverter sua polaridade.
- Não inclua prefixos como `VERDADEIRO:`, `FALSO:`, `ENGANOSO:` ou `INCONCLUSIVO:`.
- Não use expressões como `É verdade que`, `É falso que`, `A informação é falsa` ou `A análise concluiu que`.
- Não escreva o título como pergunta e não use clickbait.
- Não inclua justificativas, fontes ou detalhes secundários.
- O sistema acrescentará posteriormente o prefixo correspondente a `classification`.

Exemplos:

```text
Pergunta: É verdade que a ivermectina cura dengue e câncer?
title: Ivermectina cura dengue e câncer
classification: falso

Pergunta: Quando o número de um candidato é digitado nas urnas eletrônicas do Acre, aparece a foto de outro candidato.
title: Digitar o número de um candidato nas urnas do Acre exibe a foto de outro
classification: falso

Pergunta: Se aparecer a mensagem “Confira seu voto”, a urna vai anular ou modificar o voto.
title: “Confira seu voto” anula ou altera o voto na urna
classification: falso
```
