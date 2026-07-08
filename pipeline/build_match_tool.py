#!/usr/bin/env python3
"""
Build match_breakdown.html — a self-serve tool: pick any World Cup match,
it fetches live Polymarket data in-browser and shows what the chronic-loser
wallets bet on it. The chronic-loser set (from results.json) is embedded.
"""
import json, os

CACHE = os.path.join(os.path.dirname(__file__), "cache")
OUT = os.path.join(os.path.dirname(__file__), "match_breakdown.html")

res = json.load(open(f"{CACHE}/results.json"))
# compact loser map: wallet -> [longest, current, winrate%, n_games, name, sell%]
losers = {}
for x in res:
    losers[x["wallet"]] = [
        x["longest_loss_streak"], x["current_loss_streak"],
        int((x["win_rate"] or 0) * 100), x["n_games"],
        x["name"] or "",
        int(round(x.get("sell_ratio", 0) * 100)),
    ]
LOSERS_JSON = json.dumps(losers, ensure_ascii=False, separators=(",", ":"))

HTML = r"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>连输钱包 · 单场拆解工具</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--bd:#272e3a;--tx:#e6edf3;--mut:#8b949e;
--loss:#f85149;--win:#3fb950;--accent:#58a6ff;--warn:#d29922;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);
font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC",sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:24px 20px 60px}
h1{font-size:21px;margin:0 0 4px}
.sub{color:var(--mut);font-size:13px;margin-bottom:18px}
.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:18px}
select,input{background:var(--card);color:var(--tx);border:1px solid var(--bd);
border-radius:8px;padding:9px 12px;font-size:14px}
select{min-width:320px}
button{background:#1f6feb;color:#fff;border:none;border-radius:8px;padding:9px 16px;
font-size:14px;font-weight:600;cursor:pointer}
button:disabled{opacity:.5;cursor:default}
.navbtn{display:inline-block;background:#21262d;color:var(--tx);text-decoration:none;
font-weight:600;padding:10px 16px;border-radius:8px;white-space:nowrap;border:1px solid var(--bd)}
.navbtn:hover{border-color:var(--accent);color:var(--accent)}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px 18px;margin:14px 0}
.match-h{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px}
.match-h h2{font-size:18px;margin:0}
.badge{font-size:12px;padding:3px 10px;border-radius:20px;font-weight:600}
.live{background:#d2992222;color:var(--warn);border:1px solid var(--warn)}
.done{background:#3fb95022;color:var(--win);border:1px solid var(--win)}
.odds{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
.odd{flex:1;min-width:140px;background:#0d1117;border:1px solid var(--bd);border-radius:10px;padding:10px 12px}
.odd .t{color:var(--mut);font-size:12px}
.odd .p{font-size:20px;font-weight:700;margin-top:2px}
.odd.winner{border-color:var(--win)}.odd.winner .p{color:var(--win)}
table{width:100%;border-collapse:collapse;margin-top:6px}
th,td{padding:8px 10px;text-align:right;border-bottom:1px solid var(--bd);font-size:13px}
th{color:var(--mut);font-size:12px;font-weight:600}
td:first-child,th:first-child{text-align:left}
.barcell{position:relative}
.fill{position:absolute;left:0;top:0;bottom:0;background:#f8514922;border-radius:4px;z-index:0}
.barcell span{position:relative;z-index:1}
.loss{color:var(--loss)}.win{color:var(--win)}.warnc{color:var(--warn);font-weight:700}
.addr{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--accent);text-decoration:none}
h3{font-size:14px;margin:18px 0 6px}
.hint{color:var(--mut);font-size:12px}
.spin{color:var(--mut);padding:20px;text-align:center}
.pill{font-size:11px;background:#21262d;border-radius:6px;padding:2px 7px;color:var(--mut)}
</style></head><body><div class="wrap">
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px">
<div>
<h1>⚽ 连输钱包 · 单场拆解工具</h1>
<div class="sub">选任意一场世界杯比赛 → 实时抓 Polymarket 数据，看连输榜上的钱包押了哪一边。
已内置 __NLOSER__ 个连输榜钱包名单。数据现抓现算。</div>
</div>
<a href="dashboard.html" class="navbtn">← 返回连输总榜</a>
</div>
<div class="bar">
  <select id="sel"><option>加载比赛列表中…</option></select>
  <button id="go" disabled>拆解这场</button>
  <label style="cursor:pointer;user-select:none;color:var(--mut);font-size:13px">
    <input type="checkbox" id="holdcb" style="vertical-align:middle"> 💎 只看从头拿到尾的钱包
  </label>
  <span class="hint" id="status"></span>
</div>
<div id="out"></div>
</div>
<script>
const LOSERS = __LOSERS__;   // wallet -> [longest,current,winrate,n_games,name]
const GAMMA="https://gamma-api.polymarket.com", DATA="https://data-api.polymarket.com";
const sel=document.getElementById("sel"), go=document.getElementById("go"),
      out=document.getElementById("out"), status=document.getElementById("status");
let EVENTS=[];

function label(q,oi){
  const low=(q||"").toLowerCase();
  if(low.includes("draw")) return oi===0?"平局":"不平局";
  if(low.startsWith("will ")&&low.includes(" win")){
    const team=q.slice(5, low.indexOf(" win")).trim();
    return oi===0? team+" 胜" : team+" 不胜";
  }
  return q+" = "+(oi===0?"Yes":"No");
}
async function getj(u){const r=await fetch(u); if(!r.ok) throw new Error(r.status); return r.json();}

// 1) load match list (result events: "A vs. B", exactly 3 markets)
async function loadEvents(){
  let evs=[];
  for(const closed of [false,true]){
    for(let off=0; off<=5000; off+=100){
      let d; try{ d=await getj(`${GAMMA}/events?tag_slug=fifa-world-cup&limit=100&offset=${off}&closed=${closed}&order=endDate&ascending=false`);}catch(e){break;}
      if(!d.length) break; evs=evs.concat(d);
      status.textContent=`加载比赛列表… ${evs.length} 个事件`;
      if(d.length<100) break;
    }
  }
  const seen=new Set();
  EVENTS = evs.filter(e=>{
    const t=e.title||"";
    if(seen.has(e.id)) return false; seen.add(e.id);
    if((e.markets||[]).length!==3) return false;
    if(t.includes(" - ")) return false;
    return t.toLowerCase().includes(" vs");
  }).sort((a,b)=>(b.endDate||"").localeCompare(a.endDate||""));
  sel.innerHTML = EVENTS.map(e=>{
    const d=(e.endDate||"").slice(0,10);
    const st = e.closed? "✅已结束":"🔴进行/未结算";
    return `<option value="${e.id}">${d} · ${e.title} · ${st}</option>`;
  }).join("");
  go.disabled=false;
  status.textContent = `共 ${EVENTS.length} 场比赛`;
}

// 2) breakdown a selected match
async function breakdown(id){
  const ev=EVENTS.find(e=>String(e.id)===String(id));
  out.innerHTML=`<div class="spin">⏳ 正在实时抓取「${ev.title}」的成交并比对连输榜…</div>`;
  // market conds + odds + winner
  const full=(await getj(`${GAMMA}/events?id=${id}`))[0];
  const conds=full.markets.map(m=>{
    let pr=[]; try{pr=JSON.parse(m.outcomePrices||"[]");}catch(e){}
    let winIdx=-1; if(pr.includes("1")) winIdx=pr.indexOf("1");
    return {cid:m.conditionId, q:m.question, pr, winIdx};
  });
  const resolved = conds.some(c=>c.winIdx>=0);
  // pull recent trades for 3 markets
  const net={};   // wallet -> {key: shares}, key=cid#oi
  const qByCid={}; conds.forEach(c=>qByCid[c.cid]=c.q);
  let tradeCount=0;
  for(const c of conds){
    for(let page=0; page<4; page++){
      let d; try{ d=await getj(`${DATA}/trades?market=${c.cid}&limit=500&offset=${page*500}`);}catch(e){break;}
      if(!d.length) break;
      for(const t of d){
        tradeCount++;
        const w=t.proxyWallet; const k=c.cid+"#"+t.outcomeIndex;
        const s=parseFloat(t.size)||0;
        (net[w]=net[w]||{}); net[w][k]=(net[w][k]||0)+(t.side==="BUY"?s:-s);
      }
      if(d.length<500) break;
    }
  }
  // classify pick = largest net-long position
  const pickOf={};
  for(const w in net){
    let best=null;
    for(const k in net[w]){ const s=net[w][k];
      if(s>0 && (!best||s>best.s)){ const [cid,oi]=k.split("#"); best={s,cid,oi:+oi}; } }
    if(best) pickOf[w]=label(qByCid[best.cid], best.oi);
  }
  LAST={ev, conds, resolved, pickOf, tradeCount};
  render(ev, conds, resolved, pickOf, tradeCount);
}

let LAST=null;   // last breakdown, so the 💎 toggle can re-render without re-fetching

function render(ev, conds, resolved, pickOf, tradeCount){
  const holdOnly=document.getElementById("holdcb").checked;
  // which loser wallets are here (💎 filter: sell% <= 10 = held to settlement)
  const here = Object.keys(pickOf).filter(w=>LOSERS[w] && (!holdOnly || LOSERS[w][5]<=10));
  const dist={}, hard={};
  let nHard=0;
  for(const w of here){
    const p=pickOf[w]; dist[p]=(dist[p]||0)+1;
    if(LOSERS[w][0]>=8){ nHard++; hard[p]=(hard[p]||0)+1; }
  }
  // per-pick win/loss map. Each binary market settles BOTH its sides:
  // e.g. Belgium wins => "Belgium 胜"✅, "United States 不胜"✅, "不平局"✅.
  const pickResult={};        // pick label -> true(won)/false(lost)
  let winLabel=null;          // the actual match outcome ("X 胜" or "平局")
  if(resolved){
    for(const c of conds){
      if(c.winIdx<0) continue;
      pickResult[label(c.q,0)] = (c.winIdx===0);
      pickResult[label(c.q,1)] = (c.winIdx===1);
      if(c.winIdx===0) winLabel=label(c.q,0);
    }
  }
  // odds cards
  const oddCards = conds.map(c=>{
    const yes=c.pr[0]!=null?(c.pr[0]*100).toFixed(0)+"%":"–";
    const lab=label(c.q,0);
    const isWin = resolved && c.winIdx===0;
    return `<div class="odd ${isWin?'winner':''}"><div class="t">${lab}${isWin?' ✅赢':''}</div><div class="p">${yes}</div></div>`;
  }).join("");
  const maxd=Math.max(1,...Object.values(dist));
  const tagOf=p=>{
    if(!resolved || !(p in pickResult)) return '';
    return pickResult[p] ? '<span class="win">✅这场赢了</span>'
                         : '<span class="loss">❌这场输了</span>';
  };
  // per-pick wallet lists (sorted: current streak desc, then win rate asc)
  const byPick={}, byPickH={};
  for(const w of here){
    const p=pickOf[w];
    (byPick[p]=byPick[p]||[]).push(w);
    if(LOSERS[w][0]>=8) (byPickH[p]=byPickH[p]||[]).push(w);
  }
  const bySeverity=(a,b)=>LOSERS[b][1]-LOSERS[a][1] || LOSERS[a][2]-LOSERS[b][2];
  for(const p in byPick) byPick[p].sort(bySeverity);
  for(const p in byPickH) byPickH[p].sort(bySeverity);
  const distRows = Object.entries(dist).sort((a,b)=>b[1]-a[1]).map(([p,n])=>
    `<tr data-pick="${p}" style="cursor:pointer"><td class="barcell"><div class="fill" style="width:${n/maxd*100}%"></div><span>▸ ${p}</span></td>
      <td>${n}</td><td>${tagOf(p)}</td></tr>`).join("");
  const hardRows = Object.entries(hard).sort((a,b)=>b[1]-a[1]).map(([p,n])=>
    `<tr data-pick="${p}" style="cursor:pointer"><td>▸ ${p}</td><td>${n}</td><td>${tagOf(p)}</td></tr>`).join("");
  // notable: hardcore losers betting against the favorite / on longshots
  const fav = conds.map(c=>({lab:label(c.q,0),p:+c.pr[0]||0})).sort((a,b)=>b.p-a.p)[0];
  const notable = here.filter(w=>LOSERS[w][0]>=6)
    .map(w=>({w, L:LOSERS[w], p:pickOf[w]}))
    .filter(o=> o.p!==fav.lab )   // not on the favorite
    .sort((a,b)=> b.L[1]-a.L[1] || a.L[2]-b.L[2])   // by current streak, then low winrate
    .slice(0,25);
  const notableRows = notable.map(o=>`<tr>
     <td><a class="addr" href="https://polymarket.com/profile/${o.w}" target="_blank">${o.w}</a></td>
     <td>${o.p}</td>
     <td class="${o.L[1]>0?'warnc':''}">${o.L[1]}</td>
     <td>${o.L[0]}</td>
     <td class="${o.L[2]<34?'loss':''}">${o.L[2]}%</td>
     <td>${o.L[3]}</td></tr>`).join("");

  out.innerHTML = `
  <div class="card">
   <div class="match-h"><h2>${ev.title}</h2>
     <span class="badge ${resolved?'done':'live'}">${resolved? '已结束 · 胜方 '+(winLabel||'?') : '🔴 进行中/未结算'}</span></div>
   <div class="odds">${oddCards}</div>
   <div class="hint" style="margin-top:8px">本次抓到 ${tradeCount} 笔近期成交 · 命中连输榜钱包 <b>${here.length}</b> 个${resolved?'':'（实时快照，比赛未结算）'}</div>
  </div>

  <h3>📊 连输榜钱包押注方向（${here.length} 个）<span class="hint">　点任意一行展开具体钱包</span></h3>
  <table id="dtab"><thead><tr><th>押注方向</th><th>钱包数</th><th>${resolved?'结果':''}</th></tr></thead>
   <tbody>${distRows||'<tr><td colspan=3 class=hint>这场没抓到连输榜钱包</td></tr>'}</tbody></table>

  <h3>🔥 硬核连输者（最长连输≥8场，${nHard} 个）押注<span class="hint">　点行展开</span></h3>
  <table id="htab"><thead><tr><th>押注方向</th><th>人数</th><th>${resolved?'结果':''}</th></tr></thead>
   <tbody>${hardRows||'<tr><td colspan=3 class=hint>无</td></tr>'}</tbody></table>

  <h3>🎯 没押热门(${fav.lab} ${(fav.p*100).toFixed(0)}%)的资深连输钱包（最长连输≥6，按当前连输排）</h3>
  <table><thead><tr><th>钱包</th><th>本场押</th><th>当前连输</th><th>最长连输</th><th>胜率</th><th>历史场次</th></tr></thead>
   <tbody>${notableRows||'<tr><td colspan=6 class=hint>无</td></tr>'}</tbody></table>
  <div class="hint" style="margin-top:14px">口径：押注方向 = 该钱包在三个结果盘里净持仓最大的一边。💎 = 从头拿到尾（卖出≤10%），🔄 = 波段型。实时盘只抓每盘近 ~2000 笔成交，为当前活跃钱包的快照，非全量。点地址核对。</div>`;
  bindExpand("dtab", byPick);
  bindExpand("htab", byPickH);
}

function walletList(list){
  const head=`<tr class="ghead"><th style="text-align:left">钱包（按当前连输排）</th>
    <th>当前连输</th><th>最长连输</th><th>胜率</th><th>场次</th></tr>`;
  const rows=list.slice(0,60).map(w=>{const L=LOSERS[w];
    const flag=L[5]<=10?' 💎':(L[5]>=50?' <span class="pill">🔄'+L[5]+'%</span>':'');
    const nm=L[4]?` <span class="pill">${L[4]}</span>`:'';
    return `<tr>
     <td style="text-align:left"><a class="addr" href="https://polymarket.com/profile/${w}" target="_blank">${w}</a>${flag}${nm}</td>
     <td class="${L[1]>0?'warnc':''}">${L[1]}</td><td>${L[0]}</td>
     <td class="${L[2]<34?'loss':''}">${L[2]}%</td><td>${L[3]}</td></tr>`;}).join("");
  const more=list.length>60?`<tr><td colspan="5" class="hint" style="text-align:center">…共 ${list.length} 个，仅显示当前连输最深的前 60 个</td></tr>`:'';
  return `<table style="margin:4px 0 10px;background:#0d1117">${head}${rows}${more}</table>`;
}

function bindExpand(tid, map){
  const tb=document.querySelector(`#${tid} tbody`); if(!tb) return;
  tb.querySelectorAll("tr[data-pick]").forEach(tr=>{
    tr.onclick=()=>{
      const nx=tr.nextElementSibling;
      if(nx && nx.classList.contains("wexp")){ nx.remove(); return; }
      const dr=document.createElement("tr"); dr.className="wexp";
      dr.innerHTML=`<td colspan="3" style="padding:0 0 0 14px">${walletList(map[tr.dataset.pick]||[])}</td>`;
      tr.after(dr);
    };
  });
}

go.onclick=()=>breakdown(sel.value);
document.getElementById("holdcb").onchange=()=>{
  if(LAST) render(LAST.ev, LAST.conds, LAST.resolved, LAST.pickOf, LAST.tradeCount);
};
loadEvents().catch(e=>{status.textContent="加载比赛列表失败："+e.message;});
</script></body></html>"""

HTML = HTML.replace("__LOSERS__", LOSERS_JSON).replace("__NLOSER__", str(len(losers)))
open(OUT, "w").write(HTML)
print(f"[match-tool] wrote {OUT}  ({len(losers)} losers embedded, "
      f"{round(len(HTML)/1024)}KB)")
