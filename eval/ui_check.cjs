// Headless UI check: visits every showcase route in jsdom and reports JS errors.
// Setup once: npm install --no-save jsdom@24.1.3   Usage: node eval/ui_check.cjs "<absolute path to out-x/site>"
const { JSDOM, VirtualConsole } = require("jsdom");
const fs = require("fs"), path = require("path");
const site = process.argv[2];
const html = fs.readFileSync(path.join(site, "index.html"), "utf8");
const errs = [];
const vc = new VirtualConsole();
vc.on("jsdomError", e => errs.push(String(e.message || e)));
const dom = new JSDOM(html, {
  runScripts: "dangerously", resources: "usable", url: "file:///" + site + "/index.html", virtualConsole: vc, pretendToBeVisual: true,
  beforeParse(w) { w.matchMedia = () => ({ matches: false }); w.scrollTo = () => {}; }
});
const w = dom.window;
const org = JSON.parse(fs.readFileSync(path.join(site, "..", "envelopes.jsonl"), "utf8").split("\n")[0]).organisation_number;
const routes = ["#/", "#/companies", "#/c/" + org, "#/compare/" + org, "#/changes", "#/method"];
(async () => {
  for (const r of routes) {
    w.location.hash = r;
    await new Promise(f => setTimeout(f, 800));
    const t = w.document.getElementById("app").textContent;
    console.log(r.padEnd(16), t.length, t.slice(0, 80).replace(/\s+/g, " "));
    if (r.startsWith("#/c/")) {
      const c = w.document.querySelector(".cite");
      if (c) c.click();
      console.log("drawer open:", w.document.getElementById("drawer").classList.contains("open"), w.document.getElementById("dbody").textContent.slice(0, 80));
    }
  }
  console.log("errors:", errs.slice(0, 5));
  process.exit(0);
})();
