"""Write measured numbers into README.md and SUBMISSION.md from the committed reports (no hand-typed metrics).

    uv run python eval/write_docs.py
Replaces the text between <!-- metrics:start --> and <!-- metrics:end -->.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def line(name: str, path: Path) -> str | None:
    if not path.exists():
        return None
    r = json.loads(path.read_text(encoding="utf-8"))
    o = r["operations"]
    cov = r.get("family_coverage", {})
    top = ", ".join(f"{k} {v:.0%}" for k, v in cov.items())
    return (f"- **{name}** ({r['run_id']} @ `{r.get('agent_version')}`): {r['emitted_envelopes']}/{r['input_count']} valid envelopes "
            f"(validation {'passed' if r['validation']['passed'] else 'FAILED'}), {o['requests']} requests, "
            f"{o['elapsed_seconds'] / 60:.1f} min, ${r.get('third_party_cost_usd', 0):.2f}. Coverage: {top}.")


def main() -> None:
    rows = [x for x in (line("100 random companies (smoke test)", ROOT / "reports/smoke-100-run-report.json"),
                        line("1,000 random companies (official limits)", ROOT / "reports/run-1000-run-report.json")) if x]
    block = "<!-- metrics:start -->\n" + "\n".join(rows) + "\n<!-- metrics:end -->"
    for doc in ("README.md", "SUBMISSION.md"):
        p = ROOT / doc
        text = p.read_text(encoding="utf-8")
        new = re.sub(r"<!-- metrics:start -->.*?<!-- metrics:end -->", block, text, flags=re.S)
        p.write_text(new, encoding="utf-8")
        print(doc, "updated" if new != text else "unchanged (add the metrics markers)")


if __name__ == "__main__":
    main()
