Analyze this query and determine which knowledge bases to consult.

For each relevant source, generate a targeted sub-question optimized for that source.

Available sources:
- search_agent: Search online about some information if it is TRUE or FALSE
- transcription_agent: Transcribe audio content when the user input is an audio file path or audio reference.
- image_agent: Analyze an image and extract the factual claims that must be researched online.

If the user input is audio, route to transcription_agent first and pass the audio file path or audio reference as the query.
If the user input is an image URL or image reference, route ONLY to image_agent first and pass the image URL or reference as the query. The image_agent will forward its analysis to the search_agent.


Return ONLY the sources that are relevant to the query. Each source should have a targeted sub-question optimized for that specific knowledge domain.
