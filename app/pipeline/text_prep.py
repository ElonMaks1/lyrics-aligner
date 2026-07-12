from __future__ import annotations

import re
from dataclasses import dataclass

SECTION_RE = re.compile(r"^\[[^\]]+\]\s*$")
PAREN_ONLY_RE = re.compile(r"^\([^)]*\)\s*$")
ADLIB_RE = re.compile(r"\([^)]*\)")
SONG_TEXT_TAG_RE = re.compile(r"\[Текст песни[^\]]*\]", re.IGNORECASE)
GENIUS_PREFACE_RE = re.compile(r"Contributors|Read\s+More|\bLyrics\b", re.IGNORECASE)


def _is_preface_line(line: str) -> bool:
    """Строка из Genius-предисловия (до первого реального куплета/припева)."""
    stripped = line.strip()
    if not stripped:
        return True
    if re.match(r"^\[Текст песни[^\]]*\]\s*$", stripped, re.IGNORECASE):
        return True
    if GENIUS_PREFACE_RE.search(stripped):
        return True
    remainder = SONG_TEXT_TAG_RE.sub("", stripped).strip()
    if not remainder:
        return True
    if SONG_TEXT_TAG_RE.search(stripped) and not SECTION_RE.match(remainder):
        return True
    return False


def strip_lyrics_preface(raw: str) -> str:
    """Убирает предисловие Genius до текста песни ([Текст песни ...] не считается началом)."""
    lines = raw.splitlines()
    for i, line in enumerate(lines):
        if not _is_preface_line(line):
            return "\n".join(lines[i:]).strip("\n")
    return raw.strip()


@dataclass
class LyricLine:
    text: str
    raw: str
    section: str | None = None
    is_instrumental: bool = False


def _strip_adlibs(text: str) -> str:
    cleaned = ADLIB_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def parse_lyrics(raw: str) -> tuple[list[LyricLine], str]:
    raw = strip_lyrics_preface(raw)
    lines: list[LyricLine] = []
    current_section: str | None = None
    align_parts: list[str] = []

    for raw_line in raw.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue

        if SECTION_RE.match(stripped):
            current_section = stripped
            if re.search(r"соло|solo|instrumental", stripped, re.I):
                lines.append(
                    LyricLine(
                        text="",
                        raw=stripped,
                        section=current_section,
                        is_instrumental=True,
                    )
                )
            continue

        if PAREN_ONLY_RE.match(stripped):
            continue

        clean = _strip_adlibs(stripped)
        if not clean:
            continue

        lines.append(
            LyricLine(text=clean, raw=stripped, section=current_section, is_instrumental=False)
        )
        align_parts.append(clean)

    align_text = " ".join(align_parts)
    return lines, align_text


def language_to_iso3(lang: str) -> str:
    mapping = {
        "ru": "rus",
        "rus": "rus",
        "russian": "rus",
        "en": "eng",
        "eng": "eng",
        "english": "eng",
        "mixed": "mixed",
        "ru-en": "mixed",
        "ru_en": "mixed",
        "multi": "mixed",
    }
    return mapping.get(lang.lower().strip(), "rus")


def is_mixed_language(lang: str) -> bool:
    return language_to_iso3(lang) == "mixed"


def primary_iso3_for_mixed(lang: str) -> str:
    """Базовый язык для цифр и неопределённых токенов в mixed-режиме."""
    key = lang.lower().strip()
    if key in ("mixed-en", "en-mixed", "en"):
        return "eng"
    return "rus"
