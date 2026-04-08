"""
DayBay Daily — Gerador de Boletim
Usa Anthropic Claude para gerar o boletim completo do dia em UMA única chamada.
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

CATEGORY_LABELS = {
    "brasil": "Brasil",
    "mundo": "Mundo",
    "tecnologia": "Tecnologia",
    "esportes": "Esportes",
    "entretenimento": "Entretenimento",
    "cultura": "Cultura",
}


def _build_news_text(news_by_category: Dict[str, List[Dict]], max_per_cat: int = 5) -> str:
    """Constrói texto de headlines para o prompt."""
    lines = []
    for category, items in news_by_category.items():
        if not items:
            continue
        label = CATEGORY_LABELS.get(category, category).upper()
        lines.append(f"\n[{label}]")
        for item in items[:max_per_cat]:
            source = item.get("source", "")
            summary = item.get("summary", "").strip()
            line = f"• {item['title']}"
            if source:
                line += f" ({source})"
            if summary and len(summary) > 20:
                line += f"\n  {summary[:200]}"
            lines.append(line)
    return "\n".join(lines) if lines else "Nenhuma notícia disponível no momento."


async def generate_bulletin_script(
    client: anthropic.AsyncAnthropic,
    model: str,
    today: date,
    news_by_category: Dict[str, List[Dict]],
    english_word: Dict,
    mandarin_word: Dict,
    events: List[Dict],
    tasks: List[Dict],
) -> str:
    """
    Gera o script completo do boletim em UMA única chamada ao Claude.
    Inclui resumo das notícias, palavras do dia e agenda — tudo em texto corrido para TTS.
    """
    weekday = WEEKDAYS_PT[today.weekday()]
    date_str = f"{weekday}, {today.day:02d} de {MONTHS_PT[today.month]} de {today.year}"

    news_text = _build_news_text(news_by_category)

    # Agenda
    agenda_text = ""
    if events:
        agenda_text = "Agenda de hoje:\n"
        for ev in events[:5]:
            agenda_text += f"- {ev['start'][:5]}: {ev['subject']}"
            if ev.get("location"):
                agenda_text += f" ({ev['location']})"
            agenda_text += "\n"
    if tasks:
        high = [t for t in tasks if t.get("importance") == "high"]
        pendentes = (high or tasks)[:3]
        if pendentes:
            agenda_text += "Tarefas pendentes:\n"
            for t in pendentes:
                due = f" — vence {t['due_date']}" if t.get("due_date") else ""
                agenda_text += f"- {t['title']}{due}\n"

    prompt = f"""Você é "Day", apresentador de um boletim matinal de rádio brasileiro — carismático, informativo e descontraído.

Hoje é {date_str}.

Crie o SCRIPT COMPLETO do boletim para ser convertido em áudio (TTS). O script deve ter pelo menos 700 palavras e cobrir todos os blocos abaixo em texto corrido, natural e fluente — como se estivesse falando ao vivo.

=== NOTÍCIAS DE HOJE ===
{news_text}

=== PALAVRA DO DIA — INGLÊS (nível avançado) ===
Palavra: {english_word.get('word', 'Perspicacious')} ({english_word.get('type', 'adjetivo')})
Pronúncia: {english_word.get('phonetic', 'pər-spɪ-ˈkeɪ-shəs')}
Significado em português: {english_word.get('definition_pt', 'perspicaz, de percepção aguçada')}
Exemplo: {english_word.get('example_pt', 'Sua análise perspicaz impressionou todos.')}

=== PALAVRA DO DIA — MANDARIM (nível básico) ===
Caractere: {mandarin_word.get('word', '你好')} — Pinyin: {mandarin_word.get('pinyin', 'nǐ hǎo')}
Significado: {mandarin_word.get('definition_pt', 'Olá')}
Exemplo: {mandarin_word.get('example_pt', 'Você diz nǐ hǎo para cumprimentar alguém.')}

=== AGENDA ===
{agenda_text if agenda_text else "Nenhum compromisso registrado para hoje."}

ESTRUTURA DO SCRIPT (siga esta ordem):
1. Abertura calorosa com saudação, dia da semana e data completa (2-3 frases)
2. Bloco de notícias — para cada categoria com notícias, apresente os destaques de forma narrativa e envolvente (não liste — conte como uma história). Se houver poucas notícias, aprofunde o contexto.
3. Bloco "Palavra do Dia em Inglês" — apresente a palavra, diga como se pronuncia, explique o significado e use o exemplo naturalmente
4. Bloco "Palavra do Dia em Mandarim" — mesmo formato, com dica cultural
5. Bloco de agenda — mencione compromissos e tarefas de forma prática
6. Encerramento motivacional original (2-3 frases)

