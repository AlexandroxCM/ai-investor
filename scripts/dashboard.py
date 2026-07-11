"""Local dashboard for the audit trail. Reads runs/audit.db, serves a web UI.
Usage: python scripts/dashboard.py   ->   http://localhost:8017
Read-only: it never touches trading state."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

ROOT = Path(__file__).parent.parent
DB = ROOT / "runs" / "audit.db"

app = FastAPI(title="ai-investor dashboard")


def q(sql: str, args: tuple = ()) -> list[dict]:
    if not DB.exists():
        return []
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


@app.get("/api/summary")
def summary():
    rows = q("SELECT record_json, started_at FROM runs ORDER BY started_at")
    points = []
    for r in rows:
        rec = json.loads(r["record_json"])
        eq = (rec.get("portfolio_after") or {}).get("equity")
        bm = rec.get("benchmark_value")
        if eq is not None:
            points.append({"t": r["started_at"][:19], "equity": eq, "benchmark": bm})
    stats = q("""SELECT COUNT(*) AS cycles, SUM(filled) AS fills,
                 SUM(CASE WHEN verdict='reject' THEN 1 ELSE 0 END) AS rejections,
                 SUM(CASE WHEN verdict='resize' THEN 1 ELSE 0 END) AS resizes
                 FROM runs""")[0]
    latest = points[-1] if points else {}
    edge = None
    if latest.get("equity") is not None and latest.get("benchmark") is not None:
        edge = round(latest["equity"] - latest["benchmark"], 2)
    return {"points": points, "stats": stats, "edge": edge,
            "equity": latest.get("equity"), "benchmark": latest.get("benchmark")}


@app.get("/api/runs")
def runs(limit: int = 100):
    return q("""SELECT run_id, started_at, ticker, signal, confidence, verdict,
                rules, filled, fill_price FROM runs
                ORDER BY started_at DESC LIMIT ?""", (limit,))


@app.get("/api/run/{run_id}")
def run_detail(run_id: str):
    rows = q("SELECT record_json FROM runs WHERE run_id = ?", (run_id,))
    if not rows:
        return JSONResponse({"error": "run not found"}, status_code=404)
    return json.loads(rows[0]["record_json"])


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ai-investor · audit desk</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{
  --ink:#0b0e14; --panel:#11151f; --panel-2:#151b28; --line:#232b3b;
  --paper:#e7e4da; --dim:#8a93a6; --amber:#e6a23c; --amber-soft:#e6a23c33;
  --up:#4cb782; --down:#d95f5f; --mono:'IBM Plex Mono',monospace; --sans:'IBM Plex Sans',sans-serif;
}
*{box-sizing:border-box;margin:0}
body{background:var(--ink);color:var(--paper);font-family:var(--sans);font-size:14px;line-height:1.5}
a{color:inherit}
.wrap{max-width:1100px;margin:0 auto;padding:20px 20px 60px}
header{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:20px}
header h1{font:600 15px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--amber)}
header .sub{font:400 12px var(--mono);color:var(--dim)}
.board{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin-bottom:20px}
.cell{background:var(--panel);padding:14px 16px}
.cell .k{font:500 10px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--dim);margin-bottom:6px}
.cell .v{font:600 22px var(--mono)}
.cell .v.up{color:var(--up)}.cell .v.down{color:var(--down)}
.panel{background:var(--panel);border:1px solid var(--line);margin-bottom:20px}
.panel h2{font:500 11px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--dim);padding:12px 16px;border-bottom:1px solid var(--line)}
.chartbox{padding:16px;height:240px}
table{width:100%;border-collapse:collapse;font:400 13px var(--mono)}
th{font:500 10px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--dim);text-align:left;padding:10px 16px;border-bottom:1px solid var(--line)}
td{padding:9px 16px;border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap}
tr:hover td{background:var(--panel-2)}
tr:focus-visible td{outline:2px solid var(--amber);outline-offset:-2px}
.sig-buy{color:var(--up)}.sig-sell{color:var(--down)}.sig-hold{color:var(--dim)}
.stamp{display:inline-block;font:600 10px var(--mono);letter-spacing:.1em;text-transform:uppercase;padding:2px 8px;border:1px solid}
.stamp.approve{color:var(--up);border-color:var(--up)}
.stamp.reject{color:var(--down);border-color:var(--down)}
.stamp.resize{color:var(--amber);border-color:var(--amber)}
.empty{padding:40px 16px;text-align:center;color:var(--dim);font-family:var(--mono);font-size:13px}
/* transcript drawer */
#drawer{position:fixed;inset:0 0 0 auto;width:min(620px,100%);background:var(--panel);border-left:1px solid var(--line);transform:translateX(100%);transition:transform .25s ease;overflow-y:auto;z-index:10}
#drawer.open{transform:none}
@media (prefers-reduced-motion:reduce){#drawer{transition:none}}
#drawer .head{position:sticky;top:0;background:var(--panel);display:flex;justify-content:space-between;align-items:center;padding:14px 20px;border-bottom:1px solid var(--line)}
#drawer .head .t{font:600 13px var(--mono);letter-spacing:.08em}
#drawer .head button{background:none;border:1px solid var(--line);color:var(--dim);font:500 11px var(--mono);padding:5px 12px;cursor:pointer;letter-spacing:.08em}
#drawer .head button:hover{color:var(--paper);border-color:var(--dim)}
.transcript{padding:20px}
.turn{margin-bottom:18px;padding-left:14px;border-left:2px solid var(--line)}
.turn .who{font:600 10px var(--mono);letter-spacing:.14em;text-transform:uppercase;margin-bottom:5px}
.turn.report .who{color:var(--dim)}
.turn.decision{border-left-color:var(--amber)}.turn.decision .who{color:var(--amber)}
.turn.skeptic{border-left-color:var(--down)}.turn.skeptic .who{color:var(--down)}
.turn.rebuttal .who{color:var(--paper)}
.turn.risk.approve{border-left-color:var(--up)}.turn.risk.reject{border-left-color:var(--down)}
.turn p{color:var(--paper);font-size:13px}
.turn .meta{font:400 11px var(--mono);color:var(--dim);margin-top:4px}
.scorebar{display:inline-block;height:6px;background:var(--line);width:80px;vertical-align:middle;margin:0 6px;position:relative}
.scorebar i{position:absolute;top:0;bottom:0;left:50%;background:var(--amber)}
overlay{display:none}
#overlay{position:fixed;inset:0;background:#0008;opacity:0;pointer-events:none;transition:opacity .25s;z-index:9}
#overlay.open{opacity:1;pointer-events:auto}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>ai-investor · audit desk</h1>
    <span class="sub" id="asof">reading runs/audit.db…</span>
  </header>

  <div class="board" id="board"></div>

  <div class="panel">
    <h2>Equity vs benchmark</h2>
    <div class="chartbox"><canvas id="chart"></canvas></div>
  </div>

  <div class="panel">
    <h2>Run ledger — select a row to read the full reasoning chain</h2>
    <div style="overflow-x:auto">
    <table id="ledger">
      <thead><tr><th>Time</th><th>Ticker</th><th>Signal</th><th>Conf</th><th>Verdict</th><th>Fill</th></tr></thead>
      <tbody></tbody>
    </table>
    </div>
    <div class="empty" id="empty" hidden>No runs yet. Run a cycle: python scripts/run_cycle.py</div>
  </div>
</div>

<div id="overlay" onclick="closeDrawer()"></div>
<aside id="drawer" aria-label="Reasoning transcript">
  <div class="head"><span class="t" id="d-title"></span><button onclick="closeDrawer()">Close</button></div>
  <div class="transcript" id="d-body"></div>
</aside>

<script>
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const money=v=>v==null?'—':'$'+Number(v).toFixed(2);

async function load(){
  const s=await (await fetch('/api/summary')).json();
  $('#asof').textContent='as of '+(s.points.at(-1)?.t??'—')+' UTC';
  const edgeCls=s.edge>0?'up':s.edge<0?'down':'';
  $('#board').innerHTML=`
    <div class="cell"><div class="k">Equity</div><div class="v">${money(s.equity)}</div></div>
    <div class="cell"><div class="k">Benchmark (VOO)</div><div class="v">${money(s.benchmark)}</div></div>
    <div class="cell"><div class="k">Edge vs boring</div><div class="v ${edgeCls}">${s.edge==null?'—':(s.edge>0?'+':'')+s.edge.toFixed(2)}</div></div>
    <div class="cell"><div class="k">Cycles</div><div class="v">${s.stats.cycles??0}</div></div>
    <div class="cell"><div class="k">Fills</div><div class="v">${s.stats.fills??0}</div></div>
    <div class="cell"><div class="k">Risk rejections</div><div class="v">${s.stats.rejections??0}</div></div>`;
  drawChart(s.points);
  const runs=await (await fetch('/api/runs')).json();
  const tb=$('#ledger tbody'); tb.innerHTML='';
  $('#empty').hidden=runs.length>0;
  for(const r of runs){
    const tr=document.createElement('tr'); tr.tabIndex=0;
    tr.innerHTML=`<td>${esc(r.started_at.slice(0,19).replace('T',' '))}</td>
      <td>${esc(r.ticker)}</td>
      <td class="sig-${esc(r.signal)}">${esc(r.signal??'—')}</td>
      <td>${r.confidence==null?'—':Number(r.confidence).toFixed(2)}</td>
      <td><span class="stamp ${esc(r.verdict)}">${esc(r.verdict??'—')}${r.rules?' · '+esc(r.rules):''}</span></td>
      <td>${r.filled?money(r.fill_price):'—'}</td>`;
    const open=()=>openRun(r.run_id);
    tr.onclick=open; tr.onkeydown=e=>{if(e.key==='Enter')open()};
    tb.appendChild(tr);
  }
}

let chart;
function drawChart(pts){
  if(chart)chart.destroy();
  chart=new Chart($('#chart'),{type:'line',data:{
    labels:pts.map(p=>p.t.slice(5,16).replace('T',' ')),
    datasets:[
      {label:'Portfolio',data:pts.map(p=>p.equity),borderColor:'#e6a23c',backgroundColor:'#e6a23c22',tension:.25,pointRadius:2,fill:true},
      {label:'VOO benchmark',data:pts.map(p=>p.benchmark),borderColor:'#8a93a6',borderDash:[5,4],tension:.25,pointRadius:0}
    ]},
    options:{maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8a93a6',font:{family:'IBM Plex Mono',size:11}}}},
      scales:{x:{ticks:{color:'#8a93a6',font:{family:'IBM Plex Mono',size:10},maxTicksLimit:8},grid:{color:'#232b3b'}},
              y:{ticks:{color:'#8a93a6',font:{family:'IBM Plex Mono',size:10}},grid:{color:'#232b3b'}}}}});
}

function bar(score){
  const w=Math.min(Math.abs(score)*40,40);
  const left=score>=0?'50%':`calc(50% - ${w}px)`;
  return `<span class="scorebar"><i style="left:${left};width:${w}px"></i></span>`;
}

async function openRun(id){
  const r=await (await fetch('/api/run/'+id)).json();
  $('#d-title').textContent=id;
  let h='';
  for(const rep of r.reports??[])
    h+=`<div class="turn report"><div class="who">${esc(rep.agent)} report</div>
        <p>${esc(rep.summary)}</p>
        <div class="meta">score ${rep.score>=0?'+':''}${rep.score} ${bar(rep.score)} conf ${rep.confidence}</div></div>`;
  if(r.proposal)
    h+=`<div class="turn decision"><div class="who">Decision — ${esc(r.proposal.signal)} ${esc(r.proposal.ticker)}</div>
        <p>${esc(r.proposal.thesis)}</p>
        <div class="meta">qty ${r.proposal.quantity} · confidence ${r.proposal.confidence}</div></div>`;
  for(const o of r.objections??[])
    h+=`<div class="turn skeptic"><div class="who">Skeptic · ${esc(o.id)}</div><p>${esc(o.text)}</p></div>`;
  for(const rb of r.rebuttals??[])
    h+=`<div class="turn rebuttal"><div class="who">Rebuttal · ${esc(rb.objection_id)}</div><p>${esc(rb.response)}</p></div>`;
  if(r.verdict)
    h+=`<div class="turn risk ${esc(r.verdict.action)}"><div class="who">Risk manager</div>
        <p><span class="stamp ${esc(r.verdict.action)}">${esc(r.verdict.action)}</span>
        ${r.verdict.rules_triggered?.length?' rules: '+esc(r.verdict.rules_triggered.join(', ')):''}</p>
        ${r.verdict.note?`<div class="meta">${esc(r.verdict.note)}</div>`:''}</div>`;
  if(r.order)
    h+=`<div class="turn report"><div class="who">Execution</div>
        <p>${esc(r.order.status)} ${r.order.fill_price?'@ '+money(r.order.fill_price):''}</p></div>`;
  if(r.portfolio_after)
    h+=`<div class="turn report"><div class="who">Portfolio after</div>
        <p>cash ${money(r.portfolio_after.cash)} · equity ${money(r.portfolio_after.equity)}</p></div>`;
  $('#d-body').innerHTML=h;
  $('#drawer').classList.add('open');$('#overlay').classList.add('open');
}
function closeDrawer(){$('#drawer').classList.remove('open');$('#overlay').classList.remove('open')}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer()});
load();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


if __name__ == "__main__":
    print("Audit desk: http://localhost:8017  (Ctrl+C to stop)")
    uvicorn.run(app, host="127.0.0.1", port=8017, log_level="warning")
