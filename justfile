import:
    uv run sqlite-utils insert data.db items main.csv --csv --detect-types

tables:
    uv run sqlite-utils tables data.db --counts

schema:
    uv run sqlite-utils schema data.db
