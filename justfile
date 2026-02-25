load:
    uv run sqlite-utils insert data-raw/data.db items data-raw/main.csv --csv --detect-types

tables:
    uv run sqlite-utils tables data-raw/data.db --counts

schema:
    uv run sqlite-utils schema data-raw/data.db

transform:
    uv run python build_db.py

serve:
    cd site && python3 -m http.server 8000
