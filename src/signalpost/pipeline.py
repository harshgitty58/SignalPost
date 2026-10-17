"""Batch pipeline: one terminal envelope per input organisation number, inside the official budget.

Phase plan (request caps are reserved per phase so no source can starve another):
  P0  NAV job feed (background thread, shared)            ~ pages for the last N days
  P1  registry entities (100 per request) + bulk snapshot ~ N/100
  P2  official dated activity (100 orgs per request)      ~ 2·N/100
  P3  per company: accounts → roles → workplaces → group (only if in a group) → website gate + extraction
  P4  jobs verification per company (orgnr check)
  P5  refresh diff vs --previous, cited brief, envelope validation, run report, showcase
A watchdog stops new work before the time limit and still emits every envelope (unfinished families -> failed).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from typing import Any

from . import __version__
from .budget import Budget, BudgetExhausted
from .bulk import bulk_roles, bulk_subunits
from .http import Fetcher, utc_now
from .jobs import JobFeed, job_claims
from .model import FAMILIES, STATES, ProfileBuilder
from .refresh import diff, load_previous
from .registry import (ACCOUNTS_URL, GROUP_URL, HISTORY_URL, ROLES_URL, SUBUNITS_URL, accounts_claims, history_claims, pace_history, activity_claims, entity_claims,
                       fetch_activity, fetch_entities, group_claims, load_bulk, roles_claims, subunit_claims)
from .synthesis import build_brief
from .web import research_website, valid_orgnr
from .wikidata import websites as wikidata_websites


def read_inputs(path: str | Path) -> list[str]:
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    values: list[Any]
    stripped = text.strip()
    if stripped.startswith("["):
        values = json.loads(stripped)
    elif stripped.startswith("{") and "\n" not in stripped:
        body = json.loads(stripped)
        values = body.get("organisation_numbers") or body.get("organisations") or [body]
    else:
        values = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                values.append(json.loads(line))
            elif any(ch.isdigit() for ch in line):
                values.append(line)  # lines without any digit (e.g. a CSV header) are not inputs
    orgs: list[str] = []
    seen: set[str] = set()
    for value in values:
        raw = value.get("organisation_number") or value.get("organisasjonsnummer") or value.get("orgnr") if isinstance(value, dict) else value
        org = "".join(ch for ch in str(raw or "") if ch.isdigit())
        if org in seen:
            continue  # duplicate input: one envelope per distinct organisation number
        seen.add(org)
        orgs.append(org)
    return orgs


def git_version() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True, timeout=5,
                             cwd=Path(__file__).resolve().parents[2]).stdout.strip()
        return sha or __version__
    except (OSError, subprocess.SubprocessError):
        return __version__


class Runner:
    def __init__(self, orgs: list[str], *, out_dir: Path, run_id: str, bulk: str | None, previous: str | None,
                 max_requests: int, max_minutes: float, max_cost: float, workers: int, job_days: int, web: bool = True, bulk_files: bool = False, events: bool = False,
                 log=print):
        self.orgs = orgs
        self.out_dir = out_dir
        self.run_id = run_id
        self.bulk_path = bulk
        self.previous_path = previous
        self.workers = workers
        self.web_enabled = web
        self.bulk_files = bulk_files
        self.events = events
        self.log = log
        n = max(1, len(orgs))
        self.budget = Budget(max_requests=max_requests, max_seconds=max_minutes * 60, max_cost_usd=max_cost,
                             safety_requests=max(25, int(max_requests * 0.04)), safety_seconds=max(60.0, min(240.0, max_minutes * 60 * 0.08)))
        self.fetcher = Fetcher(self.budget, api_concurrency=8, web_concurrency=2)
        self.fetcher.set_min_interval("pam-stilling-feed.nav.no", 0.05)
        self.started_at = utc_now()
        self.t0 = time.monotonic()
        self.builders: dict[str, ProfileBuilder] = {o: ProfileBuilder(o) for o in orgs}
        self.entities: dict[str, dict] = {}
        self.bulk_rows: dict[str, dict] = {}
        self.timings: dict[str, float] = {}
        self.company_ms: dict[str, int] = {}
        self.stop = threading.Event()
        self.finished = threading.Event()
        self.job_feed = JobFeed(self.fetcher, days=job_days, max_pages=max(20, min(130, int(job_days * 2.6))))
        self.notes: list[str] = []
        self._plan(n)

    # ------------------------------------------------------------------ budget plan
    def _plan(self, n: int) -> None:
        usable = self.budget.usable_requests
        batches = -(-n // 100)
        plan = {
            "registry": batches * 3 + 2,
            "activity": batches * 4 + 2,
            "jobs": self.job_feed.max_pages + 3,
            "accounts": n + n // 20 + 2,
            "roles": n + n // 20 + 2,
            "locations": n + n // 20 + 2,
            "group": int(n * 0.35) + 2,
            "jobs_verify": max(10, int(n * 0.6)),
            "history": n + 2 if n <= 200 else 0,  # paced endpoint (~30/min): only for small batches
        }
        self.bulk_mode = self.bulk_files and n * 3 > usable * 0.6
        self.bulk: dict[str, dict | None] = {"roles": None, "locations": None}
        if self.bulk_mode:
            # large batch: roles and workplaces come from Brreg's nightly bulk files (1 request each)
            self.notes.append(f"large batch ({n}): roles and workplaces from Brreg bulk files")
            plan["roles"] = plan["locations"] = 2
        fixed = sum(plan.values())
        if fixed > usable * 0.75:
            # large batch: keep identity + accounts first, scale the rest down proportionally
            self.notes.append(f"large batch ({n}); per-company official sources scaled to fit {usable} requests")
            # exact-key official sources yield ~1 fact per request; website attempts ~0.03 accepted sites per request,
            # so in a large batch the remaining budget goes to roles/workplaces first and websites get what is left
            plan["jobs"] = min(plan["jobs"], 40)
            self.job_feed.max_pages = plan["jobs"] - 3
            core = plan["registry"] + plan["activity"] + plan["jobs"] + plan["accounts"]
            rest = max(0, int(usable * 0.97) - core)
            for key in (("group", "jobs_verify") if self.bulk_mode else ("roles", "locations", "group", "jobs_verify")):
                plan[key] = int(rest * {"roles": 0.46, "locations": 0.42, "group": 0.07, "jobs_verify": 0.05}[key])
            fixed = sum(plan.values())
        plan["web"] = max(0, usable - fixed) if self.web_enabled else 0
        plan["web_news"] = 0  # shares the web cap (see below)
        for phase, cap in plan.items():
            if phase != "web_news":
                self.budget.set_phase_cap(phase, cap)
        # news pages are optional extras: allow at most 15% of the web budget
        self.budget.set_phase_cap("web_news", int(plan["web"] * 0.15))
        self.budget.set_phase_cap("web", int(plan["web"] * 0.85))
        self.plan = plan

    def phase(self, name: str, started: float) -> None:
        self.timings[name] = round(time.monotonic() - started, 1)

    # ------------------------------------------------------------------ per-company work
    def company(self, org: str) -> None:
        pb = self.builders[org]
        t = time.monotonic()
        self.fetcher.take_count()
        entity = self.entities.get(org) or self.bulk_rows.get(org) or {}
        try:
            steps = [
                ("financials", "accounts", ACCOUNTS_URL, accounts_claims),
                ("leadership", "roles", ROLES_URL, roles_claims),
                ("locations", "locations", SUBUNITS_URL, subunit_claims),
            ]
            if self.plan.get("history"):
                steps.insert(1, ("financials", "history", HISTORY_URL, history_claims))
            if entity.get("erIKonsern"):
                steps.append(("group", "group", GROUP_URL, group_claims))
            elif entity:
                pb.set_state("group", "not_applicable" if entity.get("erIKonsern") is False else "not_available",
                             "registry: not part of a corporate group" if entity.get("erIKonsern") is False else "group membership not reported")
            for family, phase, url, handler in steps:
                if self.stop.is_set():
                    break
                pre = self.bulk.get(phase) if self.bulk_mode else None
                if pre is not None:
                    if org in pre:
                        handler(pb, pre[org])
                    else:
                        pb.set_state(family, "not_available", "no record for this organisation number in Brreg's bulk file")
                    continue
                try:
                    if phase == "history":
                        pace_history()
                    snap = self.fetcher.get_json(url.format(org=org), phase=phase, retries=1)
                except BudgetExhausted as exc:
                    pb.set_state(family, "failed", f"request budget: {exc}")
                    continue
                if snap.status in (404, 410) or (snap.ok and snap.body.strip() in (b"", b"[]", b"{}")):
                    pb.set_state(family, "not_available", f"source returned no record (HTTP {snap.status})", snap.url)
                elif snap.status in (401, 403, 429):
                    pb.set_state(family, "blocked", f"source refused the request (HTTP {snap.status})", snap.url)
                elif not snap.ok:
                    pb.set_state(family, "failed", f"source error ({snap.status} {snap.error or ''})".strip(), snap.url)
                    pb.error(family, f"HTTP {snap.status} {snap.error or ''}", snap.url)
                else:
                    try:
                        handler(pb, snap)
                    except (ValueError, KeyError, TypeError) as exc:
                        pb.set_state(family, "failed", f"could not parse source response: {type(exc).__name__}", snap.url)
                        pb.error(family, f"parse: {exc}", snap.url)
            if self.web_enabled and not self.stop.is_set() and entity:
                related = {c.value.get("organisation_number") for c in pb.family_claims("group") if isinstance(c.value, dict)}
                related |= {c.value.split("org. ")[-1].rstrip(")") for c in pb.family_claims("leadership") if "org. " in str(c.value)}
                if self.budget.phase_remaining("web") < 4:
                    pb.set_state("website", "failed", "request budget: website phase exhausted")
                else:
                    research_website(pb, self.fetcher, entity, self.bulk_rows.get(org), {r for r in related if r})
        except BudgetExhausted as exc:
            pb.error("run", f"budget: {exc}")
        except Exception as exc:  # one company must never take down the batch
            pb.error("run", f"{type(exc).__name__}: {exc}")
            pb.extra["traceback"] = traceback.format_exc()[-1500:]
        finally:
            pb.requests += self.fetcher.take_count()
            self.company_ms[org] = int((time.monotonic() - t) * 1000)
            self.event("company", org)

    def event(self, kind: str, org: str) -> None:
        """Machine-readable progress line for the live console (only with --events)."""
        if not self.events:
            return
        pb = self.builders[org]
        name = next((c.value for c in pb.family_claims("identity") if c.field == "legal_name"), None)
        payload = {"kind": kind, "org": org, "name": name, "ms": self.company_ms.get(org), "requests": pb.requests,
                   "claims": len(pb.claims), "budget": {"requests": self.budget.requests, "elapsed": round(self.budget.elapsed(), 1)},
                   "states": {f: [st.state, st.reason] for f, st in pb.families.items()},
                   "candidates": pb.candidates[:6], "errors": pb.errors[:3],
                   "website": next((c.value for c in pb.family_claims("website")), None)}
        try:
            print("@event " + json.dumps(payload, ensure_ascii=False, default=str), file=sys.stderr, flush=True)
        except (OSError, ValueError):
            pass

    def jobs_for(self, org: str) -> None:
        pb = self.builders[org]
        self.fetcher.take_count()
        try:
            names = [c.value for c in pb.family_claims("identity") if c.field in ("legal_name", "public_brand")]
            names += [c.value.get("name") for c in pb.family_claims("locations") if isinstance(c.value, dict) and c.value.get("name")]
            valid = {org} | {c.value.get("organisation_number") for c in pb.family_claims("locations") if isinstance(c.value, dict)}
            if not names:
                ent = self.entities.get(org) or self.bulk_rows.get(org) or {}
                names = [ent.get("navn")] if ent.get("navn") else []
            job_claims(pb, self.job_feed, [n for n in names if n], {v for v in valid if v})
        except BudgetExhausted:
            pb.set_state("jobs", "failed", "request budget: jobs verification exhausted")
        except Exception as exc:
            pb.set_state("jobs", "failed", f"{type(exc).__name__}")
            pb.error("jobs", str(exc))
        finally:
            pb.requests += self.fetcher.take_count()

    # ------------------------------------------------------------------ run
    def run(self) -> dict[str, Any]:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self._hard_watchdog, daemon=True, name="watchdog").start()
        partial = (self.out_dir / "envelopes.partial.jsonl").open("w", encoding="utf-8")
        self.job_feed.start()

        t = time.monotonic()
        if self.bulk_path:
            try:
                self.bulk_rows, self.bulk_meta = load_bulk(self.bulk_path, self.orgs)
                self.log(f"[bulk] matched {len(self.bulk_rows)}/{len(self.orgs)} in snapshot {self.bulk_meta['sha256'][:12]}")
            except (OSError, ValueError) as exc:
                self.bulk_meta = {"error": str(exc)}
                self.log(f"[bulk] could not read snapshot: {exc}")
        else:
            self.bulk_meta = {"note": "no bulk snapshot supplied; live registry API only"}
        self.phase("bulk_snapshot", t)

        t = time.monotonic()
        live, errors = fetch_entities(self.fetcher, [o for o in self.orgs if valid_orgnr(o)])
        self.log(f"[registry] live entities {len(live)}/{len(self.orgs)} errors={errors}")
        for org in self.orgs:
            pb = self.builders[org]
            try:
                if org in live:
                    entity, snap = live[org]
                    self.entities[org] = entity
                    entity_claims(pb, entity, retrieved_at=snap.retrieved_at, source_class="official_registry", method="brreg_enheter_api")
                    pb.set_state("identity", "available", "live Enhetsregisteret record", snap.url.split("?")[0])
                    continue
                if org in self.bulk_rows:
                    entity_claims(pb, self.bulk_rows[org], retrieved_at=self.started_at, source_class="official_registry_bulk",
                                  method="brreg_bulk_snapshot", source_url="https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv")
                    pb.set_state("identity", "available", "frozen registry snapshot (live lookup unavailable)")
                    continue
            except Exception as exc:  # a malformed record must not stop the batch
                pb.error("identity", f"{type(exc).__name__}: {exc}")
                pb.set_state("identity", "failed", "could not parse registry record")
                continue
            if not valid_orgnr(org):
                for fam in FAMILIES:
                    pb.set_state(fam, "not_applicable", "input is not a valid Norwegian organisation number (mod-11 check failed)")
            else:
                for fam in FAMILIES:
                    pb.set_state(fam, "not_available" if not errors else "failed",
                                 "organisation number not found in Enhetsregisteret (deleted or invalid)" if not errors else "registry unavailable")
        self.phase("registry", t)

        bulk_threads = []
        if self.bulk_mode:
            wanted = {o for o in self.orgs if valid_orgnr(o)}
            for key, fn in (("roles", bulk_roles), ("locations", bulk_subunits)):
                def job(key=key, fn=fn):
                    t1 = time.monotonic()
                    try:
                        self.bulk[key] = fn(wanted, self.budget)
                        self.log(f"[bulk] {key}: {len(self.bulk[key])} companies in {time.monotonic() - t1:.0f}s")
                    except Exception as exc:  # fall back to per-company requests
                        self.notes.append(f"bulk {key} failed: {type(exc).__name__}")
                        self.log(f"[bulk] {key} failed: {exc}")
                        self.budget.set_phase_cap(key, self.budget.phase_remaining("web") // 3)
                bulk_threads.append(threading.Thread(target=job, daemon=True))
                bulk_threads[-1].start()

        t = time.monotonic()
        known = [o for o in self.orgs if o in self.entities or o in self.bulk_rows]
        ent_events, role_events, act_errors = fetch_activity(self.fetcher, known)
        for org in known:
            try:
                n = activity_claims(self.builders[org], ent_events.get(org, []), role_events.get(org, []))
            except Exception as exc:
                self.builders[org].error("activity", f"{type(exc).__name__}: {exc}")
                n = 0
            if not n:
                self.builders[org].set_state("activity", "not_available" if not act_errors else "failed",
                                             "no official registry events in the last 24 months" if not act_errors else f"registry change log unavailable: {act_errors[0]}")
        self.log(f"[activity] events for {sum(1 for o in known if ent_events.get(o) or role_events.get(o))} companies; errors={act_errors}")
        self.phase("activity", t)
        try:
            wd = wikidata_websites(self.fetcher, known)
            for org, sites in wd.items():
                self.builders[org].extra.setdefault("site_candidates", []).extend((u, "wikidata_p856") for u in sites)
            self.log(f"[wikidata] websites for {len(wd)} companies")
        except Exception as exc:
            self.log(f"[wikidata] skipped: {exc}")

        for th in bulk_threads:
            th.join(timeout=max(0.0, min(900.0, self.budget.time_left() - 600)))
        # per-company pool with watchdog
        t = time.monotonic()
        hard_stop = self.budget.deadline_seconds - 45
        done = 0
        pool = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="co")
        futures = {pool.submit(self.company, org): org for org in known}
        pending = set(futures)
        last_log = 0
        while pending:
            remaining = hard_stop - self.budget.elapsed()
            if remaining <= 0:
                self.stop.set()
                self.notes.append("watchdog: stopped new work before the time limit")
                self.log("[watchdog] time limit approaching; finalising")
                break
            finished, pending = wait(pending, timeout=min(10, remaining), return_when=FIRST_COMPLETED)
            done += len(finished)
            if done - last_log >= 25 or not pending:
                last_log = done
                self.log(f"[companies] {done}/{len(known)} done, requests={self.budget.requests}, t={self.budget.elapsed():.0f}s")
        if self.stop.is_set():
            wait(pending, timeout=25)  # in-flight requests are bounded by their timeouts; budget now refuses new ones
        pool.shutdown(wait=False, cancel_futures=True)
        self.phase("companies", t)

        t = time.monotonic()
        feed_wait = max(0.0, min(self.budget.time_left() - 60, 600))
        if not self.job_feed.wait(feed_wait):
            self.log("[jobs] feed not finished; marking jobs as failed")
        self.log(f"[jobs] feed pages={self.job_feed.pages} ads={len(self.job_feed.ads)} error={self.job_feed.error}")
        if not self.stop.is_set():
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(self.jobs_for, known))
        self.phase("jobs", t)

        t = time.monotonic()
        previous = load_previous(self.previous_path)
        completed_at = utc_now()
        envelopes = []
        for org in self.orgs:
            try:
                env = self.envelope(org, completed_at, previous.get(org))
                if self.events:
                    self.event("final", org)
            except Exception as exc:  # last resort: still emit a valid terminal envelope
                env = self.fallback_envelope(org, completed_at, exc)
            envelopes.append(env)
            partial.write(json.dumps(env, ensure_ascii=False, separators=(",", ":")) + "\n")
        partial.close()
        self.phase("finalise", t)
        return self.write(envelopes, completed_at, previous)

    # ------------------------------------------------------------------ envelope
    def envelope(self, org: str, completed_at: str, previous: dict | None) -> dict[str, Any]:
        pb = self.builders[org]
        for fam in FAMILIES:
            if fam not in pb.families:
                if self.stop.is_set():
                    pb.set_state(fam, "failed", "not reached before the run's time limit")
        pb.finalize_states()
        identity = {c.field: c.value for c in pb.family_claims("identity") if c.field in ("legal_name", "legal_form", "municipality", "public_brand")}
        env: dict[str, Any] = {
            "organisation_number": org,
            "name": identity.get("legal_name"),
            "run": {"run_id": self.run_id, "started_at": self.started_at, "completed_at": completed_at,
                    "terminal_status": "completed" if not self.stop.is_set() else "completed_partial", "agent_version": git_version()},
            "identity": identity,
            "availability": {fam: {"state": st.state, "reason": st.reason, **({"checked_sources": st.checked_sources[:5]} if st.checked_sources else {})}
                             for fam, st in sorted(pb.families.items(), key=lambda kv: list(FAMILIES).index(kv[0]) if kv[0] in FAMILIES else 99)},
            "claims": [c.to_dict() for c in pb.claims.values()],
            "evidence": [e.to_dict() for e in pb.evidence.values()],
            "changes": [],
            "refresh": {},
            "brief": {},
            "unpublished_candidates": pb.candidates[:20],
            "errors": pb.errors[:20],
            "operations": {"requests": pb.requests, "runtime_ms": self.company_ms.get(org, 0), "third_party_cost_usd": 0.0},
        }
        changes, meta = diff(previous, env, detected_at=completed_at)
        env["changes"] = changes
        env["refresh"] = meta
        if previous:
            prev_ev = {e["id"]: e for e in previous.get("evidence", [])}
            current_ids = {e["id"] for e in env["evidence"]}
            keep = {eid for ch in changes for eid in ch.get("previous_evidence_ids", []) if eid not in current_ids}
            env["prior_evidence"] = [prev_ev[eid] for eid in sorted(keep) if eid in prev_ev]
        env["brief"] = build_brief(env)
        state_counts: dict[str, int] = {}
        for st in env["availability"].values():
            state_counts[st["state"]] = state_counts.get(st["state"], 0) + 1
        env["summary"] = {"claims": len(env["claims"]), "families_available": state_counts.get("available", 0), "states": state_counts}
        # explicit absence, per the output contract: a claim per unavailable family with its terminal state (never a zero)
        for fam, st in env["availability"].items():
            if st["state"] != "available":
                env["claims"].append({"id": f"c-absent-{org}-{fam}", "family": fam, "field": fam, "key": f"absent:{fam}",
                                      "label": FAMILIES.get(fam, {}).get("label", fam), "value": None, "availability": st["state"],
                                      "reason": st.get("reason"), "confidence": None, "evidence_ids": []})
        return env

    def _hard_watchdog(self) -> None:
        """Last line of defence: if the run is not finished 30 s before the limit, write every envelope and exit."""
        if self.finished.wait(max(0.0, self.budget.max_seconds - 30 - self.budget.elapsed())):
            return
        self.stop.set()
        self.log("[watchdog] hard limit reached: writing all envelopes now")
        completed_at = utc_now()
        envelopes = []
        for org in self.orgs:
            try:
                envelopes.append(self.envelope(org, completed_at, None))
            except Exception as exc:
                envelopes.append(self.fallback_envelope(org, completed_at, exc))
        try:
            self.write(envelopes, completed_at, {})
        finally:
            os._exit(0)

    def fallback_envelope(self, org: str, completed_at: str, exc: Exception) -> dict[str, Any]:
        return {
            "organisation_number": org, "name": None,
            "run": {"run_id": self.run_id, "started_at": self.started_at, "completed_at": completed_at, "terminal_status": "failed", "agent_version": git_version()},
            "identity": {}, "availability": {fam: {"state": "failed", "reason": f"envelope assembly error: {type(exc).__name__}"} for fam in FAMILIES},
            "claims": [], "evidence": [], "changes": [], "refresh": {"mode": "baseline"}, "brief": {"sentences": [], "unknowns": []},
            "unpublished_candidates": [], "errors": [{"family": "run", "message": f"{type(exc).__name__}: {exc}"}],
            "operations": {"requests": 0, "runtime_ms": 0, "third_party_cost_usd": 0.0}, "summary": {"claims": 0, "families_available": 0, "states": {"failed": len(FAMILIES)}},
        }

    # ------------------------------------------------------------------ outputs
    def write(self, envelopes: list[dict], completed_at: str, previous: dict) -> dict[str, Any]:
        out = self.out_dir
        tmp = out / "envelopes.jsonl.tmp"
        with tmp.open("w", encoding="utf-8") as handle:
            for env in envelopes:
                handle.write(json.dumps(env, ensure_ascii=False, separators=(",", ":")) + "\n")
        tmp.replace(out / "envelopes.jsonl")
        try:
            (out / "envelopes.partial.jsonl").unlink()
        except OSError:
            pass
        validation = validate(envelopes, self.orgs)
        fam_states: dict[str, dict[str, int]] = {}
        for env in envelopes:
            for fam, st in env["availability"].items():
                fam_states.setdefault(fam, {}).setdefault(st["state"], 0)
                fam_states[fam][st["state"]] += 1
        coverage = {fam: round(states.get("available", 0) / max(1, len(envelopes)), 3) for fam, states in fam_states.items()}
        gate: dict[str, int] = {}
        for env in envelopes:
            for cand in env.get("unpublished_candidates", []):
                if cand.get("family") == "website":
                    gate[cand["decision"]] = gate.get(cand["decision"], 0) + 1
            if any(c["field"] == "official_website" for c in env["claims"]):
                gate["accepted"] = gate.get("accepted", 0) + 1
        ms = sorted(self.company_ms.values())
        report = {
            "run_id": self.run_id,
            "agent_version": git_version(),
            "started_at": self.started_at,
            "completed_at": completed_at,
            "input_count": len(self.orgs),
            "emitted_envelopes": len(envelopes),
            "validation": validation,
            "mode": "refresh" if previous else "baseline",
            "changes_detected": sum(len(e["changes"]) for e in envelopes),
            "family_states": fam_states,
            "family_coverage": coverage,
            "claims_total": sum(len(e["claims"]) for e in envelopes),
            "identity_gate": gate,
            "jobs_feed": {"pages": self.job_feed.pages, "ads_indexed": len(self.job_feed.ads), "window_days": self.job_feed.days, "error": self.job_feed.error},
            "operations": {**self.budget.report(), "p50_company_ms": ms[len(ms) // 2] if ms else None,
                           "p95_company_ms": ms[min(len(ms) - 1, int(len(ms) * 0.95))] if ms else None},
            "phase_seconds": self.timings,
            "budget_plan": self.plan,
            "bulk_snapshot": self.bulk_meta,
            "notes": self.notes,
            "third_party_cost_usd": round(self.budget.cost_usd, 4),
            "models": [],
        }
        (out / "run-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / "identity-audit.md").write_text(identity_audit(envelopes, self.run_id), encoding="utf-8")
        self.finished.set()
        return report


def validate(envelopes: list[dict], orgs: list[str]) -> dict[str, Any]:
    emitted = [e["organisation_number"] for e in envelopes]
    bad_states = [(e["organisation_number"], f, s["state"]) for e in envelopes for f, s in e["availability"].items() if s["state"] not in STATES]
    claims_without_evidence = 0
    zero_for_missing = 0
    for e in envelopes:
        ev_ids = {x["id"] for x in e["evidence"]} | {x["id"] for x in e.get("prior_evidence", [])}
        for c in e["claims"]:
            if c.get("availability", "available") != "available":
                if c["value"] is not None or c["availability"] not in STATES:
                    zero_for_missing += 1
                continue
            if not c["evidence_ids"] or any(i not in ev_ids for i in c["evidence_ids"]):
                claims_without_evidence += 1
            if c["value"] is None:
                zero_for_missing += 1
        for x in e["evidence"]:
            if not (x.get("source_url") and x.get("retrieved_at") and x.get("content_sha256")):
                claims_without_evidence += 1
    checks = {
        "one_envelope_per_input": emitted == orgs,
        "unique_organisation_numbers": len(set(emitted)) == len(emitted),
        "all_family_states_valid": not bad_states,
        "every_claim_has_evidence": claims_without_evidence == 0,
        "no_null_values_published": zero_for_missing == 0,
        "all_families_present": all(set(FAMILIES) <= set(e["availability"]) for e in envelopes),
    }
    return {"passed": all(checks.values()), "checks": checks, "invalid_states": bad_states[:20]}


def identity_audit(envelopes: list[dict], run_id: str) -> str:
    """Human-reviewable list of every published website (with proof) and every held-back candidate."""
    lines = [f"# Identity audit — {run_id}", "", "## Published official websites", "",
             "| Company | Org. nr | Website | Proof |", "|---|---|---|---|"]
    held = []
    for e in envelopes:
        evidence = {x["id"]: x for x in e.get("evidence", [])}
        for c in e.get("claims", []):
            if c.get("field") == "official_website" and c.get("availability", "available") == "available":
                ev = evidence.get(c["evidence_ids"][0], {})
                proof = (ev.get("identity_reason") or "") + " — " + (ev.get("claim_span") or "")[:140]
                lines.append(f"| {e.get('name')} | {e['organisation_number']} | {c['value']} | {proof.replace('|', '/')} |")
        for cand in e.get("unpublished_candidates", []):
            if cand.get("family") == "website":
                held.append(f"| {e.get('name')} | {e['organisation_number']} | {cand.get('candidate')} | {cand.get('source')} | "
                            f"{cand.get('decision')} | {str(cand.get('reason')).replace('|', '/')} |")
    lines += ["", "## Held back (never published)", "", "| Company | Org. nr | Candidate | Source | Decision | Reason |",
              "|---|---|---|---|---|---|", *held, ""]
    return "\n".join(lines)
