#!/usr/bin/env bash
# Defer any git push to main — requires human approval.
set -euo pipefail

payload="$(cat)"
cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

case "$cmd" in
  *"git push"*"origin main"*|*"git push"*" main"*|*"git push --force"*)
    jq -nc '{
      "permissionDecision": "defer",
      "reason": "Push to main requires Sanjana approval."
    }'
    ;;
  *)
    jq -nc '{"permissionDecision": "allow"}'
    ;;
esac
