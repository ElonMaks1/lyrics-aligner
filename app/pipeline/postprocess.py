import logging
import re
from typing import Any

from rapidfuzz import fuzz

from app.config import settings
from app.pipeline.text_prep import LyricLine

logger = logging.getLogger(__name__)

WORD_RE = re.compile(r"[\wа-яёА-ЯЁ'-]+", re.UNICODE)
MATCH_THRESHOLD = 40
GAP_SPLIT_SEC = 1.4


def _extract_words(text: str) -> list[str]:
    return [m.group(0) for m in WORD_RE.finditer(text)]


def _tokenize_line(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text)]


def _distribute_words_evenly(words: list[str], start: float, end: float) -> list[dict]:
    if not words:
        return []
    start = float(start)
    end = max(float(end), start + 0.05 * len(words))
    step = (end - start) / len(words)
    out: list[dict] = []
    for i, text in enumerate(words):
        s = start + i * step
        out.append(
            {
                "text": text,
                "start": round(s, 3),
                "end": round(s + step, 3),
                "interpolated": True,
                "score_norm": 0.0,
            }
        )
    return out


def _interpolate_word_gaps(
    slots: list[dict | None],
    expected: list[str],
    line_start: float | None,
    line_end: float | None,
    min_dur: float = 0.06,
) -> list[dict]:
    n = len(expected)
    anchors = [i for i, s in enumerate(slots) if s is not None]
    if not anchors:
        if line_start is not None and line_end is not None:
            return _distribute_words_evenly(expected, line_start, line_end)
        return []

    result: list[dict | None] = list(slots)
    segments: list[tuple[int, int, float, float]] = []

    first = anchors[0]
    if first > 0:
        t_end = float(result[first]["start"])
        t_start = float(line_start) if line_start is not None else max(0.0, t_end - min_dur * first)
        segments.append((0, first, t_start, t_end))

    for a, b in zip(anchors, anchors[1:]):
        if b - a > 1:
            segments.append((a + 1, b, float(result[a]["end"]), float(result[b]["start"])))

    last = anchors[-1]
    if last < n - 1:
        t_start = float(result[last]["end"])
        t_end = float(line_end) if line_end is not None else t_start + min_dur * (n - last - 1)
        segments.append((last + 1, n, t_start, t_end))

    for i_start, i_end, t0, t1 in segments:
        count = i_end - i_start
        if count <= 0:
            continue
        gap = max(t1 - t0, min_dur * count)
        step = gap / count
        for k, i in enumerate(range(i_start, i_end)):
            result[i] = {
                "text": expected[i],
                "start": round(t0 + k * step, 3),
                "end": round(t0 + (k + 1) * step, 3),
                "interpolated": True,
                "score_norm": 0.0,
            }

    return [w for w in result if w is not None]


def fill_missing_words(lines: list[dict]) -> list[dict]:
    """Добавляет пропущенные слова из текста, интерполируя тайминги между якорями CTC."""
    for line in lines:
        if line.get("instrumental") or not line.get("text"):
            continue

        expected = _extract_words(line["text"])
        if not expected:
            continue

        existing = line.get("words") or []
        if not existing:
            if line.get("start") is not None and line.get("end") is not None:
                line["words"] = _distribute_words_evenly(expected, line["start"], line["end"])
            continue

        norm_expected = [_norm_token(t) for t in expected]
        mapping = _sequence_align_tokens(norm_expected, existing)

        slots: list[dict | None] = [None] * len(expected)
        used_existing: set[int] = set()
        for ti in range(len(expected)):
            wi = mapping.get(ti)
            if wi is None or wi in used_existing:
                continue
            used_existing.add(wi)
            slots[ti] = {
                **existing[wi],
                "text": expected[ti],
                "interpolated": False,
            }

        filled = _interpolate_word_gaps(slots, expected, line.get("start"), line.get("end"))
        if filled:
            line["words"] = filled
            pad = settings.line_padding_ms / 1000.0
            line["start"] = round(max(0.0, filled[0]["start"] - pad * 0.25), 3)
            line["end"] = round(filled[-1]["end"] + pad * 0.25, 3)

    return lines


def _norm_token(token: str) -> str:
    return token.lower().replace("ё", "е")


def _match_score(a: str, b: str) -> int:
    return fuzz.ratio(_norm_token(a), _norm_token(b))


def _word_is_reliable(score: float | None) -> bool:
    if score is None:
        return True
    if score <= 1.0:
        return score >= settings.min_word_log_score
    return score >= settings.min_word_confidence


def _normalize_score(score: float | None) -> float:
    if score is None:
        return 0.0
    if score <= 1.0:
        import math

        return max(0.0, min(1.0, math.exp(score)))
    return float(score)


