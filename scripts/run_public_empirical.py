from __future__ import annotations

"""One-command public empirical build for SignalLab.

Downloads checksum-verified Binance public daily spot klines, builds the full
research payload, writes the Markdown report, and renders the static HTML
portfolio preview. The downloader intentionally targets completed calendar
months so a run is reproducible within a month.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2021-01")
    p.add_argument("--end", default=None, help="YYYY-MM; defaults to previous completed month")
    p.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    p.add_argument("--data-dir", default="data/processed")
    p.add_argument("--payload", default="dashboard/public/results.json")
    p.add_argument("--report", default="docs/RESEARCH_REPORT.md")
    p.add_argument("--preview", default="docs/dashboard-preview.html")
    p.add_argument("--fee-bps", type=float, default=10.0)
    p.add_argument("--no-checksum", action="store_true")
    args = p.parse_args()

    root = Path(__file__).resolve().parents[1]
    py = sys.executable
    download = [py, "scripts/download_binance.py", "--symbols", *args.symbols, "--start", args.start, "--output-dir", args.data_dir]
    if args.end:
        download += ["--end", args.end]
    if args.no_checksum:
        download += ["--no-checksum"]
    run(download, cwd=root)

    env = dict(os.environ)
    src = str(root / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    run([py, "-m", "signallab.cli", "build", "--data-dir", args.data_dir, "--output", args.payload, "--symbols", *args.symbols], cwd=root, env=env)
    run([py, "-m", "signallab.cli", "report", "--payload", args.payload, "--output", args.report, "--fee-bps", str(args.fee_bps)], cwd=root, env=env)
    run([py, "scripts/render_preview.py", "--payload", args.payload, "--output", args.preview, "--fee-bps", str(args.fee_bps)], cwd=root, env=env)
    print(f"Empirical build complete: {root / args.payload}")


if __name__ == "__main__":
    main()
