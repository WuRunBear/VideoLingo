import os
import datetime
import re
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint
from core.prompts import get_subtitle_trim_prompt
from core.tts_backend.estimate_duration import init_estimator, estimate_duration
from core.utils import *
from core.utils.models import *

console = Console()
speed_factor = load_key("speed_factor")

TRANS_SUBS_FOR_AUDIO_FILE = 'static/output/audio/trans_subs_for_audio.srt'
SRC_SUBS_FOR_AUDIO_FILE = 'static/output/audio/src_subs_for_audio.srt'
SPEAKER_MAPPING_LOCKED = "static/output/log/speaker_mapping_locked.xlsx"
TRANSLATION_RESULTS = "static/output/log/translation_results.xlsx"
ESTIMATOR = None

def check_len_then_trim(text, duration):
    global ESTIMATOR
    if ESTIMATOR is None:
        ESTIMATOR = init_estimator()
    estimated_duration = estimate_duration(text, ESTIMATOR) / speed_factor['max']
    
    console.print(f"Subtitle text: {text}, "
                  f"[bold green]Estimated reading duration: {estimated_duration:.2f} seconds[/bold green]")

    if estimated_duration > duration:
        rprint(Panel(f"Estimated reading duration {estimated_duration:.2f} seconds exceeds given duration {duration:.2f} seconds, shortening...", title="Processing", border_style="yellow"))
        original_text = text
        prompt = get_subtitle_trim_prompt(text, duration)
        def valid_trim(response):
            if 'result' not in response:
                return {'status': 'error', 'message': 'No result in response'}
            return {'status': 'success', 'message': ''}
        try:    
            response = ask_gpt(prompt, resp_type='json', log_title='sub_trim', valid_def=valid_trim)
            shortened_text = response['result']
        except Exception:
            rprint("[bold red]🚫 AI refused to answer due to sensitivity, so manually remove punctuation[/bold red]")
            shortened_text = re.sub(r'[,.!?;:，。！？；：]', ' ', text).strip()
        rprint(Panel(f"Subtitle before shortening: {original_text}\nSubtitle after shortening: {shortened_text}", title="Subtitle Shortening Result", border_style="green"))
        return shortened_text
    else:
        return text

def time_diff_seconds(t1, t2, base_date):
    """Calculate the difference in seconds between two time objects"""
    dt1 = datetime.datetime.combine(base_date, t1)
    dt2 = datetime.datetime.combine(base_date, t2)
    return (dt2 - dt1).total_seconds()

