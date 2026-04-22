import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = SCRIPT_DIR / "static" / "output"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


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


def _find_files_in_dir(dir_path: Path, exts):
    lower_exts = {e.lower() for e in exts}
    files = []
    for p in dir_path.iterdir():
        if p.is_file() and p.suffix.lower() in lower_exts:
            files.append(p)
    return sorted(files, key=lambda x: x.name.lower())


def _run(cmd):
    proc = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    if proc.returncode != 0:
        raise RuntimeError(f"命令执行失败，退出码: {proc.returncode}")


def _ffmpeg_exists():
    return shutil.which("ffmpeg") is not None


def _build_vf(width: int, height: int):
    return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"


def _load_manifest(manifest_path: Path):
    if not manifest_path.exists():
        raise RuntimeError(f"JSON 文件不存在: {manifest_path}")
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "items" not in data or not isinstance(data["items"], list):
        raise RuntimeError("JSON 缺少 items 数组")
    return data


def _save_manifest(manifest_path: Path, data):
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _project_root_by_manifest(manifest_path: Path):
    return manifest_path.parent.resolve()


def _abs_from_project(project_root: Path, rel_path: str):
    return (project_root / rel_path).resolve()


def _validate_item_paths(project_root: Path, items):
    for item in items:
        image_rel = item.get("image_path", "")
        if not image_rel:
            raise RuntimeError(f"条目 {item.get('index')} 缺少 image_path")
        image_abs = _abs_from_project(project_root, image_rel)
        if not image_abs.exists():
            raise RuntimeError(f"图片不存在: {image_abs}")


def _cmd_init(args):
    _ensure_project_env()
    images_dir = _resolve_path(args.images)
    if not images_dir.exists():
        print(f"图片目录不存在: {images_dir}")
        return 1

    src_images = _find_files_in_dir(images_dir, IMAGE_EXTS)
    if not src_images:
        print(f"图片目录为空: {images_dir}")
        return 1

    project_name = args.name.strip() if args.name else datetime.now().strftime("slideshow_%Y%m%d_%H%M%S")
    project_root = (DEFAULT_ROOT / project_name).resolve()
    if project_root.exists() and not args.force:
        print(f"项目目录已存在: {project_root}")
        print("如需覆盖，请添加 --force")
        return 1

    if project_root.exists() and args.force:
        shutil.rmtree(project_root, ignore_errors=True)

    images_out = project_root / "images"
    audios_out = project_root / "audios"
    video_out = project_root / "video"
    images_out.mkdir(parents=True, exist_ok=True)
    audios_out.mkdir(parents=True, exist_ok=True)
    video_out.mkdir(parents=True, exist_ok=True)

    items = []
    for idx, src in enumerate(src_images, start=1):
        file_name = f"{idx:04d}{src.suffix.lower()}"
        dst = images_out / file_name
        shutil.copy2(src, dst)
        items.append(
            {
                "index": idx,
                "image_path": f"images/{file_name}",
                "text": "",
                "audio_path": f"audios/{idx:04d}.wav",
            }
        )

    manifest = {
        "version": 1,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_root": str(project_root),
        "output_video": "video/output.mp4",
        "video_settings": {
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "crf": 18,
            "preset": "veryfast",
        },
        "items": items,
    }

    manifest_path = project_root / "manifest.json"
    _save_manifest(manifest_path, manifest)

    print(f"已初始化项目: {project_root}")
    print(f"已生成 JSON: {manifest_path}")
    print("请编辑 JSON 的 items[*].text 后，再执行 tts 和 video。")
    return 0


def _cmd_tts(args):
    _ensure_project_env()
    manifest_path = _resolve_path(args.json)
    data = _load_manifest(manifest_path)
    project_root = _project_root_by_manifest(manifest_path)
    items = data["items"]
    _validate_item_paths(project_root, items)

    missing = [str(it.get("index")) for it in items if not str(it.get("text", "")).strip()]
    if missing:
        print(f"以下条目 text 为空，请先填写 JSON: {', '.join(missing)}")
        return 1

    try:
        from core.tts_backend.tts_main import tts_main
    except Exception as e:
        print(f"无法导入项目 TTS: {e}")
        return 1

    for item in items:
        idx = int(item.get("index", 0))
        text = str(item.get("text", "")).strip()
        audio_rel = str(item.get("audio_path", "")).strip()
        if not audio_rel:
            print(f"条目 {idx} 缺少 audio_path")
            return 1
        audio_abs = _abs_from_project(project_root, audio_rel)
        audio_abs.parent.mkdir(parents=True, exist_ok=True)
        tts_main(text, str(audio_abs), idx, None)
        if not audio_abs.exists():
            print(f"生成音频失败: {audio_abs}")
            return 1
        print(f"已生成配音: {audio_abs}")

    print("配音已全部生成。")
    return 0


