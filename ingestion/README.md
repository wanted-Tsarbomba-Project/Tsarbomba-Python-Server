# Learning problem-set ingestion

The ingestion job reads ACTIVE problem sets from MySQL with a read-only account,
embeds only new or changed records, and synchronizes the local Chroma index.

Required environment variables:

- `GEMINI_API_KEY`
- `MYSQL_URL`

Run from the project root:

```powershell
python -m ingestion.run_ingest
```

The FastAPI server does not connect to MySQL. `MYSQL_URL` is used only by this
offline command. Do not log or commit database credentials.
