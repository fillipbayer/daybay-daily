"""
DayBay Daily — Gerador de Áudio com Edge TTS (Microsoft Neural)
Converte o script do boletim em áudio MP3 usando vozes neurais gratuitas
"""

import asyncio
import logging
import tempfile
import os
from pathlib import Path

import edge_tts

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "audio"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Limite de caracteres por chunk (edge-tts suporta textos longos, mas chunks garantem estabilidade)
TTS_CHUNK_SIZE = 3000

# Vozes disponíveis em pt-BR:
# pt-BR-FranciscaNeural (feminina, padrão)
# pt-BR-AntonioNeural   (masculina)
DEFAULT_VOICE = "pt-BR-FranciscaNeural"


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
    script: str,
    bulletin_id: str,
    voice: str = DEFAULT_VOICE,
    force: bool = False,
) -> str:
    """
    Gera arquivo de áudio MP3 a partir do script usando Edge TTS.
    Retorna o caminho do arquivo gerado.
    force=True apaga o arquivo anterior e regenera.
    """
    output_path = DATA_DIR / f"{bulletin_id}.mp3"

    if output_path.exists():
        if not force:
            logger.info(f"Áudio já existe: {output_path}")
            return str(output_path)
        else:
            output_path.unlink()
            logger.info(f"Áudio anterior removido para regeneração: {output_path}")

    chunks = _split_text(script)
    logger.info(f"Gerando áudio em {len(chunks)} chunk(s)... Voz: {voice}")

    audio_parts = []

    for i, chunk in enumerate(chunks):
        try:
            communicate = edge_tts.Communicate(chunk, voice)
            # Grava em arquivo temporário e lê os bytes
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name

            await communicate.save(tmp_path)

            with open(tmp_path, "rb") as f:
                audio_parts.append(f.read())

            os.unlink(tmp_path)
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
