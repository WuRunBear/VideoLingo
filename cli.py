import argparse
import importlib.util
import os
import shutil
import socket
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
CLI_SCRIPTS_DIR = SCRIPT_DIR / "tools" / "cli_scripts"


def _ensure_project_env():
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    os.chdir(SCRIPT_DIR)


def _check_package(name, import_name=None):
    import_name = import_name or name
    try:
        mod = __import__(import_name)
        return getattr(mod, "__version__", "ok")
    except ImportError:
        return None


def _run_preflight_checks():
    errors = []
    warnings = []

    for pkg, imp in [("streamlit", None), ("json_repair", "json_repair")]:
        if not _check_package(pkg, imp):
            errors.append(f"{pkg} 未安装。请先运行: python install.py")

    torch_ver = _check_package("torch")
    if torch_ver:
        import torch
        if not torch.cuda.is_available():
            warnings.append("torch 无 CUDA 支持，将以 CPU 运行。可尝试重装: python install.py")

    if not _check_package("whisperx"):
        warnings.append("whisperx 未安装，ASR 相关步骤将失败。")

    if not shutil.which("ffmpeg"):
        errors.append("未在 PATH 中找到 ffmpeg。Windows 可尝试: choco install ffmpeg")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", 8501)) == 0:
            warnings.append("8501 端口占用。可关闭占用程序，或启动时改端口。")

    return errors, warnings


def _print_preflight_summary(errors, warnings):
    if errors:
        print()
        for e in errors:
            print(f"  [ERROR] {e}")
        print()
    if warnings:
        print()
        for w in warnings:
            print(f"  [WARN] {w}")
        print()


def _flatten_yaml_keys(obj, prefix=""):
    keys = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_str = str(k)
            next_prefix = f"{prefix}.{k_str}" if prefix else k_str
            keys.extend(_flatten_yaml_keys(v, next_prefix))
    elif isinstance(obj, list):
        keys.append(prefix)
    else:
        keys.append(prefix)
    return keys


def _is_sensitive_key_path(key_path):
    lowered = key_path.lower()
    return any(s in lowered for s in ("api_key", "apikey", "key", "token", "secret", "password"))


def _tool_doctor(_args):
    _ensure_project_env()
    errors, warnings = _run_preflight_checks()
    _print_preflight_summary(errors, warnings)
    return 1 if errors else 0


def _tool_paths(_args):
    _ensure_project_env()
    print(f"项目根目录: {SCRIPT_DIR}")
    print(f"配置文件: {SCRIPT_DIR / 'config.yaml'}")
    print(f"启动入口: {SCRIPT_DIR / 'st.py'}")
    print(f"启动脚本: {SCRIPT_DIR / 'launch.py'}")
    print(f"CLI 脚本目录: {CLI_SCRIPTS_DIR}")
    return 0


def _load_config_yaml():
    try:
        from ruamel.yaml import YAML
    except Exception:
        print("未安装 ruamel.yaml，无法读取 config.yaml。请先运行: python install.py")
        return None

    yaml = YAML()
    try:
        with open(SCRIPT_DIR / "config.yaml", "r", encoding="utf-8") as f:
            return yaml.load(f) or {}
    except FileNotFoundError:
        print("未找到 config.yaml。")
        return None


def _tool_config_get(args):
    _ensure_project_env()
    data = _load_config_yaml()
    if data is None:
        return 1

    key_path = args.key
    cur = data
    for part in key_path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            print(f"未找到配置项: {key_path}")
            return 1

    if _is_sensitive_key_path(key_path) and not args.show_secret:
        print(f"{key_path}: <已隐藏>")
        return 0

    print(f"{key_path}: {cur}")
    return 0


def _tool_config_keys(args):
    _ensure_project_env()
    data = _load_config_yaml()
    if data is None:
        return 1

    prefix = args.prefix or ""
    all_keys = sorted(set(k for k in _flatten_yaml_keys(data) if k))
    for k in all_keys:
        if not prefix or k.startswith(prefix):
            print(k)
    return 0


