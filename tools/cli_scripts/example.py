import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="example", add_help=True)
    parser.add_argument("--echo", default="", help="回显一段文本")
    parser.add_argument("--show-cwd", action="store_true", help="输出当前工作目录")
    args = parser.parse_args(list(argv or []))

    if args.echo:
        print(args.echo)
    if args.show_cwd:
        print(Path.cwd())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
