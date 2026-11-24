"""Language settings for AI-generated text and EPUB labels."""

from __future__ import annotations

from datetime import datetime

from config import get_settings

LANGUAGE_LABELS: dict[str, str] = {
    "pt-BR": "Brazilian Portuguese",
    "en": "English",
}

EPUB_LABELS: dict[str, dict[str, str]] = {
    "pt-BR": {
        "digest_title": "Resumo de Notícias",
        "summary": "Resumo",
        "relevance_score": "Pontuação de relevância",
        "relevance": "Relevância",
        "top_stories": "Principais histórias por relevância",
        "score": "nota",
        "articles": "artigos",
        "article_of": "de",
        "read_full": "Ler artigo completo online →",
        "contents": "Índice",
        "sections_today": "Suas seções nesta edição.",
        "edition_overview": "Nesta edição",
        "also_inside": "Também nesta edição",
        "by_section": "Por editoria",
        "fallback_section_editorial": "{count} histórias em {category} hoje.",
        "fallback_section_lead": "Destaque:",
        "fallback_global_headline": "Resumo de hoje",
        "fallback_global_editorial": (
            "Este resumo cobre {total} histórias em {sections} seções."
        ),
        "tipo_resumo": "Resumo",
        "tipo_artigo_completo": "Artigo completo",
        "story": "matéria",
        "stories": "matérias",
        "mention": "menção",
        "mentions": "menções",
        "lead_story": "Manchete",
        "highlights_today": "Destaques de hoje",
        "reading": "leitura",
        "edition_number": "Edição {number}",
        "edition_topics": "Temas da edição",
        "other_topics": "outros",
        "includes_lead_story": "inclui a manchete",
        "topic": "tema",
        "topics": "temas",
        "topic_of_day": "Tema do dia",
        "share_of_mentions": "{percent} das menções",
        "most_crossed": "Mais cruzada",
        "story_number": "Matéria {number}",
        "in_topics": "em {count} temas",
        "novelty": "Novidade",
        "not_last_edition": "não apareceu ontem",
        "all_mentions": "Todas as menções",
        "square_legend": "1 quadrado = 1 menção",
        "vs_last_edition": "vs. ontem",
        "topic_header": "Tema",
        "count_header": "Nº",
        "trend_new": "novo",
        "trend_same": "igual",
        "tied_with": "empate com {name}",
        "where_to_read": "Onde ler",
        "contents_short": "Sumário",
        "section_of": "Editoria {index} de {total}",
        "section_lead": "Destaque",
        "start_reading": "Começar a ler",
        "in_this_section": "{index} de {total} nesta editoria",
        "long_read": "Leitura longa",
        "words": "palavras",
        "key_points": "Pontos-chave",
        "in_this_article": "Neste artigo",
        "part_of": "{index} de {total}",
        "original_source": "Fonte original",
        "back_to_top": "Voltar ao início da matéria",
        "up_next": "A seguir",
        "next": "Próxima",
        "tema_política": "política",
        "tema_saúde": "saúde",
        "tema_economia": "economia",
        "tema_tecnologia": "tecnologia",
        "tema_mundo": "mundo",
        "tema_brasil": "brasil",
        "tema_cultura": "cultura",
        "tema_esportes": "esportes",
        "tema_ciência": "ciência",
        "tema_opinião": "opinião",
        "tema_clima": "clima",
        "weekdays": (
            "segunda-feira",
            "terça-feira",
            "quarta-feira",
            "quinta-feira",
            "sexta-feira",
            "sábado",
            "domingo",
        ),
        "months": (
            "janeiro",
            "fevereiro",
            "março",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        ),
    },
    "en": {
        "digest_title": "News Digest",
        "summary": "Summary",
        "relevance_score": "Relevance score",
        "relevance": "Relevance",
        "top_stories": "Top stories by relevance",
        "score": "score",
        "articles": "articles",
        "article_of": "of",
        "read_full": "Read full article online →",
        "contents": "Contents",
        "sections_today": "Your sections for this edition.",
        "edition_overview": "In this edition",
        "also_inside": "Also inside",
        "by_section": "By section",
        "fallback_section_editorial": "{count} stories in {category} today.",
        "fallback_section_lead": "Lead:",
        "fallback_global_headline": "Today's digest",
        "fallback_global_editorial": (
            "Today's digest covers {total} stories across {sections} sections."
        ),
        "tipo_resumo": "Summary",
        "tipo_artigo_completo": "Full article",
        "story": "story",
        "stories": "stories",
        "mention": "mention",
        "mentions": "mentions",
        "lead_story": "Lead story",
        "highlights_today": "Today's highlights",
        "reading": "reading",
        "edition_number": "Edition {number}",
        "edition_topics": "Topics in this edition",
        "other_topics": "others",
        "includes_lead_story": "includes the lead story",
        "topic": "topic",
        "topics": "topics",
        "topic_of_day": "Topic of the day",
        "share_of_mentions": "{percent} of mentions",
        "most_crossed": "Most crossed",
        "story_number": "Story {number}",
        "in_topics": "in {count} topics",
        "novelty": "New today",
        "not_last_edition": "not in the last edition",
        "all_mentions": "All mentions",
        "square_legend": "1 square = 1 mention",
        "vs_last_edition": "vs. last",
        "topic_header": "Topic",
        "count_header": "No.",
        "trend_new": "new",
        "trend_same": "same",
        "tied_with": "tied with {name}",
        "where_to_read": "Where to read",
        "contents_short": "Contents",
        "section_of": "Section {index} of {total}",
        "section_lead": "Top story",
        "start_reading": "Start reading",
        "in_this_section": "{index} of {total} in this section",
        "long_read": "Long read",
        "words": "words",
        "key_points": "Key points",
        "in_this_article": "In this article",
        "part_of": "{index} of {total}",
        "original_source": "Original source",
        "back_to_top": "Back to the start of the story",
        "up_next": "Up next",
        "next": "Next",
        "tema_política": "política",
        "tema_saúde": "saúde",
        "tema_economia": "economia",
        "tema_tecnologia": "tecnologia",
        "tema_mundo": "mundo",
        "tema_brasil": "brasil",
        "tema_cultura": "cultura",
        "tema_esportes": "esportes",
        "tema_ciência": "ciência",
        "tema_opinião": "opinião",
        "tema_clima": "clima",
        "weekdays": (
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ),
        "months": (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
    },
}


def ai_language_code() -> str:
    code = (get_settings().ai_language or "pt-BR").strip()
    return code if code in LANGUAGE_LABELS else code


def ai_language_name() -> str:
    code = ai_language_code()
    return LANGUAGE_LABELS.get(code, code)


def ai_output_language_rule() -> str:
    """Append to AI prompts so generated strings use the configured language."""
    name = ai_language_name()
    code = ai_language_code()
    return (
        f" Language: write ALL user-facing string values (summary, headline, editorial, "
        f"one_liner, story, note, and any rewritten titles) in {name} ({code}). "
        "Keep JSON keys in English."
    )


def _labels() -> dict[str, str]:
    code = ai_language_code()
    if code in EPUB_LABELS:
        return EPUB_LABELS[code]
    return EPUB_LABELS["en"]


def _tema_label_key(tema: str) -> str:
    return "tema_" + tema.replace(" ", "_")


def format_tag_line(tipo: str, temas: list[str]) -> str:
    """One-line display: tipo label, then temas joined."""
    tipo_key = "tipo_artigo_completo" if tipo == "artigo-completo" else "tipo_resumo"
    parts = [epub_label(tipo_key)]
    if temas:
        tema_labels = [epub_label(_tema_label_key(t)) for t in temas]
        parts.append(", ".join(tema_labels))
    return " · ".join(parts)


def epub_label(key: str, **kwargs: str | int) -> str:
    text = _labels().get(key, EPUB_LABELS["en"].get(key, key))
    if kwargs:
        return text.format(**kwargs)
    return text


def format_digest_date(when: datetime) -> str:
    labels = _labels()
    weekday = labels["weekdays"][when.weekday()]
    month = labels["months"][when.month - 1]
    code = ai_language_code()
    if code == "pt-BR":
        return f"{weekday}, {when.day} de {month} de {when.year}"
    return when.strftime("%A, %B %d, %Y")


def format_long_date(when: datetime) -> str:
    """`8 de novembro de 2026` or `November 8, 2026`, without the weekday."""
    month = _labels()["months"][when.month - 1]
    if ai_language_code() == "pt-BR":
        return f"{when.day} de {month} de {when.year}"
    return f"{month} {when.day}, {when.year}"


def format_short_date(when: datetime) -> str:
    """`Dom · 8 nov 2026` or `Sun · Nov 8 2026`."""
    labels = _labels()
    weekday = labels["weekdays"][when.weekday()][:3].capitalize()
    month = labels["months"][when.month - 1][:3]
    if ai_language_code() == "pt-BR":
        return f"{weekday} · {when.day} {month} {when.year}"
    return f"{weekday} · {month} {when.day} {when.year}"


def format_count(count: int, singular_key: str, plural_key: str) -> str:
    """`1 matéria`, `7 matérias`."""
    return f"{count} {epub_label(singular_key if count == 1 else plural_key)}"


def format_decimal(value: float, decimals: int = 1) -> str:
    """`9,2` in pt-BR, `9.2` in English."""
    text = f"{value:.{decimals}f}"
    return text.replace(".", ",") if ai_language_code() == "pt-BR" else text


def tema_label(tema: str) -> str:
    return epub_label(_tema_label_key(tema))


def tipo_label(tipo: str) -> str:
    return epub_label("tipo_artigo_completo" if tipo == "artigo-completo" else "tipo_resumo")


def format_digest_timestamp(when: datetime) -> str:
    """Title-safe date/time for EPUB filenames and headers."""
    labels = _labels()
    month = labels["months"][when.month - 1]
    code = ai_language_code()
    if code == "pt-BR":
        return f"{when.day} {month} {when.year} {when.strftime('%H%M')}"
    return when.strftime("%B %d %Y %H%M")
