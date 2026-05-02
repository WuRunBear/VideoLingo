import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List
from uuid import uuid4
 
 
SCRIPT_DIR = Path(__file__).resolve().parents[2]
 
 
def _ensure_project_env():
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    os.chdir(SCRIPT_DIR)
 
 
def _resolve_path(p: str):
    path = Path(p)
    if path.is_absolute():
        return path.resolve()
    return (SCRIPT_DIR / path).resolve()
 
 
def _run(cmd: List[str]):
    proc = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    if proc.returncode != 0:
        raise RuntimeError(f"命令执行失败，退出码: {proc.returncode}")
 
 
def _ffmpeg_exists():
    return shutil.which("ffmpeg") is not None
 
 
def _write_concat_list(video_paths: List[Path], list_path: Path):
    list_path.parent.mkdir(parents=True, exist_ok=True)
    with open(list_path, "w", encoding="utf-8") as f:
        for p in video_paths:
            p_str = str(p).replace("\\", "/").replace("'", "\\'")
            f.write(f"file '{p_str}'\n")
 
 
def _concat_copy(list_path: Path, out_path: Path):
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        str(out_path),
    ]
    _run(cmd)
 
 
def _concat_encode(list_path: Path, out_path: Path, crf: int, preset: str):
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    _run(cmd)
 
 
def _cmd_merge(args):
    _ensure_project_env()
    if not _ffmpeg_exists():
        print("未找到 ffmpeg。请先安装并加入 PATH。")
        return 1
 
    if len(args.inputs) < 2:
        print("请至少提供 2 个输入视频。")
        return 1
 
    inputs = []
    for raw in args.inputs:
        p = _resolve_path(raw).resolve()
        if not p.exists() or not p.is_file():
            print(f"输入不存在: {p}")
            return 1
        inputs.append(p)
 
    out_path = _resolve_path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
 
    work_dir = out_path.parent / f"_merge_work_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)
    list_path = work_dir / "concat_list.txt"
    _write_concat_list(inputs, list_path)
 
    in_place = any(p.resolve() == out_path for p in inputs)
    out_tmp = out_path
    if in_place:
        out_tmp = work_dir / f"_out_tmp{out_path.suffix or '.mp4'}"
 
    mode = str(args.mode).lower().strip()
    if mode not in {"auto", "copy", "encode"}:
        print("mode 仅支持: auto / copy / encode")
        return 1
 
    try:
        if mode == "copy":
            _concat_copy(list_path, out_tmp)
        elif mode == "encode":
            _concat_encode(list_path, out_tmp, int(args.crf), str(args.preset))
        else:
            try:
                _concat_copy(list_path, out_tmp)
            except Exception:
                _concat_encode(list_path, out_tmp, int(args.crf), str(args.preset))
    except Exception as e:
        print(f"合并失败: {e}")
        return 1
 
    if in_place:
        if out_path.exists():
            try:
                out_path.unlink()
            except Exception as e:
                print(f"无法覆盖输出文件（删除失败）: {out_path}，原因: {e}")
                return 1
        shutil.move(str(out_tmp), str(out_path))
 
    print(f"已生成合并视频: {out_path}")
    return 0
 
 
def main(argv=None):
    parser = argparse.ArgumentParser(prog="merge_videos", add_help=True)
    parser.add_argument("--out", required=True, help="输出视频路径（相对路径默认基于项目根目录）")
    parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "copy", "encode"],
        help="auto: 先尝试无损拼接(copy)，失败则转码；copy: 仅无损拼接；encode: 强制转码",
    )
    parser.add_argument("--crf", type=int, default=18, help="转码质量（仅 mode=encode 或 auto 回退时生效）")
    parser.add_argument("--preset", default="veryfast", help="转码速度/压缩比（仅 mode=encode 或 auto 回退时生效）")
    parser.add_argument("inputs", nargs="+", help="输入视频路径，按给定顺序合并")
 
    if argv is None:
        argv = sys.argv[1:]
    args = parser.parse_args(list(argv))
    return int(_cmd_merge(args))
 
 
if __name__ == "__main__":
    raise SystemExit(main())
