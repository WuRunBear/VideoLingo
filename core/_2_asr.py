import os

from core.utils import *
from core.asr_backend.demucs_vl import demucs_audio
from core.asr_backend.audio_preprocess import process_transcription, convert_video_to_audio, split_audio, save_results, normalize_audio_volume
from core._1_ytdlp import find_video_files
from core.utils.models import *

@check_file_exists(_2_CLEANED_CHUNKS)
def transcribe():
    # 1. video to audio
    video_file = find_video_files()
    convert_video_to_audio(video_file)

    # 2. Demucs vocal separation:
    if load_key("demucs"):
        demucs_audio()
        vocal_audio = normalize_audio_volume(_VOCAL_AUDIO_FILE, _VOCAL_AUDIO_FILE, format="mp3")
    else:
        vocal_audio = _RAW_AUDIO_FILE

    all_results = []
    runtime = load_key("whisper.runtime")
    if runtime == "youtube":
        from core.asr_backend.youtube_json3 import (
            find_youtube_json3,
            parse_youtube_json3_to_event_sentences,
            parse_youtube_json3_to_words,
        )
        preferred_lang = load_key("whisper.language")
        json3_path = find_youtube_json3("static/output", preferred_lang=preferred_lang)
        rprint(f"[cyan]📝 Using YouTube subtitles (json3) to build cleaned_chunks:[/cyan] {json3_path}")
        df = parse_youtube_json3_to_words(json3_path)
        save_results(df)
        try:
            youtube_sentence_split = load_key("whisper.youtube_sentence_split")
        except KeyError:
            youtube_sentence_split = "nlp"

        if str(youtube_sentence_split).strip().lower() == "events":
            language = load_key("whisper.detected_language") if preferred_lang == "auto" else preferred_lang
            sentences = parse_youtube_json3_to_event_sentences(json3_path, language=language)
            os.makedirs(os.path.dirname(_3_1_SPLIT_BY_NLP), exist_ok=True)
            with open(_3_1_SPLIT_BY_NLP, "w", encoding="utf-8") as f:
                f.write("\n".join(sentences))
        return

    # 3. Extract audio
    segments = split_audio(_RAW_AUDIO_FILE)
    
    # 4. Transcribe audio by clips
    if runtime == "local":
        from core.asr_backend.whisperX_local import transcribe_audio as ts
        rprint("[cyan]🎤 Transcribing audio with local model...[/cyan]")
    elif runtime == "cloud":
        from core.asr_backend.whisperX_302 import transcribe_audio_302 as ts
        rprint("[cyan]🎤 Transcribing audio with 302 API...[/cyan]")
    elif runtime == "elevenlabs":
        from core.asr_backend.elevenlabs_asr import transcribe_audio_elevenlabs as ts
        rprint("[cyan]🎤 Transcribing audio with ElevenLabs API...[/cyan]")
    else:
        raise ValueError(f"Invalid whisper.runtime: {runtime}")

    for start, end in segments:
        result = ts(_RAW_AUDIO_FILE, vocal_audio, start, end)
        all_results.append(result)
    
    # 5. Combine results
    combined_result = {'segments': []}
    for result in all_results:
        combined_result['segments'].extend(result['segments'])
    
    # 6. Process df
    df = process_transcription(combined_result)
    save_results(df)
        
if __name__ == "__main__":
    transcribe()
