"""Web 入口:零依赖 http.server,单页 + JSON API。

启动:`python -m moneyagent web --port 8000`,浏览器打开 http://127.0.0.1:8000
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import agent, llm
from . import db as dbmod

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>钱袋 · 本周花到哪了</title>
<style>
  :root {
    --bg:#f4f7fb; --card:#ffffff; --ink:#1f2937; --muted:#6b7280;
    --blue:#2563eb; --blue-soft:#dbeafe; --amber:#f59e0b; --amber-soft:#fef3c7;
    --red:#dc2626; --red-soft:#fee2e2; --green:#16a34a; --green-soft:#dcfce7;
    --line:#e5e7eb; --radius:16px;
  }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
         background:var(--bg); color:var(--ink); }
  .wrap { max-width:1080px; margin:0 auto; padding:28px 20px 80px; }
  header { display:flex; align-items:baseline; gap:12px; margin-bottom:4px; }
  header h1 { font-size:24px; margin:0; letter-spacing:.5px; }
  .badge { font-size:12px; padding:3px 10px; border-radius:999px; background:var(--blue-soft); color:var(--blue); }
  .sub { color:var(--muted); margin:4px 0 22px; font-size:14px; }
  .grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; align-items:start; }
  @media (max-width:860px){ .grid { grid-template-columns:1fr; } }
  .card { background:var(--card); border:1px solid var(--line); border-radius:var(--radius);
          padding:18px; box-shadow:0 1px 2px rgba(16,24,40,.04); }
  textarea { width:100%; padding:12px 14px; border:1px solid var(--line); border-radius:12px;
             font-size:15px; font-family:inherit; resize:vertical; min-height:64px; }
  textarea:focus { outline:none; border-color:var(--blue); box-shadow:0 0 0 3px var(--blue-soft); }
  button { background:var(--blue); color:#fff; border:none; padding:11px 22px; border-radius:12px;
           font-size:15px; cursor:pointer; }
  button:hover { filter:brightness(1.06); }
  button:disabled { opacity:.6; cursor:not-allowed; }
  .hint { color:var(--muted); font-size:12px; margin:8px 0 12px; }
  .spin { display:inline-block; width:15px; height:15px; border:2px solid #fff;
          border-top-color:transparent; border-radius:50%; animation:sp .7s linear infinite; vertical-align:-2px; }
  @keyframes sp { to { transform:rotate(360deg); } }
  .answer { display:none; }
  .answer.show { display:block; margin-top:16px; }
  .answer-box { background:var(--blue-soft); border-radius:12px; padding:13px 15px; line-height:1.7; white-space:pre-wrap; font-size:15px; }
  .steps { margin-top:12px; }
  .step { border:1px solid var(--line); border-radius:12px; padding:9px 12px; margin-bottom:8px; font-size:13px; }
  .step .tool { font-weight:600; color:var(--blue); font-family:ui-monospace,monospace; }
  .step .args { color:var(--muted); margin:3px 0; word-break:break-all; }
  .step .res { color:var(--muted); border-top:1px dashed var(--line); padding-top:5px; margin-top:5px; }
  .step .res .err { color:var(--red); }
  .stats { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:14px; }
  .stat { border:1px solid var(--line); border-radius:12px; padding:12px; text-align:center; }
  .stat .v { font-size:22px; font-weight:700; }
  .stat .k { color:var(--muted); font-size:12px; margin-top:2px; }
  .stat.out .v { color:var(--red); } .stat.in .v { color:var(--green); } .stat.bal .v { color:var(--blue); }
  h3 { font-size:14px; margin:0 0 10px; color:var(--muted); font-weight:600; }
  .bar-row { margin-bottom:10px; }
  .bar-row .lbl { display:flex; justify-content:space-between; font-size:13px; margin-bottom:4px; }
  .bar { height:9px; border-radius:999px; background:var(--line); overflow:hidden; }
  .bar > i { display:block; height:100%; border-radius:999px; background:var(--blue); }
  .bar > i.over { background:var(--red); }
  .bar > i.warm { background:var(--amber); }
  .tx { display:flex; justify-content:space-between; font-size:13px; padding:7px 0; border-bottom:1px solid #f1f5f9; }
  .tx:last-child { border-bottom:none; }
  .tx .amt.out { color:var(--red); } .tx .amt.in { color:var(--green); }
  .empty { color:var(--muted); font-size:13px; }

h1{font-size:clamp(31px,5vw,39px);line-height:1.26}
.prod{display:block;font-size:11px;line-height:1.4;letter-spacing:.18em;font-weight:650;margin-bottom:8px;opacity:.72}
.lede,.sub{max-width:62ch;line-height:1.75}
.route{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;margin:0 0 20px;border:1px solid var(--line);background:var(--line)}
.route span{padding:11px 13px;background:var(--card);font-size:12px;line-height:1.5}
.route b{display:block;font-size:10px;letter-spacing:.1em;margin-bottom:3px;opacity:.66}
button{min-height:46px}
input,select{min-height:44px}
@media(max-width:680px){
  .wrap{padding:20px 16px 56px}
  .route{grid-template-columns:1fr}
  h1{font-size:30px!important}
  .row>div{min-width:100%!important}
  button{width:100%}
}

body{background:#f0eee8;color:#23332b;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:940px}
header{padding:8px 0 20px;border-bottom:1px solid #b9b5a5;margin-bottom:20px}
header h1{font-family:"Songti SC","SimSun",Georgia,serif;font-size:38px;line-height:1.24;letter-spacing:-.01em}
header p{color:#6e7068;font-size:14px}
.card{background:#fbfaf6;border:1px solid #d6d2c4;border-radius:2px;box-shadow:none}
button{background:#1f6b4a;border-radius:2px;letter-spacing:.05em}
button:hover{background:#19583d}
textarea,input,select{background:#fffefb;border-color:#d3cfc0;border-radius:2px;font-variant-numeric:tabular-nums}
textarea:focus,input:focus,select:focus{border-color:#1f6b4a;box-shadow:0 0 0 2px #d6e5dc}
.cost .cell,.cell{border-color:#d6d2c4;border-radius:2px}
.cost .cell b{font-family:"Cascadia Mono",Consolas,monospace;font-variant-numeric:tabular-nums}
.item{border-left:3px solid #1f6b4a}
h3{color:#1f6b4a;letter-spacing:.08em}


/* palette-normalized */
:root{--bg:#f0eee8;--card:#fbfaf6;--ink:#23332b;--text:#23332b;--dim:#6e7068;--line:#d6d2c4;--accent:#1f6b4a}

/* polish-batch1 */
button.ghost,button.secondary{background:transparent!important;color:#1f6b4a!important;border:1px solid #d6d2c4!important}
header{display:block!important}
header h1{font-size:38px!important;line-height:1.25!important}

/* mobile-32 */

@media(max-width:760px){
  main{grid-template-columns:1fr!important}
  aside{border-right:0!important;border-bottom:1px solid #d6d2c4;width:auto!important}
  section{padding:16px!important}
  .row{flex-wrap:wrap!important}
  .row>div{min-width:100%!important}
  h1{font-size:30px!important}
  .route{grid-template-columns:1fr!important}
  button{min-height:48px}
  pre{overflow-x:auto}
}

/* mobile-height */
@media(max-width:760px){main{min-height:auto!important}aside{min-height:0!important}}
</style>
</head>
<body>
<div class="wrap">
  <header><h1><span class="prod">钱袋</span>本周的钱，花到哪了</h1><span class="badge" id="badge">…</span>
    <p class="lede">给每周想知道钱花哪的家庭：一句话变成待确认账条，退款跟原消费一起看，月度差异能点回每一笔。</p>
  </header>
  <div class="route" aria-label="任务步骤"><span><b>01</b>说一笔支出</span><span><b>02</b>确认金额类别</span><span><b>03</b>对账到月度</span></div>

  <p class="sub">像聊天一样记账、查账、管预算——它会自己一步步调工具完成,你看着就行。</p>

  <div class="grid">
    <div>
      <div class="card">
        <textarea id="inp" placeholder="例:今天中午吃了碗面15块,帮我记一下,顺便看看这个月餐饮超没超预算"></textarea>
        <div class="hint">支持口语化描述,模型会自动提取金额、分类、判断是否重复记账。</div>
        <button id="send">发送</button>
        <div class="answer" id="ans">
          <div class="answer-box" id="ans-box"></div>
          <div class="steps" id="steps"></div>
        </div>
      </div>
    </div>
    <div>
      <div class="card">
        <div class="stats">
          <div class="stat out"><div class="v" id="st-out">—</div><div class="k">本月支出</div></div>
          <div class="stat in"><div class="v" id="st-in">—</div><div class="k">本月收入</div></div>
          <div class="stat bal"><div class="v" id="st-bal">—</div><div class="k">结余</div></div>
        </div>
        <h3>预算执行</h3>
        <div id="budgets"><div class="empty">还没有预算,说「餐饮预算设 500」即可。</div></div>
        <h3 style="margin-top:16px">分类占比</h3>
        <div id="cats"><div class="empty">暂无支出。</div></div>
        <h3 style="margin-top:16px">最近流水</h3>
        <div id="txs"><div class="empty">暂无流水。</div></div>
      </div>
    </div>
  </div>
</div>

<script>
const $ = s => document.querySelector(s);
const esc = s => String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = n => (Number(n)||0).toFixed(2);

async function post(path, body){
  const r = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
  return r.json();
}

function renderSteps(steps){
  const el = $('#steps'); el.innerHTML='';
  if(!steps||!steps.length) return;
  steps.forEach((s,i)=>{
    const args = Object.entries(s.arguments||{}).map(([k,v])=>k+'='+esc(JSON.stringify(v))).join(', ');
    let resHtml = '';
    const r = s.result||{};
    if(r.error){ resHtml = '<span class="err">❌ '+esc(r.error)+'</span>'; }
    else if(r.recorded){ resHtml = esc(r.recorded); }
    else { resHtml = esc(JSON.stringify(r)); }
    el.innerHTML += '<div class="step"><div class="tool">'+(i+1)+'. '+esc(s.tool)+'</div>'+
      '<div class="args">'+esc(args)+'</div><div class="res">'+resHtml+'</div></div>';
  });
}

$('#send').onclick = async ()=>{
  const text = $('#inp').value.trim();
  if(!text) return;
  const btn = $('#send'); btn.disabled=true; btn.innerHTML='<span class="spin"></span>';
  $('#ans').classList.remove('show');
  try{
    const r = await post('/api/chat',{text});
    $('#ans-box').textContent = r.answer||'';
    renderSteps(r.steps);
    $('#ans').classList.add('show');
    loadDashboard();
  }catch(e){ $('#ans-box').textContent='请求失败:'+e; $('#ans').classList.add('show'); }
  btn.disabled=false; btn.innerHTML='发送';
};
$('#inp').addEventListener('keydown',e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); $('#send').click(); } });

async function loadDashboard(){
  try{
    const d = await (await fetch('/api/dashboard')).json();
    $('#st-out').textContent = fmt(d.summary.total_expense);
    $('#st-in').textContent = fmt(d.summary.total_income);
    $('#st-bal').textContent = (d.summary.balance>=0?'':'−')+fmt(Math.abs(d.summary.balance));
    // 预算
    const bEl = $('#budgets');
    if(!Object.keys(d.budgets||{}).length){ bEl.innerHTML='<div class="empty">还没有预算,说「餐饮预算设 500」即可。</div>'; }
    else{
      bEl.innerHTML='';
      for(const [cat,amt] of Object.entries(d.budgets)){
        const spent = d.spent[cat]||0; const pct = amt>0? Math.min(spent/amt*100,100):0; const over = spent>amt;
        bEl.innerHTML += '<div class="bar-row"><div class="lbl"><span>'+esc(cat)+'</span><span>'+fmt(spent)+' / '+fmt(amt)+(over?' ⚠️超支':'')+'</span></div>'+
          '<div class="bar"><i class="'+(over?'over':'')+'" style="width:'+pct+'%"></i></div></div>';
      }
    }
    // 分类占比
    const cEl = $('#cats');
    if(!d.breakdown.length){ cEl.innerHTML='<div class="empty">暂无支出。</div>'; }
    else{
      const max = d.breakdown[0].total||1;
      cEl.innerHTML='';
      d.breakdown.forEach(x=>{
        cEl.innerHTML += '<div class="bar-row"><div class="lbl"><span>'+esc(x.category)+'</span><span>'+fmt(x.total)+' 元</span></div>'+
          '<div class="bar"><i class="warm" style="width:'+(x.total/max*100)+'%"></i></div></div>';
      });
    }
    // 流水
    const tEl = $('#txs');
    if(!d.recent.length){ tEl.innerHTML='<div class="empty">暂无流水。</div>'; }
    else{
      tEl.innerHTML='';
      d.recent.forEach(t=>{
        const sign = t.type==='expense'?'-':'+'; const cls = t.type==='expense'?'out':'in';
        tEl.innerHTML += '<div class="tx"><span>'+esc(t.date)+' '+(t.merchant?esc(t.merchant):esc(t.category||'未分类'))+'</span>'+
          '<span class="amt '+cls+'">'+sign+fmt(t.amount)+'</span></div>';
      });
    }
  }catch(e){}
}

fetch('/api/status').then(r=>r.json()).then(s=>{
  const b=$('#badge');
  if(s.mock){ b.textContent='离线模式'; b.style.background='#fee2e2'; b.style.color='#b91c1c'; }
  else{ b.textContent=s.model||'已连接'; b.style.background='#dcfce7'; b.style.color='#15803d'; }
}).catch(()=>{});
loadDashboard();
</script>
</body>
</html>
"""


