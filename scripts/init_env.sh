#!/usr/bin/env bash
# Create .env from .env.example with freshly generated secrets. Safe to re-run: it never overwrites.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo ".env already exists, leaving it untouched"
  exit 0
fi

rand() { python3 -c "import secrets; print(secrets.token_hex(24))" 2>/dev/null || python -c "import secrets; print(secrets.token_hex(24))"; }
HMAC="$(rand)"
PW="$(rand)"

sed -e "s|^HMAC_SECRET=.*|HMAC_SECRET=${HMAC}|" \
    -e "s|^AI_READONLY_PASSWORD=.*|AI_READONLY_PASSWORD=${PW}|" \
    -e "s|ai_readonly:CHANGE_ME@|ai_readonly:${PW}@|" \
    .env.example > .env
echo "Created .env with generated secrets. Add your GEMINI_API_KEY (or OPENAI_API_KEY) to it."
