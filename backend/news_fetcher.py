"""
DayBay Daily — Buscador de notícias via RSS
Busca headlines de fontes confiáveis sem necessidade de API key
"""

import feedparser
import httpx
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Fontes RSS por categoria
# ─────────────────────────────────────────────
RSS_FEEDS = {
    "brasil": [
        {"name": "G1", "url": "https://g1.globo.com/rss/g1/"},
        {"name": "UOL Notícias", "url": "https://rss.uol.com.br/feed/noticias.xml"},
        {"name": "Folha de S.Paulo", "url": "https://feeds.folha.uol.com.br/folha/brasil/rss091.xml"},
        {"name": "Agência Brasil", "url": "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml"},
    ],
    "mundo": [
        {"name": "BBC Brasil", "url": "https://feeds.bbci.co.uk/portuguese/rss.xml"},
        {"name": "Reuters", "url": "https://feeds.reuters.com/reuters/topNews"},
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    ],
    "tecnologia": [
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
        {"name": "Canaltech", "url": "https://canaltech.com.br/rss/"},
    ],
    "esportes": [
        {"name": "Globo Esporte", "url": "https://ge.globo.com/rss/ge.xml"},
        {"name": "ESPN Brasil", "url": "https://www.espn.com.br/rss/"},
        {"name": "Lance!", "url": "https://www.lance.com.br/rss.xml"},
    ],
    "entretenimento": [
        {"name": "Variety", "url": "https://variety.com/feed/"},
        {"name": "Deadline", "url": "https://deadline.com/feed/"},
        {"name": "Gshow", "url": "https://gshow.globo.com/rss/gshow/"},
    ],
    "cultura": [
        {"name": "Folha Ilustrada", "url": "https://feeds.folha.uol.com.br/folha/ilustrada/rss091.xml"},
        {"name": "Cultura Estadão", "url": "https://cultura.estadao.com.br/rss/ultimas.xml"},
        {"name": "The Guardian Culture", "url": "https://www.theguardian.com/culture/rss"},
    ],
}

CATEGORY_LABELS = {
    "brasil": "🇧🇷 Brasil",
    "mundo": "🌍 Mundo",
    "tecnologia": "💻 Tecnologia",
    "esportes": "⚽ Esportes",
    "entretenimento": "🎬 Entretenimento",
    "cultura": "🎭 Cultura",
}


def _parse_entry(entry: Any, source_name: str, category: str) -> Dict:
    """Extrai campos relevantes de uma entrada RSS."""
    published = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            published = None

    summary = ""
    if hasattr(entry, "summary"):
        summary = entry.summary
        # Remove tags HTML simples
        import re
        summary = re.sub(r"<[^>]+>", "", summary).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."

    return {
        "title": getattr(entry, "title", "Sem título"),
        "summary": summary,
        "link": getattr(entry, "link", ""),
        "source": source_name,
        "category": category,
        "category_label": CATEGORY_LABELS.get(category, category),
        "published": published,
    }


async def fetch_feed(session: httpx.AsyncClient, feed_info: Dict, category: str) -> List[Dict]:
    """Busca um feed RSS e retorna os itens mais recentes."""
    try:
        response = await session.get(
            feed_info["url"],
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "DayBay-Daily/1.0 (+https://github.com/daybay)"},
        )
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        items = []
        for entry in feed.entries[:4]:  # máximo 4 por fonte
            item = _parse_entry(entry, feed_info["name"], category)
            items.append(item)
        logger.info(f"✅ {feed_info['name']}: {len(items)} itens")
        return items
    except Exception as e:
        logger.warning(f"⚠️  Erro ao buscar {feed_info['name']}: {e}")
        return []


async def fetch_all_news(categories: List[str] = None) -> Dict[str, List[Dict]]:
    """
    Busca notícias de todas as categorias em paralelo.
    Retorna dicionário {categoria: [notícias]}
    """
    if categories is None:
        categories = list(RSS_FEEDS.keys())

    results: Dict[str, List[Dict]] = {cat: [] for cat in categories}
    tasks = []
    meta = []  # (category, feed_info)

    async with httpx.AsyncClient() as session:
        for category in categories:
            if category not in RSS_FEEDS:
                continue
            for feed_info in RSS_FEEDS[category]:
                tasks.append(fetch_feed(session, feed_info, category))
                meta.append(category)

        fetched = await asyncio.gather(*tasks, return_exceptions=True)

    for category, items in zip(meta, fetched):
        if isinstance(items, list):
            results[category].extend(items)

    # Limita a 8 itens por categoria e ordena por data
    for cat in results:
        items = results[cat]
        items.sort(key=lambda x: x.get("published") or "", reverse=True)
        results[cat] = items[:8]

    total = sum(len(v) for v in results.values())
    logger.info(f"📰 Total de notícias buscadas: {total}")
    return results


def get_top_headlines(news_by_category: Dict[str, List[Dict]], per_category: int = 3) -> List[Dict]:
    """Retorna os principais headlines de todas as categorias para o boletim."""
    headlines = []
    for category, items in news_by_category.items():
        for item in items[:per_category]:
            headlines.append(item)
    return headlines