def _list_cli_script_files():
    if not CLI_SCRIPTS_DIR.exists():
        return []
    files = []
    for p in CLI_SCRIPTS_DIR.glob("*.py"):
        if p.name == "__init__.py":
            continue
        if p.name.startswith("_"):
            continue
        files.append(p)
    return sorted(files, key=lambda x: x.name.lower())


def _tool_script_list(_args):
    _ensure_project_env()
    files = _list_cli_script_files()
    if not files:
        print("未找到可用脚本。")
        print(f"请把脚本放到: {CLI_SCRIPTS_DIR}")
        return 0
    for p in files:
        print(p.stem)
    return 0


def _load_script_module(script_path: Path):
    spec = importlib.util.spec_from_file_location(f"videolingo_cli_script_{script_path.stem}", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载脚本: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tool_script_run(args):
    _ensure_project_env()
    name = args.name
    script_args = list(args.script_args or [])
    if script_args and script_args[0] == "--":
        script_args = script_args[1:]

    if any(sep in name for sep in ("/", "\\", ":")) or name.endswith(".py"):
        script_path = Path(name)
        if not script_path.is_absolute():
            script_path = (SCRIPT_DIR / script_path).resolve()
    else:
        script_path = (CLI_SCRIPTS_DIR / f"{name}.py").resolve()

    if not script_path.exists() or not script_path.is_file():
        print(f"脚本不存在: {script_path}")
        return 1

    try:
        module = _load_script_module(script_path)
    except Exception as e:
        print(f"加载脚本失败: {e}")
        return 1

    entry = None
    for attr in ("main", "run"):
        candidate = getattr(module, attr, None)
        if callable(candidate):
            entry = candidate
            break

    if entry is None:
        print("脚本缺少可调用入口函数：main(argv) 或 run(argv)")
        return 1

    try:
        rc = entry(script_args)
        return 0 if rc is None else int(rc)
    except SystemExit as e:
        code = getattr(e, "code", 0)
        return 0 if code is None else int(code)
    except Exception as e:
        print(f"脚本执行失败: {e}")
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python cli.py", add_help=True)
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    p_doctor = subparsers.add_parser("doctor", help="检查运行环境（不启动 Streamlit）")
    p_doctor.set_defaults(_handler=_tool_doctor)

    p_paths = subparsers.add_parser("paths", help="输出项目关键路径（不修改任何文件）")
    p_paths.set_defaults(_handler=_tool_paths)

    p_config = subparsers.add_parser("config", help="读取 config.yaml（默认会隐藏敏感值）")
    config_sub = p_config.add_subparsers(dest="config_cmd", required=True)

    p_cfg_get = config_sub.add_parser("get", help="读取单个配置项：例如 api.model 或 whisper.runtime")
    p_cfg_get.add_argument("key")
    p_cfg_get.add_argument("--show-secret", action="store_true")
    p_cfg_get.set_defaults(_handler=_tool_config_get)

    p_cfg_keys = config_sub.add_parser("keys", help="列出所有配置键（点号路径）")
    p_cfg_keys.add_argument("--prefix", default="")
    p_cfg_keys.set_defaults(_handler=_tool_config_keys)

    p_script = subparsers.add_parser("script", help="管理/运行 tools/cli_scripts 下的脚本")
    script_sub = p_script.add_subparsers(dest="script_cmd", required=True)

    p_script_list = script_sub.add_parser("list", help="列出可运行脚本（按文件名）")
    p_script_list.set_defaults(_handler=_tool_script_list)

    p_script_run = script_sub.add_parser("run", help="运行脚本：script run <name> -- [args...]")
    p_script_run.add_argument("name")
    p_script_run.add_argument("script_args", nargs=argparse.REMAINDER)
    p_script_run.set_defaults(_handler=_tool_script_run)

    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    return int(args._handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
