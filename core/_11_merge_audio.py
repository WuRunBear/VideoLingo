import os
import pandas as pd
import numpy as np
import subprocess
from pydub import AudioSegment
from typing import Optional
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.console import Console
from core.utils import *
from core.utils.models import *
console = Console()

DUB_VOCAL_FILE = 'static/output/dub.mp3'

DUB_SUB_FILE = 'static/output/dub.srt'
OUTPUT_FILE_TEMPLATE = f"{_AUDIO_SEGS_DIR}/{{}}.wav"

def load_and_flatten_data(excel_file):
    """Load and flatten Excel data"""
    df = pd.read_excel(excel_file)
    
    # Define a safe eval function that handles nan
    def safe_eval(val):
        if pd.isna(val):
            return []
        if isinstance(val, str):
            try:
                # Provide np for numpy array representations if any exist in the string
                return eval(val, {"__builtins__": {}, "np": np})
            except Exception:
                return []
        return val

    lines = [safe_eval(line) for line in df['lines'].tolist()]
    lines = [item for sublist in lines for item in sublist if isinstance(sublist, list)]
    
    new_sub_times = [safe_eval(time) for time in df['new_sub_times'].tolist()]
    new_sub_times = [item for sublist in new_sub_times for item in sublist if isinstance(sublist, list)]
    
    return df, lines, new_sub_times

def get_audio_files(df):
    """Generate a list of audio file paths"""
    audios = []
    
    # Define safe_eval locally or reuse logic
    def safe_eval(val):
        if pd.isna(val):
            return []
        if isinstance(val, str):
            try:
                return eval(val, {"__builtins__": {}, "np": np})
            except Exception:
                return []
        return val

    for index, row in df.iterrows():
        number = row['number']
        lines_data = safe_eval(row['lines'])
        line_count = len(lines_data) if isinstance(lines_data, list) else 0
        
        for line_index in range(line_count):
            temp_file = OUTPUT_FILE_TEMPLATE.format(f"{number}_{line_index}")
            audios.append(temp_file)
    return audios

def process_audio_segment(audio_file):
    """Process a single audio segment with MP3 compression"""
    temp_file = f"{audio_file}_temp.mp3"
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-i', audio_file,
        '-ar', '16000',
        '-ac', '1',
        '-b:a', '64k',
        temp_file
    ]
    subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    audio_segment = AudioSegment.from_mp3(temp_file)
    os.remove(temp_file)
    return audio_segment

def _merge_time_ranges_ms(ranges_ms):
    if not ranges_ms:
        return []
    ranges_ms = sorted([(int(s), int(e)) for s, e in ranges_ms if e > s], key=lambda x: x[0])
    merged = [ranges_ms[0]]
    for s, e in ranges_ms[1:]:
        ps, pe = merged[-1]
        if s <= pe:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged

