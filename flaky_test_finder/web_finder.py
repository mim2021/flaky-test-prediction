"""Step 9 (final): the web page with three charts, the table and a Download CSV button.

It starts a small web server on YOUR computer only (127.0.0.1).
You open the page in your browser, choose a folder with XML reports, and press the button.
The page sends the files to this program, and this program uses the same finder code
as before (read_reports and sort_tests). It sends back the warnings and one row
for every test, and the page shows them as a coloured table.
The Download CSV button saves the same table as flaky_report.csv (made inside your browser).

How to run:   python web_finder.py
Then open     http://127.0.0.1:8000     (the program tries to open it for you)
To stop it:   press Ctrl+C in the cmd window
"""
import json
import tempfile
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from flaky_test_finder import (CONFIDENCE, EXAMPLE_RATE, FIX_FIRST_RATE,
                               read_reports, reruns_needed, sort_tests)

HOST = "127.0.0.1"   # only this computer can reach the page, so nothing leaves your computer
PORT = 8000

PAGE = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flaky Test Finder</title>
<style>
  :root {
    --bg: #f9f9f7; --surface: #fcfcfb; --text: #0b0b0b; --text2: #52514e; --muted: #898781;
    --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
    --c-flaky: #2a78d6; --c-broken: #d03b3b; --c-healthy: #898781;
    --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a;
    --flaky-bg: #e8f0fb; --flaky-text: #1c4a85;
    --broken-bg: #fbe9e9; --broken-text: #8a1c1c;
    --healthy-bg: #f1f0ec; --healthy-text: #52514e;
    --warn-bg: #fff8d6; --warn-text: #5c4a00;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0d0d0d; --surface: #1a1a19; --text: #f0efec; --text2: #c3c2b7; --muted: #898781;
      --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
      --c-flaky: #3987e5; --c-broken: #e66767; --c-healthy: #898781;
      --s1: #3987e5; --s2: #d95926; --s3: #199e70;
      --flaky-bg: #1c2a3d; --flaky-text: #a9c8f2;
      --broken-bg: #3a2022; --broken-text: #f0b0b0;
      --healthy-bg: #232321; --healthy-text: #c3c2b7;
      --warn-bg: #3a3514; --warn-text: #f0e08a;
    }
  }
  body { background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         max-width: 1280px; margin: 40px auto; padding: 0 16px; }
  button { padding: 8px 16px; font-size: 16px; }
  #summary { margin-top: 24px; font-size: 18px; }
  .warning { background: var(--warn-bg); color: var(--warn-text); padding: 8px 12px;
             margin: 8px 0; border-radius: 4px; }

  .charts { display: grid; grid-template-columns: 1fr 1.5fr; gap: 16px; margin-top: 16px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; min-width: 0; }
  .card.wide { grid-column: 1 / -1; }
  .card h2 { font-size: 13px; letter-spacing: 0.04em; text-transform: uppercase; color: var(--text2); margin: 0 0 4px; font-weight: 600; }
  .card p.sub { font-size: 13px; color: var(--muted); margin: 0 0 10px; }
  .card svg { width: 100%; height: auto; display: block; }
  .scroll { overflow-x: auto; }
  .table-scroll { overflow-x: auto; }
  .card svg text { font-family: inherit; }
  .legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--text2); margin-top: 8px; }
  .legend span.item { display: inline-flex; align-items: center; gap: 6px; }
  .key-box { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
  .key-line { width: 16px; height: 2px; border-radius: 1px; display: inline-block; }
  .legend b { color: var(--text); font-weight: 600; }
  .empty { color: var(--muted); font-size: 14px; padding: 24px 0; }

  #tip { position: fixed; display: none; z-index: 10; pointer-events: none; max-width: 300px;
         background: var(--surface); color: var(--text); border: 1px solid var(--axis); border-radius: 6px;
         padding: 8px 10px; font-size: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.18); }
  #tip .tt { color: var(--text2); margin-bottom: 4px; }
  #tip .row { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
  #tip .val { font-weight: 600; color: var(--text); font-size: 13px; }
  #tip .nm { color: var(--text2); }

  table { border-collapse: collapse; width: 100%; margin-top: 16px; }
  th, td { text-align: left; padding: 8px; border-bottom: 1px solid var(--grid); }
  td:nth-child(n+2) { white-space: nowrap; }
  tr.FLAKY td { background: var(--flaky-bg); color: var(--flaky-text); }
  tr.BROKEN td { background: var(--broken-bg); color: var(--broken-text); }
  tr.HEALTHY td { background: var(--healthy-bg); color: var(--healthy-text); }

  @media (max-width: 720px) { .charts { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<h1>Flaky Test Finder</h1>
<p>Choose a folder with JUnit XML reports. One file = one full test run of the same code.
The files stay on your computer.</p>
<input type="file" id="folder" webkitdirectory multiple>
<button id="go">Find flaky tests</button>
<div id="summary"></div>
<div id="warnings"></div>
<div id="charts" class="charts"></div>
<div id="table"></div>
<button id="download" style="display:none; margin-top:16px;">Download CSV</button>
<div id="tip" role="tooltip"></div>

<script>
const summary = document.getElementById("summary");
const warnings = document.getElementById("warnings");
const chartsBox = document.getElementById("charts");
const tableBox = document.getElementById("table");
const downloadButton = document.getElementById("download");
const tip = document.getElementById("tip");
const SVG_NS = "http://www.w3.org/2000/svg";
let lastData = null;   // the latest answer, kept so the Download button can use it

// ---------- small helpers ----------

// Make an SVG element. Text is always put in with textContent, so a strange test name can never run as code.
function svg(tag, attrs, parent, text) {
  const e = document.createElementNS(SVG_NS, tag);
  for (const key in attrs) { e.setAttribute(key, attrs[key]); }
  if (text !== undefined) { e.textContent = text; }
  if (parent) { parent.appendChild(e); }
  return e;
}

// Make an HTML element.
function html(tag, className, text, parent) {
  const e = document.createElement(tag);
  if (className) { e.className = className; }
  if (text !== undefined) { e.textContent = text; }
  if (parent) { parent.appendChild(e); }
  return e;
}

function shortName(fullName) {          // "shop.LoginTests.test_logout" -> "test_logout"
  const name = fullName.split(".").pop();
  return name.length > 36 ? name.slice(0, 35) + "…" : name;
}

// ---------- the tooltip (one for all charts) ----------

function showTip(event, title, items) {
  tip.innerHTML = "";
  if (title) { html("div", "tt", title, tip); }
  for (const item of items) {
    const row = html("div", "row", undefined, tip);
    const key = html("span", item.line ? "key-line" : "key-box", undefined, row);
    key.style.background = item.color;
    html("span", "val", item.value, row);
    html("span", "nm", item.name, row);
  }
  tip.style.display = "block";
  const box = tip.getBoundingClientRect();
  let x = event.clientX + 14, y = event.clientY + 14;
  if (x + box.width > window.innerWidth - 8) { x = event.clientX - box.width - 14; }
  if (y + box.height > window.innerHeight - 8) { y = event.clientY - box.height - 14; }
  tip.style.left = Math.max(8, x) + "px";
  tip.style.top = Math.max(8, y) + "px";
}
function hideTip() { tip.style.display = "none"; }

function makeCard(title, subtitle, wide) {
  const card = html("div", "card" + (wide ? " wide" : ""), undefined, chartsBox);
  html("h2", "", title, card);
  html("p", "sub", subtitle, card);
  return card;
}

// ---------- chart 1: donut (part of the whole) ----------

function drawDonut(data) {
  const card = makeCard("Test health", "How many tests are in each group", false);
  const parts = [
    { name: "Flaky", n: data.flaky, color: "var(--c-flaky)" },
    { name: "Broken", n: data.broken, color: "var(--c-broken)" },
    { name: "Healthy", n: data.healthy, color: "var(--c-healthy)" },
  ];
  const total = parts.reduce((sum, p) => sum + p.n, 0);
  const shown = parts.filter(p => p.n > 0);

  const chart = svg("svg", { viewBox: "0 0 200 200", role: "img",
    "aria-label": "Donut chart: " + parts.map(p => p.n + " " + p.name.toLowerCase()).join(", ") }, card);
  chart.style.maxWidth = "230px";
  chart.style.margin = "0 auto";

  const radius = 72, width = 20, circumference = 2 * Math.PI * radius;
  const gap = shown.length > 1 ? 2 : 0;           // a 2px gap in the surface colour between segments
  let used = 0;
  for (const p of shown) {
    const length = p.n / total * circumference;
    const dash = Math.max(length - gap, 0.5);
    const ring = svg("circle", { cx: 100, cy: 100, r: radius, fill: "none", "stroke-width": width,
      "stroke-dasharray": dash + " " + (circumference - dash), "stroke-dashoffset": -used,
      transform: "rotate(-90 100 100)" }, chart);
    ring.style.stroke = p.color;
    ring.addEventListener("pointermove", e => showTip(e, null,
      [{ color: p.color, value: p.n + " tests", name: p.name + " (" + Math.round(p.n / total * 100) + "%)" }]));
    ring.addEventListener("pointerleave", hideTip);
    used += length;
  }
  const big = svg("text", { x: 100, y: 104, "text-anchor": "middle", "font-size": 28, "font-weight": 600 }, chart, String(total));
  big.style.fill = "var(--text)";
  const small = svg("text", { x: 100, y: 122, "text-anchor": "middle", "font-size": 11 }, chart, "tests");
  small.style.fill = "var(--muted)";

  const legend = html("div", "legend", undefined, card);
  for (const p of parts) {
    const item = html("span", "item", undefined, legend);
    html("span", "key-box", undefined, item).style.background = p.color;
    item.appendChild(document.createTextNode(p.name + " "));
    html("b", "", String(p.n), item);
  }
}

// ---------- chart 2: bars (failure rate of each test that is not healthy) ----------

function drawBars(data) {
  const card = makeCard("Failure rate by test", "Share of runs in which the test failed", false);
  const items = data.rows.filter(r => r.label !== "HEALTHY")
                         .sort((a, b) => b.rate_value - a.rate_value).slice(0, 10);
  if (items.length === 0) {
    html("div", "empty", "No flaky or broken tests found in these runs.", card);
    return;
  }

  const W = 460, left = 6, right = 46, top = 24, rowH = 44, bottom = 26;
  const plotW = W - left - right;
  const H = top + items.length * rowH + bottom;
  const wrap = html("div", "scroll", undefined, card);
  const chart = svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
    "aria-label": "Bar chart of failure rates: " + items.map(r => shortName(r.test) + " " + r.rate).join(", ") }, wrap);
  chart.style.minWidth = "380px";

  // grid and axis labels (solid hairlines)
  for (const t of [0, 25, 50, 75, 100]) {
    const x = left + plotW * t / 100;
    svg("line", { x1: x, x2: x, y1: top - 4, y2: H - bottom, "stroke-width": 1 }, chart).style.stroke = t === 0 ? "var(--axis)" : "var(--grid)";
    const label = svg("text", { x: x, y: H - 8, "text-anchor": t === 0 ? "start" : (t === 100 ? "end" : "middle"), "font-size": 10 }, chart, t + "%");
    label.style.fill = "var(--muted)";
  }

  // the FIX FIRST line
  const tx = left + plotW * data.fix_first_rate;
  svg("line", { x1: tx, x2: tx, y1: top - 10, y2: H - bottom, "stroke-width": 1 }, chart).style.stroke = "var(--muted)";
  const tlabel = svg("text", { x: tx + 5, y: top - 12, "font-size": 10 }, chart, Math.round(data.fix_first_rate * 100) + "% = FIX FIRST");
  tlabel.style.fill = "var(--muted)";

  items.forEach((r, i) => {
    const y0 = top + i * rowH;
    const color = r.label === "BROKEN" ? "var(--c-broken)" : "var(--c-flaky)";
    const name = svg("text", { x: left, y: y0 + 12, "font-size": 12 }, chart, shortName(r.test));
    name.style.fill = "var(--text2)";


    // bar: square at the baseline, 4px round at the data end
    const barW = Math.max(r.rate_value * plotW, 3), h = 14, y = y0 + 19, rad = Math.min(4, barW, h / 2);
    const x1 = left + barW;
    const d = "M" + left + "," + y + " H" + (x1 - rad) + " a" + rad + "," + rad + " 0 0 1 " + rad + "," + rad +
              " V" + (y + h - rad) + " a" + rad + "," + rad + " 0 0 1 " + (-rad) + "," + rad + " H" + left + " Z";
    const bar = svg("path", { d: d }, chart);
    bar.style.fill = color;

    const value = svg("text", { x: x1 + 6, y: y + 11, "font-size": 12, "font-weight": 600 }, chart, r.rate);
    value.style.fill = "var(--text)";

    // a bigger invisible area on top of the row, so the tooltip is easy to hit
    const hit = svg("rect", { x: 0, y: y0, width: W, height: rowH, fill: "transparent" }, chart);
    hit.addEventListener("pointermove", e => {
      bar.style.opacity = "0.8";
      showTip(e, r.test, [{ color: color, value: r.rate, name: r.fails + " of " + r.runs + " runs failed (" + r.label.toLowerCase() + ")" }]);
    });
    hit.addEventListener("pointerleave", () => { bar.style.opacity = "1"; hideTip(); });
  });

  const legend = html("div", "legend", undefined, card);
  const kinds = [["Flaky", "var(--c-flaky)", "FLAKY"], ["Broken", "var(--c-broken)", "BROKEN"]];
  for (const [text, color, label] of kinds) {
    if (!items.some(r => r.label === label)) { continue; }
    const item = html("span", "item", undefined, legend);
    html("span", "key-box", undefined, item).style.background = color;
    item.appendChild(document.createTextNode(text));
  }
}