def _month_range() -> tuple[str, str]:
    t = dbmod.today()
    return f"{t[:7]}-01", t


def _dashboard(db) -> dict:
    s, e = _month_range()
    return {
        "summary": db.summary(s, e),
        "budgets": db.get_budgets(),
        "spent": {x["category"]: x["total"] for x in db.category_breakdown(s, e)},
        "breakdown": db.category_breakdown(s, e)[:8],
        "recent": db.recent(10),
    }


def _make_handler(db, cfg, force_mock):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, ctype: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status: int = 200):
            self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8", status)

        def _read_json(self):
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("gbk", errors="replace")
            return json.loads(text) if text else {}

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/status":
                mock_mode = force_mock or not cfg.get("api_key")
                self._json({"mock": mock_mode, "model": None if mock_mode else cfg.get("model")})
            elif path == "/api/dashboard":
                self._json(_dashboard(db))
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                body = self._read_json()
                if path == "/api/chat":
                    r = agent.run(body.get("text", ""), db=db, config=cfg, force_mock=force_mock)
                    self._json(r)
                else:
                    self._json({"error": "not found"}, 404)
            except llm.LLMError as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:  # noqa: BLE001
                self._json({"error": str(e)}, 500)

        def log_message(self, *args):
            pass

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8000, db_path: str | None = None, force_mock: bool = False):
    db = dbmod.Database(db_path)
    cfg = llm.default_config()
    handler = _make_handler(db, cfg, force_mock)
    httpd = ThreadingHTTPServer((host, port), handler)
    mode = "离线模式(未配置 key)" if (force_mock or not cfg.get("api_key")) else f"模型:{cfg.get('model')}"
    print(f"💰 钱袋已启动:http://{host}:{port}  [{mode}]")
    print("   按 Ctrl+C 停止")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
