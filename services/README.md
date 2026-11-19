# Project T Cloud Control Plane (`services/`)

Optional MVP v0.5 cloud control plane providing:
- `authentication`: User accounts, PBKDF2 password hashing, JWT tokens, and local installation/device pairing.
- `cloud_sync`: Strict opt-in, metadata-only synchronization with idempotent `(installation_id, run_id)` upsert and monotonic `optimization_rules` conflict handling.
- `analytics`: Multi-device rollups separating `exact`, `estimated`, and `provider-confirmed` savings, cost avoided, trends, fallbacks, benchmarks, and latency percentiles.

Runs against PostgreSQL (`infrastructure/database/postgres/001_initial_cloud_schema.sql`) in Docker/cloud deployments, with built-in SQLite support for local tests and offline CI verification. Local Runtime never requires this service to operate.
