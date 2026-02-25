# Design

## Data pipeline
`data-raw/main.csv` → `just load` → `data-raw/data.db` → `just transform` → `site/data.db` + `site/data.db.gz`

For deployment on GitHub Pages, the app fetches `site/data.db.gz` and decompresses it in-browser before opening SQLite.

## Approach: sql.js (WASM SQLite in the browser)
Serve a slim SQLite database artifact as `site/data.db.gz`, decompress in-browser, and query it client-side using sql.js. This gives real SQL WHERE/LIMIT/OFFSET without a backend.

## Data model
- **items** table: tipo, grupo (short code), classe (short code), codigo, spec (especificacaoCompleta), situacao, natureza, material_codigo, material_nome, agricultura_familiar, sustentavel — 201,785 rows
- **items_fts** FTS5 virtual table: spec, material_nome, grupo_label, classe_label — tokenized with `unicode61 remove_diacritics 2` for accent-insensitive Portuguese search. Rowids match items table. Grupo/classe stored as full labels for searchability.
- **hierarchy** table: tipo, grupo (full label), classe (full label) — 831 rows for populating cascading dropdowns
- Grupo/classe stored as short codes in items to reduce DB size

## Table columns (matching legacy Portal de Compras)
| Column | Source field |
|--------|-------------|
| Código | codigo |
| Especificação do item | especificacaoCompleta |
| Situação | situacao_descricao |
| Natureza de Despesa | materialOuServico_naturezaDespesa_nome |
| Material | materialOuServico_codigoFormatado + materialOuServico_nome |
| Grupo | materialOuServico_classe_codigoGrupoFormatado |

## Filter UI by cardinality
| Column | Distinct | UI |
|--------|----------|----|
| tipo | 2 | Django-admin-style list: Todos / Material / Serviço (single-select) |
| situacao | 2 | Django-admin-style list: Todos / Ativo / Suspenso para compra (single-select, Todos = no filter) |
| agricultura_familiar | 2 | Django-admin-style list: Todos / Sim / Não (single-select) |
| sustentavel | 2 | Django-admin-style list: Todos / Sim / Não (single-select) |
| grupo | 85 | Tom Select search + visible facet list sorted by count desc (cascaded from tipo) |
| classe | 831 | Tom Select search + visible facet list sorted by count desc (cascaded from grupo) |
| spec (especificacaoCompleta) | 201,785 | Text input with FTS5 MATCH (searches spec, material name, grupo label, classe label) |

## Faceted counts
Each filter displays the count of matching items next to each value. Counts are computed excluding the facet's own filter (standard faceted search: shows what you'd get for each option given all other constraints). Counts update live as any filter or the spec search changes.

## Pagination
50 rows/page via SQL LIMIT/OFFSET. Prev/Next buttons + result count.

## Architecture
Single self-contained SPA — no build tools, no frameworks. HTML + CSS + vanilla JS in one file.

## Compressed DB loading strategy
- Runtime fetch target: `data.db.gz` (instead of `data.db`)
- Preferred decompression path: browser-native `DecompressionStream("gzip")`
- Fallback decompression path: `pako` CDN (`pako.ungzip`) when `DecompressionStream` is unavailable
- Decompressed bytes are passed directly to `new SQL.Database(...)`, preserving existing SQL/FTS query flow
