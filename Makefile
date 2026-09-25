DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: demo up down test test-js lint ingest eval-rag eval-agent chat

demo:       ## create the Odoo demo DB, install views/role/module, start everything
	./scripts/setup_demo.sh

up:         ## start the stack in development mode (code, tests and evals mounted, auto-reload)
	$(DEV) up -d --build

down:
	docker compose down

test:       ## Python tests (the ones that need a database run when the stack is up)
	$(DEV) run --rm assistant python -m pytest -q

test-js:    ## chat component tests (needs Node 22)
	node --test "tests/js/*.test.mjs"

lint:
	$(DEV) run --rm assistant ruff check .

ingest:     ## (re)index the documents in ./corpus
	docker compose exec assistant python -m api.rag.ingest corpus

eval-rag:   ## retrieval quality on the golden set (run `make up` first)
	$(DEV) exec assistant python -m evals.rag_eval

eval-agent: ## end-to-end agent evaluation against the demo data (uses LLM quota)
	$(DEV) exec assistant python -m evals.agent_eval

chat:       ## console chat as a regular employee
	docker compose exec assistant python -m api.dev_cli --role user
