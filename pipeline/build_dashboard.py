#!/usr/bin/env python3
"""Turn cache/results.json into a self-contained dashboard.html.

Usage:
  python3 build_dashboard.py          -> dashboard.html (full, local)
  python3 build_dashboard.py share    -> dashboard_share.html (trimmed,
                                         wrapper-free, for Claude Artifact)
  python3 build_dashboard.py site     -> site/index.html (trimmed, complete
                                         page for GitHub Pages, links to
                                         match.html)
"""
import json, os, datetime, sys

MODE = sys.argv[1] if len(sys.argv) > 1 else "full"
SHARE = MODE in ("share", "site")          # both use the trimmed wallet set
CACHE = os.path.join(os.path.dirname(__file__), "cache")
_outs = {"full": "dashboard.html", "share": "dashboard_share.html",
         "site": "site/index.html"}
OUT = os.path.join(os.path.dirname(__file__), _outs[MODE])
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

results = json.load(open(f"{CACHE}/results.json"))
games_data = json.load(open(f"{CACHE}/games.json"))
n_games_total = len(games_data["games"])
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

n_full = len(results)
if SHARE:
    # keep only the wallets any sort view could realistically show
    K = 2500
    keep = set()
    for key, rev in [("longest_loss_streak", True), ("current_loss_streak", True)]:
        for x in sorted(results, key=lambda x: x[key], reverse=rev)[:K]:
            keep.add(x["wallet"])
    eligible = [x for x in results if x["n_games"] >= 5]
    for x in sorted(eligible, key=lambda x: x["win_rate"] or 1)[:K]:
        keep.add(x["wallet"])
    results = [x for x in results if x["wallet"] in keep]

# enrich + serialise for the page.
# games are stored ONCE in a lookup table; each wallet references them by index
# (25k wallets × ~10 games each would otherwise repeat every title string).
game_list = sorted(games_data["games"].values(),
                   key=lambda g: g["end_date"] or "")
game_idx = {g["game_id"]: i for i, g in enumerate(game_list)}
GAMES_JSON = json.dumps(
    [[(g["end_date"] or "")[:10], g["title"]] for g in game_list],
    ensure_ascii=False, separators=(",", ":"))

rows = []
pick_wallets = {}   # pick label -> set of wallets that LOST a game with this pick
pick_count = {}     # pick label -> total losing instances
for r in results:
    # compact per-game entries: [gameIdx, isLoss, stake, pnl, pick]
    gcompact = [[game_idx.get(g["game_id"], -1),
                 1 if g["result"] == "loss" else 0,
                 round(g["stake"], 2), round(g["pnl"], 2),
                 g.get("pick") or ""] for g in r["games"]]
    rows.append({
        "wallet": r["wallet"],
        "name": r["name"] or (r["wallet"][:6] + "…" + r["wallet"][-4:]),
        "n_games": r["n_games"], "wins": r["wins"], "losses": r["losses"],
        "win_rate": r["win_rate"],
        "longest": r["longest_loss_streak"],
        "current": r["current_loss_streak"],
        "stake": r["total_stake"], "pnl": r["net_pnl"],
        "top_loss_pick": r.get("top_loss_pick"),
        "top_loss_pick_n": r.get("top_loss_pick_n", 0),
        "sr": r.get("sell_ratio", 0),
        "games": gcompact,
    })
    for g in r["games"]:
        if g["result"] == "loss" and g.get("pick"):
            pick_count[g["pick"]] = pick_count.get(g["pick"], 0) + 1
            pick_wallets.setdefault(g["pick"], set()).add(r["wallet"])

# cross-wallet "most-piled-into losing options"
common = sorted(
    ([p, len(pick_wallets[p]), pick_count[p]] for p in pick_count),
    key=lambda x: -x[1])[:12]

DATA_JSON = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
COMMON_JSON = json.dumps(common, ensure_ascii=False, separators=(",", ":"))