REGRAS OBRIGATÓRIAS:
- Use APENAS texto corrido — zero markdown, zero bullets, zero colchetes, zero títulos com asteriscos
- Tom: profissional mas descontraído, como um podcast premium brasileiro
- Mínimo de 700 palavras — o ouvinte precisa de pelo menos 5 minutos de conteúdo
- Transições naturais entre blocos (ex: "Falando agora de tecnologia...", "E por falar em esportes...")
- Escreva exatamente como seria falado em voz alta — sem abreviações estranhas
- Pronuncie números por extenso quando possível (ex: "dois mil e vinte e seis" em vez de "2026")"""

    try:
        logger.info(f"Chamando Claude ({model}) para gerar script do boletim...")
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}],
        )
        script = response.content[0].text.strip()
        word_count = len(script.split())
        char_count = len(script)
        logger.info(f"✅ Script gerado: {word_count} palavras / {char_count} caracteres / ~{word_count//150} min de áudio")
        return script
    except Exception as e:
        logger.error(f"❌ Erro ao gerar script com Claude: {type(e).__name__}: {e}")
        # Fallback: script básico baseado nas notícias sem IA
        return _generate_fallback_script(date_str, news_by_category, english_word, mandarin_word, agenda_text)


def _generate_fallback_script(
    date_str: str,
    news_by_category: Dict[str, List[Dict]],
    english_word: Dict,
    mandarin_word: Dict,
    agenda_text: str,
) -> str:
    """Gera um script básico sem IA quando a API falha."""
    lines = [
        f"Bom dia! Hoje é {date_str}. Eu sou Day, e este é o seu boletim diário.",
        "",
    ]

    for category, items in news_by_category.items():
        if not items:
            continue
        label = CATEGORY_LABELS.get(category, category)
        lines.append(f"Nos destaques de {label}:")
        for item in items[:3]:
            lines.append(f"{item['title']}.")
        lines.append("")

    word = english_word.get('word', '')
    if word:
        lines.append(
            f"A palavra do dia em inglês é {word}, que significa {english_word.get('definition_pt', '')}. "
            f"Exemplo: {english_word.get('example_pt', '')}."
        )

    mword = mandarin_word.get('word', '')
    if mword:
        lines.append(
            f"Em mandarim, aprenda {mword}, pronunciado {mandarin_word.get('pinyin', '')}, "
            f"que significa {mandarin_word.get('definition_pt', '')}."
        )

    if agenda_text:
        lines.append(f"\nSua agenda: {agenda_text}")

    lines.append("\nTenha um excelente dia! Até amanhã.")
    return "\n".join(lines)


async def summarize_news(
    client: anthropic.AsyncAnthropic,
    model: str,
    news_by_category: Dict[str, List[Dict]],
) -> Dict[str, str]:
    """
    Compatibilidade: retorna resumos simples das headlines (sem chamada de API).
    A geração real do script agora é feita em generate_bulletin_script diretamente.
    """
    summaries = {}
    for category, items in news_by_category.items():
        if items:
            titles = [item["title"] for item in items[:5]]
            summaries[category] = " | ".join(titles)
    return summaries


async def generate_quick_summary(
    client: anthropic.AsyncAnthropic,
    model: str,
    news_by_category: Dict[str, List[Dict]],
    events: List[Dict],
) -> str:
    """
    Gera um resumo rápido e dinâmico dos destaques do dia.
    """
    all_headlines = []
    for category, items in news_by_category.items():
        label = CATEGORY_LABELS.get(category, category)
        for item in items[:3]:
            all_headlines.append(f"[{label}] {item['title']}")

    headlines_text = "\n".join(all_headlines[:20]) if all_headlines else "Sem destaques disponíveis no momento."

    agenda_reminder = ""
    if events:
        pending = [e for e in events if e["start"] > datetime.now().strftime("%Y-%m-%d %H:%M")]
        if pending:
            agenda_reminder = f"\n\nAinda hoje: {pending[0]['subject']} às {pending[0]['start'][:5]}"

    prompt = f"""Você é Day, apresentador de um boletim de rádio brasileiro.

É final de tarde. Faça um resumo rápido e dinâmico dos destaques do dia com pelo menos 300 palavras em texto corrido, para ser lido em áudio:

DESTAQUES DE HOJE:
{headlines_text}
{agenda_reminder}

REGRAS:
- Comece com "Boa tarde! Aqui estão os destaques de hoje..."
- Apresente as notícias de forma ágil e envolvente — conte, não liste
- Termine com "Até amanhã!" ou similar
- Mínimo de 300 palavras
- Apenas texto corrido, sem markdown, sem bullets"""

    try:
        logger.info(f"Chamando Claude ({model}) para resumo rápido...")
        response = await client.messages.create(
            model=model,
            max_tokens=1500,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}],
        )
        script = response.content[0].text.strip()
        logger.info(f"✅ Resumo rápido: {len(script.split())} palavras")
        return script
    except Exception as e:
        logger.error(f"❌ Erro ao gerar resumo rápido: {type(e).__name__}: {e}")
        # Fallback sem IA
        lines = ["Boa tarde! Aqui estão os destaques de hoje."]
        for category, items in news_by_category.items():
            for item in items[:2]:
                lines.append(f"{item['title']}.")
        lines.append("Fique bem e até amanhã!")
        return " ".join(lines)
