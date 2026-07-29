"""Build the compact, public CATMAS history database from the relational export."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import sqlite3
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


ACTION_LABELS = {
    1: "Criação do item",
    2: "Mudança de situação",
    7: "Inclusão de linha de fornecimento",
    9: "Inclusão de unidade de serviço",
    11: "Alteração de sustentabilidade",
    12: "Inativação de unidade de serviço",
    13: "Inativação de linha de fornecimento",
    14: "Inativação de unidade de material",
    15: "Inclusão de unidade de material",
    16: "Comunicação com pendência",
    17: "Comunicação com sistema externo",
    18: "Atualização de situação",
    19: "Inclusão de característica",
    20: "Substituição de característica",
    21: "Alteração de característica",
    22: "Alteração da natureza de despesa",
    23: "Alteração do material",
    24: "Reordenação de características",
    25: "Alteração de especificação",
}

REQUEST_STATUS_LABELS = {
    1: "Gerada",
    2: "Aguardando análise",
    3: "Em análise",
    4: "Aprovada",
    5: "Reprovada",
    6: "Aprovada parcialmente",
}

REQUEST_TYPE_LABELS = {
    1: "Características ou complementação de material",
    2: "Situação do item",
    3: "Elemento de despesa",
    4: "Unidade de aquisição de material",
    5: "Linha de fornecimento",
    6: "Situação do item — outra modalidade",
    7: "Elemento de despesa — outra modalidade",
    8: "Unidade de fornecimento de serviço",
    9: "Linha de fornecimento — outra modalidade",
    10: "Especificação de serviço",
}

STAGE_LABELS = {
    1: "Antes",
    2: "Solicitado",
    3: "Analisado",
}

SCHEMA = """
PRAGMA journal_mode=OFF;
PRAGMA synchronous=OFF;
PRAGMA temp_store=MEMORY;
PRAGMA foreign_keys=ON;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE action_labels (
    code INTEGER PRIMARY KEY,
    label TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE request_statuses (
    code INTEGER PRIMARY KEY,
    label TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE request_types (
    code INTEGER PRIMARY KEY,
    label TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE stages (
    code INTEGER PRIMARY KEY,
    label TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE items (
    item_id INTEGER PRIMARY KEY,
    code TEXT,
    item_type TEXT,
    material_service_id INTEGER,
    material_service_code TEXT,
    material_service_name TEXT,
    current_version INTEGER,
    current_status_code INTEGER,
    current_status_label TEXT,
    created_at TEXT,
    updated_at TEXT,
    current_specification TEXT,
    first_event_at TEXT,
    last_event_at TEXT,
    event_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE events (
    history_id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL,
    occurred_at TEXT NOT NULL,
    action_code INTEGER NOT NULL,
    resulting_status_code INTEGER,
    automatic INTEGER NOT NULL,
    unit_id INTEGER,
    user_name TEXT,
    user_masp TEXT,
    details TEXT,
    FOREIGN KEY (item_id) REFERENCES items(item_id),
    FOREIGN KEY (action_code) REFERENCES action_labels(code)
);

CREATE TABLE requests (
    request_id INTEGER PRIMARY KEY,
    request_type INTEGER NOT NULL,
    version INTEGER,
    code TEXT,
    status INTEGER NOT NULL,
    justification TEXT,
    included_at TEXT,
    responsible_name TEXT,
    analyst_id INTEGER,
    requester_id INTEGER,
    analyst_justification TEXT,
    attachment_id INTEGER,
    FOREIGN KEY (request_type) REFERENCES request_types(code),
    FOREIGN KEY (status) REFERENCES request_statuses(code)
);

CREATE TABLE request_events (
    request_event_id INTEGER PRIMARY KEY,
    request_id INTEGER NOT NULL,
    version INTEGER,
    action_code INTEGER,
    occurred_at TEXT,
    unit_id INTEGER,
    user_masp TEXT,
    user_name TEXT,
    details TEXT,
    FOREIGN KEY (request_id) REFERENCES requests(request_id)
);

CREATE TABLE snapshots (
    snapshot_id INTEGER PRIMARY KEY,
    class_type TEXT,
    version INTEGER,
    stage INTEGER NOT NULL,
    request_id INTEGER NOT NULL,
    material_service_id INTEGER,
    item_id INTEGER,
    item_status INTEGER,
    specification_complement TEXT,
    specification TEXT,
    FOREIGN KEY (stage) REFERENCES stages(code),
    FOREIGN KEY (request_id) REFERENCES requests(request_id)
);

CREATE TABLE snapshot_components (
    component_row_id INTEGER PRIMARY KEY,
    snapshot_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    component_key TEXT NOT NULL,
    label TEXT NOT NULL,
    value TEXT,
    situation INTEGER,
    acceptance INTEGER,
    sort_order INTEGER,
    source_kind TEXT NOT NULL,
    source_id INTEGER,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id)
);
"""


def integer(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def truthy(value: str | None) -> int:
    return 1 if (value or "").strip().lower() == "true" else 0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ExportArchive:
    def __init__(self, source: Path):
        self.archive = zipfile.ZipFile(source)
        self.by_basename = {
            Path(name).name: name
            for name in self.archive.namelist()
            if name.lower().endswith(".csv")
        }

    def close(self) -> None:
        self.archive.close()

    def rows(self, basename: str) -> Iterator[dict[str, str]]:
        member = self.by_basename.get(basename)
        if member is None:
            raise KeyError(f"CSV ausente no ZIP: {basename}")
        with self.archive.open(member) as binary:
            with io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as handle:
                yield from csv.DictReader(handle)


def seed_catalog_items(conn: sqlite3.Connection, catalog_db: Path | None) -> int:
    if not catalog_db or not catalog_db.exists():
        return 0
    source = sqlite3.connect(f"file:{catalog_db}?mode=ro", uri=True)
    rows = source.execute(
        """
        SELECT item_id, codigo, tipo, servico_id, material_codigo, material_nome,
               versao, situacao, data_criacao, data_ultima_atualizacao, spec
        FROM items
        """
    )
    batch = []
    total = 0
    for row in rows:
        batch.append(
            (
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                row[6],
                None,
                row[7],
                row[8],
                row[9],
                row[10],
                None,
                None,
                0,
            )
        )
        total += 1
        if len(batch) >= 10_000:
            conn.executemany(
                "INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch
            )
            batch.clear()
    if batch:
        conn.executemany(
            "INSERT INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch
        )
    source.close()
    return total


def load_item_history(conn: sqlite3.Connection, export: ExportArchive) -> tuple[int, int]:
    item_rows: dict[int, tuple] = {}
    event_batch: list[tuple] = []
    total_events = 0

    def flush_events() -> None:
        if not event_batch:
            return
        event_item_ids = {event[1] for event in event_batch}
        conn.executemany(
            """
            INSERT OR IGNORE INTO items (item_id, code, item_type, event_count)
            VALUES (?, ?, ?, 0)
            """,
            (
                (item_id, item_rows[item_id][1], item_rows[item_id][2])
                for item_id in event_item_ids
            ),
        )
        conn.executemany(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?)", event_batch
        )
        event_batch.clear()

    for row in export.rows("01historico_itens.csv"):
        total_events += 1
        item_id = int(row["item_id"])
        occurred_at = row["data_acao"]
        current = item_rows.get(item_id)
        item_rows[item_id] = (
            item_id,
            text(row["codigo_item"]),
            text(row["tipo_item"]),
            integer(row["material_servico_id"]),
            text(row["material_servico_codigo"]),
            text(row["material_servico_nome"]),
            integer(row["versao_atual_item"]),
            integer(row["situacao_atual_item"]),
            text(row["data_criacao_item"]),
            text(row["especificacao_atual_item"]),
            min(current[10], occurred_at) if current else occurred_at,
            max(current[11], occurred_at) if current else occurred_at,
            (current[12] + 1) if current else 1,
        )
        event_batch.append(
            (
                int(row["historico_id"]),
                item_id,
                occurred_at,
                int(row["codigo_acao"]),
                integer(row["codigo_situacao_resultante"]),
                truthy(row["automatico"]),
                integer(row["unidade_id"]),
                text(row["usuario_nome"]),
                text(row["usuario_masp"]),
                text(row["informacoes_complementares_completas"]),
            )
        )
        if len(event_batch) >= 10_000:
            flush_events()
    flush_events()

    conn.executemany(
        """
        INSERT INTO items (
            item_id, code, item_type, material_service_id, material_service_code,
            material_service_name, current_version, current_status_code,
            created_at, current_specification, first_event_at, last_event_at,
            event_count
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(item_id) DO UPDATE SET
            code = COALESCE(excluded.code, items.code),
            item_type = COALESCE(excluded.item_type, items.item_type),
            material_service_id = COALESCE(
                excluded.material_service_id, items.material_service_id
            ),
            material_service_code = COALESCE(
                excluded.material_service_code, items.material_service_code
            ),
            material_service_name = COALESCE(
                excluded.material_service_name, items.material_service_name
            ),
            current_version = COALESCE(excluded.current_version, items.current_version),
            current_status_code = excluded.current_status_code,
            created_at = COALESCE(excluded.created_at, items.created_at),
            current_specification = COALESCE(
                excluded.current_specification, items.current_specification
            ),
            first_event_at = excluded.first_event_at,
            last_event_at = excluded.last_event_at,
            event_count = excluded.event_count
        """,
        item_rows.values(),
    )
    return total_events, len(item_rows)


def load_requests(conn: sqlite3.Connection, export: ExportArchive) -> dict[int, dict]:
    requests = {}
    rows = []
    for row in export.rows("03solicitacoes_catalogo.csv"):
        request_id = int(row["id"])
        requests[request_id] = row
        rows.append(
            (
                request_id,
                int(row["tipo"]),
                integer(row["versao"]),
                text(row["codigo"]),
                int(row["situacao"]),
                text(row["justificativa"]),
                text(row["datainclusao"]),
                text(row["nomeresponsavel"]),
                integer(row["analista_id"]),
                integer(row["solicitante_id"]),
                text(row["justificativaanalista"]),
                integer(row["arqdetalhamentosolic_id"]),
            )
        )
    conn.executemany(
        "INSERT INTO requests VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    return requests


def load_request_events(conn: sqlite3.Connection, export: ExportArchive) -> int:
    event_rows = list(export.rows("04historico_solicitacoes_catalogo.csv"))
    needed_text_ids = {
        row["informacoescomplementares_id"]
        for row in event_rows
        if row["informacoescomplementares_id"]
    }
    texts = {}
    for row in export.rows("05textos_portal_catalogo.csv"):
        if row["id"] in needed_text_ids:
            texts[row["id"]] = row["texto"]
    conn.executemany(
        """
        INSERT INTO request_events (
            request_event_id, request_id, version, action_code, occurred_at,
            unit_id, user_masp, user_name, details
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            (
                int(row["id"]),
                int(row["solicitacao_id"]),
                integer(row["versao"]),
                integer(row["acao"]),
                text(row["datahora"]),
                integer(row["unidade_id"]),
                text(row["masp"]),
                text(row["nome"]),
                text(texts.get(row["informacoescomplementares_id"])),
            )
            for row in event_rows
        ),
    )
    return len(event_rows)


def load_snapshots(
    conn: sqlite3.Connection, export: ExportArchive
) -> dict[int, dict[str, str]]:
    snapshots = {}
    rows = []
    for row in export.rows("02dados_alteracao_catalogo.csv"):
        snapshot_id = int(row["id"])
        snapshots[snapshot_id] = row
        rows.append(
            (
                snapshot_id,
                text(row["tipocls"]),
                integer(row["versao"]),
                int(row["conteudo"]),
                int(row["solicitacao_id"]),
                integer(row["materialouservico_id"]),
                integer(row["itemmaterialouservico_id"]),
                integer(row["situacaoitemcatalogo"]),
                text(row["complementacaoespecificacao"]),
                text(row["especificacao"]),
            )
        )
    conn.executemany(
        "INSERT INTO snapshots VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    return snapshots


def component(
    snapshot_id: int,
    category: str,
    component_key: str,
    label: str,
    value: str | None,
    situation: int | None,
    acceptance: int | None,
    sort_order: int | None,
    source_kind: str,
    source_id: int | None,
) -> tuple:
    return (
        None,
        snapshot_id,
        category,
        component_key,
        label,
        value,
        situation,
        acceptance,
        sort_order,
        source_kind,
        source_id,
    )


def format_unit(unit: dict[str, str] | None) -> tuple[str, str | None]:
    if not unit:
        return "Unidade não identificada", None
    code = text(unit.get("codigo"))
    quantity = text(unit.get("quantidade"))
    measure = text(unit.get("entunidademedida_id"))
    package = text(unit.get("entembalagem_id"))
    label = f"Unidade {code}" if code else f"Unidade interna {unit.get('id', '—')}"
    details = []
    if quantity:
        details.append(f"Quantidade: {quantity}")
    if measure:
        details.append(f"Unidade de medida ID: {measure}")
    if package:
        details.append(f"Embalagem ID: {package}")
    if unit.get("observacoes"):
        details.append(unit["observacoes"])
    return label, "; ".join(details) or None


def load_components(conn: sqlite3.Connection, export: ExportArchive) -> int:
    rows: list[tuple] = []

    characteristics = {
        row["id"]: row for row in export.rows("11caracteristica.csv")
    }
    altered_characteristics = list(export.rows("07alteracao_caracteristica.csv"))
    needed_material_characteristics = {
        row["caracteristica_id"] for row in altered_characteristics
    }
    material_characteristics = {
        row["id"]: row
        for row in export.rows("10caracteristica_material.csv")
        if row["id"] in needed_material_characteristics
    }
    for row in altered_characteristics:
        material_characteristic = material_characteristics.get(row["caracteristica_id"])
        base = (
            characteristics.get(material_characteristic["caracteristica_id"])
            if material_characteristic
            else None
        )
        label = text((base or {}).get("nome")) or text(
            (material_characteristic or {}).get("nome")
        )
        label = label or f"Característica {row['caracteristica_id']}"
        rows.append(
            component(
                int(row["alteracao_id"]),
                "Características",
                f"caracteristica:{row['caracteristica_id']}",
                label,
                text(row["valor"]),
                None,
                None,
                integer(row["numerodeordem"]),
                "alteracao_caracteristica",
                int(row["id"]),
            )
        )

    new_characteristics = {
        row["id"]: row for row in export.rows("08nova_caracteristica.csv")
    }
    for link in export.rows("09dados_alt_item_mat_caract_n_carac.csv"):
        new = new_characteristics[link["novacaracteristica_id"]]
        rows.append(
            component(
                int(link["dadosalteracao_id"]),
                "Características",
                f"nova_caracteristica:{new['id']}",
                text(new["caracteristica"]) or "Nova característica",
                text(new["valor"]),
                None,
                integer(new["aceitacao"]),
                integer(new["numerodeordem"]),
                "nova_caracteristica",
                int(new["id"]),
            )
        )

    units = {row["id"]: row for row in export.rows("16unidade_fornec_mov.csv")}

    altered_acquisition_units = list(
        export.rows("12alteracao_unidade_aquisicao.csv")
    )
    needed_acquisition_units = {
        row["unidadeaquisicaomaterial_id"] for row in altered_acquisition_units
    }
    acquisition_units = {
        row["id"]: row
        for row in export.rows("15unidade_aquisicao_material.csv")
        if row["id"] in needed_acquisition_units
    }
    for row in altered_acquisition_units:
        acquisition = acquisition_units.get(row["unidadeaquisicaomaterial_id"], {})
        supply_label, supply_details = format_unit(
            units.get(acquisition.get("unidadefornecimento_id"))
        )
        movement_label, movement_details = format_unit(
            units.get(acquisition.get("unidademovimentacao_id"))
        )
        value_parts = [
            f"Fornecimento: {supply_label}",
            f"Movimentação: {movement_label}",
        ]
        if acquisition.get("fatorconversao"):
            value_parts.append(f"Fator: {acquisition['fatorconversao']}")
        if supply_details:
            value_parts.append(supply_details)
        if movement_details and movement_details != supply_details:
            value_parts.append(movement_details)
        if acquisition.get("observacoes"):
            value_parts.append(acquisition["observacoes"])
        rows.append(
            component(
                int(row["alteracao_id"]),
                "Unidades de aquisição",
                f"unidade_aquisicao:{row['unidadeaquisicaomaterial_id']}",
                supply_label,
                "; ".join(value_parts),
                integer(row["situacao"]),
                None,
                None,
                "alteracao_unidade_aquisicao",
                int(row["id"]),
            )
        )

    new_acquisition_units = {
        row["id"]: row for row in export.rows("13nova_unidade_aquisicao.csv")
    }
    for link in export.rows("14dados_alt_unid_aqui_n_carac.csv"):
        new = new_acquisition_units[link["novaunidadeaquisicao_id"]]
        supply_label, supply_details = format_unit(
            units.get(new["unidadefornecimento_id"])
        )
        movement_label, movement_details = format_unit(
            units.get(new["unidademovimentacao_id"])
        )
        value_parts = [
            f"Fornecimento: {supply_label}",
            f"Movimentação: {movement_label}",
        ]
        if new.get("fatorconversao"):
            value_parts.append(f"Fator: {new['fatorconversao']}")
        if supply_details:
            value_parts.append(supply_details)
        if movement_details and movement_details != supply_details:
            value_parts.append(movement_details)
        rows.append(
            component(
                int(link["dadosalteracao_id"]),
                "Unidades de aquisição",
                f"nova_unidade_aquisicao:{new['id']}",
                supply_label,
                "; ".join(value_parts),
                None,
                integer(new["aceitacao"]),
                None,
                "nova_unidade_aquisicao",
                int(new["id"]),
            )
        )

    natures = {row["id"]: row for row in export.rows("21natureza_despesa.csv")}
    expenses = {
        row["id"]: row for row in export.rows("20elemento_item_despesa.csv")
    }
    for row in export.rows("17alteracao_item_despesa.csv"):
        expense = expenses.get(row["itemdespesa_id"], {})
        nature = natures.get(expense.get("naturezadespesa_id"), {})
        code = text(expense.get("codigo"))
        name = text(expense.get("nome"))
        label = " — ".join(part for part in [code, name] if part)
        value = text(nature.get("nome"))
        rows.append(
            component(
                int(row["alteracao_id"]),
                "Elementos de despesa",
                f"elemento_despesa:{row['itemdespesa_id']}",
                label or f"Elemento {row['itemdespesa_id']}",
                value,
                integer(row["situacao"]),
                None,
                None,
                "alteracao_item_despesa",
                int(row["id"]),
            )
        )

    new_expenses = {
        row["id"]: row for row in export.rows("18novo_item_despesa.csv")
    }
    for link in export.rows("19dados_alt_item_desp_n_i_despesa.csv"):
        new = new_expenses[link["novoitemdespesa_id"]]
        expense = expenses.get(new["elementoitemdespesa_id"], {})
        nature = natures.get(expense.get("naturezadespesa_id"), {})
        code = text(expense.get("codigo"))
        name = text(expense.get("nome"))
        label = " — ".join(part for part in [code, name] if part)
        value = text(nature.get("nome"))
        rows.append(
            component(
                int(link["dadosalteracao_id"]),
                "Elementos de despesa",
                f"novo_elemento_despesa:{new['id']}",
                label or f"Elemento {new['elementoitemdespesa_id']}",
                value,
                None,
                integer(new["aceitacao"]),
                None,
                "novo_item_despesa",
                int(new["id"]),
            )
        )

    service_units = {
        row["id"]: row
        for row in export.rows("25unidade_fornecimento_servico.csv")
    }
    for row in export.rows("22alteracao_unidade_fornecimento.csv"):
        service_unit = service_units.get(row["unidadefornecimento_id"], {})
        unit_label, unit_details = format_unit(
            units.get(service_unit.get("unidadefornecimento_id"))
        )
        value_parts = []
        if unit_details:
            value_parts.append(unit_details)
        if service_unit.get("observacoes"):
            value_parts.append(service_unit["observacoes"])
        rows.append(
            component(
                int(row["alteracao_id"]),
                "Unidades de fornecimento",
                f"unidade_fornecimento:{row['unidadefornecimento_id']}",
                unit_label,
                "; ".join(value_parts) or None,
                integer(row["situacao"]),
                None,
                None,
                "alteracao_unidade_fornecimento",
                int(row["id"]),
            )
        )

    new_service_units = {
        row["id"]: row for row in export.rows("23nova_unidade_fornecimento.csv")
    }
    for link in export.rows("24dados_alt_uni_forn_n_unid_forn.csv"):
        new = new_service_units[link["novaunidade_id"]]
        unit_label, unit_details = format_unit(
            units.get(new["unidadefornecimento_id"])
        )
        rows.append(
            component(
                int(link["dadosalteracao_id"]),
                "Unidades de fornecimento",
                f"nova_unidade_fornecimento:{new['id']}",
                unit_label,
                unit_details,
                None,
                integer(new["aceitacao"]),
                None,
                "nova_unidade_fornecimento",
                int(new["id"]),
            )
        )

    groups = {row["id"]: row for row in export.rows("30grupo_fornecimento.csv")}
    supply_lines = {
        row["id"]: row for row in export.rows("29linha_fornecimento.csv")
    }
    for row in export.rows("26alteracao_linha_fornecimento.csv"):
        line = supply_lines.get(row["linhafornecimento_id"], {})
        group = groups.get(line.get("grupofornecimento_id"), {})
        code = text(line.get("codigo"))
        name = text(line.get("nome"))
        label = " — ".join(part for part in [code, name] if part)
        rows.append(
            component(
                int(row["alteracao_id"]),
                "Linhas de fornecimento",
                f"linha_fornecimento:{row['linhafornecimento_id']}",
                label or f"Linha {row['linhafornecimento_id']}",
                text(group.get("nome")),
                integer(row["situacao"]),
                None,
                None,
                "alteracao_linha_fornecimento",
                int(row["id"]),
            )
        )

    new_supply_lines = {
        row["id"]: row for row in export.rows("27nova_linha_fornecimento.csv")
    }
    for link in export.rows("28dados_alt_lin_forn_n_linha.csv"):
        new = new_supply_lines[link["novalinha_id"]]
        line = supply_lines.get(new["linhafornecimento_id"], {})
        group = groups.get(line.get("grupofornecimento_id"), {})
        code = text(line.get("codigo"))
        name = text(line.get("nome"))
        label = " — ".join(part for part in [code, name] if part)
        rows.append(
            component(
                int(link["dadosalteracao_id"]),
                "Linhas de fornecimento",
                f"nova_linha_fornecimento:{new['id']}",
                label or f"Linha {new['linhafornecimento_id']}",
                text(group.get("nome")),
                None,
                integer(new["aceitacao"]),
                None,
                "nova_linha_fornecimento",
                int(new["id"]),
            )
        )

    conn.executemany(
        """
        INSERT INTO snapshot_components (
            component_row_id, snapshot_id, category, component_key, label, value,
            situation, acceptance, sort_order, source_kind, source_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )
    return len(rows)


def add_indexes(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE INDEX idx_items_code ON items(code);
        CREATE INDEX idx_items_parent ON items(material_service_id);
        CREATE INDEX idx_events_item_date
            ON events(item_id, occurred_at, history_id);
        CREATE INDEX idx_requests_date ON requests(included_at, request_id);
        CREATE INDEX idx_request_events_request_date
            ON request_events(request_id, occurred_at, request_event_id);
        CREATE INDEX idx_snapshots_item ON snapshots(item_id, request_id, stage);
        CREATE INDEX idx_snapshots_parent
            ON snapshots(material_service_id, request_id, stage);
        CREATE INDEX idx_snapshots_request ON snapshots(request_id, stage);
        CREATE INDEX idx_components_snapshot_category
            ON snapshot_components(snapshot_id, category, sort_order, component_row_id);
        ANALYZE;
        PRAGMA optimize;
        """
    )


def validate(conn: sqlite3.Connection) -> dict[str, int | str]:
    foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise RuntimeError(
            f"Falha de integridade referencial: {foreign_key_errors[:10]}"
        )
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"Falha de integridade SQLite: {integrity}")
    return {
        "items": conn.execute("SELECT COUNT(*) FROM items").fetchone()[0],
        "items_with_events": conn.execute(
            "SELECT COUNT(*) FROM items WHERE event_count > 0"
        ).fetchone()[0],
        "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "requests": conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0],
        "request_events": conn.execute(
            "SELECT COUNT(*) FROM request_events"
        ).fetchone()[0],
        "snapshots": conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0],
        "components": conn.execute(
            "SELECT COUNT(*) FROM snapshot_components"
        ).fetchone()[0],
        "integrity": integrity,
    }


def write_gzip(source: Path, destination: Path) -> None:
    with source.open("rb") as source_handle:
        with destination.open("wb") as raw_destination:
            with gzip.GzipFile(
                fileobj=raw_destination, mode="wb", compresslevel=9, mtime=0
            ) as destination_handle:
                for block in iter(lambda: source_handle.read(1024 * 1024), b""):
                    destination_handle.write(block)


def build(
    source_zip: Path,
    destination: Path,
    compressed_destination: Path,
    catalog_db: Path | None,
) -> dict[str, int | str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    compressed_destination.unlink(missing_ok=True)

    export = ExportArchive(source_zip)
    try:
        conn = sqlite3.connect(destination)
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO action_labels(code, label) VALUES (?, ?)",
            ACTION_LABELS.items(),
        )
        conn.executemany(
            "INSERT INTO request_statuses(code, label) VALUES (?, ?)",
            REQUEST_STATUS_LABELS.items(),
        )
        conn.executemany(
            "INSERT INTO request_types(code, label) VALUES (?, ?)",
            REQUEST_TYPE_LABELS.items(),
        )
        conn.executemany(
            "INSERT INTO stages(code, label) VALUES (?, ?)", STAGE_LABELS.items()
        )

        catalog_items = seed_catalog_items(conn, catalog_db)
        total_events, historical_items = load_item_history(conn, export)
        requests = load_requests(conn, export)
        request_events = load_request_events(conn, export)
        snapshots = load_snapshots(conn, export)
        components = load_components(conn, export)

        metadata = {
            "source_zip": source_zip.name,
            "source_sha256": sha256(source_zip),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "catalog_items": str(catalog_items),
            "historical_items": str(historical_items),
            "events": str(total_events),
            "requests": str(len(requests)),
            "request_events": str(request_events),
            "snapshots": str(len(snapshots)),
            "components": str(components),
        }
        conn.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)", metadata.items()
        )
        add_indexes(conn)
        conn.commit()
        result = validate(conn)
        conn.execute("VACUUM")
        conn.close()
    finally:
        export.close()

    write_gzip(destination, compressed_destination)
    result.update(
        {
            "database_bytes": destination.stat().st_size,
            "gzip_bytes": compressed_destination.stat().st_size,
            "source_sha256": sha256(source_zip),
        }
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_zip", type=Path)
    parser.add_argument(
        "--catalog-db",
        type=Path,
        default=Path("site/data.db"),
        help="Banco atual do catálogo usado para incluir itens sem eventos.",
    )
    parser.add_argument(
        "--destination", type=Path, default=Path("site/history.db")
    )
    parser.add_argument(
        "--gzip-destination", type=Path, default=Path("site/history.db.gz")
    )
    args = parser.parse_args()

    result = build(
        args.source_zip,
        args.destination,
        args.gzip_destination,
        args.catalog_db,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
