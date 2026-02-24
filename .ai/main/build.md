# Build

## Key files
| File | Purpose |
|------|---------|
| `build_db.py` | Exports slim DB from full data.db → site/data.db |
| `site/index.html` | Self-contained SPA (HTML + CSS + vanilla JS) |
| `site/data.db` | Slim SQLite with items + hierarchy tables (gitignored) |
| `justfile` | Recipes: `export`, `serve`, `import`, `tables`, `schema` |

## Indexes on items table
- idx_tipo, idx_grupo, idx_classe, idx_codigo
- idx_composite (tipo, grupo, classe)

## Justfile recipes
- `just export` — runs build_db.py to create site/data.db
- `just serve` — starts local HTTP server on port 8000

## Changelog
- Initial implementation: build_db.py, site/index.html, justfile recipes, .gitignore
- Optimized DB size: normalized grupo/classe to short codes (133 MB → 43 MB)
- Removed `id` column (duplicates in source data), removed `spec` column (redundant with nome)
- Added Tom Select (v2.4.1 via CDN) for grupo/classe dropdowns with type-to-search
- All filters support multi-select: tipo via checkboxes, grupo/classe via Tom Select multi. SQL uses IN() clauses. Cascading preserves valid selections when parent changes.
