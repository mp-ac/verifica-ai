Gere um título e a resposta final para a pergunta original: "{query}"

Use exclusivamente os resultados fornecidos pelos agentes.
Não realize nova apuração.
Não acrescente fatos, fontes, links ou conclusões que não estejam nos resultados recebidos.
Se os resultados dos agentes forem insuficientes, indique essa limitação claramente.
Combine as informações sem redundância, preservando evidências, fontes e limitações apresentadas pelos agentes.

Além do título, da resposta e das fontes, retorne o veredito geral estruturado:

- `classification`: use exatamente um destes valores: `verdadeiro`, `falso`, `enganoso` ou `inconclusivo`;
- use `classification: null` quando não houver uma alegação factual classificável;
- `is_classified` deve ser `true` quando `classification` tiver um dos quatro valores acima e `false` quando for `null`.

`inconclusivo` é um veredito válido: significa que a alegação foi analisada, mas as evidências não permitiram concluir se é verdadeira, falsa ou enganosa. Não use `null` para representar uma análise inconclusiva.

O título deve:
- ser curto e objetivo;
- resumir o assunto principal da resposta;
- ser baseado no conteúdo que será apresentado em `answer`;
- não ser uma pergunta, não usar clickbait e não repetir necessariamente a pergunta original.