def smooth_word_boundaries(words: list[dict]) -> list[dict]:
    if not words:
        return words

    sorted_words = sorted(words, key=lambda w: w["start"])
    for i in range(len(sorted_words) - 1):
        if sorted_words[i]["end"] > sorted_words[i + 1]["start"]:
            mid = (sorted_words[i]["start"] + sorted_words[i + 1]["start"]) / 2
            sorted_words[i]["end"] = mid
            sorted_words[i + 1]["start"] = mid
        elif sorted_words[i]["end"] < sorted_words[i]["start"]:
            sorted_words[i]["end"] = sorted_words[i]["start"] + 0.05

    pad = settings.line_padding_ms / 1000.0
    for w in sorted_words:
        w["start"] = max(0.0, w["start"] - pad * 0.25)
        w["end"] = w["end"] + pad * 0.25

    return sorted_words


def _line_dict(line: LyricLine, start, end, words: list[dict]) -> dict:
    return {
        "text": line.text,
        "raw": line.raw,
        "section": line.section,
        "instrumental": False,
        "start": start,
        "end": end,
        "words": words,
    }


def _sequence_align_tokens(tokens: list[str], usable: list[dict]) -> dict[int, int]:
    """DP: индекс токена текста -> индекс слова CTC."""
    n, m = len(tokens), len(usable)
    if n == 0:
        return {}

    inf = 1e9
    dp = [[inf] * (m + 1) for _ in range(n + 1)]
    parent: list[list[tuple[int, int, str] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0

    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] >= inf:
                continue
            if i < n:
                c = dp[i][j] + 2.0
                if c < dp[i + 1][j]:
                    dp[i + 1][j] = c
                    parent[i + 1][j] = (i, j, "skip_t")
            if j < m:
                c = dp[i][j] + 1.0
                if c < dp[i][j + 1]:
                    dp[i][j + 1] = c
                    parent[i][j + 1] = (i, j, "skip_w")
            if i < n and j < m:
                sc = _match_score(tokens[i], usable[j]["text"])
                c = dp[i][j] + max(0.0, (85 - sc) / 18.0)
                if c < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = c
                    parent[i + 1][j + 1] = (i, j, "match")

    token_to_word: dict[int, int] = {}
    i, j = n, m
    while i > 0 or j > 0:
        p = parent[i][j]
        if p is None:
            break
        pi, pj, op = p
        if op == "match":
            token_to_word[i - 1] = j - 1
        i, j = pi, pj

    return token_to_word


def assign_words_to_lines(
    lyric_lines: list[LyricLine],
    aligned_words: list[dict],
) -> tuple[list[dict], list[dict]]:
    smoothed = smooth_word_boundaries(aligned_words)
    for w in smoothed:
        w["score_norm"] = _normalize_score(w.get("score"))

    usable = smoothed
    low_conf = [w for w in smoothed if not _word_is_reliable(w.get("score"))]

    all_tokens: list[str] = []
    line_token_spans: list[tuple[int, int]] = []
    for line in lyric_lines:
        if line.is_instrumental:
            line_token_spans.append((len(all_tokens), len(all_tokens)))
            continue
        toks = _tokenize_line(line.text)
        start = len(all_tokens)
        all_tokens.extend(toks)
        line_token_spans.append((start, len(all_tokens)))

    token_to_word = _sequence_align_tokens(all_tokens, usable)

    result_lines: list[dict] = []
    used_words: set[int] = set()

    for line, (t0, t1) in zip(lyric_lines, line_token_spans):
        if line.is_instrumental:
            result_lines.append(
                {
                    "text": line.raw,
                    "raw": line.raw,
                    "section": line.section,
                    "instrumental": True,
                    "start": None,
                    "end": None,
                    "words": [],
                }
            )
            continue

        line_words: list[dict] = []
        for ti in range(t0, t1):
            wi = token_to_word.get(ti)
            if wi is None or wi in used_words:
                continue
            used_words.add(wi)
            picked = dict(usable[wi])
            picked["text"] = all_tokens[ti]
            line_words.append(picked)

        if line_words:
            pad = settings.line_padding_ms / 1000.0
            result_lines.append(
                _line_dict(
                    line,
                    max(0.0, line_words[0]["start"] - pad),
                    line_words[-1]["end"] + pad,
                    line_words,
                )
            )
        else:
            result_lines.append(_line_dict(line, None, None, []))

    return result_lines, low_conf


def proportional_stream_assign(
    lyric_lines: list[LyricLine],
    usable: list[dict],
) -> list[dict]:
    """Раздать поток слов CTC по строкам пропорционально длине текста (fallback)."""
    usable = sorted(usable, key=lambda w: w["start"])
    lyric_only = [l for l in lyric_lines if not l.is_instrumental]
    counts = [max(1, len(_tokenize_line(l.text))) for l in lyric_only]
    total = sum(counts)
    if not usable or total == 0:
        return []

    cursor = 0
    out: list[dict] = []
    pad = settings.line_padding_ms / 1000.0

    for line, n_tok in zip(lyric_only, counts):
        n_words = max(1, round(len(usable) * n_tok / total))
        chunk = usable[cursor : cursor + n_words]
        cursor = min(cursor + n_words, len(usable))
        if not chunk:
            out.append(_line_dict(line, None, None, []))
            continue
        toks = _tokenize_line(line.text)
        words = [{**w, "text": toks[k] if k < len(toks) else w["text"]} for k, w in enumerate(chunk)]
        out.append(
            _line_dict(
                line,
                max(0.0, words[0]["start"] - pad),
                words[-1]["end"] + pad,
                words,
            )
        )
    return out


def recover_low_coverage(
    lyric_lines: list[LyricLine],
    lines: list[dict],
    aligned_words: list[dict],
) -> list[dict]:
    """Если матчинг слабый — line-level по потоку CTC + интерполяция."""
    usable = smooth_word_boundaries(aligned_words)
    lyric_only_idx = [i for i, l in enumerate(lyric_lines) if not l.is_instrumental]
    if not lyric_only_idx:
        return lines

    total_expected = sum(len(_tokenize_line(lyric_lines[i].text)) for i in lyric_only_idx)
    total_matched = sum(
        len(lines[i].get("words") or []) for i in lyric_only_idx if i < len(lines)
    )
    ratio = total_matched / max(total_expected, 1)
    if ratio >= 0.55:
        return lines

    logger.info(
        "recover_low_coverage: matched %.1f%% — proportional stream fallback",
        ratio * 100,
    )
    recovered = proportional_stream_assign(
        [lyric_lines[i] for i in lyric_only_idx],
        usable,
    )
    out = list(lines)
    for idx, rec in zip(lyric_only_idx, recovered):
        if idx < len(out):
            out[idx] = {**rec, "recovered": True}
    return out


def interpolate_missing_lines(lines: list[dict]) -> list[dict]:
    timed = [i for i, l in enumerate(lines) if l.get("start") is not None and not l.get("instrumental")]
    if len(timed) < 1:
        return lines

    for i in range(len(lines)):
        if lines[i].get("start") is not None or lines[i].get("instrumental"):
            continue

        prev_idx = max((t for t in timed if t < i), default=None)
        next_idx = min((t for t in timed if t > i), default=None)
        if prev_idx is None and next_idx is not None:
            lines[i]["start"] = max(0.0, lines[next_idx]["start"] - 2.0)
            lines[i]["end"] = lines[next_idx]["start"] - 0.05
            continue
        if next_idx is None and prev_idx is not None:
            lines[i]["start"] = lines[prev_idx]["end"] + 0.05
            lines[i]["end"] = lines[prev_idx]["end"] + 2.0
            continue
        if prev_idx is None or next_idx is None:
            continue

        prev_end = lines[prev_idx]["end"]
        next_start = lines[next_idx]["start"]
        gap = next_start - prev_end
        missing = [j for j in range(prev_idx + 1, next_idx) if lines[j].get("start") is None]
        if not missing or gap <= 0:
            continue

        weights = [max(1, len(_tokenize_line(lines[j]["text"]))) for j in missing]
        wsum = sum(weights)
        pos = prev_end
        for j, w in zip(missing, weights):
            dur = gap * w / wsum
            lines[j]["start"] = round(pos, 3)
            lines[j]["end"] = round(pos + dur, 3)
            pos += dur

    return lines


def compute_quality(lines: list[dict], aligned_words: list[dict], low_conf: list[dict]) -> dict[str, Any]:
    lyric_lines = [l for l in lines if not l.get("instrumental")]
    total_tokens = sum(len(_tokenize_line(l["text"])) for l in lyric_lines)
    aligned_tokens = sum(len(l.get("words") or []) for l in lyric_lines)
    interpolated = sum(
        1
        for l in lyric_lines
        for w in (l.get("words") or [])
        if w.get("interpolated")
    )
    matched = aligned_tokens - interpolated
    line_coverage = sum(1 for l in lyric_lines if l.get("start") is not None) / max(len(lyric_lines), 1)

    scores = [_normalize_score(w.get("score")) for w in aligned_words if w.get("score") is not None]
    avg_conf = sum(scores) / len(scores) if scores else 0.0
    word_coverage = aligned_tokens / max(total_tokens, 1)
    recovered = sum(1 for l in lines if l.get("recovered"))

    return {
        "coverage": round(word_coverage, 4),
        "line_coverage": round(line_coverage, 4),
        "average_confidence": round(avg_conf, 4),
        "percent_aligned_words": round(word_coverage * 100, 2),
        "total_words_expected": total_tokens,
        "total_words_aligned": aligned_tokens,
        "words_from_ctc": matched,
        "words_interpolated": interpolated,
        "low_confidence_dropped": len(low_conf),
        "lines_recovered": recovered,
        "degraded_to_line_level": word_coverage < settings.target_coverage,
    }
