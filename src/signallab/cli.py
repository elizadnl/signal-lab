from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import build_dashboard_payload
from .report import build_markdown_report


def main() -> None:
    p = argparse.ArgumentParser(prog="signallab")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="Build dashboard JSON from normalized market CSVs")
    b.add_argument("--data-dir", default="data/processed")
    b.add_argument("--output", default="dashboard/public/results.json")
    b.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    r = sub.add_parser("report", help="Build a concise Markdown research report from a dashboard payload")
    r.add_argument("--payload", default="dashboard/public/results.json")
    r.add_argument("--output", default="docs/RESEARCH_REPORT.md")
    r.add_argument("--fee-bps", type=float, default=10.0)

    args = p.parse_args()
    if args.cmd == "build":
        payload = build_dashboard_payload(Path(args.data_dir), Path(args.output), symbols=tuple(args.symbols))
        print(f"Built {len(payload['runs'])} dashboard runs -> {args.output}")
    elif args.cmd == "report":
        build_markdown_report(args.payload, args.output, fee_bps=args.fee_bps)
        print(f"Built research report -> {args.output}")


if __name__ == "__main__":
    main()
