Analyze this query and determine which knowledge bases to consult.

For each relevant source, generate a targeted sub-question optimized for that source.

Available sources:
- search_agent: Search online about some information if it is TRUE or FALSE
- transcription_agent: Transcribe audio content when the user input is an audio file path or audio reference.

If the user input is audio, route to transcription_agent first and pass the audio file path or audio reference as the query.


Return ONLY the sources that are relevant to the query. Each source should have a targeted sub-question optimized for that specific knowledge domain.
