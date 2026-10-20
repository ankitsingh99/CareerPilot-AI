#!/usr/bin/env bash
# harden_repo.sh - audit and clean up the ai-job-search repo. Run from the repo root.
# Dry run by default (prints, changes nothing). Apply with:  DRY=0 bash harden_repo.sh
set -uo pipefail
DRY="${DRY:-1}"
[ -d .git ] || { echo "Run this from the repo root."; exit 1; }
say() { printf '\n== %s ==\n' "$*"; }

say "1. Tracked files that .gitignore says must NOT be tracked"
LEAKED=$(git ls-files -ci --exclude-standard)
if [ -z "$LEAKED" ]; then
  echo "none"
else
  echo "$LEAKED"
  if [ "$DRY" = "0" ]; then
    git ls-files -ci --exclude-standard -z | xargs -0 git rm --cached -q --
    echo "-> untracked (files stay on disk). Commit this."
  else
    echo "[dry] would run: git rm --cached on the files above"
  fi
fi

say "2. Personal-data patterns in tracked files (review every hit)"
git grep -nIE '\b[6-9][0-9]{9}\b|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|\b[0-9]{4} ?[0-9]{4} ?[0-9]{4}\b|\b[A-Z]{5}[0-9]{4}[A-Z]\b|\b(LPA|CTC)\b' -- . ':!bun.lock' | head -60

say "3. History: commits that ever touched secret-bearing paths"
git log --all --oneline -- client_secret.json user_inputs .browser_session jobs.db job_search_tracker.csv | head -20
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --source . --redact
else
  echo "tip: brew install gitleaks, then re-run for a full-history secret scan"
fi

say "4. .gitignore additions"
for p in "user_inputs/" "candidate_preferences_and_rules.md"; do
  if ! grep -qxF "$p" .gitignore 2>/dev/null; then
    [ "$DRY" = "0" ] && echo "$p" >> .gitignore
    echo "add: $p"
  fi
done

say "5. .geminiignore suggestion (written to .geminiignore.suggested, never overwrites)"
if [ "$DRY" = "0" ]; then
cat > .geminiignore.suggested <<'EOT'
# Upstream docs the agent never needs
README.md
CONTRIBUTING.md
CHANGELOG.md
SECURITY.md
SETUP.md
LICENSE
.github/
assets/
tests/
tools/
# Denmark-only code (no use for an India search)
salary_lookup.py
.agents/skills/jobbank-search/
.agents/skills/jobdanmark-search/
.agents/skills/jobindex-search/
.agents/skills/jobnet-search/
# Dependencies and binaries
**/node_modules/
**/bun.lock
*.pdf
*.gif
cover_letters/OpenFonts/
# Data the agent should query via script, not read whole
job_search_tracker.csv
jobs.db
*.db
company_research/
# Sensitive or archived
client_secret.json
.browser_session/
user_inputs/
**/Archive/
**/archive/
EOT
echo "wrote .geminiignore.suggested - diff it against your current .geminiignore"
else
  echo "[dry] would write .geminiignore.suggested"
fi

say "6. Always-loaded instruction files (approx tokens = bytes / 4)"
for f in CLAUDE.md GEMINI.md AGENTS.md; do
  [ -f "$f" ] && printf '%7d tok  %s\n' $(( $(wc -c < "$f") / 4 )) "$f"
done

say "7. Largest tracked text files (approx tokens)"
git ls-files -z | xargs -0 wc -c 2>/dev/null | grep -v ' total$' \
  | grep -viE '\.(gif|ttf|otf|png|jpg|pdf|lock)$' | sort -nr | head -15 \
  | awk '{n=$1; $1=""; printf "%7d tok %s\n", n/4, substr($0,2)}'

say "Manual steps this script cannot do"
cat <<'EOT'
1. GitHub > Settings > Danger Zone > Change visibility > Private   (do this first)
2. Move client_secret.json and .browser_session/ OUT of the repo folder, e.g. ~/.config/job-agent/
3. Remove address, phone, email and CTC from GEMINI.md and CLAUDE.md; keep one profile file, read on demand
4. Add permissions.deny Read rules for secrets in .claude/settings.json
5. If the repo ever goes public again, purge history first (git filter-repo) or start a fresh repo
EOT
