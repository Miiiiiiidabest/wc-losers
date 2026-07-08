#!/bin/bash
# Daily refresh of the World Cup losing-wallets dashboards.
# Self-uninstalls after the World Cup final (2026-07-19).
set -u
# NOTE: lives OUTSIDE ~/Documents on purpose — macOS TCC blocks launchd
# background jobs from touching Documents ("Operation not permitted").
PROJ="$HOME/wclosers"
cd "$PROJ" || exit 1
LOG="$PROJ/refresh.log"
LOCK="$PROJ/.refresh.lock"
PLIST="$HOME/Library/LaunchAgents/com.wclosers.refresh.plist"
END="2026-07-20"          # day AFTER the final; stop once past this
TODAY=$(date +%Y-%m-%d)

echo "=== refresh start $(date) (today=$TODAY) ===" >> "$LOG"

# 1) stop after the World Cup is over
if [[ "$TODAY" > "$END" ]]; then
  echo "World Cup finished ($TODAY > $END). Self-uninstalling daily job." >> "$LOG"
  launchctl unload "$PLIST" 2>/dev/null
  rm -f "$PLIST"
  exit 0
fi

# 2) don't overlap with a still-running refresh
if [ -f "$LOCK" ]; then
  echo "Previous refresh still running (lock present). Skipping." >> "$LOG"
  exit 0
fi
touch "$LOCK"
trap 'rm -f "$LOCK"' EXIT

PY=$(command -v python3)
[ -z "$PY" ] && PY=/usr/bin/python3

# 3) refresh pipeline: games+discover -> clear stale cache -> crawl -> rebuild
"$PY" collect.py discover            >> "$LOG" 2>&1
rm -rf cache/activity && mkdir -p cache/activity
rm -f cache/results_partial.json cache/results.json
"$PY" crawl.py                       >> "$LOG" 2>&1
"$PY" build_dashboard.py             >> "$LOG" 2>&1
"$PY" build_match_tool.py            >> "$LOG" 2>&1

# 4) publish to GitHub Pages (miiiiiiidabest.github.io/wc-losers)
# launchd's PATH lacks /opt/homebrew/bin, where gh (git's credential helper) lives
export PATH="/opt/homebrew/bin:$PATH"
if [ -d "$PROJ/site/.git" ]; then
  "$PY" build_dashboard.py site      >> "$LOG" 2>&1
  sed 's|href="dashboard.html"|href="./"|' "$PROJ/match_breakdown.html" > "$PROJ/site/match.html"
  cd "$PROJ/site"
  git add -A
  if ! git diff --cached --quiet; then
    git commit -q -m "daily refresh $(date +%Y-%m-%d)"
    git push -q origin main          >> "$LOG" 2>&1 && \
      echo "site published $(date)"  >> "$LOG" || \
      echo "site push FAILED $(date)" >> "$LOG"
  fi
  cd "$PROJ"
fi

echo "=== refresh done $(date) ===" >> "$LOG"
