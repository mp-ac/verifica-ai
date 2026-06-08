import json5
from langchain_core.tools import tool


@tool("audio_transcription")
def audio_transcription(file_path: str):
    """
    Inicia a transcrição de um áudio ou vídeo. Use essa tool quando receber o caminho/link de um áudio.

    O retorno da função será uma transcrição do áudio que deverá ser passada para o search_agent
    """
    return json5.dumps(
        {
            "results": "Um amigo meu disse que a vacina da pfizer causa câncer, é verdade?"
        }
    )
