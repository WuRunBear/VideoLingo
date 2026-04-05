import json
import os
from typing import Any

import pandas as pd
from core.utils.config_utils import get_joiner


def _iter_json3_token_events(data: dict[str, Any]):
    events = data.get("events", [])
    for event in events:
        if not isinstance(event, dict):
            continue
        if "segs" not in event or "tStartMs" not in event or "dDurationMs" not in event:
            continue
        segs = event.get("segs")
        if not isinstance(segs, list) or len(segs) == 0:
            continue
        yield event


def parse_youtube_json3_to_words(json3_path: str, max_end_seconds: float | None = None) -> pd.DataFrame:
    if not os.path.exists(json3_path):
        raise FileNotFoundError(json3_path)

    with open(json3_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    valid_events = list(_iter_json3_token_events(data))

    words: list[dict[str, Any]] = []
    for idx, event in enumerate(valid_events):
        start_ms = int(event.get("tStartMs", 0) or 0)
        dur_ms = int(event.get("dDurationMs", 0) or 0)
        event_end_ms = start_ms + max(0, dur_ms)
        next_event_start_ms = (
            int(valid_events[idx + 1].get("tStartMs", event_end_ms) or event_end_ms)
            if idx + 1 < len(valid_events)
            else event_end_ms
        )
        segs = event.get("segs", [])

        token_times_ms: list[int] = []
        token_texts: list[str] = []
        for seg in segs:
            if not isinstance(seg, dict):
                continue
            text = str(seg.get("utf8", ""))
            if text == "\n":
                continue
            text = text.strip()
            if not text:
                continue
            offset_ms = int(seg.get("tOffsetMs", 0) or 0)
            token_times_ms.append(start_ms + max(0, offset_ms))
            token_texts.append(text)

        if not token_texts:
            continue

        for i, text in enumerate(token_texts):
            token_start_ms = token_times_ms[i]
            next_start_ms = (
                token_times_ms[i + 1]
                if i + 1 < len(token_times_ms)
                else min(event_end_ms, next_event_start_ms)
            )
            delta_ms = next_start_ms - token_start_ms
            if delta_ms > 0:
                token_end_ms = token_start_ms + max(1, int(delta_ms * 0.9))
                if token_end_ms >= next_start_ms:
                    token_end_ms = next_start_ms - 1
                if token_end_ms < token_start_ms:
                    token_end_ms = token_start_ms
            else:
                token_end_ms = token_start_ms
            if token_end_ms < token_start_ms:
                token_end_ms = token_start_ms

            words.append(
                {
                    "text": text,
                    "start": token_start_ms / 1000.0,
                    "end": token_end_ms / 1000.0,
                    "speaker_id": None,
                }
            )

    if not words:
        return pd.DataFrame(columns=["text", "start", "end", "speaker_id"])

    df = pd.DataFrame(words)
    df["text"] = df["text"].astype(str)
    df["start"] = pd.to_numeric(df["start"], errors="coerce")
    df["end"] = pd.to_numeric(df["end"], errors="coerce")
    df = df.dropna(subset=["start", "end"])
    if max_end_seconds is not None:
        try:
            max_end_seconds = float(max_end_seconds)
        except Exception:
            max_end_seconds = None
    if max_end_seconds is not None and max_end_seconds > 0:
        df["start"] = df["start"].clip(lower=0.0, upper=max_end_seconds)
        df["end"] = df["end"].clip(lower=0.0, upper=max_end_seconds)
    df = df[df["text"].str.len() > 0]
    df = df[df["end"] >= df["start"]]
    df = df.sort_values(["start", "end"]).reset_index(drop=True)
    return df


def parse_youtube_json3_to_event_sentences(json3_path: str, language: str) -> list[str]:
    if not os.path.exists(json3_path):
        raise FileNotFoundError(json3_path)

    with open(json3_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    joiner = get_joiner(language)

    sentences: list[str] = []
    for event in _iter_json3_token_events(data):
        segs = event.get("segs", [])
        raw = "".join(str(seg.get("utf8", "")) for seg in segs if isinstance(seg, dict))
        raw = raw.replace("\n", "")

        if joiner == " ":
            text = " ".join(raw.split()).strip()
        else:
            text = raw.strip()

        if not text:
            continue
        sentences.append(text)

    return sentences


def find_youtube_json3(save_path: str, preferred_lang: str | None = None) -> str:
    if not os.path.exists(save_path):
        raise FileNotFoundError(save_path)

    candidates = [f for f in os.listdir(save_path) if f.lower().endswith(".json3")]
    if not candidates:
        raise FileNotFoundError("No .json3 subtitles found in static/output")

    preferred_lang = (preferred_lang or "").strip().lower()
    if preferred_lang:
        exact = [f for f in candidates if f.lower().endswith(f".{preferred_lang}.json3")]
        if exact:
            exact.sort(key=lambda x: os.path.getmtime(os.path.join(save_path, x)), reverse=True)
            return os.path.join(save_path, exact[0])

        contains = [f for f in candidates if f".{preferred_lang}." in f.lower()]
        if contains:
            contains.sort(key=lambda x: os.path.getmtime(os.path.join(save_path, x)), reverse=True)
            return os.path.join(save_path, contains[0])

    candidates.sort(key=lambda x: os.path.getmtime(os.path.join(save_path, x)), reverse=True)
    return os.path.join(save_path, candidates[0])

