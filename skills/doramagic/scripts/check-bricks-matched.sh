#!/usr/bin/env bash
# PreToolUse hook: block Write if doramagic compiler hasn't run yet.
#
# Called by OpenClaw before any Write tool use when /dora skill is active.
# Checks that a compiler run exists and bricks were matched.
# Exit 0 = allow, exit 2 = block with message (TOOLUSE_REJECTED).

RUN_DIR="${HOME}/clawd/doramagic/runs"

if [ ! -d "$RUN_DIR" ]; then
    echo "BLOCKED: Doramagic compiler has not been executed yet. Run Step 1 first."
    exit 2
fi

# Find the most recent run directory (by modification time)
LATEST_RUN=$(ls -td "$RUN_DIR"/run_* 2>/dev/null | head -1)

if [ -z "$LATEST_RUN" ]; then
    echo "BLOCKED: No compiler run found. You must run the compiler before generating code."
    exit 2
fi

# Check that this run has completed (controller_state.json exists with a
# terminal phase). The pipeline writes controller_state.json on every phase
# transition and delivery_manifest.json on successful completion.
STATE_FILE="$LATEST_RUN/controller_state.json"
MANIFEST_FILE="$LATEST_RUN/delivery_manifest.json"

if [ ! -f "$STATE_FILE" ]; then
    echo "BLOCKED: Compiler run exists but has no state yet. Wait for it to complete."
    exit 2
fi

# Verify bricks were actually matched by checking phase_artifacts.
# Also verify the run is recent (within last 30 minutes) to prevent stale
# runs from granting blanket Write access.
python3 -c "
import json, sys, time, os

state = json.load(open('$STATE_FILE'))
arts = state.get('phase_artifacts', {})

# Check freshness — run must be from current session (mtime within 30 min)
mtime = os.path.getmtime('$STATE_FILE')
age_minutes = (time.time() - mtime) / 60
if age_minutes > 30:
    print('BLOCKED: Most recent compiler run is %.0f minutes old. Run the compiler again for this session.' % age_minutes)
    sys.exit(2)

# Check bricks were matched (via brick_stitch_result or compile output)
brick_result = arts.get('brick_stitch_result')
compile_result = arts.get('compile_result', {})
has_bricks = False

if brick_result and isinstance(brick_result, dict):
    has_bricks = True
elif compile_result.get('matched_bricks'):
    has_bricks = True

if not has_bricks:
    print('BLOCKED: Compiler ran but no bricks were matched. Re-run with a clearer requirement.')
    sys.exit(2)

# Check the run reached a delivery phase or completed
phase = state.get('phase', '')
terminal_phases = {'PHASE_G', 'COMPLETE', 'DONE', 'BRICK_STITCH_DONE', 'ERROR'}
if phase not in terminal_phases and not os.path.exists('$MANIFEST_FILE'):
    print('BLOCKED: Compiler is still running (phase: %s). Wait for completion.' % phase)
    sys.exit(2)

sys.exit(0)
" 2>/dev/null

RESULT=$?
if [ $RESULT -ne 0 ]; then
    # If python check failed and printed nothing, give a generic message
    [ $RESULT -eq 2 ] && exit 2
    echo "BLOCKED: Could not verify compiler state. Run the compiler first."
    exit 2
fi

exit 0
