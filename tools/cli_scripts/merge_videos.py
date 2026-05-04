import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[2]


def _ensure_project_env():
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    os.chdir(SCRIPT_DIR)


def _resolve_path(p: str) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path.resolve()
    return (SCRIPT_DIR / path).resolve()


def _ffmpeg_exists() -> bool:
    return shutil.which("ffmpeg") is not None


def _run(cmd):
    proc = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    if proc.returncode != 0:
        raise RuntimeError(f"命令执行失败，退出码: {proc.returncode}")


def _ffmpeg_concat_line(p: Path) -> str:
    s = p.resolve().as_posix()
    s = s.replace("'", r"\'")
    return f"file '{s}'"


def _write_concat_list(video_paths):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
        for p in video_paths:
            f.write(_ffmpeg_concat_line(p) + "\n")
        return Path(f.name)


def _cmd_concat(args) -> int:
    _ensure_project_env()
    if not _ffmpeg_exists():
        print("未找到 ffmpeg。请先安装并加入 PATH。")
        return 1

    if args.list:
        list_path = _resolve_path(args.list)
        if not list_path.exists():
            print(f"列表文件不存在: {list_path}")
            return 1
        video_paths = []
        for line in list_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            video_paths.append(_resolve_path(line))
    else:
        video_paths = [_resolve_path(p) for p in (args.videos or [])]

    if len(video_paths) < 2:
        print("请至少提供 2 个视频文件。")
        return 1

    missing = [str(p) for p in video_paths if not p.exists()]
    if missing:
        print("以下文件不存在：")
        for p in missing:
            print(f"- {p}")
        return 1

    out_path = _resolve_path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_list = None
    try:
        tmp_list = _write_concat_list(video_paths)
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
            str(tmp_list),
        ]

        if args.reencode:
            cmd += [
                "-c:v",
                "libx264",
                "-preset",
                str(args.preset),
                "-crf",
                str(args.crf),
                "-c:a",
                "aac",
                "-b:a",
                str(args.audio_bitrate),
                "-movflags",
                "+faststart",
            ]
        else:
            cmd += ["-c", "copy"]

        cmd.append(str(out_path))
        _run(cmd)

        if not out_path.exists():
            print("合并失败：未生成输出文件。")
            return 1
        print(f"已生成: {out_path}")
        return 0
    finally:
        if tmp_list and tmp_list.exists():
            try:
                tmp_list.unlink()
            except Exception:
                pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog="merge_videos", add_help=True)
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    p_concat = subparsers.add_parser("concat", help="按顺序拼接多个视频（前后衔接）")
    p_concat.add_argument("videos", nargs="*", help="要拼接的视频路径（按顺序）")
    p_concat.add_argument("-o", "--output", default="merged.mp4", help="输出文件路径（默认 merged.mp4）")
    p_concat.add_argument(
        "--list",
        default="",
        help="从文本文件读取视频路径（每行一个路径；与 videos 二选一）",
    )
    p_concat.add_argument("--reencode", action="store_true", help="强制重编码（兼容不同编码/分辨率/音频格式）")
    p_concat.add_argument("--crf", type=int, default=18, help="重编码画质参数（默认 18）")
    p_concat.add_argument("--preset", default="veryfast", help="重编码速度/压缩参数（默认 veryfast）")
    p_concat.add_argument("--audio-bitrate", default="192k", help="重编码音频码率（默认 192k）")
    p_concat.set_defaults(_handler=_cmd_concat)

    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    return int(args._handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
