#!/usr/bin/env python3
"""
Polymarket World Cup "losing wallets" collector.

Pipeline:
  1) games   -> fetch all RESOLVED 2026 World Cup match-result events (3-way: home/draw/away)
                build conditionId -> (game, winning outcome index) map
  2) discover -> walk accessible recent trades of every market, collect candidate wallets
                 keep only wallets active in >= MIN_GAMES distinct games
  3) crawl    -> for each candidate, pull full per-wallet activity, compute per-game P&L,
                 win/loss sequence, longest & current losing streak, win rate
Outputs JSON into cache/ ; build_dashboard.py turns results.json into an HTML page.
"""
import urllib.request, urllib.error, json, time, os, sys

CACHE = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}
GAMMA = "https://gamma-api.polymarket.com"
DATA = "https://data-api.polymarket.com"

MIN_GAMES = 3          # a wallet must bet on >= this many games to be a candidate
DISCOVER_PAGES = 4     # pages of 500 recent trades per market for wallet discovery (cap ~2000)


def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 400:
                return None          # offset past the cap
            time.sleep(1.5 * (i + 1))
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


# ---------------------------------------------------------------- 1) games
def is_result_event(e):
    t = e.get("title", "").lower()
    if len(e.get("markets", [])) != 3:
        return False
    bad = ["announcer", " say", "h2h", "corner", "exact", "halftime",
           "half result", "first team", "props", "more markets", "total",
           "penalty", "starting", "second half"]
    if any(b in t for b in bad):
        return False
    return " vs" in t


def fetch_games():
    events = []
    off = 0
    while True:                     # page until exhausted (event count keeps growing)
        d = get(f"{GAMMA}/events?tag_slug=fifa-world-cup&limit=100&offset={off}"
                f"&closed=true&order=endDate&ascending=false")
        if not d:
            break
        events += d
        if len(d) < 100 or off > 5000:
            break
        off += 100
    games = {}            # game_id -> game record
    cond_map = {}         # conditionId -> {game_id, win_index}
    for e in events:
        if not is_result_event(e):
            continue
        gid = str(e["id"])
        markets = []
        resolved = True
        for m in e["markets"]:
            try:
                prices = json.loads(m.get("outcomePrices") or "[]")
            except Exception:
                prices = []
            if not prices or "1" not in prices:
                resolved = False
                break
            win_index = prices.index("1")          # 0=Yes wins, 1=No wins
            cid = m["conditionId"]
            markets.append({"conditionId": cid, "question": m.get("question"),
                            "win_index": win_index})
            cond_map[cid] = {"game_id": gid, "win_index": win_index}
        if not resolved:
            # roll back any cond entries for this unresolved game
            for m in e["markets"]:
                cond_map.pop(m.get("conditionId"), None)
            continue
        games[gid] = {"game_id": gid, "title": e.get("title", "").strip(),
                      "end_date": e.get("endDate"), "slug": e.get("slug"),
                      "conditions": markets}
    out = {"games": games, "cond_map": cond_map}
    json.dump(out, open(f"{CACHE}/games.json", "w"))
    print(f"[games] {len(games)} resolved games, {len(cond_map)} markets")
    return out


# ---------------------------------------------------------------- 2) discover
def discover(games_data):
    cond_map = games_data["cond_map"]
    # wallet -> set of game_ids seen
    wallet_games = {}
    conds = list(cond_map.keys())
    for i, cid in enumerate(conds):
        gid = cond_map[cid]["game_id"]
        for page in range(DISCOVER_PAGES):
            d = get(f"{DATA}/trades?market={cid}&limit=500&offset={page*500}")
            if not d:
                break
            for tr in d:
                w = tr.get("proxyWallet")
                if w:
                    wallet_games.setdefault(w, set()).add(gid)
            if len(d) < 500:
                break
        if (i + 1) % 10 == 0 or i + 1 == len(conds):
            print(f"[discover] {i+1}/{len(conds)} markets, "
                  f"{len(wallet_games)} wallets so far")
    candidates = {w: sorted(gs) for w, gs in wallet_games.items()
                  if len(gs) >= MIN_GAMES}
    json.dump({w: gs for w, gs in candidates.items()},
              open(f"{CACHE}/candidates.json", "w"))
    dist = {}
    for gs in wallet_games.values():
        dist[len(gs)] = dist.get(len(gs), 0) + 1
    print(f"[discover] {len(wallet_games)} total wallets; "
          f"{len(candidates)} candidates with >= {MIN_GAMES} games")
    print(f"[discover] games-per-wallet distribution (top): "
          f"{dict(sorted(dist.items())[:12])}")
    return candidates


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("games", "all", "discover"):
        gd = fetch_games()
    if stage in ("discover", "all"):
        gd = json.load(open(f"{CACHE}/games.json"))
        discover(gd)
