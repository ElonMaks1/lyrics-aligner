from __future__ import annotations

import re

from ctc_forced_aligner.text_utils import get_uroman_tokens, text_normalize

CYRILLIC_RE = re.compile(r"[а-яёА-ЯЁ]")
LATIN_RE = re.compile(r"[a-zA-ZÀ-ÿ]")


def detect_token_lang(token: str, primary_iso3: str = "rus") -> str:
    has_cyr = bool(CYRILLIC_RE.search(token))
    has_lat = bool(LATIN_RE.search(token))
    if has_cyr and not has_lat:
        return "rus"
    if has_lat and not has_cyr:
        return "eng"
    return primary_iso3


def preprocess_text_mixed(
    text: str,
    primary_iso3: str = "rus",
    star_frequency: str = "segment",
) -> tuple[list, list]:
    words = [w for w in text.split() if w.strip()]
    if not words:
        return ["<star>"], ["<star>"]

    tokens: list[str] = []
    kept_words: list[str] = []

    for word in words:
        iso = detect_token_lang(word, primary_iso3)
        norm = text_normalize(word.strip(), iso)
        if not norm:
            continue
        tokens.append(get_uroman_tokens([norm], iso)[0])
        kept_words.append(word)

    if not tokens:
        return ["<star>"], ["<star>"]

    if star_frequency == "segment":
        tokens_starred: list[str] = []
        text_starred: list[str] = []
        for token, word in zip(tokens, kept_words):
            tokens_starred.extend(["<star>", token])
            text_starred.extend(["<star>", word])
        return tokens_starred, text_starred

    return ["<star>"] + tokens + ["<star>"], ["<star>"] + kept_words + ["<star>"]
