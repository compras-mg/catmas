# Design

## Data pipeline
`data-raw/main.csv` → `just load` → `data-raw/data.db` → `just transform` → `site/data.db`

## Approach: sql.js (WASM SQLite in the browser)
Serve a slim SQLite database from data/data.db and query it client-side using sql.js. This gives real SQL WHERE/LIMIT/OFFSET without a backend.

## Data model
- **items** table: tipo, grupo (short code), classe (short code), codigo, spec (especificacaoCompleta), situacao, natureza, material_codigo, material_nome, agricultura_familiar, sustentavel — 201,785 rows
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
| tipo | 2 | Checkboxes (multi-select, both checked = all) |
| situacao | 2 | Checkboxes: Ativo, Suspenso para compra (both checked = all) |
| agricultura_familiar | 2 | Checkboxes: Sim (true), Não (false) (both checked = all) |
| sustentavel | 2 | Checkboxes: Sim (true), Não (false) (both checked = all) |
| grupo | 85 | Tom Select search + visible facet list sorted by count desc (cascaded from tipo) |
| classe | 831 | Tom Select search + visible facet list sorted by count desc (cascaded from grupo) |
| spec (especificacaoCompleta) | 201,785 | Text input with LIKE |

## Faceted counts
Each filter displays the count of matching items next to each value. Counts are computed excluding the facet's own filter (standard faceted search: shows what you'd get for each option given all other constraints). Counts update live as any filter or the spec search changes.

## Pagination
50 rows/page via SQL LIMIT/OFFSET. Prev/Next buttons + result count.

## Architecture
Single self-contained SPA — no build tools, no frameworks. HTML + CSS + vanilla JS in one file.
