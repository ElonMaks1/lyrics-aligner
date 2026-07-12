from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

LRC_RE = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)$")
SRT_TIME_RE = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def _lrc_to_sec(m: int, s: float) -> float:
    return m * 60 + float(s)


def _srt_ts_to_sec(h: int, m: int, s: int, ms: int) -> float:
    return h * 3600 + m * 60 + s + ms / 1000.0


def parse_lrc(text: str) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for raw in text.splitlines():
        m = LRC_RE.match(raw.strip())
        if not m:
            continue
        start = _lrc_to_sec(int(m.group(1)), float(m.group(2)))
        lyric = m.group(3).strip()
        if not lyric:
            continue
        lines.append({"text": lyric, "start": start, "end": None})
    for i in range(len(lines)):
        if lines[i]["end"] is None:
            if i + 1 < len(lines):
                lines[i]["end"] = lines[i + 1]["start"]
            else:
                lines[i]["end"] = lines[i]["start"] + 4.0
    return lines


def parse_srt(text: str) -> list[dict[str, Any]]:
    blocks = re.split(r"\n\s*\n", text.strip())
    out: list[dict[str, Any]] = []
    for block in blocks:
        parts = [p.strip() for p in block.splitlines() if p.strip()]
        if len(parts) < 2:
            continue
        if parts[0].isdigit():
            parts = parts[1:]
        if not parts or "-->" not in parts[0]:
            continue
        t0, t1 = [x.strip() for x in parts[0].split("-->")]
        m0 = SRT_TIME_RE.match(t0)
        m1 = SRT_TIME_RE.match(t1)
        if not m0 or not m1:
            continue
        start = _srt_ts_to_sec(*(int(x) for x in m0.groups()))
        end = _srt_ts_to_sec(*(int(x) for x in m1.groups()))
        text_line = " ".join(parts[1:])
        if text_line:
            out.append({"text": text_line, "start": start, "end": end})
    return out


def parse_json_timings(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and "lines" in data:
        items = data["lines"]
    elif isinstance(data, list):
        items = data
    else:
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("start") is None:
            continue
        out.append(
            {
                "text": str(item.get("text", "")),
                "start": float(item["start"]),
                "end": float(item.get("end") or item["start"] + 2),
            }
        )
    return out


def parse_timing_content(text: str, suffix: str) -> list[dict[str, Any]]:
    suf = suffix.lower()
    if suf == ".json":
        return parse_json_timings(json.loads(text))
    if suf == ".lrc":
        return parse_lrc(text)
    if suf == ".srt":
        return parse_srt(text)
    if suf == ".vtt":
        return parse_srt(text.replace(".", ","))
    raise ValueError(f"Unsupported format: {suf}")


def parse_timing_file(path: Path) -> list[dict[str, Any]]:
    return parse_timing_content(path.read_text(encoding="utf-8"), path.suffix)
