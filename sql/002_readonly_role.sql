-- Read-only role for the assistant. Pass the password with: psql -v ai_pw="'...'"
-- (psql does not interpolate variables inside DO $$ blocks, hence format() + \gexec)
SELECT format('CREATE ROLE ai_readonly LOGIN PASSWORD %L', :ai_pw)
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ai_readonly')
\gexec

-- Keep the password in sync when the script is re-run with a new one.
SELECT format('ALTER ROLE ai_readonly PASSWORD %L', :ai_pw)
\gexec

REVOKE ALL ON SCHEMA public FROM ai_readonly;
SELECT format('GRANT CONNECT ON DATABASE %I TO ai_readonly', current_database())
\gexec
GRANT USAGE ON SCHEMA ai TO ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA ai TO ai_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA ai GRANT SELECT ON TABLES TO ai_readonly;
ALTER ROLE ai_readonly SET default_transaction_read_only = on;
ALTER ROLE ai_readonly SET statement_timeout = '5s';