def _make_segment(image_path: Path, audio_path: Path, seg_path: Path, width: int, height: int, fps: int, crf: int, preset: str):
    vf = _build_vf(width, height)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-i",
        str(audio_path),
        "-vf",
        vf,
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(seg_path),
    ]
    _run(cmd)


def _concat_files(file_paths, out_path: Path, crf: int, preset: str, list_filename: str):
    list_file = out_path.parent / list_filename
    with open(list_file, "w", encoding="utf-8") as f:
        for p in file_paths:
            p_str = str(p).replace("\\", "/")
            f.write(f"file '{p_str}'\n")

    cmd_copy = [
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
        str(list_file),
        "-c",
        "copy",
        str(out_path),
    ]

    try:
        _run(cmd_copy)
        return
    except Exception:
        pass

    cmd_encode = [
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
        str(list_file),
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
    _run(cmd_encode)


def _concat_segments(seg_paths, out_path: Path, crf: int, preset: str):
    _concat_files(seg_paths, out_path, crf, preset, "segments.txt")


def _normalize_video(in_path: Path, out_path: Path, width: int, height: int, fps: int, crf: int, preset: str):
    vf = _build_vf(width, height)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(in_path),
        "-vf",
        vf,
        "-r",
        str(fps),
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


def _cmd_video(args):
    _ensure_project_env()
    if not _ffmpeg_exists():
        print("未找到 ffmpeg。请先安装并加入 PATH。")
        return 1

    manifest_path = _resolve_path(args.json)
    data = _load_manifest(manifest_path)
    project_root = _project_root_by_manifest(manifest_path)
    items = data["items"]
    _validate_item_paths(project_root, items)

    settings = data.get("video_settings", {})
    width = int(settings.get("width", 1920))
    height = int(settings.get("height", 1080))
    fps = int(settings.get("fps", 30))
    crf = int(settings.get("crf", 18))
    preset = str(settings.get("preset", "veryfast"))
    out_rel = str(data.get("output_video", "video/output.mp4"))
    out_path = _abs_from_project(project_root, out_rel)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    seg_dir = project_root / "segments"
    if seg_dir.exists() and args.clean_segments:
        shutil.rmtree(seg_dir, ignore_errors=True)
    seg_dir.mkdir(parents=True, exist_ok=True)

    seg_paths = []
    for item in items:
        idx = int(item.get("index", 0))
        image_abs = _abs_from_project(project_root, str(item.get("image_path", "")))
        audio_rel = str(item.get("audio_path", "")).strip()
        if not audio_rel:
            print(f"条目 {idx} 缺少 audio_path")
            return 1
        audio_abs = _abs_from_project(project_root, audio_rel)
        if not audio_abs.exists():
            print(f"条目 {idx} 音频不存在: {audio_abs}")
            return 1
        seg_path = seg_dir / f"{idx:04d}.mp4"
        _make_segment(image_abs, audio_abs, seg_path, width, height, fps, crf, preset)
        seg_paths.append(seg_path)
        print(f"已生成片段: {seg_path}")

    _concat_segments(seg_paths, out_path, crf, preset)
    print(f"已生成视频: {out_path}")
    return 0


def _cmd_append(args):
    _ensure_project_env()
    if not _ffmpeg_exists():
        print("未找到 ffmpeg。请先安装并加入 PATH。")
        return 1

    manifest_path = _resolve_path(args.json)
    data = _load_manifest(manifest_path)
    project_root = _project_root_by_manifest(manifest_path)
    items = data["items"]
    _validate_item_paths(project_root, items)

    settings = data.get("video_settings", {})
    width = int(settings.get("width", 1920))
    height = int(settings.get("height", 1080))
    fps = int(settings.get("fps", 30))
    crf = int(settings.get("crf", 18))
    preset = str(settings.get("preset", "veryfast"))

    base_raw = str(args.base_video).strip()
    base_abs = Path(base_raw)
    if not base_abs.is_absolute():
        base_candidate = _abs_from_project(project_root, base_raw)
        base_abs = base_candidate if base_candidate.exists() else _resolve_path(base_raw)
    base_abs = base_abs.resolve()
    if not base_abs.exists():
        print(f"基础视频不存在: {base_abs}")
        return 1

    out_abs = Path(str(args.out).strip()) if str(args.out).strip() else base_abs
    if not out_abs.is_absolute():
        out_abs = _abs_from_project(project_root, str(out_abs))
    out_abs = out_abs.resolve()
    out_abs.parent.mkdir(parents=True, exist_ok=True)

    seg_dir = project_root / "segments_append"
    if seg_dir.exists() and args.clean_segments:
        shutil.rmtree(seg_dir, ignore_errors=True)
    seg_dir.mkdir(parents=True, exist_ok=True)

    base_norm = seg_dir / "_base_norm.mp4"
    _normalize_video(base_abs, base_norm, width, height, fps, crf, preset)

    seg_paths = []
    for item in items:
        idx = int(item.get("index", 0))
        image_abs = _abs_from_project(project_root, str(item.get("image_path", "")))
        audio_rel = str(item.get("audio_path", "")).strip()
        if not audio_rel:
            print(f"条目 {idx} 缺少 audio_path")
            return 1
        audio_abs = _abs_from_project(project_root, audio_rel)
        if not audio_abs.exists():
            print(f"条目 {idx} 音频不存在: {audio_abs}")
            return 1
        seg_path = seg_dir / f"{idx:04d}.mp4"
        _make_segment(image_abs, audio_abs, seg_path, width, height, fps, crf, preset)
        seg_paths.append(seg_path)
        print(f"已生成片段: {seg_path}")

    concat_paths = [base_norm] + seg_paths
    inplace = out_abs == base_abs
    out_tmp = out_abs
    if inplace:
        out_tmp = seg_dir / f"_append_tmp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

    _concat_files(concat_paths, out_tmp, crf, preset, "append_list.txt")

    if inplace:
        if out_abs.exists():
            try:
                out_abs.unlink()
            except Exception as e:
                print(f"无法覆盖原视频（删除失败）: {out_abs}，原因: {e}")
                return 1
        shutil.move(str(out_tmp), str(out_abs))
        print(f"已追加到原视频: {out_abs}")
        return 0

    print(f"已生成合并视频: {out_abs}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="slideshow_dub", add_help=True)
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    p_init = subparsers.add_parser("init", help="初始化项目：复制图片到 static/output 并生成 JSON")
    p_init.add_argument("--images", required=True, help="原始图片目录（按文件名排序）")
    p_init.add_argument("--name", default="", help="项目名（默认按时间生成）")
    p_init.add_argument("--force", action="store_true", help="若项目已存在则覆盖")
    p_init.set_defaults(_handler=_cmd_init)

    p_tts = subparsers.add_parser("tts", help="按 JSON 生成配音")
    p_tts.add_argument("--json", required=True, help="manifest.json 路径")
    p_tts.set_defaults(_handler=_cmd_tts)

    p_video = subparsers.add_parser("video", help="按 JSON 生成视频")
    p_video.add_argument("--json", required=True, help="manifest.json 路径")
    p_video.add_argument("--clean-segments", action="store_true", help="生成前先清理 segments 目录")
    p_video.set_defaults(_handler=_cmd_video)

    p_append = subparsers.add_parser("append", help="把 JSON 生成的内容追加到已有视频后面")
    p_append.add_argument("--json", required=True, help="manifest.json 路径")
    p_append.add_argument("--base-video", required=True, help="基础视频路径（支持相对项目目录）")
    p_append.add_argument("--out", default="", help="输出视频路径（默认覆盖 base-video）")
    p_append.add_argument("--clean-segments", action="store_true", help="生成前先清理 segments_append 目录")
    p_append.set_defaults(_handler=_cmd_append)

    if argv is None:
        argv = sys.argv[1:]
    args = parser.parse_args(list(argv))
    return int(args._handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
