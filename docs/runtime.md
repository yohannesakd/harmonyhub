# Runtime and Verification Notes

## Canonical startup

From `repo/`:

```bash
docker compose up --build
```

This starts the PostgreSQL database, FastAPI API, worker, Vue web runtime, and HTTPS proxy.

## Access points

- HTTPS application: `https://localhost:9443`
- HTTP redirect: `http://localhost:9080`
- API via proxy: `https://localhost:9443/api/v1`

## Canonical test gate

From `repo/`:

```bash
./run_tests.sh
```

This verifies:

- API pytest against a PostgreSQL test database
- worker pytest
- web Vitest suite

## Browser verification

From `repo/apps/web`:

```bash
npm run test:e2e
```

Artifacts are written to `repo/apps/web/e2e-artifacts/`.
