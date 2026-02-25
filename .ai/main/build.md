# Build

## Key files
| File | Purpose |
|------|---------|
| `data-raw/main.csv` | Source CSV (gitignored) |
| `data-raw/data.db` | Full SQLite import from CSV (gitignored) |
| `build_db.py` | Transforms data-raw/data.db → site/data.db |
| `site/data.db` | Slim SQLite with items + hierarchy tables (gitignored) |
| `site/index.html` | Self-contained SPA (HTML + CSS + vanilla JS) |
| `justfile` | Recipes: `load`, `transform`, `serve`, `tables`, `schema` |

## Indexes on items table
- idx_tipo, idx_grupo, idx_classe, idx_codigo
- idx_composite (tipo, grupo, classe)

## Data pipeline
`data-raw/main.csv` → `just load` → `data-raw/data.db` → `just transform` → `site/data.db`

## Justfile recipes
- `just load` — imports data-raw/main.csv into data-raw/data.db via sqlite-utils
- `just transform` — runs build_db.py to create data/data.db from data-raw/data.db
- `just serve` — starts local HTTP server on port 8000

## Changelog
- Initial implementation: build_db.py, site/index.html, justfile recipes, .gitignore
- Optimized DB size: normalized grupo/classe to short codes (133 MB → 43 MB)
- Removed `id` column (duplicates in source data), removed `spec` column (redundant with nome)
- Added Tom Select (v2.4.1 via CDN) for grupo/classe dropdowns with type-to-search
- All filters support multi-select: tipo via checkboxes, grupo/classe via Tom Select multi. SQL uses IN() clauses. Cascading preserves valid selections when parent changes.
- Added spec (codigoEspecificacao) column to slim DB and search/display in the UI. DB size now ~75 MB.
- Added faceted counts to all filters (tipo checkboxes, grupo/classe Tom Selects). Uses GROUP BY queries excluding each facet's own filter. Counts update live on every filter/search change. Guard flag prevents cascading onChange loops during facet updates.
- Grupo/classe now show visible facet lists below their Tom Select search boxes, sorted by count desc. Clicking a value toggles it in the Tom Select. Selected items are highlighted. Lists scroll at 220px max-height.
- Added mark.js (v8.11.1 via CDN) to highlight spec search matches in the Especificação table column.
- Reorganized data pipeline: data-raw/ for source files (CSV + full DB), site/data.db as transform output. Renamed recipes: import→load, export→transform.
