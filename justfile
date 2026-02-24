import:
    uv run sqlite-utils insert data.db items main.csv --csv --detect-types

tables:
    uv run sqlite-utils tables data.db --counts

schema:
    uv run sqlite-utils schema data.db

export:
    uv run python build_db.py

serve:
    cd site && python3 -m http.server 8000
