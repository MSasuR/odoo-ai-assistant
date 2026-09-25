#!/usr/bin/env bash
# One-shot demo setup: Odoo 19 with demo data + the `ai` views + the assistant + the sample corpus.
# Idempotent: safe to run again.
set -euo pipefail
cd "$(dirname "$0")/.."

DB="${ODOO_DEMO_DB:-demo}"
COMPOSE="docker compose"

[ -f .env ] || ./scripts/init_env.sh
set -a
# shellcheck disable=SC1091
source .env
set +a

echo "==> 1/6 Starting the databases"
$COMPOSE up -d --wait odoo-db pgvector

echo "==> 2/6 Creating the Odoo '$DB' database with demo data (first run takes a few minutes)"
if $COMPOSE exec -T odoo-db psql -U odoo -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -q 1; then
  echo "    database already exists, installing/updating the module only"
  $COMPOSE run --rm odoo odoo -d "$DB" -u ai_assistant_chat --stop-after-init
else
  # Odoo 19 only loads demo data when asked to (--with-demo).
  $COMPOSE run --rm odoo odoo -d "$DB" --with-demo \
    -i base,hr,hr_holidays,sale_management,account,ai_assistant_chat --stop-after-init
fi

echo "==> 3/6 Installing the read-only 'ai' views and role"
$COMPOSE exec -T odoo-db psql -U odoo -d "$DB" -v ON_ERROR_STOP=1 -q < sql/001_ai_schema_views.sql
$COMPOSE exec -T odoo-db psql -U odoo -d "$DB" -v ON_ERROR_STOP=1 -q \
  -v ai_pw="'${AI_READONLY_PASSWORD}'" < sql/002_readonly_role.sql

echo "==> 4/6 Configuring the Odoo module (API URL and signing secret)"
$COMPOSE run --rm -T -e HMAC_SECRET="$HMAC_SECRET" odoo \
  odoo shell -d "$DB" --no-http < scripts/configure_odoo.py 2>&1 | grep -E "CONFIGURED|Error|Traceback" || true

echo "==> 5/6 Building and starting the assistant"
$COMPOSE up -d --build assistant

echo "==> 6/6 Ingesting the sample corpus (needs a working API key in .env)"
if grep -Eq '^(GEMINI_API_KEY|OPENAI_API_KEY)=.+' .env; then
  $COMPOSE exec -T assistant python -m api.rag.ingest corpus
else
  echo "    skipped: add GEMINI_API_KEY (or OPENAI_API_KEY) to .env, then run:"
  echo "    docker compose exec assistant python -m api.rag.ingest corpus"
fi

$COMPOSE up -d odoo
cat <<MSG

Ready.
  Odoo      http://localhost:${ODOO_PORT:-8069}   (database: $DB)   logins: admin / admin, demo / demo
  Assistant http://localhost:${ASSISTANT_PORT:-8000}/health

Open Odoo and click the chat icon in the top bar. Or try it from the terminal:
  docker compose exec assistant python -m api.dev_cli --role user
MSG