def _duck_audio(audio: AudioSegment, ranges_ms, duck_db: float, fade_ms: int = 10) -> AudioSegment:
    if not ranges_ms:
        return audio
    out = audio
    for start_ms, end_ms in ranges_ms:
        start_ms = max(0, min(len(out), start_ms))
        end_ms = max(0, min(len(out), end_ms))
        if end_ms <= start_ms:
            continue
        seg = out[start_ms:end_ms].apply_gain(duck_db)
        fm = int(fade_ms)
        if fm > 0 and end_ms - start_ms >= 2:
            fm = min(fm, (end_ms - start_ms) // 2)
            if fm > 0:
                seg = seg.fade_in(fm).fade_out(fm)
        out = out[:start_ms] + seg + out[end_ms:]
    return out

def merge_audio_segments(audios, new_sub_times, sample_rate, base_audio_path: Optional[str] = None):
    base_audio = None
    if base_audio_path and os.path.exists(base_audio_path):
        base_audio = AudioSegment.from_file(base_audio_path).set_frame_rate(sample_rate).set_channels(1)
    merged_audio = base_audio if base_audio is not None else AudioSegment.silent(duration=0, frame_rate=sample_rate)
    target_end_ms = 0
    for time_range in new_sub_times:
        if not isinstance(time_range, (list, tuple)) or len(time_range) != 2:
            continue
        start_time, end_time = time_range
        try:
            target_end_ms = max(target_end_ms, int(float(end_time) * 1000))
        except Exception:
            continue
    if len(merged_audio) < target_end_ms:
        merged_audio += AudioSegment.silent(duration=target_end_ms - len(merged_audio), frame_rate=sample_rate)

    if base_audio is not None:
        ranges_ms = []
        for audio_file, time_range in zip(audios, new_sub_times):
            if not os.path.exists(audio_file):
                continue
            if not isinstance(time_range, (list, tuple)) or len(time_range) != 2:
                continue
            start_time, end_time = time_range
            try:
                ranges_ms.append((int(float(start_time) * 1000), int(float(end_time) * 1000)))
            except Exception:
                continue
        merged_audio = _duck_audio(merged_audio, _merge_time_ranges_ms(ranges_ms), duck_db=-30.0, fade_ms=10)
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TaskProgressColumn()) as progress:
        merge_task = progress.add_task("🎵 Merging audio segments...", total=len(audios))
        
        for i, (audio_file, time_range) in enumerate(zip(audios, new_sub_times)):
            if not os.path.exists(audio_file):
                console.print(f"[bold yellow]⚠️  Warning: File {audio_file} does not exist, skipping...[/bold yellow]")
                progress.advance(merge_task)
                continue
                
            audio_segment = process_audio_segment(audio_file)
            start_time, end_time = time_range
            try:
                start_ms = int(float(start_time) * 1000)
            except Exception:
                start_ms = 0
            end_candidate_ms = start_ms + len(audio_segment)
            if len(merged_audio) < end_candidate_ms:
                merged_audio += AudioSegment.silent(duration=end_candidate_ms - len(merged_audio), frame_rate=sample_rate)
            merged_audio = merged_audio.overlay(audio_segment, position=max(0, start_ms))
            progress.advance(merge_task)
    
    return merged_audio

def create_srt_subtitle():
    df, lines, new_sub_times = load_and_flatten_data(_8_1_AUDIO_TASK)
    
    with open(DUB_SUB_FILE, 'w', encoding='utf-8') as f:
        for i, ((start_time, end_time), line) in enumerate(zip(new_sub_times, lines), 1):
            start_str = f"{int(start_time//3600):02d}:{int((start_time%3600)//60):02d}:{int(start_time%60):02d},{int((start_time*1000)%1000):03d}"
            end_str = f"{int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{int(end_time%60):02d},{int((end_time*1000)%1000):03d}"
            
            f.write(f"{i}\n")
            f.write(f"{start_str} --> {end_str}\n")
            f.write(f"{line}\n\n")
    
    rprint(f"[bold green]✅ Subtitle file created: {DUB_SUB_FILE}[/bold green]")

def merge_full_audio():
    """Main function: Process the complete audio merging process"""
    console.print("\n[bold cyan]🎬 Starting audio merging process...[/bold cyan]")
    
    with console.status("[bold cyan]📊 Loading data from Excel...[/bold cyan]"):
        df, lines, new_sub_times = load_and_flatten_data(_8_1_AUDIO_TASK)
    console.print("[bold green]✅ Data loaded successfully[/bold green]")
    
    with console.status("[bold cyan]🔍 Getting audio file list...[/bold cyan]"):
        audios = get_audio_files(df)
    console.print(f"[bold green]✅ Found {len(audios)} audio segments[/bold green]")
    
    with console.status("[bold cyan]📝 Generating subtitle file...[/bold cyan]"):
        create_srt_subtitle()
    
    if not os.path.exists(audios[0]):
        console.print(f"[bold red]❌ Error: First audio file {audios[0]} does not exist![/bold red]")
        return
    
    sample_rate = 16000
    console.print(f"[bold green]✅ Sample rate: {sample_rate}Hz[/bold green]")

    console.print("[bold cyan]🔄 Starting audio merge process...[/bold cyan]")
    base_audio_path = _VOCAL_AUDIO_FILE if os.path.exists(_VOCAL_AUDIO_FILE) else None
    merged_audio = merge_audio_segments(audios, new_sub_times, sample_rate, base_audio_path=base_audio_path)
    
    with console.status("[bold cyan]💾 Exporting final audio file...[/bold cyan]"):
        merged_audio = merged_audio.set_frame_rate(16000).set_channels(1)
        merged_audio.export(DUB_VOCAL_FILE, format="mp3", parameters=["-b:a", "64k"])
    console.print(f"[bold green]✅ Audio file successfully merged![/bold green]")
    console.print(f"[bold green]📁 Output file: {DUB_VOCAL_FILE}[/bold green]")

if __name__ == "__main__":
    merge_full_audio()
