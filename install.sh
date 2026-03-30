#!/usr/bin/env bash
# Doramagic one-line installer
# Usage: curl -fsSL https://raw.githubusercontent.com/tangweigang-jpg/Doramagic/main/install.sh | bash
#
# Detects OpenClaw / Claude Code and installs Doramagic as a skill.
# No git clone needed — downloads the latest release directly.

set -euo pipefail

REPO="tangweigang-jpg/Doramagic"
BRANCH="main"
SKILL_DIR_NAME="dora"
TARBALL_URL="https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { printf '\033[1;34m[info]\033[0m  %s\n' "$*"; }
ok()    { printf '\033[1;32m[ok]\033[0m    %s\n' "$*"; }
warn()  { printf '\033[1;33m[warn]\033[0m  %s\n' "$*"; }
fail()  { printf '\033[1;31m[error]\033[0m %s\n' "$*"; exit 1; }

# ---------------------------------------------------------------------------
# Detect host environment
# ---------------------------------------------------------------------------
TARGETS=()

if command -v openclaw &>/dev/null; then
    # OpenClaw can install directly from ClawHub
    TARGETS+=("openclaw")
    info "Detected OpenClaw $(openclaw -V 2>/dev/null || echo '')"
fi

if [ -d "$HOME/.claude" ]; then
    TARGETS+=("claude")
    info "Detected Claude Code (~/.claude exists)"
fi

if [ ${#TARGETS[@]} -eq 0 ]; then
    fail "No supported host found. Install OpenClaw or Claude Code first."
fi

# ---------------------------------------------------------------------------
# Check Python 3.12+
# ---------------------------------------------------------------------------
PYTHON=""
for cmd in python3.12 python3.13 python3.14 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c 'import sys; print(sys.version_info[:2])' 2>/dev/null || echo "(0,0)")
        major=$(echo "$ver" | grep -o '[0-9]*' | head -1)
        minor=$(echo "$ver" | grep -o '[0-9]*' | tail -1)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 12 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python 3.12+ is required. Install it first: https://docs.astral.sh/uv/"
fi
info "Using $PYTHON ($($PYTHON --version))"

# ---------------------------------------------------------------------------
# Set up dedicated virtualenv for Doramagic
# ---------------------------------------------------------------------------
VENV_DIR="$HOME/.doramagic/venv"

if [ ! -d "$VENV_DIR" ]; then
    info "Creating virtualenv at $VENV_DIR..."
    if command -v uv &>/dev/null; then
        uv venv "$VENV_DIR" --python "$PYTHON"
    else
        $PYTHON -m venv "$VENV_DIR"
    fi
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

info "Installing Python dependencies into $VENV_DIR..."

if command -v uv &>/dev/null; then
    uv pip install --python "$VENV_PYTHON" pydantic 2>/dev/null
else
    "$VENV_PIP" install --quiet pydantic
fi

# Install at least one LLM SDK if none is available
has_sdk=false
for sdk in anthropic openai google.generativeai; do
    if "$VENV_PYTHON" -c "import $sdk" 2>/dev/null; then
        has_sdk=true
        break
    fi
done

if ! $has_sdk; then
    warn "No LLM SDK found. Installing 'anthropic' (you can also install 'openai' or 'google-genai')."
    if command -v uv &>/dev/null; then
        uv pip install --python "$VENV_PYTHON" anthropic 2>/dev/null
    else
        "$VENV_PIP" install --quiet anthropic
    fi
fi

ok "Python dependencies ready"

# ---------------------------------------------------------------------------
# Install for each detected host
# ---------------------------------------------------------------------------
for target in "${TARGETS[@]}"; do
    case "$target" in

    openclaw)
        info "Installing to OpenClaw via ClawHub..."
        if openclaw skills install doramagic --force 2>&1; then
            ok "OpenClaw: installed doramagic from ClawHub"
        else
            warn "ClawHub install failed, falling back to manual copy..."
            # Fallback: download and copy
            tmpdir=$(mktemp -d)
            trap "rm -rf $tmpdir" EXIT
            curl -fsSL "$TARBALL_URL" | tar xz -C "$tmpdir"
            src="$tmpdir/Doramagic-${BRANCH}/skills/doramagic"
            dest="$HOME/.openclaw/skills/$SKILL_DIR_NAME"
            mkdir -p "$HOME/.openclaw/skills"
            rm -rf "$dest"
            cp -rL "$src" "$dest"
            ok "OpenClaw: installed to $dest (manual copy)"
        fi
        ;;

    claude)
        info "Installing to Claude Code..."
        tmpdir=$(mktemp -d)
        trap "rm -rf $tmpdir" EXIT
        curl -fsSL "$TARBALL_URL" | tar xz -C "$tmpdir"
        src="$tmpdir/Doramagic-${BRANCH}/skills/doramagic"
        dest="$HOME/.claude/skills/$SKILL_DIR_NAME"
        mkdir -p "$HOME/.claude/skills"
        rm -rf "$dest"
        cp -rL "$src" "$dest"
        ok "Claude Code: installed to $dest"
        ;;

    esac
done

# ---------------------------------------------------------------------------
# Post-install: configure models.json
# ---------------------------------------------------------------------------
echo ""
info "Almost done! Configure your models:"
echo ""

for target in "${TARGETS[@]}"; do
    case "$target" in
    openclaw)
        models_dir="$HOME/.openclaw/workspace/skills/doramagic"
        [ -d "$models_dir" ] || models_dir="$HOME/.openclaw/skills/$SKILL_DIR_NAME"
        ;;
    claude)
        models_dir="$HOME/.claude/skills/$SKILL_DIR_NAME"
        ;;
    esac

    models_json="$models_dir/models.json"
    models_example="$models_dir/models.json.example"

    if [ ! -f "$models_json" ] && [ -f "$models_example" ]; then
        cp "$models_example" "$models_json"
        info "Created $models_json from example template"
        echo "  -> Edit this file to declare your available models."
    elif [ -f "$models_json" ]; then
        ok "$models_json already exists"
    fi
done

echo ""
echo "  Set your API key(s):"
echo "    export ANTHROPIC_API_KEY=\"sk-...\""
echo "    export GOOGLE_API_KEY=\"...\"       # optional"
echo "    export OPENAI_API_KEY=\"...\"       # optional"
echo ""
echo "  Then restart your session and run:"
echo "    /dora https://github.com/owner/repo"
echo ""
ok "Doramagic installation complete!"
