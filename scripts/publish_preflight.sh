#!/usr/bin/env bash
# Doramagic -- GitHub Release Preflight Check
#
# Run this BEFORE every GitHub push/release.
# All checks must pass. Any failure blocks the release.
#
# Usage:
#   bash scripts/publish_preflight.sh           # check current tree
#   bash scripts/publish_preflight.sh --fix     # auto-fix what's possible, report the rest
#
# Exit codes:
#   0 = all checks passed
#   1 = failures found (release blocked)

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

FAIL_COUNT=0
WARN_COUNT=0
FIX_MODE=false
[[ "${1:-}" == "--fix" ]] && FIX_MODE=true

pass() { echo -e "  ${GREEN}PASS${NC}  $1"; }
fail() { echo -e "  ${RED}FAIL${NC}  $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
warn() { echo -e "  ${YELLOW}WARN${NC}  $1"; WARN_COUNT=$((WARN_COUNT + 1)); }

echo -e "\n${BOLD}=== Doramagic Publish Preflight ===${NC}\n"

# -- 1. Community standard files --
echo -e "${BOLD}[1/9] Community standard files${NC}"
for f in README.md LICENSE CHANGELOG.md CONTRIBUTING.md SECURITY.md INSTALL.md .env.example .gitignore; do
    if [[ -f "$f" ]]; then
        pass "$f exists"
    else
        fail "$f missing"
    fi
done

# Helper: grep only git-tracked files
grep_tracked() {
    # $1 = pattern, rest = grep flags
    local pattern="$1"; shift
    git ls-files -z "$@" | xargs -0 grep -n "$pattern" 2>/dev/null || true
}

# -- 2. No hardcoded internal IPs --
echo -e "\n${BOLD}[2/9] No hardcoded internal IPs${NC}"
IP_HITS=$(grep_tracked '192\.168\.[0-9]\+\.[0-9]\+' -- '*.py' '*.sh' '*.md' '*.yml' '*.yaml' '*.json' | grep -v 'publish_preflight.sh' || true)
if [[ -z "$IP_HITS" ]]; then
    pass "No internal IPs found"
else
    fail "Internal IPs found:"
    echo "$IP_HITS" | head -20 | sed 's/^/         /'
fi

# -- 3. No credentials or secrets --
echo -e "\n${BOLD}[3/9] No credentials or secrets${NC}"
SECRET_HITS=$(grep_tracked 'sk-ant\|sk-[a-zA-Z0-9]\{20,\}\|ghp_\|gho_\|github_pat_\|password\s*=\s*["\x27][A-Za-z0-9]' -- '*.py' '*.ts' '*.js' '*.json' '*.md' | grep -v '.env.example\|models.json.example\|publish_preflight.sh' || true)
if [[ -z "$SECRET_HITS" ]]; then
    pass "No secrets found"
else
    fail "Potential secrets found:"
    echo "$SECRET_HITS" | head -20 | sed 's/^/         /'
fi

# -- 4. No hardcoded paths --
echo -e "\n${BOLD}[4/9] No hardcoded user paths${NC}"
PATH_HITS=$(grep_tracked '/Users/\|/home/tangsir\|/home/admin\|vibecoding\|Doramagic-racer' -- '*.py' '*.sh' '*.md' '*.yml' | grep -v 'publish_preflight.sh' || true)
if [[ -z "$PATH_HITS" ]]; then
    pass "No hardcoded user paths"
else
    fail "Hardcoded paths found:"
    echo "$PATH_HITS" | head -20 | sed 's/^/         /'
fi

# -- 5. No internal artifacts (stranger test) --
echo -e "\n${BOLD}[5/9] No internal artifacts${NC}"

# Files that should never be in a public repo
INTERNAL_PATTERNS=(
    "WORKLOG" "DECISIONS" "BRIEF" "backup" "draft"
    "dev-brief" "engineering-plan" "brainstorm"
)
INTERNAL_HITS=""
for pattern in "${INTERNAL_PATTERNS[@]}"; do
    hits=$(git ls-files "*${pattern}*" 2>/dev/null || true)
    [[ -n "$hits" ]] && INTERNAL_HITS="${INTERNAL_HITS}${hits}\n"
done
if [[ -z "$INTERNAL_HITS" ]]; then
    pass "No internal artifact filenames"
else
    fail "Internal artifacts found:"
    echo -e "$INTERNAL_HITS" | head -20 | sed 's/^/         /'
fi

# Date-stamped files (AI session artifacts)
DATE_HITS=$(git ls-files '2026[0-9]*_*.md' '**/2026[0-9]*_*.md' 2>/dev/null || true)
if [[ -z "$DATE_HITS" ]]; then
    pass "No date-stamped files"
else
    fail "Date-stamped files found (AI session artifacts):"
    echo "$DATE_HITS" | head -10 | sed 's/^/         /'
fi

# Binary files
BINARY_HITS=$(git ls-files '*.pdf' '*.png' '*.jpg' '*.jpeg' '*.xlsx' '*.zip' '*.tar.gz' 2>/dev/null || true)
if [[ -z "$BINARY_HITS" ]]; then
    pass "No binary files"
else
    fail "Binary files found:"
    echo "$BINARY_HITS" | head -10 | sed 's/^/         /'
fi

# Backup files
BACKUP_HITS=$(git ls-files '*.bak' '*.old' '*.backup' '*-backup*' 2>/dev/null || true)
if [[ -z "$BACKUP_HITS" ]]; then
    pass "No backup files"
else
    fail "Backup files found:"
    echo "$BACKUP_HITS" | head -10 | sed 's/^/         /'
fi

# Directories that should not be public
for dir in research experiments races docs; do
    if [[ -d "./$dir" ]] && git ls-files "$dir" 2>/dev/null | head -1 | grep -q .; then
        fail "$dir/ is tracked by git (should be gitignored)"
    else
        pass "$dir/ not tracked (or absent)"
    fi
done

# Internal files that should not be tracked
for f in TODOS.md INDEX.md; do
    if git ls-files "$f" 2>/dev/null | grep -q .; then
        fail "$f is tracked (internal file)"
    else
        pass "$f not tracked"
    fi
done

# -- 6. Stranger test -- list non-code files for human review --
echo -e "\n${BOLD}[6/9] Stranger test (manual review required)${NC}"
NON_CODE=$(git ls-files '*.md' '*.txt' '*.rst' '*.html' '*.pdf' '*.py' | grep -v '^packages/\|^tests/\|^scripts/\|^skills/doramagic/\|^bricks/\|^data/fixtures/' | grep -v '^README\|^LICENSE\|^CHANGELOG\|^CONTRIBUTING\|^SECURITY\|^INSTALL\|^Makefile\|^pyproject\|^\.env\|^\.git\|^models\.json' || true)
if [[ -z "$NON_CODE" ]]; then
    pass "No unexpected non-code files"
else
    warn "Non-standard files tracked -- does a stranger need each of these?"
    echo "$NON_CODE" | sed 's/^/         /'
    echo -e "         ${YELLOW}^ Review each file above. Remove if it fails the stranger test.${NC}"
fi

# -- 7. Version consistency --
echo -e "\n${BOLD}[7/9] Version consistency${NC}"

# Extract version from pyproject.toml
PY_VER=$(grep '^version' pyproject.toml 2>/dev/null | head -1 | sed 's/.*"\(.*\)".*/\1/' || echo "unknown")
# Extract version from SKILL.md
SKILL_VER=$(grep '^version:' skills/doramagic/SKILL.md 2>/dev/null | awk '{print $2}' || echo "unknown")
# Extract version from CHANGELOG.md (first version heading)
CL_VER=$(grep -m1 '^## \[v\?[0-9]' CHANGELOG.md 2>/dev/null | sed 's/.*\[\(v\?\)\([0-9][0-9.]*\).*/\2/' || echo "unknown")

echo "         pyproject.toml: $PY_VER"
echo "         SKILL.md:       $SKILL_VER"
echo "         CHANGELOG.md:   $CL_VER"

if [[ "$SKILL_VER" == "$CL_VER" ]] || [[ "$PY_VER" != "0.1.0" && "$PY_VER" == "$SKILL_VER" ]]; then
    pass "Versions are consistent"
else
    warn "Version mismatch -- review before tagging"
fi

# -- 8. README freshness --
echo -e "\n${BOLD}[8/9] README freshness${NC}"
README_VER=$(grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' README.md 2>/dev/null | head -1 || echo "none")
echo "         README mentions: $README_VER"
if [[ "$README_VER" == "v${SKILL_VER}" ]] || [[ "$README_VER" == "${SKILL_VER}" ]]; then
    pass "README version matches SKILL.md"
else
    warn "README version ($README_VER) differs from SKILL.md ($SKILL_VER)"
fi

# -- 9. Dependency lockfile --
echo -e "\n${BOLD}[9/9] Dependency lockfile${NC}"
if [[ -f "uv.lock" ]]; then
    if git ls-files uv.lock 2>/dev/null | grep -q .; then
        pass "uv.lock exists and is tracked"
    else
        warn "uv.lock exists but is NOT tracked by git"
    fi
else
    warn "uv.lock not found"
fi

# -- Summary --
echo -e "\n${BOLD}====================================${NC}"
if [[ $FAIL_COUNT -eq 0 && $WARN_COUNT -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}ALL CHECKS PASSED${NC} -- clear to release"
elif [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "${YELLOW}${BOLD}$WARN_COUNT WARNING(s)${NC} -- review before release"
else
    echo -e "${RED}${BOLD}$FAIL_COUNT FAILURE(s), $WARN_COUNT WARNING(s)${NC} -- RELEASE BLOCKED"
fi
echo -e "${BOLD}====================================${NC}\n"

exit $FAIL_COUNT
