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
- items_fts: FTS5 virtual table indexing spec, material_nome, grupo_label, classe_label with `unicode61 remove_diacritics 2` tokenizer

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
- Changed table columns to match legacy Portal de Compras: Código, Especificação do item, Situação, Natureza de Despesa, Material, Grupo. Replaced nome/codigoEspecificacao with especificacaoCompleta, situacao_descricao, materialOuServico_naturezaDespesa_nome, materialOuServico_codigoFormatado, materialOuServico_nome.
- Added three sidebar filters: Situação (Ativo/Suspenso para compra), Agricultura Familiar (Sim/Não), Sustentável (Sim/Não). Added agricultura_familiar and sustentavel columns to items table in build_db.py (sourced from ehAgriculturaFamiliar and sustentavel, nulls coalesced to "false").
- Changed all low-cardinality filters (tipo, situação, agricultura familiar, sustentável) to Django-admin-style single-select lists (Todos / values). Active item has left border + colored text. Clicking an option selects it exclusively; "Todos" clears the filter. Faceted counts shown inline. Removed checkbox UI entirely.
- Switched search from LIKE to SQLite FTS5 (via sql.js-fts5@1.4.0 CDN). build_db.py creates items_fts virtual table indexing spec, material_nome, grupo_label, classe_label with unicode61 remove_diacritics 2 tokenizer. index.html uses ftsQuery() helper to sanitize input and FTS5 MATCH for fast token-based search across all four columns. Results ranked by BM25 relevance (ORDER BY rank) when searching; falls back to ORDER BY codigo when no search active. mark.js highlights each word separately across all four FTS-indexed columns (spec, material, classe, grupo).
