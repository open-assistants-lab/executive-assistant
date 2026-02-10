# Langfuse Deployment Plan (Ken Docker Stack)

## 1) Goal

Deploy Langfuse into the existing `docker/docker-compose.yml` stack (same VM as current `ken` + `postgres`) to improve model/tool visibility, latency debugging, and traceability.

This is a production-oriented plan with staged rollout and rollback.

---

## 2) Why This Is Worthwhile

Langfuse is not overkill for this stack because Ken has:
- Multiple LLM providers/models
- Heavy tool usage (including MCP)
- Multi-step workflows and stateful behavior
- Existing latency and reliability tuning work

Langfuse gives:
- End-to-end traces (model + tool chain)
- Cost/latency visibility
- Better debugging for false-positive “tool succeeded” cases

---

## 3) Target Architecture (Same Docker Compose)

Current:
- `ken`
- `postgres`

Add:
- `langfuse-web`
- `langfuse-worker`
- `redis` (or valkey)
- `clickhouse`
- `minio` (S3-compatible blob storage)

Decision:
- Reuse existing `postgres` container with a dedicated Langfuse DB/user (recommended for simplicity on same VM).

---

## 4) Environment and Secrets Plan

Add Langfuse env vars (in compose env file or dedicated `.env.langfuse`):

Core:
- `DATABASE_URL` (Langfuse DB connection in existing Postgres)
- `DIRECT_URL` (optional; migrations)
- `CLICKHOUSE_MIGRATION_URL`
- `CLICKHOUSE_URL`
- `CLICKHOUSE_USER`
- `CLICKHOUSE_PASSWORD`
- `REDIS_CONNECTION_STRING`
- `NEXTAUTH_URL`
- `NEXTAUTH_SECRET`
- `SALT`
- `ENCRYPTION_KEY` (64 hex chars)

Blob storage (MinIO):
- `LANGFUSE_S3_EVENT_UPLOAD_BUCKET`
- `LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT`
- `LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID`
- `LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY`
- `LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=true`
- `LANGFUSE_S3_MEDIA_UPLOAD_BUCKET`
- `LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT`
- `LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID`
- `LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY`
- `LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE=true`

Notes:
- Use separate passwords for Postgres (Ken vs Langfuse DB user), ClickHouse, Redis, MinIO.
- Keep secrets out of Git.
- Rotate existing exposed secrets in `docker/.env` before production hardening.

---

## 5) Compose Change Plan

## 5.1 New Services in `docker/docker-compose.yml`

1. `redis`
- Internal-only port (no public bind unless needed)
- Healthcheck

2. `clickhouse`
- Persistent volume
- Healthcheck
- Internal network only

3. `minio`
- Persistent volume
- Buckets initialized on startup (one-time init helper or manual bootstrap)

4. `langfuse-worker`
- Depends on postgres/clickhouse/redis/minio healthy
- Uses full env set above

5. `langfuse-web`
- Depends on worker + deps healthy
- Expose one UI port (default 3000) behind reverse proxy if internet-facing

## 5.2 Existing Services

1. `postgres`
- Add init SQL for Langfuse DB/user (new database + user + grants).
- Keep Ken DB untouched.

2. `ken`
- No startup dependency on Langfuse in phase 1 (avoid coupling).
- Add optional Langfuse SDK env vars later for tracing export.

---

## 6) Ken Integration Plan

Phase 1 (infra only):
- Bring up Langfuse stack and verify UI, project, API keys.

Phase 2 (instrumentation):
- Add Langfuse tracing to Ken LLM and tool execution paths.
- Attach metadata/tags:
  - `thread_id`
  - `conversation_id`
  - `channel`
  - `provider`
  - `model`
  - `tool_name`

Phase 3 (dashboards and guardrails):
- Dashboards:
  - p95/p99 latency by model
  - tool error rate by tool name
  - token and cost trends by model
- Add redaction policy for sensitive inputs/outputs.

---

## 7) API Access and Automation

Langfuse supports API access for trace/observation/metrics retrieval.

Planned use:
- Add a small internal script in Ken repo to query Langfuse APIs for:
  - failed tool-call traces
  - top slow traces
  - model cost/latency aggregates

Operational note:
- Some aggregate APIs may be eventually consistent (short lag acceptable for ops dashboards).

---

## 8) Rollout Steps

1. Prepare secrets and dedicated Langfuse DB user.
2. Add compose services and volumes.
3. `docker compose up -d postgres redis clickhouse minio`
4. Initialize buckets and DB grants.
5. Start `langfuse-worker` and `langfuse-web`.
6. Validate Langfuse UI and API key creation.
7. Integrate Ken tracing in staging.
8. Validate traces for:
  - normal chat turn
  - tool call turn
  - error turn
9. Roll to production and monitor.

---

## 9) Validation Checklist

- Langfuse UI reachable.
- Web and worker healthy.
- ClickHouse, Redis, MinIO healthy.
- Langfuse project and API keys created.
- Ken requests emit traces (model + tool spans visible).
- Sensitive fields redacted.
- No regression in Ken request latency > agreed threshold.

---

## 10) Rollback Plan

If issues occur:
1. Disable Ken->Langfuse instrumentation via env flag.
2. Keep Langfuse containers running for postmortem, or stop only web/worker.
3. Restore previous compose file and redeploy `ken`.

Data safety:
- Ken data remains in existing Postgres/volumes and is independent of Langfuse tracing path.

---

## 11) Sizing (Initial)

For single-VM start:
- VM: at least 4 vCPU / 16 GB RAM (Langfuse docs baseline for VM guidance)
- Disk: >=100 GB if trace volume expected to grow

Scale later by:
- Moving Redis/ClickHouse/Postgres to managed services
- Migrating from compose to Kubernetes/Terraform modules

---

## 12) Open Decisions

1. Public exposure:
- keep Langfuse UI private via VPN/SSH tunnel, or expose with SSO?

2. Storage:
- keep MinIO local in compose, or use managed S3-compatible storage?

3. Data retention:
- define retention windows for traces and media uploads.

4. Deployment mode:
- single compose file with Ken + Langfuse vs separate compose project on same host.

---

## 13) Reference Links

- Langfuse self-host Docker Compose guide: https://langfuse.com/self-hosting/deployment/docker-compose
- Langfuse self-host config/env vars: https://langfuse.com/self-hosting/configuration
- Langfuse public API docs: https://langfuse.com/docs/api-and-data-platform/features/public-api
- Langfuse observations API: https://langfuse.com/docs/api-and-data-platform/features/observations-api
- Langfuse metrics API: https://langfuse.com/docs/metrics/features/metrics-api