def process_srt():
    """Process srt file, generate audio tasks"""
    
    mapping_df = None
    if os.path.exists(SPEAKER_MAPPING_LOCKED):
        try:
            mapping_df = pd.read_excel(SPEAKER_MAPPING_LOCKED)
        except Exception:
            mapping_df = None

    if mapping_df is not None and os.path.exists(TRANSLATION_RESULTS):
        try:
            df_tr = pd.read_excel(TRANSLATION_RESULTS)
            if "Source" not in df_tr.columns or "Translation" not in df_tr.columns:
                raise ValueError("translation_results.xlsx 缺少 Source/Translation 列")
            if "line_id" in mapping_df.columns:
                mapping_df["line_id"] = pd.to_numeric(mapping_df["line_id"], errors="coerce").astype("Int64")
                mapping_df = mapping_df.dropna(subset=["line_id"]).copy()
            else:
                mapping_df = mapping_df.copy()
                mapping_df.insert(0, "line_id", range(1, len(mapping_df) + 1))

            mapping_df["start"] = pd.to_numeric(mapping_df.get("start"), errors="coerce")
            mapping_df["end"] = pd.to_numeric(mapping_df.get("end"), errors="coerce")
            if mapping_df["start"].isna().any() or mapping_df["end"].isna().any():
                raise ValueError("speaker_mapping_locked.xlsx 缺少 start/end 或存在无法解析为数字的值")
            if (mapping_df["end"] <= mapping_df["start"]).any():
                raise ValueError("speaker_mapping_locked.xlsx 存在 end<=start")

            df_tr = df_tr[["Source", "Translation"]].copy()
            df_tr.insert(0, "line_id", range(1, len(df_tr) + 1))
            df_join = pd.merge(mapping_df, df_tr, on="line_id", how="left", suffixes=("", "_tr"))
            missing_tr = df_join["Translation"].isna().sum()
            if missing_tr > 0:
                raise ValueError(f"translation_results.xlsx 行数不足或不匹配，缺少译文行数：{missing_tr}")

            df_join = df_join.sort_values("line_id").reset_index(drop=True)
            df_join["start_time"] = df_join["start"].apply(lambda s: (datetime.datetime.min + datetime.timedelta(seconds=float(s))).time())
            df_join["end_time"] = df_join["end"].apply(lambda s: (datetime.datetime.min + datetime.timedelta(seconds=float(s))).time())
            df_join["duration"] = df_join["end"] - df_join["start"]
            df_join["number"] = df_join["line_id"].astype(int)
            if "speaker_id" not in df_join.columns:
                df_join["speaker_id"] = None
            if "ref_audio_id" not in df_join.columns:
                df_join["ref_audio_id"] = df_join["number"]

            df_tasks = pd.DataFrame(
                {
                    "number": df_join["number"],
                    "start_time": df_join["start_time"].apply(lambda x: x.strftime("%H:%M:%S.%f")[:-3]),
                    "end_time": df_join["end_time"].apply(lambda x: x.strftime("%H:%M:%S.%f")[:-3]),
                    "duration": df_join["duration"].astype(float),
                    "text": df_join["Translation"].astype(str),
                    "origin": df_join["Source"].astype(str),
                    "speaker_id": df_join["speaker_id"],
                    "ref_audio_id": df_join["ref_audio_id"],
                }
            )
            return df_tasks
        except Exception as e:
            rprint(Panel(f"Locked mapping mode failed, fallback to srt parsing. Error: {e}", title="Warning", border_style="yellow"))

    with open(TRANS_SUBS_FOR_AUDIO_FILE, 'r', encoding='utf-8') as file:
        content = file.read()
    
    with open(SRC_SUBS_FOR_AUDIO_FILE, 'r', encoding='utf-8') as src_file:
        src_content = src_file.read()
    
    subtitles = []
    src_subtitles = {}
    
    speaker_file = 'static/output/audio/audio_sub_with_speaker.xlsx'
    speaker_dict = {}
    if os.path.exists(speaker_file):
        df_spk = pd.read_excel(speaker_file)
        for idx, row in df_spk.iterrows():
            speaker_dict[idx + 1] = row.get('speaker_id', None)

    mapping_by_line_id = None
    if mapping_df is not None and 'line_id' in mapping_df.columns:
        try:
            mapping_df['line_id'] = pd.to_numeric(mapping_df['line_id'], errors='coerce').astype('Int64')
            mapping_df = mapping_df.dropna(subset=['line_id']).copy()
            mapping_by_line_id = mapping_df.set_index('line_id')
        except Exception:
            mapping_by_line_id = None

    if mapping_df is not None and 'start' in mapping_df.columns and 'end' in mapping_df.columns:
        try:
            mapping_df['start'] = pd.to_numeric(mapping_df['start'], errors='coerce')
            mapping_df['end'] = pd.to_numeric(mapping_df['end'], errors='coerce')
            if mapping_df['start'].isna().any() or mapping_df['end'].isna().any():
                raise ValueError("speaker_mapping_locked.xlsx 的 start/end 存在无法解析为数字的值")
            if (mapping_df['end'] <= mapping_df['start']).any():
                raise ValueError("speaker_mapping_locked.xlsx 存在 end<=start，请修正时间")
            bad_mask = mapping_df['start'].diff().fillna(0) < -1e-6
            if bad_mask.any():
                bad_idx = bad_mask[bad_mask].index.tolist()
                pairs = []
                for i in bad_idx[:20]:
                    prev_i = i - 1
                    prev_line = mapping_df.loc[prev_i, 'line_id'] if 'line_id' in mapping_df.columns else prev_i + 1
                    cur_line = mapping_df.loc[i, 'line_id'] if 'line_id' in mapping_df.columns else i + 1
                    prev_start = float(mapping_df.loc[prev_i, 'start'])
                    cur_start = float(mapping_df.loc[i, 'start'])
                    pairs.append(f"{prev_line}({prev_start:.3f}s) -> {cur_line}({cur_start:.3f}s)")
                detail = "；".join(pairs)
                raise ValueError(f"speaker_mapping_locked.xlsx 的 start 非单调递增。异常相邻行（前->后）：{detail}")
        except Exception as e:
            raise ValueError(f"speaker_mapping_locked.xlsx 时间校验失败：{e}")

    for block in src_content.strip().split('\n\n'):
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if len(lines) < 3:
            continue
        
        number = int(lines[0])
        src_text = ' '.join(lines[2:])
        src_subtitles[number] = src_text
    
    for block in content.strip().split('\n\n'):
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if len(lines) < 3:
            continue
        
        try:
            number = int(lines[0])
            start_time, end_time = lines[1].split(' --> ')
            start_time = datetime.datetime.strptime(start_time, '%H:%M:%S,%f').time()
            end_time = datetime.datetime.strptime(end_time, '%H:%M:%S,%f').time()
            duration = time_diff_seconds(start_time, end_time, datetime.date.today())
            text = ' '.join(lines[2:])
            # Remove content within parentheses (including English and Chinese parentheses)
            text = re.sub(r'\([^)]*\)', '', text).strip()
            text = re.sub(r'（[^）]*）', '', text).strip()
            # Remove '-' character, can continue to add illegal characters that cause errors
            text = text.replace('-', '')

            # Add the original text from src_subs_for_audio.srt
            origin = src_subtitles.get(number, '')

            # Get speaker_id
            speaker_id = speaker_dict.get(number, None)
            ref_audio_id = number
            if mapping_by_line_id is not None:
                try:
                    row = mapping_by_line_id.loc[number]
                except Exception:
                    row = None
                if row is None:
                    raise RuntimeError(f"speaker_mapping_locked.xlsx 缺少 line_id={number}（请检查是否删除/重排导致缺号）")
                if 'start' in mapping_df.columns and 'end' in mapping_df.columns and pd.notna(row.get('start')) and pd.notna(row.get('end')):
                    start_seconds = float(row['start'])
                    end_seconds = float(row['end'])
                    start_time = (datetime.datetime.min + datetime.timedelta(seconds=start_seconds)).time()
                    end_time = (datetime.datetime.min + datetime.timedelta(seconds=end_seconds)).time()
                    duration = end_seconds - start_seconds
                elif 'start_time' in mapping_df.columns and 'end_time' in mapping_df.columns and pd.notna(row.get('start_time')) and pd.notna(row.get('end_time')):
                    start_time = datetime.datetime.strptime(str(row['start_time']), '%H:%M:%S.%f').time()
                    end_time = datetime.datetime.strptime(str(row['end_time']), '%H:%M:%S.%f').time()
                    duration = time_diff_seconds(start_time, end_time, datetime.date.today())
                if 'speaker_id' in mapping_df.columns and pd.notna(row.get('speaker_id')):
                    speaker_id = row.get('speaker_id')
                if 'ref_audio_id' in mapping_df.columns and pd.notna(row.get('ref_audio_id')):
                    try:
                        ref_audio_id = int(float(row.get('ref_audio_id')))
                    except Exception:
                        ref_audio_id = number
            elif mapping_df is not None and (number - 1) < len(mapping_df):
                row = mapping_df.iloc[number - 1]
                if 'start' in mapping_df.columns and 'end' in mapping_df.columns and pd.notna(row.get('start')) and pd.notna(row.get('end')):
                    start_seconds = float(row['start'])
                    end_seconds = float(row['end'])
                    start_time = (datetime.datetime.min + datetime.timedelta(seconds=start_seconds)).time()
                    end_time = (datetime.datetime.min + datetime.timedelta(seconds=end_seconds)).time()
                    duration = end_seconds - start_seconds
                elif 'start_time' in mapping_df.columns and 'end_time' in mapping_df.columns and pd.notna(row.get('start_time')) and pd.notna(row.get('end_time')):
                    start_time = datetime.datetime.strptime(str(row['start_time']), '%H:%M:%S.%f').time()
                    end_time = datetime.datetime.strptime(str(row['end_time']), '%H:%M:%S.%f').time()
                    duration = time_diff_seconds(start_time, end_time, datetime.date.today())
                if 'speaker_id' in mapping_df.columns and pd.notna(row.get('speaker_id')):
                    speaker_id = row.get('speaker_id')
                if 'ref_audio_id' in mapping_df.columns and pd.notna(row.get('ref_audio_id')):
                    try:
                        ref_audio_id = int(float(row.get('ref_audio_id')))
                    except Exception:
                        ref_audio_id = number

        except ValueError as e:
            rprint(Panel(f"Unable to parse subtitle block '{block}', error: {str(e)}, skipping this subtitle block.", title="Error", border_style="red"))
            continue
        
        subtitles.append({'number': number, 'start_time': start_time, 'end_time': end_time, 'duration': duration, 'text': text, 'origin': origin, 'speaker_id': speaker_id, 'ref_audio_id': ref_audio_id})
    
    df = pd.DataFrame(subtitles)
    
    if mapping_df is not None:
        sec_start = df['start_time'].apply(lambda t: t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1_000_000)
        sec_end = df['end_time'].apply(lambda t: t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1_000_000)
        if (sec_end <= sec_start).any():
            bad_rows = (sec_end <= sec_start)
            bad_nums = df.loc[bad_rows, 'number'].tolist()[:30] if 'number' in df.columns else []
            raise ValueError(f"生成 tts_tasks 时发现 end<=start。异常 number（最多30个）：{bad_nums}")
        bad_mask = sec_start.diff().fillna(0) < -1e-6
        if bad_mask.any():
            bad_idx = bad_mask[bad_mask].index.tolist()
            pairs = []
            for i in bad_idx[:20]:
                prev_i = i - 1
                prev_num = int(df.loc[prev_i, 'number']) if 'number' in df.columns else prev_i + 1
                cur_num = int(df.loc[i, 'number']) if 'number' in df.columns else i + 1
                pairs.append(f"{prev_num}({sec_start.iloc[prev_i]:.3f}s) -> {cur_num}({sec_start.iloc[i]:.3f}s)")
            detail = "；".join(pairs)
            raise ValueError(f"生成 tts_tasks 时发现 start 非单调递增。异常相邻行（前->后）：{detail}")
        df['start_time'] = df['start_time'].apply(lambda x: x.strftime('%H:%M:%S.%f')[:-3])
        df['end_time'] = df['end_time'].apply(lambda x: x.strftime('%H:%M:%S.%f')[:-3])
        return df

    i = 0
    MIN_SUB_DUR = load_key("min_subtitle_duration")
    while i < len(df):
        today = datetime.date.today()
        if df.loc[i, 'duration'] < MIN_SUB_DUR:
            spk1 = df.loc[i, 'speaker_id'] if 'speaker_id' in df.columns else None
            spk2 = df.loc[i+1, 'speaker_id'] if (i < len(df) - 1 and 'speaker_id' in df.columns) else None
            same_speaker = True
            if pd.notna(spk1) and pd.notna(spk2) and spk1 != spk2:
                same_speaker = False

            if i < len(df) - 1 and time_diff_seconds(df.loc[i, 'start_time'],df.loc[i+1, 'start_time'],today) < MIN_SUB_DUR and same_speaker:
                rprint(f"[bold yellow]Merging subtitles {i+1} and {i+2}[/bold yellow]")
                df.loc[i, 'text'] += ' ' + df.loc[i+1, 'text']
                df.loc[i, 'origin'] += ' ' + df.loc[i+1, 'origin']
                df.loc[i, 'end_time'] = df.loc[i+1, 'end_time']
                df.loc[i, 'duration'] = time_diff_seconds(df.loc[i, 'start_time'],df.loc[i, 'end_time'],today)
                df = df.drop(i+1).reset_index(drop=True)
            else:
                if i < len(df) - 1:  # Not the last audio
                    rprint(f"[bold blue]Extending subtitle {i+1} duration to {MIN_SUB_DUR} seconds[/bold blue]")
                    df.loc[i, 'end_time'] = (datetime.datetime.combine(today, df.loc[i, 'start_time']) + 
                                            datetime.timedelta(seconds=MIN_SUB_DUR)).time()
                    df.loc[i, 'duration'] = MIN_SUB_DUR
                else:
                    rprint(f"[bold red]The last subtitle {i+1} duration is less than {MIN_SUB_DUR} seconds, but not extending[/bold red]")
                i += 1
        else:
            i += 1
    
    df['start_time'] = df['start_time'].apply(lambda x: x.strftime('%H:%M:%S.%f')[:-3])
    df['end_time'] = df['end_time'].apply(lambda x: x.strftime('%H:%M:%S.%f')[:-3])

    ##! No longer perform secondary trim
    # check and trim subtitle length, for twice to ensure the subtitle length is within the limit, 允许tolerance
    # df['text'] = df.apply(lambda x: check_len_then_trim(x['text'], x['duration']+x['tolerance']), axis=1)

    return df

@check_file_exists(_8_1_AUDIO_TASK)
def gen_audio_task_main():
    df = process_srt()
    console.print(df)
    df.to_excel(_8_1_AUDIO_TASK, index=False)
    rprint(Panel(f"Successfully generated {_8_1_AUDIO_TASK}", title="Success", border_style="green"))

if __name__ == '__main__':
    gen_audio_task_main()
