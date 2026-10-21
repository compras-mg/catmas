"""Compare copies of published CATMAS data; Python standard library only.

Publication timestamps are NOT edit timestamps. Results require review for
changes in the extraction pipeline before being called catalog edits.
"""
import argparse
import gzip
import hashlib
import json
import shutil
import sqlite3
import tempfile
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

COPIAS = [
    ("9e0b2530ed7c44ad1708e0c9efcd9710b4150e4a", "2026-09-22T16:20:40Z"),
    ("8870e44eb965cf534a2246f9bcaf7c0befeaef86", "2026-10-07T01:19:51Z"),
    ("3d4423269651d452527f4a878cb489412792899a", "2026-10-20T15:36:53Z"),
]
CAMPOS = ("spec", "material_nome", "situacao", "material_codigo",
          "grupo", "classe", "natureza", "agricultura_familiar",
          "sustentavel", "ok_registro_precos", "especificacao_longa")


def sem_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if not unicodedata.combining(c))


def classificar(antes, depois):
    if isinstance(antes, str) and isinstance(depois, str):
        if unicodedata.normalize("NFC", antes) == unicodedata.normalize("NFC", depois):
            return "representacao_unicode"
        if sem_acentos(antes) == sem_acentos(depois):
            return "somente_diacriticos"
    return "outra_diferenca"


def carregar(caminho):
    con = sqlite3.connect(caminho.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(items)")]
        if not {"item_id", "codigo", "tipo", "spec"}.issubset(cols):
            raise ValueError("Esquema inesperado de items: " + repr(cols))
        campos = [c for c in CAMPOS if c in cols]
        nomes = ["item_id", "codigo", "tipo"] + campos
        dados = {}
        for row in con.execute("SELECT " + ",".join(nomes) + " FROM items"):
            registro = dict(zip(nomes, row))
            chave = registro["item_id"]
            if chave is None or chave in dados:
                raise ValueError("ID ausente ou duplicado: " + str(chave))
            dados[chave] = registro
        return dados, campos
    finally:
        con.close()


def comparar(antigos, novos, campos, origem, destino, emitir):
    comuns = antigos.keys() & novos.keys()
    alterados, so_acentos = set(), set()
    contagem = Counter()
    identidades = []
    for item_id in sorted(comuns):
        a, b = antigos[item_id], novos[item_id]
        if (a["codigo"], a["tipo"]) != (b["codigo"], b["tipo"]):
            identidades.append(item_id)
            continue
        tipos = []
        for campo in campos:
            if a[campo] == b[campo]:
                continue
            tipo = classificar(a[campo], b[campo])
            tipos.append(tipo)
            contagem[campo] += 1
            identidade = [origem[0], destino[0], item_id, campo]
            emitir({
                "id_diferenca": hashlib.sha256(json.dumps(identidade).encode()).hexdigest(),
                "item_id": item_id, "codigo": b["codigo"], "campo": campo,
                "valor_anterior": a[campo], "valor_posterior": b[campo],
                "tipo_diferenca": tipo,
                "commit_anterior": origem[0], "commit_posterior": destino[0],
                "publicacao_anterior_utc": origem[1], "publicacao_posterior_utc": destino[1],
                "data_edicao": None, "responsavel": None, "justificativa": None,
                "solicitacao_id": None, "evento_id": None,
                "evidencia": "diferenca_entre_copias_publicadas",
                "validacao_origem": "pendente_revisao_da_extracao",
            })
        if tipos:
            alterados.add(item_id)
            if all(t == "somente_diacriticos" for t in tipos):
                so_acentos.add(item_id)
    return {
        "publicacao_anterior": origem[1], "publicacao_posterior": destino[1],
        "itens_antes": len(antigos), "itens_depois": len(novos),
        "itens_comuns": len(comuns), "itens_com_diferencas": len(alterados),
        "itens_somente_diacriticos": len(so_acentos),
        "diferencas_por_campo": dict(contagem),
        "ids_presentes_apenas_depois": sorted(novos.keys() - antigos.keys()),
        "ids_presentes_apenas_antes": sorted(antigos.keys() - novos.keys()),
        "ids_com_identidade_divergente_nao_comparados": identidades,
        "campos_comparados": campos,
    }


def baixar(sha, cache):
    destino = cache / (sha + ".db.gz")
    if not destino.exists():
        url = "https://raw.githubusercontent.com/compras-mg/catmas/" + sha + "/data.db.gz"
        print("Baixando copia", sha[:10], flush=True)
        parcial = destino.with_suffix(".part")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CATMAS-comparacao"})
            with urllib.request.urlopen(req, timeout=180) as src, parcial.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            # Validate gzip CRC before promoting cache entry.
            with gzip.open(parcial, "rb") as src:
                while src.read(1024 * 1024):
                    pass
            parcial.replace(destino)
        finally:
            parcial.unlink(missing_ok=True)
    return destino


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=Path("comparacao-catmas"))
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    cache = args.saida / "cache"
    cache.mkdir(exist_ok=True)
    resumo = {"aviso": "Diferencas observadas nas copias; datas de publicacao nao sao datas de edicao. Autoria e motivo nao inferidos.",
              "intervalos": [], "fontes": [], "item_248": [], "diferencas_item_248": []}
    unicos = set()
    anterior = None
    parcial = args.saida / "diferencas.jsonl.gz.part"
    with gzip.open(parcial, "wt", encoding="utf-8") as saida:
        def emitir(registro):
            saida.write(json.dumps(registro, ensure_ascii=False) + "\n")
            unicos.add(registro["item_id"])
            if registro["item_id"] == 15:
                resumo["diferencas_item_248"].append(registro)
        for copia in COPIAS:
            arquivo = baixar(copia[0], cache)
            digest = hashlib.sha256()
            with arquivo.open("rb") as src:
                for bloco in iter(lambda: src.read(1024 * 1024), b""):
                    digest.update(bloco)
            with tempfile.TemporaryDirectory(dir=args.saida) as tmp:
                banco = Path(tmp) / "data.db"
                with gzip.open(arquivo, "rb") as src, banco.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                dados, campos = carregar(banco)
            resumo["fontes"].append({"commit": copia[0], "publicacao_utc": copia[1],
                                      "sha256": digest.hexdigest(), "bytes_gzip": arquivo.stat().st_size})
            resumo["item_248"].append({"commit": copia[0], "estado": dados.get(15)})
            if anterior is not None:
                velhos, campos_velhos, origem = anterior
                comuns = [c for c in campos if c in campos_velhos]
                resultado = comparar(velhos, dados, comuns, origem, copia, emitir)
                resultado["campos_nao_comparaveis"] = sorted(set(campos) ^ set(campos_velhos))
                resumo["intervalos"].append(resultado)
                print(origem[1], "->", copia[1], ":", resultado["itens_com_diferencas"], "itens com diferencas", flush=True)
            anterior = dados, campos, copia
    parcial.replace(args.saida / "diferencas.jsonl.gz")
    resumo["itens_distintos_com_diferencas"] = len(unicos)
    resumo["bytes_diferencas_gzip"] = (args.saida / "diferencas.jsonl.gz").stat().st_size
    (args.saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Concluido. Compartilhe:", args.saida / "resumo.json", flush=True)
    print("Diferencas comprimidas (bytes):", resumo["bytes_diferencas_gzip"], flush=True)


if __name__ == "__main__":
    main()
