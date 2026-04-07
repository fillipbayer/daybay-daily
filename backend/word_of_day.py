"""
DayBay Daily — Palavra do Dia (Inglês Avançado + Mandarim Básico)
Usa Anthropic Claude para gerar palavras únicas e contextualizadas por dia
"""

import json
import hashlib
import logging
from datetime import date
from typing import Dict
import anthropic

logger = logging.getLogger(__name__)


async def get_english_word(client: anthropic.AsyncAnthropic, model: str, today: date) -> Dict:
    """
    Gera uma palavra em inglês de nível avançado para o dia.
    Usa a data como seed para consistência ao longo do dia.
    """
    seed = int(hashlib.md5(f"en-{today.isoformat()}".encode()).hexdigest(), 16) % 10000

    prompt = f"""Você é um professor de inglês avançado. Gere UMA palavra em inglês de nível avançado (C1/C2) para o dia {today.strftime('%d/%m/%Y')}.

Use o número {seed} como variação para escolher uma palavra diferente a cada dia.

Responda SOMENTE com um JSON válido, sem texto adicional, com esta estrutura exata:
{{
  "word": "palavra em inglês",
  "phonetic": "transcrição fonética simplificada",
  "type": "substantivo/verbo/adjetivo/etc",
  "definition_en": "definição curta em inglês",
  "definition_pt": "definição em português",
  "example_en": "frase de exemplo em inglês",
  "example_pt": "tradução da frase de exemplo",
  "tip": "dica de uso ou origem etimológica interessante"
}}"""

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=400,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Remove possível markdown ```json ... ```
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        data["language"] = "english"
        data["level"] = "advanced"
        return data
    except Exception as e:
        logger.error(f"Erro ao gerar palavra em inglês: {e}")
        return {
            "word": "perspicacious",
            "phonetic": "pər-spɪ-ˈkeɪ-shəs",
            "type": "adjetivo",
            "definition_en": "having a ready insight; shrewd",
            "definition_pt": "perspicaz; de percepção aguçada",
            "example_en": "Her perspicacious analysis impressed the entire board.",
            "example_pt": "Sua análise perspicaz impressionou todo o conselho.",
            "tip": "Do latim 'perspicax' — ver através com clareza.",
            "language": "english",
            "level": "advanced",
        }


async def get_mandarin_word(client: anthropic.AsyncAnthropic, model: str, today: date) -> Dict:
    """
    Gera uma palavra em mandarim de nível básico (HSK 1-2) para o dia.
    """
    seed = int(hashlib.md5(f"zh-{today.isoformat()}".encode()).hexdigest(), 16) % 10000

    prompt = f"""Você é um professor de mandarim. Gere UMA palavra em mandarim de nível básico (HSK 1 ou HSK 2) para o dia {today.strftime('%d/%m/%Y')}.

Use o número {seed} como variação para escolher uma palavra diferente a cada dia.

Responda SOMENTE com um JSON válido, sem texto adicional, com esta estrutura exata:
{{
  "word": "caractere(s) em mandarim",
  "pinyin": "romanização com tons (ex: nǐ hǎo)",
  "pinyin_numbers": "romanização com números de tom (ex: ni3 hao3)",
  "type": "substantivo/verbo/adjetivo/etc",
  "definition_pt": "significado em português",
  "example_zh": "frase de exemplo em mandarim",
  "example_pinyin": "frase em pinyin",
  "example_pt": "tradução da frase",
  "stroke_count": 5,
  "tip": "dica cultural ou de memorização",
  "hsk_level": 1
}}"""

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=400,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Remove possível markdown ```json ... ```
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        data["language"] = "mandarin"
        data["level"] = "basic"
        return data
    except Exception as e:
        logger.error(f"Erro ao gerar palavra em mandarim: {e}")
        return {
            "word": "你好",
            "pinyin": "nǐ hǎo",
            "pinyin_numbers": "ni3 hao3",
            "type": "cumprimento",
            "definition_pt": "Olá / Oi",
            "example_zh": "你好，我叫拜尔。",
            "example_pinyin": "Nǐ hǎo, wǒ jiào Bài'ěr.",
            "example_pt": "Olá, meu nome é Bayer.",
            "stroke_count": 6,
            "tip": "O cumprimento mais básico do mandarim. 你 (nǐ) = você, 好 (hǎo) = bom.",
            "language": "mandarin",
            "level": "basic",
            "hsk_level": 1,
        }
