# Copilot Instructions (ETL Boilerplate)

These instructions guide Copilot when working in this repo.

## Scope

- Focus on ETL job creation, updates, and tests.
- Prefer small, safe changes with clear logging and error handling.

## ETL Job Workflow

1. Create a new job class in src/jobs/ that inherits from ETLJobBase.
2. Implement process() with request batch logging and attempts/state writes.
3. Register the job in src/main.py via the jobs mapping (job_code -> class).
4. Ensure logging schema exists (docs/logging.ddl.md) and configs are set.
5. Add tests under tests/ for transforms and idempotency.

## Conventions

- Use ETLJobBase.generate_uuid() for request_batch_id or attempt keys.
- Use repo helpers for insert_request_batch, insert_attempts_bulk, upsert_states_bulk.
- Prefer modular, testable design: isolate I/O from transformations.
- Keep transformations pure and small; pass dependencies in for external services.
- Split substantial logic into multiple small files/modules rather than a single large module.
- Close extra resources in finish() or __exit__.
- Use config from config/settings.py and setup_logging in src/utils/helpers.py.
- Use src/db/connection.get_connection("DB_KEY") for datamart access (keys from CONFIG["DBS"]).
- Prefer lazy connections opened in __enter__ and closed in finish() or __exit__.
- Use the context manager pattern (with ... as ...) for production runs.
- Keep production logic in src/; use notebooks only for exploration/prototyping.
- Do not override ETLJobBase lifecycle methods unless needed; put job logic in process().
- Use bulk insert patterns for writes and generator/streaming reads for large selects.
- If multithreading is required, use ThreadPoolExecutor.
- Server-side cursor note: with named cursors, `cur.description` may be None until the first fetch. In `iter_source_rows`, fetch one row if needed; return on empty result sets; only error if description remains None after a fetch (indicates non-SELECT).

## Data Extraction Rules (Mandatory)

- Use deterministic window key ranges (created_at or updated_at) with fixed [start, end) boundaries.
- For detail extracts, query in 3-hour windows (not full-day) to reduce memory use and keep capacity for other ETL jobs.
- Use generator/streaming and memory-safe processing.
- Mandate server-side cursors for large result sets.
- Forbid .fetchall() for large queries.
- Use the standard logging template (mandatory).
- Ensure runs are idempotent and replayable (mandatory).
- Use metadata-driven rules; do not hardcode KPI/dimension/filter/aggregation mappings.
- Implement error handling with retry policy and dead-letter/quarantine for bad rows.

## Useful Files

- ETL base class: src/interfaces/ETLJobBase.py
- Sample job: src/jobs/sample_push_orders.py
- Runner entry point: src/main.py
- Usage: docs/usage.md
