// Headless check of the live console: loads it from a running server in jsdom, replays a scripted stream
// (log lines, @event company lines, a benchmark table) and drives the feed, "why" dialog, results and run diff.
// Nothing is started on the server: /api/state and /api/diff are real, the stream is simulated.
// Setup once: npm install --no-save jsdom@24.1.3
// Usage: uv run --group dev signalpost serve   then   node eval/console_check.cjs [http://127.0.0.1:8765]
const { JSDOM, VirtualConsole } = require("jsdom");
const base = process.argv[2] || "http://127.0.0.1:8765";
const errs = [], problems = [];
const wait = ms => new Promise(f => setTimeout(f, ms));
const FAMS = ["identity", "status", "industry", "financials", "leadership", "locations", "group", "website", "social_profiles", "contact", "description", "jobs", "activity"];
function script(kind) {
  if (kind === "benchmark") return ["# Benchmark report", "", "### out-ui — run-x @ abc", "", "12 companies · valid=True", "",
    "| Family | Available | 95% CI | Ambiguous (abstained) | Not available | Failed/blocked | Claims |", "|---|---|---|---|---|---|---|",
    "| identity | 100% | 76%–100% | 0% | 0% | 0% | 168 |", "| website | 75% | 47%–91% | 8% | 17% | 0% | 9 |", "@exit 0"];
  const ev = (org, name, web) => "@event " + JSON.stringify({ kind: "company", org, name, ms: 4200, requests: 11, claims: 120,
    budget: { requests: 1500, elapsed: 30 }, website: web, errors: [],
    states: Object.fromEntries(FAMS.map((f, i) => [f, [i % 5 === 4 ? "ambiguous" : i % 3 === 2 ? "not_available" : "available", "reason for " + f]])),
    candidates: [{ family: "website", candidate: "https://example-name.no/", source: "name_slug_guess", decision: "rejected", reason: "site presents a different organisation number (999999999)" }] });
  return ["[signalpost] run run-test: 2 organisations -> out-console", "[registry] live entities 2/2 errors=[]", "[web] watchdog: slow host skipped",
    ev("923609016", "EQUINOR ASA", "https://www.equinor.com/"), ev("984661185", "POSTEN BRING AS", null),
    "[companies] 2/2 done, requests=1500, t=30s", "Traceback (most recent call last): simulated", "[done] envelopes=2/2 valid=True requests=1500 time=30s cost=$0.0", "@exit 0"];
}
(async () => {
  const html = await (await fetch(base + "/")).text();
  const vc = new VirtualConsole();
  vc.on("jsdomError", e => errs.push(String(e.message || e)));
  let current = "run";
  const dom = new JSDOM(html, {
    runScripts: "dangerously", url: base + "/", virtualConsole: vc, pretendToBeVisual: true,
    beforeParse(w) {
      w.fetch = (u, o) => fetch(new URL(u, base), o);
      w.requestAnimationFrame = f => setTimeout(f, 0);
      w.EventSource = class { constructor() { this.readyState = 1; const lines = script(current); let i = 0;
        const tick = () => { if (i < lines.length && this.readyState !== 2) { this.onmessage && this.onmessage({ data: JSON.stringify(lines[i++]) }); setTimeout(tick, 5); } }; setTimeout(tick, 10); }
        close() { this.readyState = 2; } };
    }
  });
  const w = dom.window, doc = w.document, $ = id => doc.getElementById(id);
  const scan = label => { const t = doc.querySelector("main").textContent + $("dlg").textContent; for (const bad of ["[object", "undefined", "NaN"]) if (t.includes(bad)) problems.push(`${label}: rendered "${bad}"`); };
  await wait(1500);
  console.log("runs listed:", doc.querySelectorAll(".runs tbody tr").length, "| diff options:", $("diffA").options.length);
  scan("initial");
  // live run
  current = "run"; w.startStream("run", "out-console"); await wait(400);
  console.log("feed cards:", doc.querySelectorAll(".co").length, "| live coverage rows:", doc.querySelectorAll("#cov .covrow").length, "| status:", $("statusText").textContent);
  console.log("meters:", [...doc.querySelectorAll(".meter")].map(m => m.className.replace("meter", "").trim() || "ok").join(","), "| terminal lines:", $("termCount").textContent);
  if (doc.querySelectorAll("#cov .covrow").length !== 13) problems.push("live coverage did not render 13 families");
  const lvl = [...$("lvl").querySelectorAll("button")].find(b => b.textContent === "Errors"); lvl.click();
  console.log("errors filter ->", doc.querySelectorAll("#term .ln").length, "line(s)");
  [...$("lvl").querySelectorAll("button")].find(b => b.textContent === "All").click();
  doc.querySelector(".co").click(); await wait(50);
  console.log("why dialog open:", $("dlg").hasAttribute("open"), "| gate rows:", $("dlgBody").querySelectorAll("tbody tr").length);
  const rerun = [...$("dlgBody").querySelectorAll("button")].find(b => /Re-run/.test(b.textContent)); rerun.click(); await wait(50);
  console.log("re-run form prefilled:", $("org") && $("org").value);
  scan("after run");
  // benchmark rendering
  current = "benchmark"; w.startStream("benchmark", "out-ui"); await wait(300);
  console.log("benchmark tables:", $("results").querySelectorAll("table").length, "| numeric cols:", $("results").querySelectorAll("th.num").length);
  if (!$("results").querySelector("table")) problems.push("benchmark output was not rendered as a table");
  scan("after benchmark");
  // diff two runs (real server)
  const opts = [...$("diffA").options].map(o => o.value);
  const hist = opts.find(v => v.includes("/history/"));
  if (hist) { $("diffA").value = hist; $("diffB").value = hist.split("/")[0]; $("diffGo").click(); await wait(2500);
    console.log("diff tiles:", [...$("diff").querySelectorAll(".tile")].map(t => t.textContent).join(" | ")); scan("after diff"); }
  else console.log("no archived run to diff");
  console.log("errors:", errs.slice(0, 8));
  console.log("problems:", problems);
  process.exit(errs.length || problems.length ? 1 : 0);
})();
