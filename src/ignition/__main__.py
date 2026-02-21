import argparse

from ignition.app import run_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="iGnition")
    parser.add_argument(
        "--background",
        action="store_true",
        help="Start minimized to tray.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without UI (monitor + orchestration only).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return run_app(start_in_background=args.background, headless=args.headless)


if __name__ == "__main__":
    raise SystemExit(main())
