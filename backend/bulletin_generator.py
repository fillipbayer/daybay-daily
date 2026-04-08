"""
DayBay Daily — Gerador de Boletim
Usa Anthropic Claude para resumir notícias e montar o boletim completo do dia
"""

import json
import logging
from datetime import date, datetime
from typing import Dict, List, Optional
import anthropic

logger = logging.getLogger(__name__)

WEEKDAYS_PT = {
    0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
    3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo",
}

MONTHS_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

CATEGORY_EMOJI = {
    "brasil": "🇧🇷",
    "mundo": "🌍",
    "tecnologia": "💻",
    "esportes": "⚽",
    "entretenimento": "🎬",
    "cultura": "🎭",
}


async def summarize_news(
    client: anthropic.AsyncAnthropic,
    model: str,
    news_by_category: Dict[str, List[Dict]],
) -> Dict[str, str]:
    """
    Gera um resumo narrativo para cada categoria de notícias.
    Retorna {categoria: texto_resumo}
    """
    summaries = {}

    for category, items in news_by_category.items():
        if not items:
            continue

        headlines = "\n".join([
            f"- {item['title']} ({item['source']})"
            for item in items[:6]
        ])

        emoji = CATEGORY_EMOJI.get(category, "📌")
        prompt = f"""Você é um apresentador de rádio brasileiro, descontraído e informativo.

Abaixo estão os principais títulos de notícias de {category.upper()} de hoje:
{headlines}

Escreva um breve resumo falado (2-3 parágrafos, máx 200 palavras) sobre estas notícias como se estivesse apresentando ao vivo um boletim matinal de rádio.
- Use linguagem natural e fluente, como se estivesse falando
- Destaque os pontos mais relevantes
- Seja objetivo mas envolvente
- NÃO use bullets, markdown ou formatação especial — apenas texto corrido
- Comece diretamente com o conteúdo (sem "Olá" nem saudações)"""

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=350,
                temperature=0.75,
                messages=[{"role": "user", "content": prompt}],
            )
            summaries[category] = response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Erro ao resumir {category}: {e}")
            titles = [item["title"] for item in items[:3]]
            summaries[category] = f"Destaques de hoje: {' | '.join(titles)}"

    return summaries


async def generate_bulletin_script(
    client: anthropic.AsyncAnthropic,
    model: str,
    today: date,
    category_summaries: Dict[str, str],
    english_word: Dict,
    mandarin_word: Dict,
    events: List[Dict],
    tasks: List[Dict],
) -> str:
    """
    Gera o script completo do boletim para leitura em áudio.
    """
    weekday = WEEKDAYS_PT[today.weekday()]
    date_str = f"{weekday}, {today.day:02d} de {MONTHS_PT[today.month]} de {today.year}"

    # Monta contexto de agenda
    agenda_text = ""
    if events:
        agenda_text = "Sua agenda de hoje:\n"
        for ev in events[:5]:
            agenda_text += f"- {ev['start'][:5]}: {ev['subject']}"
            if ev.get("location"):
                agenda_text += f" ({ev['location']})"
            agenda_text += "\n"
    if tasks:
        agenda_text += "\nSuas tarefas pendentes:\n"
        high = [t for t in tasks if t.get("importance") == "high"]
        for t in (high or tasks)[:4]:
            due = f" — vence {t['due_date']}" if t.get("due_date") else ""
            agenda_text += f"- {t['title']}{due}\n"

    # Monta resumos de notícias
    news_text = ""
    for category, summary in category_summaries.items():
        label = {"brasil": "Brasil", "mundo": "Mundo", "tecnologia": "Tecnologia",
                 "esportes": "Esportes", "entretenimento": "Entretenimento", "cultura": "Cultura"}.get(category, category)
        news_text += f"\n[{label.upper()}]\n{summary}\n"

    prompt = f"""Você é um apresentador de rádio brasileiro carismático e informativo chamado "Day".

Hoje é {date_str}.

Use os conteúdos abaixo para montar o SCRIPT COMPLETO do boletim matinal para ser lido em áudio (TTS).

=== NOTÍCIAS ===
{news_text}

=== PALAVRA DO DIA — INGLÊS AVANÇADO ===
Palavra: {english_word.get('word')} ({english_word.get('type')})
Pronúncia: {english_word.get('phonetic')}
Significado: {english_word.get('definition_pt')}
Exemplo: {english_word.get('example_pt')}

=== PALAVRA DO DIA — MANDARIM ===
Palavra: {mandarin_word.get('word')} — {mandarin_word.get('pinyin')}
Significado: {mandarin_word.get('definition_pt')}
Exemplo: {mandarin_word.get('example_pt')}

=== AGENDA ===
{agenda_text if agenda_text else "Nenhum compromisso registrado para hoje."}

INSTRUÇÕES PARA O SCRIPT:
- Comece com uma saudação calorosa mencionando o dia da semana e data
- Apresente cada seção de notícias com uma transição fluida
- Para as palavras do dia, seja didático e divertido — ensine como se fosse ao vivo
- Se houver agenda, mencione reuniões e tarefas importantes de forma prática
- Termine com uma frase motivacional breve e original para o dia
- Use APENAS texto corrido, sem markdown, sem bullets
- Tom: profissional mas descontraído, como um podcast premium
- Duração estimada de leitura: 5-8 minutos"""

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=2000,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Erro ao gerar script: {e}")
        return f"Bom dia! Hoje é {date_str}. Seu boletim está sendo preparado. Por favor, tente novamente em instantes."


async def generate_quick_summary(
    client: anthropic.AsyncAnthropic,
    model: str,
    news_by_category: Dict[str, List[Dict]],
    events: List[Dict],
) -> str:
    """
    Gera um resumo rápido para o boletim on-demand (ex: às 18h).
    Mais curto e focado nos destaques do dia.
    """
    all_headlines = []
    for category, items in news_by_category.items():
        label = category.upper()
        for item in items[:2]:
            all_headlines.append(f"[{label}] {item['title']}")

    headlines_text = "\n".join(all_headlines[:20])

    agenda_reminder = ""
    if events:
        pending = [e for e in events if e["start"] > datetime.now().strftime("%Y-%m-%d %H:%M")]
        if pending:
            agenda_reminder = f"\n\nReunião pendente hoje: {pending[0]['subject']} às {pending[0]['start'][:5]}"

    prompt = f"""Você é Day, apresentador de um boletim de rádio.

É final de tarde. Faça um resumo rápido e dinâmico dos destaques do dia (máx 400 palavras, texto corrido para TTS):

NOTÍCIAS DO DIA:
{headlines_text}
{agenda_reminder}

- Comece com "Boa tarde! Aqui estão os destaques de hoje..."
- Cubra as principais notícias de forma ágil
- Mencione a agenda se houver
- Termine com "Até amanhã!" ou similar
- Apenas texto corrido, sem markdown"""

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=700,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Erro ao gerar resumo rápido: {e}")
        return "Boa tarde! Aqui está o resumo rápido do seu dia. Os destaques estão disponíveis no seu painel."
