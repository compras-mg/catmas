# Design

## Approach: sql.js (WASM SQLite in the browser)
Serve a slim SQLite database (~43 MB) and query it client-side using sql.js. This gives real SQL WHERE/LIMIT/OFFSET without a backend.

## Data model
- **items** table: tipo, grupo (short code), classe (short code), codigo, nome — 201,785 rows
- **hierarchy** table: tipo, grupo (full label), classe (full label) — 831 rows for populating cascading dropdowns
- Grupo/classe stored as short codes in items to reduce DB size (saved ~90 MB vs full labels)

## Filter UI by cardinality
| Column | Distinct | UI |
|--------|----------|----|
| tipo | 2 | Checkboxes (multi-select, both checked = all) |
| grupo | 85 | Tom Select multi-select with search (cascaded from tipo) |
| classe | 831 | Tom Select multi-select with search (cascaded from grupo) |
| codigo | 22,935 | Text input with LIKE |
| nome | 21,813 | Text input with LIKE |

## Pagination
50 rows/page via SQL LIMIT/OFFSET. Prev/Next buttons + result count.

## Architecture
Single self-contained SPA — no build tools, no frameworks. HTML + CSS + vanilla JS in one file.
