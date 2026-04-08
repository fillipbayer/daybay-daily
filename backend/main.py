"""
DayBay Daily — Servidor Principal (FastAPI)
Execute com: uvicorn main:app --reload --port 8000
"""

import os
import json
import logging
import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import anthropic

# Carrega .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Imports locais
from news_fetcher import fetch_all_news, get_top_headlines
from bulletin_generator import summarize_news, generate_bulletin_script, generate_quick_summary
from audio_generator import generate_audio, get_audio_path, audio_exists
from word_of_day import get_english_word, get_mandarin_word
from calendar_integration import (
    get_todays_events, get_tasks, is_authenticated,
    get_device_code_flow_url, complete_device_code_flow
)

# ─────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("daybay")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
TTS_VOICE = os.getenv("TTS_VOICE", "pt-BR-FranciscaNeural")

DATA_DIR = Path(__file__).parent.parent / "data" / "bulletins"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# ─────────────────────────────────────────────
# App FastAPI
# ─────────────────────────────────────────────
app = FastAPI(
    title="DayBay Daily",
    description="Seu boletim diário personalizado",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve arquivos estáticos do frontend
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY não configurada. Configure o arquivo .env"
        )
    return anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


def bulletin_path(date_str: str, bulletin_type: str = "morning") -> Path:
    return DATA_DIR / f"{date_str}_{bulletin_type}.json"


def load_bulletin(date_str: str, bulletin_type: str = "morning") -> Optional[dict]:
    path = bulletin_path(date_str, bulletin_type)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def save_bulletin(date_str: str, bulletin_type: str, data: dict):
    path = bulletin_path(date_str, bulletin_type)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# Estado de geração em andamento
_generating: dict[str, bool] = {}


# ─────────────────────────────────────────────
# Rotas
# ─────────────────────────────────────────────