HTML = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>世界杯连输钱包 · Polymarket</title>
<style>
:root{--bg:#0d1117;--card:#161b22;--bd:#272e3a;--tx:#e6edf3;--mut:#8b949e;
--loss:#f85149;--win:#3fb950;--accent:#58a6ff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);
font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC",sans-serif}
header{padding:24px 28px 8px}
h1{margin:0 0 4px;font-size:22px}
.sub{color:var(--mut);font-size:13px}
.wrap{padding:8px 28px 60px;max-width:1100px}
.tabs{display:flex;gap:8px;margin:18px 0 14px}
.tab{padding:8px 16px;border:1px solid var(--bd);border-radius:8px;cursor:pointer;
background:var(--card);color:var(--mut);font-weight:600}
.tab.on{color:#fff;border-color:var(--accent);background:#1f6feb22}
.ctrl{display:flex;gap:16px;align-items:center;margin-bottom:12px;color:var(--mut);font-size:13px;flex-wrap:wrap}
input[type=range]{vertical-align:middle}
table{width:100%;border-collapse:collapse;background:var(--card);
border:1px solid var(--bd);border-radius:12px;overflow:hidden}
th,td{padding:10px 12px;text-align:right;border-bottom:1px solid var(--bd);white-space:nowrap}
th{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em;
cursor:pointer;user-select:none}
td:first-child,th:first-child{text-align:left}
tr:last-child td{border-bottom:none}
tr.row:hover{background:#1f6feb14}
.addr{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px}
.addr a{color:var(--accent);text-decoration:none;word-break:break-all}
.nm{color:var(--tx);font-weight:600;font-family:-apple-system,sans-serif;font-size:12px}
.copy{cursor:pointer;color:var(--mut);font-size:11px;margin-left:6px}
.copy:hover{color:var(--accent)}
.pick{font-size:12px;color:var(--loss);text-align:left;white-space:normal}
.panel{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px 18px;margin:14px 0}
.panel h3{margin:0 0 4px;font-size:14px}
.panel .hint{color:var(--mut);font-size:12px;margin-bottom:10px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{background:#f8514915;border:1px solid #f8514944;color:#ff9b94;border-radius:8px;
padding:6px 10px;font-size:12px}
.chip b{color:#fff}
.big{font-weight:700}
.loss{color:var(--loss)} .win{color:var(--win)}
.streak{display:inline-block;min-width:26px;padding:2px 8px;border-radius:6px;
background:#f8514922;color:var(--loss);font-weight:700}
.seq{font-family:ui-monospace,monospace;letter-spacing:1px}
.seq .l{color:var(--loss)} .seq .w{color:var(--win)}
.detail{background:#0d1117}
.detail td{padding:0}
.gtab{width:100%;border:none;border-radius:0;table-layout:fixed}
.gtab td,.gtab th{border-bottom:1px solid #21262d;font-size:12px;overflow:hidden;text-overflow:ellipsis}
.gtab col.c1{width:90px}.gtab col.c2{width:34%}.gtab col.c3{width:24%}
.gtab col.c4{width:60px}.gtab col.c5{width:90px}.gtab col.c6{width:100px}
.gtab .ghead th{color:var(--mut);font-weight:600;text-transform:none;letter-spacing:0;cursor:default;padding:8px 12px}
.gtab .gtot td{border-top:2px solid var(--bd);border-bottom:none;font-weight:600;color:var(--tx);padding:8px 12px}
.rank{color:var(--mut);width:34px}
.pill{font-size:11px;color:var(--mut)}
.foot{color:var(--mut);font-size:12px;margin-top:18px;line-height:1.7}
.navbtn{display:inline-block;background:#1f6feb;color:#fff;text-decoration:none;
font-weight:600;padding:10px 16px;border-radius:8px;white-space:nowrap}
.navbtn:hover{background:#388bfd}
</style></head><body>
<header>
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px">
<div>
<h1>⚽ 世界杯「连输钱包」榜 · Polymarket</h1>
<div class="sub">基于 __NGAMES__ 场已结算的 2026 世界杯比赛结果盘 · 快照时间 __NOW__ · 共 __NWALLET__ 个多场下注钱包</div>
</div>
<a href="match_breakdown.html" class="navbtn">🔍 单场拆解工具 →</a>
</div>
</header>
<div class="wrap">
<div class="panel">
<h3>🎯 输家最爱押的选项（押了它然后输掉的钱包数）</h3>
<div class="hint">统计所有上榜钱包：哪些选项被最多人押中、结果输掉。数字 = 押这个选项输掉的不同钱包数。</div>
<div class="chips" id="chips"></div>
</div>
<div class="tabs">
<div class="tab on" data-sort="longest">🔥 最长连输</div>
<div class="tab" data-sort="winrate">📉 最低胜率</div>
<div class="tab" data-sort="current">⛓️ 当前连输中</div>
</div>
<div class="ctrl">
最少下注场次：<input id="mg" type="range" min="3" max="15" value="3">
<span id="mgv">3</span> 场
<label style="cursor:pointer;user-select:none">
  <input type="checkbox" id="hold" style="vertical-align:middle"> 💎 只看从头拿到尾的（几乎不卖出，非波段）
</label>
·　点列头可排序　·　点行展开每场明细
</div>
<div style="overflow-x:auto"><table id="t"><thead></thead><tbody></tbody></table></div>
<div class="foot">
<b>怎么读：</b>「连输」= 该钱包在某场比赛结果盘上净亏损（买入成本 &gt; 赎回所得）记为一次输。
按比赛日期排序后，统计最长连续输的场次、当前是否还在连输、以及总胜率。<br>
<b>口径说明：</b>只统计「主胜 / 平 / 客胜」三选一的比赛结果盘，不含角球、比分、球员道具等子盘。
盈亏由该钱包的链上成交记录（买/卖 × 价格）加结算赔付计算，已忽略不足 $1 的零星仓位。
钱包活跃记录上限约 2000 条，极高频钱包可能略有偏差。<br>
点钱包地址可跳转其 Polymarket 主页核对。本页为只读快照，不构成任何投注建议。
</div>
</div>
<script>
const DATA = __DATA__;
const GAMES = __GAMES__;   // [[date,title],...] referenced by index
const COMMON = __COMMON__;
let sortKey="longest", sortDir=-1, minGames=3;
let holdOnly=false;            // 💎 filter: sell_ratio <= 0.1 = held to settlement
let showN=500;                 // render cap: 25k rows at once freezes the browser
const STEP=500;
const fmt=n=>n==null?"–":(n>=0?"+":"")+n.toLocaleString(undefined,{maximumFractionDigits:0});
const pct=n=>n==null?"–":(n*100).toFixed(0)+"%";
const cols=[
 {k:"name",t:"钱包地址"},
 {k:"longest",t:"最长连输"},
 {k:"current",t:"当前连输"},
 {k:"win_rate",t:"胜率"},
 {k:"n_games",t:"场次"},
 {k:"losses",t:"输"},
 {k:"wins",t:"赢"},
 {k:"top_loss_pick_n",t:"最常押错"},
 {k:"stake",t:"总下注$"},
 {k:"pnl",t:"净盈亏$"},
];
// common losing options panel
document.getElementById("chips").innerHTML = COMMON.map(c=>
 `<span class="chip">${c[0]} · <b>${c[1]}</b> 个钱包输</span>`).join("");
function rowsNow(){
 let r=DATA.filter(d=>d.n_games>=minGames && (!holdOnly || d.sr<=0.1));
 r.sort((a,b)=>{
   let x=a[sortKey], y=b[sortKey];
   if(x==null)x=-1; if(y==null)y=-1;
   if(x<y)return -sortDir; if(x>y)return sortDir;
   return b.longest-a.longest;
 });
 return r;
}
function seqHtml(games){
 // compact entry: [gameIdx, isLoss, stake, pnl, pick]
 return games.map(g=>g[1]?'<span class="l">●</span>':'<span class="w">●</span>').join("");
}
function render(){
 const thead=document.querySelector("#t thead");
 thead.innerHTML="<tr><th class='rank'>#</th>"+cols.map(c=>
   `<th data-k="${c.k}">${c.t}${sortKey===c.k?(sortDir<0?" ▼":" ▲"):""}</th>`).join("")+"</tr>";
 thead.querySelectorAll("th[data-k]").forEach(th=>th.onclick=()=>{
   const k=th.dataset.k;
   if(sortKey===k)sortDir=-sortDir; else{sortKey=k;sortDir=-1;}
   render();
 });
 const tb=document.querySelector("#t tbody"); tb.innerHTML="";
 const all=rowsNow();
 const rs=all.slice(0,showN);
 rs.forEach((d,i)=>{
  const tr=document.createElement("tr"); tr.className="row";
  const pnlc=d.pnl<0?"loss":"win";
  const pickTxt=d.top_loss_pick?`${d.top_loss_pick} <b>×${d.top_loss_pick_n}</b>`:'–';
  tr.innerHTML=`<td class="rank">${i+1}</td>
   <td class="addr">
     <div class="nm">${d.name}${d.sr<=0.1?' <span title="从头拿到尾，几乎不卖出">💎</span>':(d.sr>=0.5?' <span class="pill" title="卖出量≥买入量50%，波段交易者">🔄波段</span>':'')}<span class="copy" data-w="${d.wallet}" title="复制地址">⧉ 复制</span></div>
     <a href="https://polymarket.com/profile/${d.wallet}" target="_blank">${d.wallet}</a>
     <div class="seq">${seqHtml(d.games)}</div></td>
   <td><span class="streak">${d.longest}</span></td>
   <td>${d.current>0?'<span class="streak">'+d.current+'</span>':'<span class="pill">0</span>'}</td>
   <td class="big ${d.win_rate!=null&&d.win_rate<0.34?'loss':''}">${pct(d.win_rate)}</td>
   <td>${d.n_games}</td>
   <td class="loss">${d.losses}</td>
   <td class="win">${d.wins}</td>
   <td class="pick">${pickTxt}</td>
   <td>${d.stake.toLocaleString(undefined,{maximumFractionDigits:0})}</td>
   <td class="${pnlc}" style="font-weight:700">${fmt(d.pnl)}</td>`;
  tr.querySelector(".copy").onclick=ev=>{ev.stopPropagation();
    navigator.clipboard.writeText(ev.target.dataset.w);
    ev.target.textContent="✓ 已复制";setTimeout(()=>ev.target.textContent="⧉ 复制",1200);};
  tr.onclick=()=>toggle(tr,d);
  tb.appendChild(tr);
 });
 if(!rs.length)tb.innerHTML="<tr><td colspan='11' style='text-align:center;color:var(--mut);padding:30px'>没有符合条件的钱包</td></tr>";
 if(all.length>showN){
   const mr=document.createElement("tr");
   mr.innerHTML=`<td colspan="11" style="text-align:center;padding:14px">
     <button id="more" style="background:#1f6feb;color:#fff;border:none;border-radius:8px;
       padding:9px 18px;font-size:13px;font-weight:600;cursor:pointer">
       显示更多（已显示 ${rs.length} / 共 ${all.length}）</button></td>`;
   mr.querySelector("#more").onclick=()=>{showN+=STEP;render();};
   tb.appendChild(mr);
 }
}
function toggle(tr,d){
 if(tr.nextSibling&&tr.nextSibling.classList&&tr.nextSibling.classList.contains("detail")){
   tr.nextSibling.remove(); return;}
 const dr=document.createElement("tr"); dr.className="detail";
 const head=`<tr class="ghead">
   <th style="text-align:left">日期</th><th style="text-align:left">比赛</th>
   <th style="text-align:left">押注方向</th><th>结果</th>
   <th>下注 $</th><th>净盈亏 $</th></tr>`;
 const rows=d.games.map(g=>{
   const gm=GAMES[g[0]]||["?","?"];
   return `<tr>
   <td style="text-align:left;padding:6px 12px">${gm[0]}</td>
   <td style="text-align:left">${gm[1]}</td>
   <td style="text-align:left;color:var(--mut)">${g[4]||'?'}</td>
   <td class="${g[1]?'loss':'win'}">${g[1]?'输':'赢'}</td>
   <td>${g[2].toLocaleString(undefined,{maximumFractionDigits:2})}</td>
   <td class="${g[3]<0?'loss':'win'}" style="font-weight:700">${fmt(g[3])}</td></tr>`;}).join("");
 const tot=`<tr class="gtot"><td colspan="4" style="text-align:right">合计</td>
   <td>${d.stake.toLocaleString(undefined,{maximumFractionDigits:0})}</td>
   <td class="${d.pnl<0?'loss':'win'}" style="font-weight:700">${fmt(d.pnl)}</td></tr>`;
 const cg=`<colgroup><col class="c1"><col class="c2"><col class="c3"><col class="c4"><col class="c5"><col class="c6"></colgroup>`;
 dr.innerHTML=`<td colspan="11"><table class="gtab">${cg}<thead>${head}</thead><tbody>${rows}${tot}</tbody></table></td>`;
 tr.after(dr);
}
document.querySelectorAll(".tab").forEach(t=>t.onclick=()=>{
 document.querySelectorAll(".tab").forEach(x=>x.classList.remove("on"));
 t.classList.add("on");
 const s=t.dataset.sort;
 if(s==="longest"){sortKey="longest";sortDir=-1;}
 if(s==="winrate"){sortKey="win_rate";sortDir=1;}
 if(s==="current"){sortKey="current";sortDir=-1;}
 showN=500;
 render();
});
document.querySelector(".tab[data-sort=winrate]");
const mg=document.getElementById("mg");
mg.oninput=()=>{minGames=+mg.value;document.getElementById("mgv").textContent=mg.value;showN=500;render();};
document.getElementById("hold").onchange=e=>{holdOnly=e.target.checked;showN=500;render();};
render();
</script></body></html>"""

if SHARE:
    HTML = HTML.replace(
        "共 __NWALLET__ 个多场下注钱包",
        f"分享版收录最惨的 {len(rows):,} 个钱包（完整榜共 {n_full:,} 个）")
sub_txt = str(len(rows))
HTML = (HTML.replace("__DATA__", DATA_JSON)
            .replace("__GAMES__", GAMES_JSON)
            .replace("__COMMON__", COMMON_JSON)
            .replace("__NGAMES__", str(n_games_total))
            .replace("__NOW__", now)
            .replace("__NWALLET__", sub_txt))
if MODE == "share":
    # Claude Artifact wraps the file in <!doctype html><head>…<body>; strip ours
    HTML = HTML.replace('<!doctype html><html lang="zh"><head><meta charset="utf-8">\n'
                        '<meta name="viewport" content="width=device-width,initial-scale=1">\n', '')
    HTML = HTML.replace('</head><body>', '')
    HTML = HTML.replace('</script></body></html>', '</script>')
    # the match tool can't run under the Artifact CSP — drop the dead link
    HTML = HTML.replace('<a href="match_breakdown.html" class="navbtn">🔍 单场拆解工具 →</a>', '')
elif MODE == "site":
    # on GitHub Pages the match tool lives next door as match.html
    HTML = HTML.replace('href="match_breakdown.html"', 'href="match.html"')
open(OUT, "w").write(HTML)
print(f"[dashboard] wrote {OUT} ({len(rows)} wallets, {round(len(HTML)/1024)}KB)")
