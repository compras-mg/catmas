"""Export a slim SQLite database for the static site from the full data.db."""

import gzip
import os
import sqlite3

SRC = os.path.join("data-raw", "data.db")
DEST = os.path.join("site", "data.db")
DEST_GZ = os.path.join("site", "data.db.gz")


def code_prefix(s):
    """Extract code prefix before ' - ' from formatted strings like '01 - FOO'."""
    if s and " - " in s:
        return s.split(" - ", 1)[0].strip()
    return s or ""


def main():
    os.makedirs("site", exist_ok=True)
    if os.path.exists(DEST):
        os.remove(DEST)
    if os.path.exists(DEST_GZ):
        os.remove(DEST_GZ)

    src = sqlite3.connect(SRC)
    dst = sqlite3.connect(DEST)

    # Items table: grupo/classe stored as short codes to save space
    dst.execute("""
        CREATE TABLE items (
            tipo                TEXT NOT NULL,
            grupo               TEXT NOT NULL,
            classe              TEXT NOT NULL,
            codigo              TEXT NOT NULL,
            spec                TEXT NOT NULL,
            situacao            TEXT NOT NULL,
            natureza            TEXT NOT NULL,
            material_codigo     TEXT NOT NULL,
            material_nome       TEXT NOT NULL,
            agricultura_familiar TEXT NOT NULL,
            sustentavel         TEXT NOT NULL,
            item_id             INTEGER NOT NULL,
            servico_id          INTEGER
        )
    """)

    rows = src.execute("""
        SELECT
            ehMaterialOuServico_id,
            materialOuServico_classe_codigoGrupoFormatado,
            materialOuServico_classe_codigoNomeFormatado,
            PRINTF('%09d', codigo),
            especificacaoCompleta,
            situacao_descricao,
            materialOuServico_naturezaDespesa_nome,
            materialOuServico_codigoFormatado,
            materialOuServico_nome,
            COALESCE(ehAgriculturaFamiliar, 'false'),
            COALESCE(sustentavel, 'false'),
            id,
            materialOuServico_id
        FROM items
    """).fetchall()

    # Convert grupo/classe to short codes
    slim_rows = [
        (tipo, code_prefix(grupo), code_prefix(classe), codigo,
         spec or "", situacao or "", natureza or "", mat_codigo or "", mat_nome or "",
         agri_fam or "false", sust or "false", item_id, servico_id)
        for tipo, grupo, classe, codigo, spec, situacao, natureza, mat_codigo, mat_nome, agri_fam, sust, item_id, servico_id in rows
    ]

    dst.executemany("INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", slim_rows)

    # Hierarchy table: full labels for dropdowns
    dst.execute("""
        CREATE TABLE hierarchy (
            tipo   TEXT NOT NULL,
            grupo  TEXT NOT NULL,
            classe TEXT NOT NULL
        )
    """)

    hier = src.execute("""
        SELECT DISTINCT
            ehMaterialOuServico_id,
            materialOuServico_classe_codigoGrupoFormatado,
            materialOuServico_classe_codigoNomeFormatado
        FROM items
        ORDER BY 1, 2, 3
    """).fetchall()

    dst.executemany("INSERT INTO hierarchy VALUES (?,?,?)", hier)

    dst.execute("CREATE INDEX idx_tipo   ON items(tipo)")
    dst.execute("CREATE INDEX idx_grupo  ON items(grupo)")
    dst.execute("CREATE INDEX idx_classe ON items(classe)")
    dst.execute("CREATE INDEX idx_codigo ON items(codigo)")
    dst.execute("CREATE INDEX idx_composite ON items(tipo, grupo, classe)")

    # FTS5 full-text search index on spec, material name, grupo label, classe label
    dst.execute("""
        CREATE VIRTUAL TABLE items_fts USING fts5(
            spec, material_nome, grupo_label, classe_label,
            tokenize='unicode61 remove_diacritics 2'
        )
    """)

    fts_rows = [
        (spec or "", mat_nome or "", grupo or "", classe or "")
        for tipo, grupo, classe, codigo, spec, situacao, natureza, mat_codigo, mat_nome, agri_fam, sust, item_id, servico_id in rows
    ]
    dst.executemany(
        "INSERT INTO items_fts(spec, material_nome, grupo_label, classe_label) VALUES (?,?,?,?)",
        fts_rows,
    )

    dst.commit()
    dst.execute("VACUUM")
    dst.close()
    src.close()

    with open(DEST, "rb") as src_f, gzip.open(DEST_GZ, "wb", compresslevel=9) as dst_f:
        dst_f.write(src_f.read())

    size_mb = os.path.getsize(DEST) / (1024 * 1024)
    size_gz_mb = os.path.getsize(DEST_GZ) / (1024 * 1024)
    print(
        f"Created {DEST} ({size_mb:.1f} MB) and {DEST_GZ} ({size_gz_mb:.1f} MB), "
        f"{len(rows)} items, {len(hier)} hierarchy rows"
    )


if __name__ == "__main__":
    main()
