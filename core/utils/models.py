# ------------------------------------------
# 定义中间产出文件
# ------------------------------------------

_2_CLEANED_CHUNKS = "static/output/log/cleaned_chunks.xlsx"
_3_1_SPLIT_BY_NLP = "static/output/log/split_by_nlp.txt"
_3_2_SPLIT_BY_MEANING = "static/output/log/split_by_meaning.txt"
_4_1_TERMINOLOGY = "static/output/log/terminology.json"
_4_2_TRANSLATION = "static/output/log/translation_results.xlsx"
_5_SPLIT_SUB = "static/output/log/translation_results_for_subtitles.xlsx"
_5_REMERGED = "static/output/log/translation_results_remerged.xlsx"

_8_1_AUDIO_TASK = "static/output/audio/tts_tasks.xlsx"


# ------------------------------------------
# 定义音频文件
# ------------------------------------------
_OUTPUT_DIR = "static/output"
_AUDIO_DIR = "static/output/audio"
_RAW_AUDIO_FILE = "static/output/audio/raw.mp3"
_SEPARATION_AUDIO_FILE = "static/output/audio/raw_hq.wav"
_VOCAL_AUDIO_FILE = "static/output/audio/vocal.mp3"
_BACKGROUND_AUDIO_FILE = "static/output/audio/background.mp3"
_AUDIO_REFERS_DIR = "static/output/audio/refers"
_AUDIO_SEGS_DIR = "static/output/audio/segs"
_AUDIO_TMP_DIR = "static/output/audio/tmp"

# ------------------------------------------
# 导出
# ------------------------------------------

__all__ = [
    "_2_CLEANED_CHUNKS",
    "_3_1_SPLIT_BY_NLP",
    "_3_2_SPLIT_BY_MEANING",
    "_4_1_TERMINOLOGY",
    "_4_2_TRANSLATION",
    "_5_SPLIT_SUB",
    "_5_REMERGED",
    "_8_1_AUDIO_TASK",
    "_OUTPUT_DIR",
    "_AUDIO_DIR",
    "_RAW_AUDIO_FILE",
    "_SEPARATION_AUDIO_FILE",
    "_VOCAL_AUDIO_FILE",
    "_BACKGROUND_AUDIO_FILE",
    "_AUDIO_REFERS_DIR",
    "_AUDIO_SEGS_DIR",
    "_AUDIO_TMP_DIR"
]
