# Timesheet Matcher

Hostinger-managed Docker project for the Teamwork timesheet matching assistant.

Current milestone: FastAPI serves a built React frontend and exposes `/api/health`.

## Runtime

```bash
cd /workspace
.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## Tests

```bash
cd /workspace/backend
PYTHONPATH=/workspace/backend /workspace/.venv/bin/pytest tests -q
```
