"""Local live console: run the agent, tests and benchmarks from a browser and watch them explain themselves.

    uv run --group dev signalpost serve        ->  http://127.0.0.1:8765

Safety: binds to 127.0.0.1 only; runs a fixed whitelist of project actions (never arbitrary shell);
organisation numbers are validated to 9 digits; static files are served only from out-*/ and reports/.
Read-only helper: /api/diff compares two runs (or a run and one of its archived history snapshots) in memory.
"""
from __future__ import annotations

import copy
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
HISTORY_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,96}\.jsonl(\.gz)?$")
ORG = re.compile(r"\d{9}")


class Job:
    def __init__(self, action: str, cmd: list[str], out: str | None):
        self.id = str(int(time.time() * 1000))
        self.action, self.cmd, self.out = action, cmd, out
        self.lines: list[str] = []
        self.done = False
        self.code: int | None = None
        self.started = time.time()
        self.cond = threading.Condition()
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        self.proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                     text=True, encoding="utf-8", errors="replace", bufsize=1)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.proc.stdout
        for line in self.proc.stdout:
            with self.cond:
                self.lines.append(line.rstrip("\n"))
                self.cond.notify_all()
        self.code = self.proc.wait()
        if self.action == "verify" and self.code == 0 and self.out:
            # keep the re-verification result next to the run so the showcase can report it
            result = next((ln for ln in reversed(self.lines) if ln.startswith("{") and '"sampled"' in ln), None)
            if result:
                try:
                    (ROOT / self.out / "evidence-verification.json").write_text(json.dumps(json.loads(result), indent=1), encoding="utf-8")
                except (OSError, json.JSONDecodeError):
                    pass
        with self.cond:
            self.done = True
            self.lines.append(f"@exit {self.code}")
            self.cond.notify_all()


STATE: dict[str, Job | None] = {"job": None}
LOCK = threading.Lock()


def batches() -> list[dict]:
    out = []
    for p in sorted((ROOT / "eval").glob("*.jsonl")):
        n = sum(1 for line in p.open(encoding="utf-8") if line.strip())
        out.append({"path": f"eval/{p.name}", "count": n})
    return out


