// Headless UI check: visits every showcase route in jsdom, drives the main interactions and reports JS errors.
// Setup once: npm install --no-save jsdom@24.1.3   Usage: node eval/ui_check.cjs "<absolute path to out-x/site>"
// Exit code 1 when any JS error is raised or a rendered view contains "undefined" / "NaN" / "[object Object]".
const { JSDOM, VirtualConsole } = require("jsdom");
const fs = require("fs"), path = require("path");
const site = process.argv[2];
const html = fs.readFileSync(path.join(site, "index.html"), "utf8");
const errs = [], problems = [];
const vc = new VirtualConsole();
vc.on("jsdomError", e => errs.push(String(e.message || e)));
vc.on("error", e => errs.push("console.error: " + String(e && e.message || e)));
const dom = new JSDOM(html, {
  runScripts: "dangerously", resources: "usable", url: "file:///" + site.replace(/\\/g, "/") + "/index.html", virtualConsole: vc, pretendToBeVisual: true,
  beforeParse(w) { w.matchMedia = () => ({ matches: false, addEventListener() {} }); w.scrollTo = () => {}; w.Element.prototype.scrollIntoView = function () {}; w.print = () => {}; }
});
const w = dom.window, doc = w.document;
const envs = fs.readFileSync(path.join(site, "..", "envelopes.jsonl"), "utf8").split("\n").filter(Boolean).map(JSON.parse);
const rich = envs.slice().sort((a, b) => b.claims.length - a.claims.length)[0].organisation_number;
const orgs = envs.slice(0, 3).map(e => e.organisation_number);
const wait = ms => new Promise(f => setTimeout(f, ms));
const text = () => doc.getElementById("app").textContent;
const drawerOpen = () => doc.getElementById("drawer").classList.contains("open");
function scan(label) {
  const t = text();
  for (const bad of ["undefined", "NaN", "[object Object]"]) if (t.includes(bad)) problems.push(`${label}: rendered "${bad}"`);
}
function key(k, target) { (target || doc.body).dispatchEvent(new w.KeyboardEvent("keydown", { key: k, bubbles: true })); }
async function go(hash, label) {
  w.location.hash = hash;
  await wait(700);
  const t = text();
  console.log((label || hash).padEnd(34), String(t.length).padStart(6), t.slice(0, 70).replace(/\s+/g, " "));
  if (t.length < 40) problems.push(`${label || hash}: view looks empty`);
  scan(label || hash);
}
(async () => {
  await wait(300);
  await go("#/", "overview");
  await go("#/companies", "explorer");
  const sortBtn = doc.querySelector("th .sortbtn");
  if (sortBtn) { doc.querySelectorAll("th .sortbtn")[3].click(); await wait(100); console.log("explorer sort -> hash:", w.location.hash); }
  await go("#/companies?fam=website&st=available&sort=rev&dir=desc", "explorer filtered");
  await go("#/companies?q=zzzzzz", "explorer empty");
  await go("#/companies/has:financials", "explorer legacy link");
  await go("#/c/" + rich, "profile (richest)");
  const cite = doc.querySelector(".brief .cite") || doc.querySelector(".cite");
  if (cite) cite.click();
  console.log("drawer via citation:", drawerOpen(), "| focus in drawer:", doc.getElementById("drawer").contains(doc.activeElement), "|", doc.getElementById("dbody").textContent.slice(0, 70).replace(/\s+/g, " "));
  if (!drawerOpen()) problems.push("citation did not open the evidence drawer");
  key("Escape");
  console.log("drawer closed by Esc:", !drawerOpen());
  if (drawerOpen()) problems.push("Esc did not close the drawer");
  const bar = doc.querySelector(".chart g.pt");
  if (bar) { bar.dispatchEvent(new w.MouseEvent("click", { bubbles: true })); console.log("drawer via chart bar:", drawerOpen(), "|", doc.getElementById("dtitle").textContent); if (!drawerOpen()) problems.push("chart bar did not open evidence"); key("Escape"); }
  else console.log("no financial chart on this profile");
  const seg = doc.querySelectorAll(".seg[role=group] button");
  const grp = [...seg].find(b => /Group|Konsern/.test(b.textContent));
  if (grp) { grp.click(); await wait(50); console.log("account toggle -> group charts:", doc.querySelectorAll(".chart").length); }
  const src = doc.querySelector("dl.kv .src");
  if (src) { src.click(); console.log("drawer via source button:", drawerOpen()); key("Escape"); }
  for (const o of orgs) await go("#/c/" + o, "profile " + o);
  await go("#/compare/" + orgs.join(","), "compare (3)");
  console.log("compare columns:", doc.querySelectorAll(".cmp thead th").length - 1, "| diff rows:", doc.querySelectorAll(".cmp tr.diff").length);
  const cmpVal = doc.querySelector(".cmp .linkbtn");
  if (cmpVal) { cmpVal.click(); console.log("drawer via compare cell:", drawerOpen()); key("Escape"); }
  await go("#/compare", "compare (stored)");
  await go("#/changes", "changes");
  await go("#/changes?mat=material", "changes material");
  await go("#/method", "method");
  // language toggle
  const no = [...doc.querySelectorAll("#lang button")].find(b => b.textContent === "NO");
  no.click(); await wait(400);
  console.log("lang NO -> html lang:", doc.documentElement.lang, "| nav:", doc.getElementById("nav").textContent.trim().slice(0, 60));
  await go("#/", "overview (NO)");
  await go("#/c/" + rich, "profile (NO)");
  [...doc.querySelectorAll("#lang button")].find(b => b.textContent === "EN").click(); await wait(200);
  // theme cycle
  const th = doc.getElementById("theme");
  th.click(); console.log("theme ->", doc.documentElement.dataset.theme || "system"); th.click(); console.log("theme ->", doc.documentElement.dataset.theme || "system"); th.click();
  // keyboard shortcuts: g m, ?, /
  key("g"); key("m"); await wait(500);
  console.log("g m ->", w.location.hash);
  if (!w.location.hash.startsWith("#/method")) problems.push("g m shortcut did not navigate");
  key("?"); console.log("? opens shortcuts:", drawerOpen(), doc.getElementById("dtitle").textContent); key("Escape");
  key("/"); console.log("/ focuses search:", doc.activeElement && doc.activeElement.id === "q");
  // typeahead
  const q = doc.getElementById("q");
  q.value = envs[0].name.slice(0, 4); q.dispatchEvent(new w.Event("input", { bubbles: true }));
  console.log("typeahead options:", doc.querySelectorAll(".searchbox .ta li[role=option]").length);
  key("ArrowDown", q); key("Enter", q); await wait(600);
  console.log("typeahead Enter ->", w.location.hash);
  await go("#/c/000000000", "profile (unknown org)");
  console.log("errors:", errs.slice(0, 8));
  console.log("problems:", problems.slice(0, 12));
  process.exit(errs.length || problems.length ? 1 : 0);
})();
