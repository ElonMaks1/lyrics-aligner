import json
from pathlib import Path
from typing import Any


def _fmt_lrc_time(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"[{m:02d}:{s:05.2f}]"


def to_lrc(result: dict[str, Any], enhanced: bool = True) -> str:
    chunks: list[str] = []
    for line in result.get("lines", []):
        if line.get("start") is None:
            continue
        chunks.append(f"{_fmt_lrc_time(line['start'])}{line['text']}")
        if enhanced:
            for word in line.get("words") or []:
                chunks.append(f"{_fmt_lrc_time(word['start'])}{word['text']}")
    return "\n".join(chunks) + ("\n" if chunks else "")


def _fmt_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(result: dict[str, Any]) -> str:
    blocks: list[str] = []
    idx = 1
    for line in result.get("lines", []):
        if line.get("start") is None or line.get("end") is None:
            continue
        blocks.append(
            "\n".join(
                [
                    str(idx),
                    f"{_fmt_srt_time(line['start'])} --> {_fmt_srt_time(line['end'])}",
                    line["text"],
                    "",
                ]
            )
        )
        idx += 1
    return "\n".join(blocks)


def to_vtt(result: dict[str, Any]) -> str:
    body = to_srt(result).replace(",", ".")
    lines = ["WEBVTT", ""]
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        parts = block.split("\n")
        if len(parts) >= 3 and parts[0].isdigit():
            lines.append(parts[1])
            lines.extend(parts[2:])
            lines.append("")
    return "\n".join(lines)


def to_lines_json(result: dict[str, Any], title: str = "") -> dict[str, Any]:
    lines = []
    for line in result.get("lines", []):
        if line.get("start") is None:
            continue
        lines.append(
            {
                "text": line.get("text", ""),
                "start": round(float(line["start"]), 3),
                "end": round(float(line["end"]), 3),
            }
        )
    return {
        "title": title,
        "lines": lines,
    }


def export_all(result: dict[str, Any], job_dir: Path, lines_only: bool = False) -> None:
    if lines_only:
        title = result.get("meta", {}).get("audio", "")
        payload = to_lines_json(result, title=title)
        (job_dir / "lines.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (job_dir / "lyrics.lrc").write_text(to_lrc(result, enhanced=False), encoding="utf-8")
        (job_dir / "lyrics.srt").write_text(to_srt(result), encoding="utf-8")
        (job_dir / "lyrics.vtt").write_text(to_vtt(result), encoding="utf-8")
    else:
        (job_dir / "lyrics.lrc").write_text(to_lrc(result, enhanced=False), encoding="utf-8")
        (job_dir / "lyrics.enhanced.lrc").write_text(to_lrc(result, enhanced=True), encoding="utf-8")
        (job_dir / "lyrics.srt").write_text(to_srt(result), encoding="utf-8")
        (job_dir / "lyrics.vtt").write_text(to_vtt(result), encoding="utf-8")
        title = result.get("meta", {}).get("audio", "")
        (job_dir / "lines.json").write_text(
            json.dumps(to_lines_json(result, title), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    (job_dir / "quality.json").write_text(
        json.dumps(result.get("quality", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def to_words_json(result: dict[str, Any], title: str = "") -> dict[str, Any]:
    lines_out: list[dict[str, Any]] = []
    for line in result.get("lines", []):
        if line.get("start") is None:
            continue
        words: list[dict[str, Any]] = []
        for word in line.get("words") or []:
            if word.get("start") is None:
                continue
            words.append(
                {
                    "text": word.get("text", ""),
                    "start": round(float(word["start"]), 3),
                    "end": round(float(word["end"]), 3),
                }
            )
        lines_out.append(
            {
                "text": line.get("text", ""),
                "start": round(float(line["start"]), 3),
                "end": round(float(line["end"]), 3),
                "words": words,
            }
        )
    return {"title": title, "lines": lines_out}


def export_words_json(result: dict[str, Any], out_path: Path, title: str = "") -> Path:
    payload = to_words_json(result, title=title or result.get("meta", {}).get("audio", ""))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def export_lines_json(result: dict[str, Any], out_dir: Path, base_name: str) -> Path:
    """Один .lines.json с таймкодами строк (пакетная выгрузка)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = to_lines_json(result, title=base_name)
    path = out_dir / f"{base_name}.lines.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_lines_only(result: dict[str, Any], out_dir: Path, base_name: str) -> None:
    """Таймкоды строк + .lrc/.srt (веб-задачи и ручной экспорт)."""
    export_lines_json(result, out_dir, base_name)
    (out_dir / f"{base_name}.lrc").write_text(to_lrc(result, enhanced=False), encoding="utf-8")
    (out_dir / f"{base_name}.srt").write_text(to_srt(result), encoding="utf-8")
