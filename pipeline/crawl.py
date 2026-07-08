#!/usr/bin/env python3
"""
Stage 3: for each candidate wallet, pull full activity, compute per-game P&L,
win/loss sequence, longest & current losing streak, win rate.
Writes cache/results.json
"""
import urllib.request, urllib.error, json, time, os, sys, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE = os.path.join(os.path.dirname(__file__), "cache")
ACTDIR = os.path.join(CACHE, "activity")
os.makedirs(ACTDIR, exist_ok=True)
WORKERS = 16
UA = {"User-Agent": "Mozilla/5.0"}
DATA = "https://data-api.polymarket.com"
MIN_STAKE = 1.0        # ignore games where wallet bet < $1 (noise)


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 400:
                return None
            time.sleep(1.5 * (i + 1))
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def wallet_activity(w):
    # cache raw activity to disk so re-analysis never needs to re-fetch
    fp = os.path.join(ACTDIR, w + ".json")
    if os.path.exists(fp):
        try:
            return json.load(open(fp))
        except Exception:
            pass
    acts = []
    off = 0
    while off <= 2000:
        d = get(f"{DATA}/activity?user={w}&limit=500&offset={off}")
        if not d:
            break
        acts += d
        if len(d) < 500:
            break
        off += 500
    # keep only fields we need, store only WC-related trades to save space
    keep = [{k: a.get(k) for k in ("type", "conditionId", "outcomeIndex",
             "outcome", "size", "price", "side", "pseudonym", "name", "title")}
            for a in acts if a.get("type") == "TRADE"]
    json.dump(keep, open(fp, "w"))
    return keep


def pick_label(question, outcome, title):
    """Human-readable label for the side a wallet bet on."""
    q = (question or "")
    if "draw" in q.lower():
        return "平局" if outcome == "Yes" else "不平局"
    # "Will <TEAM> win on DATE?"
    low = q.lower()
    if low.startswith("will ") and " win" in low:
        team = q[5:low.index(" win")].strip()
        return f"{team} 胜" if outcome == "Yes" else f"{team} 不胜"
    return f"{q[:24]} = {outcome}"


def analyse(w, acts, cond_map, games):
    # group trades by game; track per (cond, outcomeIndex): shares, cash, outcome-str
    # game_id -> {cond -> {oi -> [net_shares, net_cash, outcome_str]}}
    pos = {}
    name = None
    tot_buy = [0.0]      # total shares bought across WC result markets
    tot_sell = [0.0]     # total shares sold — ~0 means "held to settlement"
    for a in acts:
        if a.get("type") != "TRADE":
            continue
        cid = a.get("conditionId")
        if cid not in cond_map:
            continue
        if not name:
            name = a.get("pseudonym") or a.get("name")
        gid = cond_map[cid]["game_id"]
        oi = a.get("outcomeIndex")
        size = float(a.get("size") or 0)
        price = float(a.get("price") or 0)
        side = a.get("side")
        g = pos.setdefault(gid, {})
        c = g.setdefault(cid, {})
        cell = c.setdefault(oi, [0.0, 0.0, a.get("outcome")])
        if side == "BUY":
            cell[0] += size
            cell[1] -= size * price
            tot_buy[0] += size
        else:
            cell[0] -= size
            cell[1] += size * price
            tot_sell[0] += size

    # per-game P&L + the main side the wallet backed
    game_results = []
    for gid, conds in pos.items():
        pnl = 0.0
        stake = 0.0
        best = None          # (net_shares, conditionId, outcome_str)
        for cid, outs in conds.items():
            win_idx = cond_map[cid]["win_index"]
            for oi, (shares, cash, ostr) in outs.items():
                stake += max(0.0, -cash)
                value = shares * (1.0 if oi == win_idx else 0.0)
                if value < 0:
                    value = 0.0
                pnl += cash + value
                if shares > 0 and (best is None or shares > best[0]):
                    best = (shares, cid, ostr)
        if stake < MIN_STAKE:
            continue
        pick = None
        if best:
            q = cond_map[best[1]].get("question")
            pick = pick_label(q, best[2], games[gid]["title"])
        end = games[gid]["end_date"] or ""
        result = "win" if pnl > 0.01 else ("loss" if pnl < -0.01 else "flat")
        game_results.append({"game_id": gid, "title": games[gid]["title"],
                             "date": end, "pnl": round(pnl, 2),
                             "stake": round(stake, 2), "result": result,
                             "pick": pick})

    game_results.sort(key=lambda x: x["date"])
    decisive = [g for g in game_results if g["result"] in ("win", "loss")]
    n = len(decisive)
    wins = sum(1 for g in decisive if g["result"] == "win")
    losses = n - wins
    # streaks
    longest = cur = 0
    for g in decisive:
        if g["result"] == "loss":
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    # current trailing losing streak
    trailing = 0
    for g in reversed(decisive):
        if g["result"] == "loss":
            trailing += 1
        else:
            break
    # most common losing pick for this wallet
    lp = {}
    for g in decisive:
        if g["result"] == "loss" and g.get("pick"):
            lp[g["pick"]] = lp.get(g["pick"], 0) + 1
    top_loss_pick = max(lp.items(), key=lambda x: x[1]) if lp else None
    return {
        "wallet": w, "name": name,
        "n_games": n, "wins": wins, "losses": losses,
        "win_rate": round(wins / n, 4) if n else None,
        "longest_loss_streak": longest,
        "current_loss_streak": trailing,
        "total_stake": round(sum(g["stake"] for g in decisive), 2),
        "net_pnl": round(sum(g["pnl"] for g in decisive), 2),
        "top_loss_pick": top_loss_pick[0] if top_loss_pick else None,
        "top_loss_pick_n": top_loss_pick[1] if top_loss_pick else 0,
        "sell_ratio": round(tot_sell[0] / tot_buy[0], 3) if tot_buy[0] else 0.0,
        "games": decisive,
    }


def main():
    games_data = json.load(open(f"{CACHE}/games.json"))
    cond_map = games_data["cond_map"]
    games = games_data["games"]
    # enrich cond_map with each market's question (for pick labels)
    for g in games.values():
        for m in g["conditions"]:
            if m["conditionId"] in cond_map:
                cond_map[m["conditionId"]]["question"] = m.get("question")
    candidates = json.load(open(f"{CACHE}/candidates.json"))
    wallets = list(candidates.keys())
    # resume support
    done = {}
    if os.path.exists(f"{CACHE}/results_partial.json"):
        done = {r["wallet"]: r for r in json.load(open(f"{CACHE}/results_partial.json"))}
    todo = [w for w in wallets if w not in done]
    results = list(done.values())
    lock = threading.Lock()
    t0 = time.time()
    counter = {"n": 0}

    def work(w):
        acts = wallet_activity(w)
        r = analyse(w, acts, cond_map, games)
        with lock:
            counter["n"] += 1
            if r["n_games"] >= 3:
                results.append(r)
            n = counter["n"]
            if n % 100 == 0 or n == len(todo):
                json.dump(results, open(f"{CACHE}/results_partial.json", "w"))
                rate = n / (time.time() - t0)
                eta = (len(todo) - n) / rate / 60 if rate else 0
                print(f"[crawl] {n}/{len(todo)} ({len(results)} kept) "
                      f"{rate:.1f}/s ETA {eta:.1f}min", flush=True)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, todo))

    json.dump(results, open(f"{CACHE}/results.json", "w"))
    print(f"[crawl] DONE: {len(results)} wallets with >=3 decisive games")


if __name__ == "__main__":
    main()