@app.get("/")
async def root():
    """Serve o frontend."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"status": "DayBay Daily rodando!", "docs": "/docs"})


@app.get("/api/status")
async def status():
    """Status do servidor e configurações."""
    return {
        "status": "online",
        "anthropic_configured": bool(ANTHROPIC_API_KEY),
        "microsoft_authenticated": is_authenticated(),
        "model": ANTHROPIC_MODEL,
        "voice": TTS_VOICE,
        "server_time": datetime.now().isoformat(),
    }


@app.get("/api/bulletin/today")
async def get_today_bulletin(background_tasks: BackgroundTasks):
    """
    Retorna o boletim de hoje. Se não existir, gera automaticamente.
    """
    today_str = date.today().isoformat()
    bulletin = load_bulletin(today_str)

    if bulletin:
        return bulletin

    # Agenda geração em background
    if not _generating.get(f"{today_str}_morning"):
        background_tasks.add_task(generate_bulletin_task, today_str, "morning")

    return {
        "status": "generating",
        "message": "Seu boletim está sendo gerado. Aguarde alguns segundos e atualize.",
        "date": today_str,
    }


@app.get("/api/bulletin/{date_str}")
async def get_bulletin_by_date(date_str: str, bulletin_type: str = "morning"):
    """Retorna um boletim de uma data específica."""
    bulletin = load_bulletin(date_str, bulletin_type)
    if not bulletin:
        raise HTTPException(status_code=404, detail=f"Boletim não encontrado para {date_str}")
    return bulletin


@app.post("/api/bulletin/generate")
async def generate_now(background_tasks: BackgroundTasks, quick: bool = False, force: bool = False):
    """
    Gera um novo boletim on-demand (ex: boletim das 18h).
    quick=true gera um resumo rápido mais curto.
    force=true apaga o boletim e áudio existentes e regenera do zero.
    """
    today_str = date.today().isoformat()
    bulletin_type = "quick" if quick else "morning"
    key = f"{today_str}_{bulletin_type}"

    if _generating.get(key):
        return {"status": "generating", "message": "Já em geração, aguarde..."}

    if force:
        # Apaga arquivos existentes para forçar regeneração completa
        bp = bulletin_path(today_str, bulletin_type)
        if bp.exists():
            bp.unlink()
            logger.info(f"Boletim anterior removido para regeneração: {bp}")

    background_tasks.add_task(generate_bulletin_task, today_str, bulletin_type, force=force)
    return {
        "status": "started",
        "message": "Gerando boletim do zero... Isso pode levar 60-90 segundos.",
        "type": bulletin_type,
        "force": force,
    }


@app.get("/api/bulletin/status/{date_str}")
async def bulletin_generation_status(date_str: str, bulletin_type: str = "morning"):
    """Verifica se o boletim foi gerado."""
    key = f"{date_str}_{bulletin_type}"
    bulletin = load_bulletin(date_str, bulletin_type)

    return {
        "date": date_str,
        "type": bulletin_type,
        "ready": bulletin is not None,
        "generating": _generating.get(key, False),
        "has_audio": audio_exists(f"{date_str}_{bulletin_type}") if bulletin else False,
    }


@app.get("/api/audio/{bulletin_id}")
async def get_audio(bulletin_id: str):
    """Retorna o arquivo de áudio do boletim."""
    path = get_audio_path(bulletin_id)
    if not path:
        raise HTTPException(status_code=404, detail="Áudio não encontrado")
    return FileResponse(path, media_type="audio/mpeg", filename=f"{bulletin_id}.mp3")


@app.get("/api/bulletins/list")
async def list_bulletins():
    """Lista todos os boletins disponíveis, organizados por data."""
    bulletins = []
    for file in sorted(DATA_DIR.glob("*.json"), reverse=True)[:30]:
        parts = file.stem.split("_", 1)
        if len(parts) == 2:
            date_str, btype = parts
            bulletin = json.loads(file.read_text(encoding="utf-8"))
            bulletins.append({
                "date": date_str,
                "type": btype,
                "generated_at": bulletin.get("generated_at"),
                "has_audio": audio_exists(file.stem),
                "categories": list(bulletin.get("news", {}).keys()),
            })
    return bulletins


@app.get("/api/bulletin/script/{date_str}")
async def get_bulletin_script(date_str: str, bulletin_type: str = "morning"):
    """Retorna o script de texto do boletim para depuração."""
    bulletin = load_bulletin(date_str, bulletin_type)
    if not bulletin:
        raise HTTPException(status_code=404, detail=f"Boletim não encontrado para {date_str}")
    script = bulletin.get("script", "")
    word_count = len(script.split()) if script else 0
    return {
        "date": date_str,
        "type": bulletin_type,
        "word_count": word_count,
        "char_count": len(script),
        "estimated_duration_min": round(word_count / 150, 1),
        "script": script,
    }


@app.get("/api/news/live")
async def get_live_news():
    """Busca notícias ao vivo sem gerar um boletim completo."""
    try:
        news = await fetch_all_news()
        total = sum(len(v) for v in news.values())
        return {
            "news": news,
            "total_items": total,
            "per_category": {cat: len(items) for cat, items in news.items()},
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calendar/today")
async def get_calendar():
    """Retorna eventos e tarefas do Microsoft Calendar."""
    events = await get_todays_events()
    tasks = await get_tasks()
    return {
        "events": events,
        "tasks": tasks,
        "authenticated": is_authenticated(),
    }


@app.get("/api/calendar/auth/start")
async def start_calendar_auth():
    """Inicia autenticação Microsoft via Device Code Flow."""
    flow = get_device_code_flow_url()
    if not flow:
        raise HTTPException(
            status_code=400,
            detail="MICROSOFT_CLIENT_ID não configurado no .env"
        )
    return flow


@app.get("/api/calendar/auth/complete")
async def complete_calendar_auth():
    """Completa a autenticação Microsoft após login do usuário."""
    success = complete_device_code_flow()
    if success:
        return {"status": "authenticated", "message": "Microsoft Calendar conectado!"}
    return {"status": "pending", "message": "Aguardando login... Tente novamente em instantes."}


# ─────────────────────────────────────────────
# Tarefa de geração em background
# ─────────────────────────────────────────────

async def generate_bulletin_task(date_str: str, bulletin_type: str, force: bool = False):
    """Gera um boletim completo de forma assíncrona."""
    key = f"{date_str}_{bulletin_type}"
    _generating[key] = True
    logger.info(f"🔄 Gerando boletim: {date_str} [{bulletin_type}]")

    try:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        today = date.fromisoformat(date_str)

        # 1. Busca notícias
        logger.info("📰 Buscando notícias...")
        news_by_category = await fetch_all_news()

        # 2. Busca agenda
        logger.info("📅 Buscando agenda...")
        events = await get_todays_events(today)
        tasks = await get_tasks()

        # 3. Palavras do dia
        logger.info("📚 Gerando palavras do dia...")
        english_word, mandarin_word = await asyncio.gather(
            get_english_word(client, ANTHROPIC_MODEL, today),
            get_mandarin_word(client, ANTHROPIC_MODEL, today),
        )

        # 4. Resumos de notícias
        logger.info("✍️  Resumindo notícias...")
        if bulletin_type == "quick":
            script = await generate_quick_summary(client, ANTHROPIC_MODEL, news_by_category, events)
            summaries = {}
        else:
            summaries = await summarize_news(client, ANTHROPIC_MODEL, news_by_category)
            # 5. Script completo
            logger.info("🎙️  Gerando script do boletim...")
            script = await generate_bulletin_script(
                client, ANTHROPIC_MODEL, today,
                summaries, english_word, mandarin_word, events, tasks,
            )

        # 6. Áudio TTS (Edge TTS — Microsoft Neural, gratuito)
        logger.info("🔊 Gerando áudio...")
        bulletin_id = f"{date_str}_{bulletin_type}"
        audio_path = await generate_audio(script, bulletin_id, TTS_VOICE, force=force)

        # 7. Salva o boletim
        bulletin_data = {
            "id": bulletin_id,
            "date": date_str,
            "type": bulletin_type,
            "generated_at": datetime.now().isoformat(),
            "script": script,
            "news": news_by_category,
            "summaries": summaries,
            "english_word": english_word,
            "mandarin_word": mandarin_word,
            "events": events,
            "tasks": tasks,
            "has_audio": True,
        }
        save_bulletin(date_str, bulletin_type, bulletin_data)
        logger.info(f"✅ Boletim gerado com sucesso: {bulletin_id}")

    except Exception as e:
        logger.error(f"❌ Erro ao gerar boletim {key}: {e}", exc_info=True)
    finally:
        _generating[key] = False


# ─────────────────────────────────────────────
# Auto-geração do boletim matinal ao iniciar
# ─────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    logger.info("🌅 DayBay Daily iniciado!")
    if not ANTHROPIC_API_KEY:
        logger.warning("⚠️  ANTHROPIC_API_KEY não configurada — configure o arquivo .env")
        return

    today_str = date.today().isoformat()
    if not load_bulletin(today_str):
        logger.info("📋 Boletim de hoje não encontrado — gerando automaticamente...")
        asyncio.create_task(generate_bulletin_task(today_str, "morning"))
