# Backend

```bash
poetry install
poetry run uvicorn app.main:app --reload
```

Health checks: `GET /live` and `GET /ready`.