// ---------- chart 3: lines (how quickly reruns catch a flaky test) ----------

function drawLines(data) {
  const card = makeCard("How many reruns do you need?",
    "Chance of seeing at least one failure after k reruns, for the flakiest tests. 1 − (1 − p)^k, where p is the failure rate.", true);
  const flaky = data.rows.filter(r => r.label === "FLAKY").slice(0, 3);
  if (flaky.length === 0) {
    html("div", "empty", "No flaky tests, so there is nothing to plot.", card);
    return;
  }
  const colors = ["var(--s1)", "var(--s2)", "var(--s3)"];
  const chance = (p, k) => 1 - Math.pow(1 - p, k);

  // x axis: from 0 up to a little past the largest "reruns needed", capped at 300
  const biggest = Math.max(...flaky.map(r => r.reruns));
  let kmax = Math.max(10, Math.ceil(biggest * 1.15 / 10) * 10);
  const capped = kmax > 300;
  if (capped) { kmax = 300; }
  const step = [1, 2, 5, 10, 20, 25, 50, 100].find(s => kmax / s <= 8);

  const W = 720, H = 300, ml = 46, mr = 24, mt = 16, mb = 42;
  const pw = W - ml - mr, ph = H - mt - mb;
  const X = k => ml + pw * k / kmax;
  const Y = c => mt + ph * (1 - c);

  const wrap = html("div", "scroll", undefined, card);
  const chart = svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
    "aria-label": "Line chart: chance of seeing a failure against number of reruns. " +
      flaky.map(r => shortName(r.test) + " needs about " + r.reruns + " reruns for " + data.confidence).join("; ") }, wrap);
  chart.style.minWidth = "560px";

  for (const t of [0, 25, 50, 75, 100]) {
    svg("line", { x1: ml, x2: W - mr, y1: Y(t / 100), y2: Y(t / 100), "stroke-width": 1 }, chart).style.stroke = t === 0 ? "var(--axis)" : "var(--grid)";
    const label = svg("text", { x: ml - 8, y: Y(t / 100) + 4, "text-anchor": "end", "font-size": 11 }, chart, t + "%");
    label.style.fill = "var(--muted)";
  }
  for (let k = 0; k <= kmax; k += step) {
    const label = svg("text", { x: X(k), y: H - mb + 18, "text-anchor": "middle", "font-size": 11 }, chart, String(k));
    label.style.fill = "var(--muted)";
  }
  const xTitle = svg("text", { x: ml + pw / 2, y: H - 6, "text-anchor": "middle", "font-size": 11 }, chart,
    "Number of reruns" + (capped ? " (axis stops at 300)" : ""));
  xTitle.style.fill = "var(--muted)";

  // the confidence line (95%)
  const level = data.confidence_value;   // for example 0.95
  svg("line", { x1: ml, x2: W - mr, y1: Y(level), y2: Y(level), "stroke-width": 1 }, chart).style.stroke = "var(--muted)";
  const cl = svg("text", { x: W - mr, y: Y(level) + 15, "text-anchor": "end", "font-size": 11 }, chart, data.confidence + " sure");
  cl.style.fill = "var(--muted)";

  // the lines: 2px, round joins, plus a dot where each line reaches the confidence level
  flaky.forEach((r, i) => {
    let d = "";
    for (let k = 0; k <= kmax; k++) { d += (k === 0 ? "M" : "L") + X(k).toFixed(1) + "," + Y(chance(r.rate_value, k)).toFixed(1) + " "; }
    const line = svg("path", { d: d, fill: "none", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, chart);
    line.style.stroke = colors[i];
    if (r.reruns <= kmax) {
      const dot = svg("circle", { cx: X(r.reruns), cy: Y(chance(r.rate_value, r.reruns)), r: 4.5, "stroke-width": 2 }, chart);
      dot.style.fill = colors[i];
      dot.style.stroke = "var(--surface)";
    }
  });

  // hover: a vertical line follows the pointer and the tooltip lists every test at that number of reruns
  const cross = svg("line", { y1: mt, y2: H - mb, "stroke-width": 1, visibility: "hidden" }, chart);
  cross.style.stroke = "var(--axis)";
  const dots = flaky.map((r, i) => {
    const dot = svg("circle", { r: 4.5, "stroke-width": 2, visibility: "hidden" }, chart);
    dot.style.fill = colors[i];
    dot.style.stroke = "var(--surface)";
    return dot;
  });
  const overlay = svg("rect", { x: ml, y: mt, width: pw, height: ph, fill: "transparent" }, chart);
  overlay.addEventListener("pointermove", e => {
    const box = chart.getBoundingClientRect();
    const x = (e.clientX - box.left) * (W / box.width);
    const k = Math.min(kmax, Math.max(0, Math.round((x - ml) / pw * kmax)));
    cross.setAttribute("x1", X(k)); cross.setAttribute("x2", X(k)); cross.setAttribute("visibility", "visible");
    const items = [];
    flaky.forEach((r, i) => {
      const c = chance(r.rate_value, k);
      dots[i].setAttribute("cx", X(k)); dots[i].setAttribute("cy", Y(c)); dots[i].setAttribute("visibility", "visible");
      items.push({ color: colors[i], line: true, value: (c * 100).toFixed(1) + "%", name: shortName(r.test) });
    });
    showTip(e, "After " + k + " reruns", items);
  });
  overlay.addEventListener("pointerleave", () => {
    cross.setAttribute("visibility", "hidden");
    dots.forEach(d => d.setAttribute("visibility", "hidden"));
    hideTip();
  });

  const legend = html("div", "legend", undefined, card);
  flaky.forEach((r, i) => {
    const item = html("span", "item", undefined, legend);
    html("span", "key-line", undefined, item).style.background = colors[i];
    item.appendChild(document.createTextNode(shortName(r.test) + " (fails " + r.rate + "): "));
    html("b", "", "about " + r.reruns + " reruns", item);
  });
  if (data.rows.filter(r => r.label === "FLAKY").length > 3) {
    html("span", "item", "Showing the 3 flakiest tests.", legend);
  }
}

