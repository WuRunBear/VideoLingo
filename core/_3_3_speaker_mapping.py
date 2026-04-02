import os
import pandas as pd

from core._6_gen_sub import get_sentence_timestamps
from core.utils import check_file_exists
from core.utils.models import _2_CLEANED_CHUNKS, _3_2_SPLIT_BY_MEANING

SPEAKER_MAPPING_DRAFT = "static/output/log/speaker_mapping_draft.xlsx"
SPEAKER_MAPPING_LOCKED = "static/output/log/speaker_mapping_locked.xlsx"


def _seconds_to_hmsms(seconds: float) -> str:
    if pd.isna(seconds):
        return ""
    seconds = float(seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    milliseconds = int(round((secs - int(secs)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{int(secs):02d}.{milliseconds:03d}"


def _read_split_by_meaning_lines() -> list[str]:
    if not os.path.exists(_3_2_SPLIT_BY_MEANING):
        raise FileNotFoundError(f"Missing file: {_3_2_SPLIT_BY_MEANING}")
    with open(_3_2_SPLIT_BY_MEANING, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.read().splitlines()]
    return [line for line in lines if line]


@check_file_exists(SPEAKER_MAPPING_DRAFT)
def generate_speaker_mapping_draft() -> pd.DataFrame:
    df_words = pd.read_excel(_2_CLEANED_CHUNKS)
    df_words["text"] = df_words["text"].astype(str).str.strip('"').str.strip()

    sentences = _read_split_by_meaning_lines()
    df_sentences = pd.DataFrame({"Source": sentences})

    timestamps, speakers = get_sentence_timestamps(df_words, df_sentences)
    df = df_sentences.copy()
    df.insert(0, "line_id", range(1, len(df) + 1))
    df["start"] = [ts[0] for ts in timestamps]
    df["end"] = [ts[1] for ts in timestamps]
    df["start_time"] = df["start"].apply(_seconds_to_hmsms)
    df["end_time"] = df["end"].apply(_seconds_to_hmsms)
    df["speaker_id"] = speakers
    df["ref_audio_id"] = df["line_id"]

    os.makedirs(os.path.dirname(SPEAKER_MAPPING_DRAFT), exist_ok=True)
    df.to_excel(SPEAKER_MAPPING_DRAFT, index=False)
    return df


def lock_speaker_mapping() -> pd.DataFrame:
    if not os.path.exists(SPEAKER_MAPPING_DRAFT):
        raise FileNotFoundError(f"Missing file: {SPEAKER_MAPPING_DRAFT}")

    df = pd.read_excel(SPEAKER_MAPPING_DRAFT)
    if "Source" not in df.columns:
        raise ValueError("speaker_mapping_draft.xlsx 缺少必要列：Source")

    df["Source"] = df["Source"].astype(str).str.strip()
    df = df[df["Source"].str.len() > 0].copy()

    if "line_id" not in df.columns:
        df.insert(0, "line_id", range(1, len(df) + 1))

    df["line_id"] = df["line_id"].astype(int)
    if "ref_audio_id" not in df.columns:
        df["ref_audio_id"] = df["line_id"]

    if "start" in df.columns and "end" in df.columns:
        df["start"] = pd.to_numeric(df["start"], errors="coerce")
        df["end"] = pd.to_numeric(df["end"], errors="coerce")
        bad_time = df[df["start"].isna() | df["end"].isna()]
        if not bad_time.empty:
            raise ValueError(f"speaker_mapping_draft.xlsx 存在无法解析的 start/end（行数：{len(bad_time)}）")
        bad_order = df[df["end"] <= df["start"]]
        if not bad_order.empty:
            raise ValueError(f"speaker_mapping_draft.xlsx 存在 end<=start（行数：{len(bad_order)}）")
        if (df["start"].diff().fillna(0) < -1e-6).any():
            raise ValueError("speaker_mapping_draft.xlsx 的 start 非单调递增，请按视频时间顺序重新排列行")
    df = df.sort_values("line_id").reset_index(drop=True)
    df.to_excel(SPEAKER_MAPPING_LOCKED, index=False)

    with open(_3_2_SPLIT_BY_MEANING, "w", encoding="utf-8") as f:
        f.write("\n".join(df["Source"].tolist()))
        f.write("\n".join(df["Source"].tolist()))

    return df
