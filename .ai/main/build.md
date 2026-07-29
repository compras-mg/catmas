# Build

## Key files
| File | Purpose |
|------|---------|
| `data-raw/main.csv` | Source CSV (gitignored) |
| `data-raw/data.db` | Full SQLite import from CSV (gitignored) |
| `scripts/transform.py` | Transforms data-raw/data.db → site/data.db and site/data.db.gz |
| `site/data.db` | Slim SQLite with items + hierarchy tables (gitignored) |
| `site/data.db.gz` | Gzipped deploy artifact for GitHub Pages |
| `site/index.html` | Self-contained SPA (HTML + CSS + vanilla JS) |
| `justfile` | Recipes: `load`, `transform`, `serve`, `tables`, `schema` |

## Indexes on items table
- idx_tipo, idx_grupo, idx_classe, idx_codigo, idx_especificacao_longa
- idx_composite (tipo, grupo, classe)
- items_fts: FTS5 virtual table indexing spec, material_nome, grupo_label, classe_label with `unicode61 remove_diacritics 2` tokenizer

## Data pipeline
`data-raw/main.csv` → `just load` → `data-raw/data.db` → `just transform` → `site/data.db` + `site/data.db.gz`

## Justfile recipes
- `just load` — imports data-raw/main.csv into data-raw/data.db via sqlite-utils
- `just transform` — runs scripts/transform.py to create `site/data.db` and `site/data.db.gz` from data-raw/data.db
- `just serve` — starts local HTTP server on port 8000

## Changelog
- Added the "Itens com Especificação Longa" filter. The transform normalizes
  `complementacaoespecificacao`, recognizes singular/plural and recurring spelling
  variants, and publishes the result as the indexed `especificacao_longa` flag.
- Renamed transform script from `build_db.py` to `scripts/transform.py` and moved it under `scripts/`
- Added gzip stop-gap deployment flow for GitHub Pages limits:
  - `scripts/transform.py` now writes `site/data.db.gz` (gzip level 9) after building/vacuuming `site/data.db`
  - `site/index.html` now fetches `data.db.gz` and decompresses client-side before initializing sql.js
  - Decompression uses `DecompressionStream("gzip")` when available, with `pako` (CDN) fallback
- Initial implementation: scripts/transform.py, site/index.html, justfile recipes, .gitignore
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
- Added three sidebar filters: Situação (Ativo/Suspenso para compra), Agricultura Familiar (Sim/Não), Sustentável (Sim/Não). Added agricultura_familiar and sustentavel columns to items table in scripts/transform.py (sourced from ehAgriculturaFamiliar and sustentavel, nulls coalesced to "false").
- Changed all low-cardinality filters (tipo, situação, agricultura familiar, sustentável) to Django-admin-style single-select lists (Todos / values). Active item has left border + colored text. Clicking an option selects it exclusively; "Todos" clears the filter. Faceted counts shown inline. Removed checkbox UI entirely.
- Switched search from LIKE to SQLite FTS5 (via sql.js-fts5@1.4.0 CDN). scripts/transform.py creates items_fts virtual table indexing spec, material_nome, grupo_label, classe_label with unicode61 remove_diacritics 2 tokenizer. index.html uses ftsQuery() helper to sanitize input and FTS5 MATCH for fast token-based search across all four columns. Results ranked by BM25 relevance (ORDER BY rank) when searching; falls back to ORDER BY codigo when no search active. mark.js highlights each word separately across all four FTS-indexed columns (spec, material, classe, grupo).
- Added "Limpar filtros" link at bottom of sidebar (hidden when no filters active, appears when any filter is set). Added x clear button inside search input (appears when text is present). Both reset their respective state and trigger a full refresh.
- Restyled to match ComprasMG portal (compras.mg.gov.br): Raleway font (400/600/900 via Google Fonts), `#344e5c` blue-gray header with uppercase h1, `#be1e2d` red accents on active filters/clear buttons/selected facets, `#f2f5f7` body background, `#949494` input borders with 3px border-radius, `#344e5c` table headers with matching bottom border, `#3c3c3b` body text color.
- Zero-padded codigo to 9 digits via PRINTF('%09d', codigo) in scripts/transform.py.
- Added item_id (from `id`) and servico_id (from `materialOuServico_id`) columns to items table. Codigo column links to ComprasMG portal: MATERIAL items use `relatorioItemMaterial.html?id={item_id}`, SERVICO items use `relatorioItemServico.html?id={servico_id}`. Styled in red accent with an external-link SVG icon.