// ---------- the table and the CSV ----------

function cell(row, text) {
  const td = document.createElement("td");
  td.textContent = text;
  row.appendChild(td);
}

// Make one safe CSV value: wrap it in quotes, and stop Excel from running a formula.
function csvValue(value) {
  let text = String(value);
  if (/^[=+\-@]/.test(text)) { text = "'" + text; }
  return '"' + text.replace(/"/g, '""') + '"';
}

downloadButton.onclick = function () {
  const header = ["test", "label", "action", "failed_runs", "runs_seen", "failure_rate", "reruns_for_" + lastData.confidence + "_sure"];
  const lines = [header.map(csvValue).join(",")];
  for (const r of lastData.rows) {
    lines.push([r.test, r.label, r.action, r.fails, r.runs, r.rate, r.reruns].map(csvValue).join(","));
  }
  // The first character (﻿) helps Excel read the file correctly.
  const blob = new Blob(["﻿" + lines.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "flaky_report.csv";
  link.click();
  URL.revokeObjectURL(link.href);
};

// ---------- the button ----------

document.getElementById("go").onclick = async function () {
  warnings.innerHTML = "";
  chartsBox.innerHTML = "";
  tableBox.innerHTML = "";
  downloadButton.style.display = "none";
  hideTip();

  // 1. Take only the .xml files from the chosen folder.
  const files = Array.from(document.getElementById("folder").files)
                     .filter(f => f.name.toLowerCase().endsWith(".xml"));
  if (files.length === 0) {
    summary.textContent = "Please choose a folder that has .xml files.";
    return;
  }
  summary.textContent = "Reading " + files.length + " files...";

  // 2. Read the text of every file in the browser.
  const items = [];
  for (const f of files) {
    items.push({ name: f.name, text: await f.text() });
  }

  // 3. Send them to the program and wait for the answer.
  const response = await fetch("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ files: items })
  });
  const data = await response.json();

  if (data.error) {
    summary.textContent = data.error;
    return;
  }

  // 4. Show the summary line, the warnings and the three charts.
  summary.textContent = "Read " + data.reports_read + " reports. Found: "
    + data.flaky + " flaky, " + data.broken + " broken, " + data.healthy + " healthy.";
  for (const text of data.warnings) {
    html("div", "warning", text, warnings);
  }
  drawDonut(data);
  drawBars(data);
  drawLines(data);

  // 5. Build the table, one row per test (this is also the text version of the charts).
  const table = document.createElement("table");
  const head = document.createElement("tr");
  for (const title of ["Test", "Label", "Action", "Failed runs", "Failure rate", "Reruns for " + data.confidence + " sure"]) {
    const th = document.createElement("th");
    th.textContent = title;
    head.appendChild(th);
  }
  table.appendChild(head);
  for (const r of data.rows) {
    const tr = document.createElement("tr");
    tr.className = r.label;   // FLAKY, BROKEN or HEALTHY: the style picks the colour
    cell(tr, r.test);
    cell(tr, r.label);
    cell(tr, r.action);
    cell(tr, r.fails + " of " + r.runs);
    cell(tr, r.rate);
    cell(tr, r.reruns);
    table.appendChild(tr);
  }
  const tableWrap = html("div", "table-scroll", undefined, tableBox);
  tableWrap.appendChild(table);
  lastData = data;
  downloadButton.style.display = "inline-block";
};
</script>
</body>
</html>
"""


def analyze(files):
    """Run the finder on a list of {"name": ..., "text": ...} and return the answer for the page."""
    with tempfile.TemporaryDirectory() as temp_folder:
        folder = Path(temp_folder)
        for number, item in enumerate(files):
            # The number in front keeps two files with the same name apart.
            (folder / f"{number:04d}_{Path(item['name']).name}").write_text(item["text"], encoding="utf-8")

        table, report_files, commits, unreadable = read_reports(folder)
        flaky, broken, healthy, fewest_runs = sort_tests(table)

    if fewest_runs is None:
        return {"error": "The reports contain no test results."}

    # Warnings: the same ones the cmd tool prints.
    warnings = []
    if unreadable:
        names = ", ".join(name[5:] for name in unreadable)  # cut off the "0003_" number
        warnings.append(f"Could not read {len(unreadable)} file(s): {names}")
    if len(commits) > 1:
        warnings.append(f"The reports come from {len(commits)} different commits. A flaky test is one that gives "
                        "different results on the SAME code, so use runs of one commit only.")
    elif not commits:
        warnings.append("No commit information found. Make sure all runs are of the same code.")
    hidden_rate = 1 - (1 - CONFIDENCE) ** (1 / fewest_runs)
    warnings.append(f"Some tests were seen in as few as {fewest_runs} runs. A flaky test that fails in less than "
                    f"about {hidden_rate:.0%} of runs can still look healthy. To be {CONFIDENCE:.0%} sure of seeing "
                    f"a test that fails in {EXAMPLE_RATE:.0%} of runs, you need about {reruns_needed(EXAMPLE_RATE)} runs. "
                    "The failure rates are rough.")

    # One row for every test: flaky first, then broken, then healthy.
    rows = []
    for rate, name, fails, runs_seen in flaky:
        action = "FIX FIRST" if rate >= FIX_FIRST_RATE else "WATCH"
        rows.append({"test": name, "label": "FLAKY", "action": action, "fails": fails,
                     "runs": runs_seen, "rate": f"{rate:.0%}", "rate_value": rate, "reruns": reruns_needed(rate)})
    for rate, name, fails, runs_seen in broken:
        rows.append({"test": name, "label": "BROKEN", "action": "FIX", "fails": fails,
                     "runs": runs_seen, "rate": f"{rate:.0%}", "rate_value": rate, "reruns": ""})
    for rate, name, fails, runs_seen in healthy:
        rows.append({"test": name, "label": "HEALTHY", "action": "NO ACTION", "fails": fails,
                     "runs": runs_seen, "rate": f"{rate:.0%}", "rate_value": rate, "reruns": ""})

    return {
        "reports_read": len(report_files) - len(unreadable),
        "flaky": len(flaky),
        "broken": len(broken),
        "healthy": len(healthy),
        "confidence": f"{CONFIDENCE:.0%}",
        "confidence_value": CONFIDENCE,
        "fix_first_rate": FIX_FIRST_RATE,
        "warnings": warnings,
        "rows": rows,
    }


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, status, content_type, data):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        # The browser asks for the page.
        if self.path == "/":
            self.send_bytes(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
        else:
            self.send_bytes(404, "text/plain", b"Not found")

    def do_POST(self):
        # The browser sends the report files here.
        if self.path != "/analyze":
            self.send_bytes(404, "text/plain", b"Not found")
            return
        size = int(self.headers.get("Content-Length", 0))
        files = json.loads(self.rfile.read(size))["files"]
        answer = analyze(files)
        self.send_bytes(200, "application/json", json.dumps(answer).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # keep the cmd window quiet


def main():
    server = HTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"Flaky Test Finder is running at {url}")
    print("Press Ctrl+C to stop.")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
