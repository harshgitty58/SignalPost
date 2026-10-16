"""Command line entry point.

    signalpost run --organisations batch.jsonl --out out/ [--previous prev_out/] [--bulk brreg-enheter.csv.gz]
    signalpost select --universe signalpost-universe.jsonl.gz --count 100 --output batch.jsonl
    signalpost showcase --envelopes out/envelopes.jsonl --report out/run-report.json --output out/site
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def cmd_run(args: argparse.Namespace) -> int:
    from .pipeline import Runner, read_inputs

    orgs = read_inputs(args.organisations)
    if args.expected_count is not None and len(orgs) != args.expected_count:
        _log(f"warning: expected {args.expected_count} organisations, received {len(orgs)} distinct; continuing (one envelope per input)")
    out = Path(args.out)
    run_id = args.run_id or datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    _log(f"[signalpost] run {run_id}: {len(orgs)} organisations -> {out}")
    runner = Runner(orgs, out_dir=out, run_id=run_id, bulk=args.bulk, previous=args.previous, max_requests=args.max_requests,
                    max_minutes=args.max_minutes, max_cost=args.max_cost, workers=args.workers, job_days=args.job_days,
                    web=not args.no_web, bulk_files=args.bulk_files, log=_log)
    try:
        report = runner.run()
    finally:
        runner.fetcher.close()
    # optional legacy output paths (starter-kit compatible flags)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out / "envelopes.jsonl", args.output)
    if args.profiles_output:
        Path(args.profiles_output).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out / "envelopes.jsonl", args.profiles_output)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out / "run-report.json", args.report)
    if not args.no_showcase:
        from .showcase.build import build_site
        site = Path(args.showcase) if args.showcase else out / "site"
        build_site(out / "envelopes.jsonl", out / "run-report.json", site)
        _log(f"[showcase] {site / 'index.html'}")
    ops = report["operations"]
    _log(f"[done] envelopes={report['emitted_envelopes']}/{report['input_count']} valid={report['validation']['passed']} "
         f"requests={ops['requests']} time={ops['elapsed_seconds']}s cost=${report['third_party_cost_usd']}")
    _log("[coverage] " + ", ".join(f"{k}={v:.0%}" for k, v in report["family_coverage"].items()))
    return 0 if report["validation"]["passed"] else 1


def cmd_select(args: argparse.Namespace) -> int:
    path = Path(args.universe)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    exclude: set[str] = set()
    for ex in args.exclude or []:
        for line in Path(ex).read_text(encoding="utf-8").splitlines():
            if line.strip():
                exclude.add(json.loads(line)["organisation_number"] if line.strip().startswith("{") else line.strip())
    rows = [r for r in rows if r["organisation_number"] not in exclude]
    chosen = random.Random(args.seed).sample(rows, args.count)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        for row in chosen:
            handle.write(json.dumps({"organisation_number": row["organisation_number"]}) + "\n")
    _log(f"wrote {len(chosen)} organisation numbers to {args.output}")
    return 0


def cmd_showcase(args: argparse.Namespace) -> int:
    from .showcase.build import build_site

    build_site(Path(args.envelopes), Path(args.report) if args.report else None, Path(args.output))
    _log(f"[showcase] {Path(args.output) / 'index.html'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="signalpost", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="research a batch of organisation numbers")
    run.add_argument("--organisations", "--input", required=True, help="JSONL/JSON/TXT list of organisation numbers")
    run.add_argument("--out", default="out", help="output directory (envelopes.jsonl, run-report.json, site/)")
    run.add_argument("--previous", help="previous output directory or envelopes.jsonl for refresh diffs")
    run.add_argument("--bulk", help="optional frozen Brreg entity snapshot (CSV/JSON, gz ok); adds e-mail domains + fallback identity")
    run.add_argument("--run-id")
    run.add_argument("--expected-count", type=int)
    run.add_argument("--max-requests", type=int, default=2000)
    run.add_argument("--max-minutes", type=float, default=45.0)
    run.add_argument("--max-cost", type=float, default=10.0)
    run.add_argument("--workers", type=int, default=24)
    run.add_argument("--job-days", type=int, default=35, help="NAV feed look-back window in days")
    run.add_argument("--bulk-files", action="store_true", help="experimental: roles/workplaces from Brreg bulk files for large batches")
    run.add_argument("--no-web", action="store_true", help="skip website discovery (registry-only run)")
    run.add_argument("--showcase", help="where to write the static showcase site (default: <out>/site)")
    run.add_argument("--no-showcase", action="store_true")
    run.add_argument("--output", help="(compat) copy envelopes to this path")
    run.add_argument("--profiles-output", help="(compat) copy envelopes to this path")
    run.add_argument("--report", help="(compat) copy run report to this path")
    run.set_defaults(func=cmd_run)

    sel = sub.add_parser("select", help="sample a local test batch from the public universe")
    sel.add_argument("--universe", required=True)
    sel.add_argument("--count", type=int, default=100)
    sel.add_argument("--seed", type=int, default=20261016)
    sel.add_argument("--exclude", nargs="*")
    sel.add_argument("--output", required=True)
    sel.set_defaults(func=cmd_select)

    show = sub.add_parser("showcase", help="build the static showcase site from a run")
    show.add_argument("--envelopes", required=True)
    show.add_argument("--report")
    show.add_argument("--output", required=True)
    show.set_defaults(func=cmd_showcase)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