def runs() -> list[dict]:
    out = []
    for d in sorted(ROOT.glob("out-*"), key=lambda p: p.stat().st_mtime, reverse=True):
        rep = d / "run-report.json"
        if not rep.exists():
            continue
        try:
            r = json.loads(rep.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append({"dir": d.name, "run_id": r.get("run_id"), "completed_at": r.get("completed_at"), "n": r.get("input_count"),
                    "valid": r.get("validation", {}).get("passed"), "requests": r.get("operations", {}).get("requests"),
                    "seconds": r.get("operations", {}).get("elapsed_seconds"), "coverage": r.get("family_coverage"),
                    "states": r.get("family_states"), "gate": r.get("identity_gate"), "mode": r.get("mode"),
                    "has_site": (d / "site" / "index.html").exists(), "has_audit": (d / "identity-audit.md").exists(),
                    "ops": r.get("operations", {}), "cost": r.get("third_party_cost_usd"), "changes": r.get("changes_detected"),
                    "history": sorted((h.name for h in (d / "history").glob("*.jsonl*") if HISTORY_NAME.match(h.name)), reverse=True)
                    if (d / "history").is_dir() else [],
                    "verification": _read_json(d / "evidence-verification.json")})
    return out[:30]


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


def build_cmd(body: dict) -> tuple[list[str], str | None]:
    py = sys.executable
    action = body.get("action")
    out = body.get("out") or ""
    if out and not (SAFE_NAME.match(out) and out.startswith("out-")):
        raise ValueError("output folder must look like out-<name>")
    if action == "run":
        batch = body.get("batch") or ""
        orgs = [o for o in re.split(r"[\s,;]+", body.get("orgs") or "") if o]
        if orgs:
            if not all(re.fullmatch(r"\d{9}", o) for o in orgs) or len(orgs) > 2000:
                raise ValueError("organisation numbers must be 9 digits")
            (ROOT / out).mkdir(exist_ok=True)
            batch_path = ROOT / out / "console-batch.jsonl"
            batch_path.write_text("".join(json.dumps({"organisation_number": o}) + "\n" for o in dict.fromkeys(orgs)), encoding="utf-8")
            batch = str(batch_path.relative_to(ROOT))
        elif batch not in {b["path"] for b in batches()}:
            raise ValueError("choose a batch or paste organisation numbers")
        cmd = [py, "-m", "signalpost.cli", "run", "--organisations", batch, "--out", out, "--events",
               "--job-days", str(max(1, min(60, int(body.get("job_days") or 60))))]
        prev = body.get("previous") or ""
        if prev:
            if not (SAFE_NAME.match(prev) and (ROOT / prev / "envelopes.jsonl").exists()):
                raise ValueError("previous run not found")
            cmd += ["--previous", prev]
        if body.get("no_web"):
            cmd.append("--no-web")
        return cmd, out
    if action == "rerun":
        # re-run one company live and diff it against the run it came from (output: out-rerun-<org>)
        target, org = body.get("target") or "", (body.get("org") or "").strip()
        if not (SAFE_NAME.match(target) and target.startswith("out-") and (ROOT / target / "envelopes.jsonl").exists()):
            raise ValueError("choose a finished run")
        if not ORG.fullmatch(org):
            raise ValueError("organisation number must be 9 digits")
        out = f"out-rerun-{org}"
        (ROOT / out).mkdir(exist_ok=True)
        (ROOT / out / "console-batch.jsonl").write_text(json.dumps({"organisation_number": org}) + "\n", encoding="utf-8")
        return [py, "-m", "signalpost.cli", "run", "--organisations", f"{out}/console-batch.jsonl", "--out", out, "--events",
                "--previous", target, "--job-days", str(max(1, min(60, int(body.get("job_days") or 7))))], out
    if action == "tests":
        return [py, "-m", "pytest", "-q"], None
    target = body.get("target") or ""
    if not (SAFE_NAME.match(target) and (ROOT / target / "envelopes.jsonl").exists()):
        raise ValueError("choose a finished run")
    if action == "benchmark":
        return [py, "eval/benchmark.py", target], target
    if action == "verify":
        return [py, "eval/verify_evidence.py", f"{target}/envelopes.jsonl", "--sample", "30"], target
    if action == "replay":
        return [py, "eval/refresh_replay.py", f"{target}/envelopes.jsonl", f"{target}/refresh-replay.json"], target
    if action == "showcase":
        return [py, "-m", "signalpost.cli", "showcase", "--envelopes", f"{target}/envelopes.jsonl", "--report", f"{target}/run-report.json",
                "--output", f"{target}/site"], target
    raise ValueError("unknown action")


def _snapshot(ref: str) -> Path:
    """Resolve 'out-x' or 'out-x/history/<file>.jsonl.gz' to an envelopes file inside the project."""
    parts = ref.split("/")
    if not (parts and SAFE_NAME.match(parts[0]) and parts[0].startswith("out-")):
        raise ValueError("unknown run")
    if len(parts) == 1:
        path = ROOT / parts[0] / "envelopes.jsonl"
    elif len(parts) == 3 and parts[1] == "history" and HISTORY_NAME.match(parts[2]):
        path = ROOT / parts[0] / "history" / parts[2]
    else:
        raise ValueError("unknown run")
    if not path.is_file():
        raise ValueError("run not found")
    return path


def diff_runs(a_ref: str, b_ref: str) -> dict:
    """Typed changes from run A (older) to run B (newer), computed in memory with the agent's own diff."""
    from ..refresh import diff, load_previous
    a, b = load_previous(_snapshot(a_ref)), load_previous(_snapshot(b_ref))
    meta = lambda envs: next(({"run_id": e.get("run", {}).get("run_id"), "completed_at": e.get("run", {}).get("completed_at")}  # noqa: E731
                              for e in envs.values()), {})
    companies, by_type, fam_a, fam_b = [], {}, {}, {}
    for org in sorted(set(a) & set(b)):
        changes, _ = diff(a[org], copy.deepcopy(b[org]), detected_at=b[org].get("run", {}).get("completed_at") or "")
        states = []
        for fam, st in b[org].get("availability", {}).items():
            old = a[org].get("availability", {}).get(fam, {}).get("state")
            fam_a[fam] = fam_a.get(fam, 0) + (old == "available")
            fam_b[fam] = fam_b.get(fam, 0) + (st.get("state") == "available")
            if old and old != st.get("state"):
                states.append({"family": fam, "a": old, "b": st.get("state"), "reason": st.get("reason")})
        for ch in changes:
            by_type[ch["type"]] = by_type.get(ch["type"], 0) + 1
        if changes or states:
            companies.append({"org": org, "name": b[org].get("name"), "states": states,
                              "changes": [{k: ch.get(k) for k in ("type", "material", "family", "label", "previous", "current")} for ch in changes]})
    return {"a": {"ref": a_ref, "n": len(a), **meta(a)}, "b": {"ref": b_ref, "n": len(b), **meta(b)}, "common": len(set(a) & set(b)),
            "only_a": sorted(set(a) - set(b))[:200], "only_b": sorted(set(b) - set(a))[:200], "by_type": by_type,
            "coverage": {f: {"a": fam_a.get(f, 0), "b": fam_b.get(f, 0)} for f in sorted(set(fam_a) | set(fam_b))},
            "companies": companies[:500], "companies_total": len(companies)}


class Handler(BaseHTTPRequestHandler):
    server_version = "SignalpostConsole/1.0"

    def log_message(self, *args) -> None:  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        url = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(url.path)
        if path == "/":
            return self._send(200, (HERE / "console.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/state":
            job = STATE["job"]
            return self._json({"batches": batches(), "runs": runs(),
                               "job": None if not job else {"id": job.id, "action": job.action, "out": job.out, "done": job.done,
                                                            "code": job.code, "cmd": " ".join(Path(c).name if i == 0 else c for i, c in enumerate(job.cmd))}})
        if path == "/api/diff":
            qs = urllib.parse.parse_qs(url.query)
            try:
                return self._json(diff_runs((qs.get("a") or [""])[0], (qs.get("b") or [""])[0]))
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                return self._json({"error": str(exc)}, 400)
        if path == "/api/stream":
            return self._stream(urllib.parse.parse_qs(url.query))
        if path.startswith("/files/"):
            return self._file(path[len("/files/"):])
        self._send(404, b'{"error":"not found"}')

    def _stream(self, qs: dict) -> None:
        job = STATE["job"]
        if not job:
            return self._send(404, b'{"error":"no job"}')
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        i = int((qs.get("from") or ["0"])[0])
        try:
            while True:
                with job.cond:
                    while i >= len(job.lines) and not job.done:
                        job.cond.wait(15)
                        if i >= len(job.lines):
                            break
                    chunk = job.lines[i:]
                    finished = job.done and i + len(chunk) >= len(job.lines)
                for line in chunk:
                    self.wfile.write(("data: " + json.dumps(line, ensure_ascii=False) + "\n\n").encode("utf-8"))
                i += len(chunk)
                if not chunk:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
                if finished:
                    break
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _file(self, rel: str) -> None:
        target = (ROOT / rel).resolve()
        allowed = target.is_file() and (target.is_relative_to(ROOT / "reports") or
                                        (target.relative_to(ROOT).parts[0].startswith("out-") if target.is_relative_to(ROOT) else False))
        if not allowed:
            return self._send(404, b'{"error":"not found"}')
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix in (".md", ".jsonl"):
            ctype = "text/plain"
        self._send(200, target.read_bytes(), ctype + ("; charset=utf-8" if ctype.startswith(("text/", "application/javascript")) else ""))

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/stop":
            job = STATE["job"]
            if job and not job.done:
                job.proc.terminate()
            return self._json({"ok": True})
        if self.path != "/api/run":
            return self._send(404, b'{"error":"not found"}')
        if self.headers.get("Origin") not in (None, f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
            return self._json({"error": "cross-origin request refused"}, 403)
        length = min(int(self.headers.get("Content-Length") or 0), 100_000)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            cmd, out = build_cmd(body)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._json({"error": str(exc)}, 400)
        with LOCK:
            job = STATE["job"]
            if job and not job.done:
                return self._json({"error": "a job is already running"}, 409)
            STATE["job"] = Job(body.get("action"), cmd, out)
        self._json({"ok": True, "id": STATE["job"].id})


def serve(port: int = 8765) -> int:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Signalpost live console: http://127.0.0.1:{port}  (Ctrl+C to stop)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
