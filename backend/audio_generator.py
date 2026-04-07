"""
DayBay Daily — Gerador de Áudio com OpenAI TTS
Converte o script do boletim em áudio MP3
"""

import os
import logging
from pathlib import Path
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "audio"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Limite de caracteres por chamada TTS (OpenAI aceita até 4096)
TTS_CHUNK_SIZE = 4000


def _split_text(text: str, max_chars: int = TTS_CHUNK_SIZE) -> list[str]:
    """Divide texto longo em chunks respeitando parágrafos."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current += ("\n\n" if current else "") + para
        else:
            if current:
                chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    return chunks


async def generate_audio(
    client: AsyncOpenAI,
    script: str,
    bulletin_id: str,
    voice: str = "nova",
) -> str:
    """
    Gera arquivo de áudio MP3 a partir do script.
    Retorna o caminho do arquivo gerado.
    """
    output_path = DATA_DIR / f"{bulletin_id}.mp3"

    if output_path.exists():
        logger.info(f"Áudio já existe: {output_path}")
        return str(output_path)

    chunks = _split_text(script)
    logger.info(f"Gerando áudio em {len(chunks)} chunk(s)... Voz: {voice}")

    audio_parts = []

    for i, chunk in enumerate(chunks):
        try:
            response = await client.audio.speech.create(
                model="tts-1-hd",
                voice=voice,
                input=chunk,
                response_format="mp3",
            )
            audio_parts.append(response.content)
            logger.info(f"  Chunk {i+1}/{len(chunks)} gerado ({len(chunk)} chars)")
        except Exception as e:
            logger.error(f"  Erro no chunk {i+1}: {e}")
            raise

    # Concatena partes (MP3 pode ser concatenado diretamente)
    combined = b"".join(audio_parts)
    output_path.write_bytes(combined)
    logger.info(f"✅ Áudio salvo: {output_path} ({len(combined)/1024:.1f} KB)")

    return str(output_path)


def get_audio_path(bulletin_id: str) -> str | None:
    """Retorna o caminho do áudio se existir."""
    path = DATA_DIR / f"{bulletin_id}.mp3"
    return str(path) if path.exists() else None


def audio_exists(bulletin_id: str) -> bool:
    """Verifica se o áudio para um boletim já foi gerado."""
    return (DATA_DIR / f"{bulletin_id}.mp3").exists()
