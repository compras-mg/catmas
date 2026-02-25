"""Export a slim SQLite database for the static site from the full data.db."""

import os
import sqlite3

SRC = os.path.join("data-raw", "data.db")
DEST = os.path.join("site", "data.db")


def code_prefix(s):
    """Extract code prefix before ' - ' from formatted strings like '01 - FOO'."""
    if s and " - " in s:
        return s.split(" - ", 1)[0].strip()
    return s or ""


def main():
    os.makedirs("site", exist_ok=True)
    if os.path.exists(DEST):
        os.remove(DEST)

    src = sqlite3.connect(SRC)
    dst = sqlite3.connect(DEST)

    # Items table: grupo/classe stored as short codes to save space
    dst.execute("""
        CREATE TABLE items (
            tipo     TEXT NOT NULL,
            grupo    TEXT NOT NULL,
            classe   TEXT NOT NULL,
            codigo   TEXT NOT NULL,
            nome     TEXT NOT NULL,
            spec     TEXT NOT NULL
        )
    """)

    rows = src.execute("""
        SELECT
            ehMaterialOuServico_id,
            materialOuServico_classe_codigoGrupoFormatado,
            materialOuServico_classe_codigoNomeFormatado,
            CAST(codigo AS TEXT),
            descricaoItem,
            codigoEspecificacao
        FROM items
    """).fetchall()

    # Convert grupo/classe to short codes
    slim_rows = [
        (tipo, code_prefix(grupo), code_prefix(classe), codigo, nome or "", spec or "")
        for tipo, grupo, classe, codigo, nome, spec in rows
    ]

    dst.executemany("INSERT INTO items VALUES (?,?,?,?,?,?)", slim_rows)

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

    dst.commit()
    dst.execute("VACUUM")
    dst.close()
    src.close()

    size_mb = os.path.getsize(DEST) / (1024 * 1024)
    print(f"Created {DEST} ({size_mb:.1f} MB, {len(rows)} items, {len(hier)} hierarchy rows)")


if __name__ == "__main__":
    main()
