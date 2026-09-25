# Security

## Reporting a vulnerability

Please open a private security advisory on GitHub (Security tab → Report a vulnerability)
instead of a public issue. Include steps to reproduce and the affected version or commit.

## Secrets

This repository must never contain secrets. Configuration comes from environment variables
(see `.env.example`); the real `.env` is git-ignored. The CI runs a secret scanner on every
push. If you fork this project:

- generate a long random `HMAC_SECRET` (the helper `scripts/init_env.sh` does it for you);
- create the read-only database role with your own password;
- rotate any API key that was ever pasted into a chat, ticket or log.

## Threat model in short

| Threat | Mitigation |
|---|---|
| Impersonating another user | Identity comes from a short-lived HMAC-signed token issued by Odoo, never from the browser or the model |
| The model reading data the user may not see | Permissions are checked in code (Odoo groups) before any query runs |
| The model running arbitrary SQL | It cannot: tools are fixed, parameterised queries |
| Reading other companies' data | Every query filters by the companies in the signed token |
| A database credential leak | The role can only `SELECT` from the `ai` views, has a 5 s statement timeout and read-only transactions |
| Prompt injection through documents or data | Tool output is declared as data in the system prompt, and tools cannot do anything outside their fixed list |
| XSS through model output | The chat escapes all HTML before applying its minimal markdown |
| Cost abuse | Per-user rate limit and a hard cap on agent iterations |

## Known limitations

- Retrieved documents are not access-controlled per user: every authenticated user can retrieve
  every ingested document. Do not ingest confidential material without adding that control.
- Question text and tool results are sent to the configured LLM provider. Use provider plans
  whose terms match your data-protection needs.
