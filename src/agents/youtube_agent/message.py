from agents.youtube_agent.tools import YouTubeMetadata


def build_message_content(
    *,
    query: str,
    video_url: str,
    metadata: YouTubeMetadata,
) -> list[dict]:
    """Build the multimodal message using authoritative YouTube metadata."""
    title = metadata.title or "INDISPONÍVEL"
    content = [{
        "type": "text",
        "text": (
            "Analise o vídeo como objeto de verificação factual. O título "
            "abaixo foi obtido diretamente dos metadados públicos do YouTube "
            "e é a única fonte autoritativa para o título do vídeo.\n\n"
            f"<titulo_oficial_youtube>\n{title}\n</titulo_oficial_youtube>\n\n"
            f"<pedido_original>\n{query}\n</pedido_original>\n\n"
            "Se houver uma imagem anexada antes do vídeo, ela é a thumbnail "
            "oficial e deve ser usada somente conforme as regras do prompt."
        ),
    }]
    if metadata.thumbnail_url:
        content.append({
            "type": "image_url",
            "image_url": {"url": metadata.thumbnail_url},
        })
    content.append({
        "type": "media",
        "file_uri": video_url,
        "mime_type": "video/mp4",
    })
    return content
