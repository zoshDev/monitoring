#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import json
import hashlib
import shutil
from datetime import datetime, timedelta
import zstandard as zstd

# 📦 Ajouter le projet au chemin Python
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 📚 Imports projet
from config.settings import settings
from app.models.models import ExpectedBackupJob
from app.core.database import SessionLocal

AGENT_BASES = [
    ("SIRPACAM", "BAFOUSSAM", "CAMPUS"),
    ("SDMC", "DOUALA", "NDOGBATI"),
    ("ENEO", "YAOUNDE", "BRIQUETERIE"),
    ("SOCIA", "BLU", "GARE"),
    ("SOCIA", "EXO", "ZAC"),
    ("CHU", "COTONOU", "HAN")
]

STATUSES = ["SUCCESS", "UNCHANGED", "FAILED", "MISSING"]

def create_zst(content: str, path: str):
    cctx = zstd.ZstdCompressor()
    with open(path, "wb") as f:
        f.write(cctx.compress(content.encode("utf-8")))

def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def timestamp(offset):
    base = datetime(2025, 6, 24, 8, 0, 0)
    return (base + timedelta(seconds=offset)).isoformat()

def insert_job(session, year, ent, city, area, db_name, agent_id):
    session.query(ExpectedBackupJob).filter_by(
        year=year, company_name=ent, city=city, neighborhood=area, database_name=db_name
    ).delete()
    session.add(ExpectedBackupJob(
        year=year, company_name=ent, city=city, neighborhood=area, database_name=db_name,
        agent_id_responsible=agent_id,
        agent_deposit_path_template=f"/mnt/agents/{agent_id}/databases",
        agent_log_deposit_path_template=f"/mnt/agents/{agent_id}/log",
        final_storage_path_template=f"/mnt/storage/{ent}/{city}/{area}",
        is_active=True,
    ))

def empty_field_block():
    return {
        "status": "False",
        "start_time": "",
        "end_time": "",
        "sha256": "",
        "size": "0"
    }

def empty_transfer_block():
    return {
        "status": "False",
        "start_time": "",
        "end_time": "",
        "error_message": "null"
    }

def generate_agent(i, year, output_root, n_bases, reused_hash=None, verbose=False):
    ent, city, area = AGENT_BASES[i % len(AGENT_BASES)]
    agent_id = f"{ent}_{city}_{area}_{i+1}"
    a_dir = os.path.join(output_root, agent_id)
    log_dir = os.path.join(a_dir, "log")
    db_dir = os.path.join(a_dir, "databases")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(db_dir, exist_ok=True)

    report = {
        "operation_start_time": timestamp(0),
        "operation_end_time": timestamp(1800),
        "agent_id": agent_id,
        "databases": {}
    }

    session = SessionLocal()
    compteur = {k: 0 for k in STATUSES}

    for j in range(n_bases):
        db_name = f"{ent}_{city}_{area}_{year}_{j+1}"
        status = STATUSES[(i + j) % len(STATUSES)]
        insert_job(session, year, ent, city, area, db_name, agent_id)

        zst_filename = f"{db_name}.zst"
        zst_path = os.path.join(db_dir, zst_filename)

        if status != "MISSING":
            create_zst(f"Mock {db_name}", zst_path)
            hash_val = reused_hash if status == "UNCHANGED" and reused_hash else sha256(zst_path)
            if status == "FAILED":
                hash_val = f"INVALID_HASH_{i}_{j}"
            size = os.path.getsize(zst_path)
        else:
            hash_val = ""
            size = 0

        backup = {
            "status": "True" if status != "MISSING" else "False",
            "start_time": timestamp(10 * j) if status != "MISSING" else "",
            "end_time": timestamp(10 * j + 2) if status != "MISSING" else "",
            "sha256": hash_val,
            "size": str(size)
        }

        compress = {
            "status": "True" if status != "MISSING" else "False",
            "start_time": timestamp(800 + j) if status != "MISSING" else "",
            "end_time": timestamp(820 + j) if status != "MISSING" else "",
            "sha256": hash_val,
            "size": str(size // 4 if size else 0)
        }

        transfer = {
            "status": "True" if status != "MISSING" else "False",
            "start_time": timestamp(1600 + j) if status != "MISSING" else "",
            "end_time": timestamp(1602 + j) if status != "MISSING" else "",
            "error_message": "null"
        }

        #staged_file = zst_path if status != "MISSING" else ""
        staged_file = str(zst_path) if status != "MISSING" else ""


        report["databases"][db_name] = {
            "BACKUP": backup,
            "COMPRESS": compress,
            "TRANSFER": transfer,
            "staged_file_name": staged_file
        }

        compteur[status] += 1

        if status == "SUCCESS":
            reused_hash = hash_val

        if verbose:
            emoji = {"SUCCESS": "✅", "UNCHANGED": "♻️", "FAILED": "❌", "MISSING": "🕳"}
            print(f"{emoji[status]} {agent_id:<30} → {db_name} → {status}")

    now = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    json_path = os.path.join(log_dir, f"{now}_{agent_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)

    session.commit()
    session.close()
    return reused_hash, compteur

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", type=int, default=6, help="Nombre d’agents")
    parser.add_argument("--bases", type=int, default=2, help="Bases par agent")
    parser.add_argument("--output", type=str, default=str(settings.BACKUP_STORAGE_ROOT),
                        help="Dossier de sortie (défaut: settings.BACKUP_STORAGE_ROOT)")
    parser.add_argument("--year", type=int, default=2025, help="Année simulée")
    parser.add_argument("--reset", action="store_true", help="Efface le dossier de sortie avant génération")
    parser.add_argument("--verbose", action="store_true", help="Affichage détaillé")
    args = parser.parse_args()

    if args.reset and os.path.exists(args.output):
        shutil.rmtree(args.output)
    os.makedirs(args.output, exist_ok=True)

    global_count = {k: 0 for k in STATUSES}
    reused_hash = None
    for i in range(args.agents):
        reused_hash, count = generate_agent(i, args.year, args.output, args.bases, reused_hash, args.verbose)
        for k in STATUSES:
            global_count[k] += count[k]

    print("\n📊 Récapitulatif des statuts générés :")
    for k in STATUSES:
        print(f"  {k:<10} : {global_count[k]}")
    print(f"\n🎯 {args.agents} agents × {args.bases} base(s) → OK dans {args.output}\n")

if __name__ == "__main__":
    main()
