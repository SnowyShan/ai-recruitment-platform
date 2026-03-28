#!/bin/bash
# Run TalentBridge prompt safety audit
# Usage: ./run_audit.sh [--html]
# Add to your workflow: run before any commit that touches claude_client.py

cd "$(dirname "$0")"

if [ "$1" = "--html" ]; then
  promptfoo eval --no-cache --output report.html
  echo ""
  echo "Report saved to: $(pwd)/report.html"
else
  promptfoo eval --no-cache
fi
