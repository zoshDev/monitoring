#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script : generate_realistic_agents.py

Ce script génère un environnement de test réaliste pour des agents de sauvegarde.
Chaque agent possède :
    - un répertoire dédié contenant `log/` et `databases/`
    - un fichier .zst compressé pour chaque base
    - un rapport JSON complet avec les blocs BACKUP, COMPRESS, TRANSFER
    - une entrée correspondante dans la base de données ExpectedBackupJob

Options :
    --agents N       : nombre d’agents à générer
    --bases N        : nombre de bases par agent
    --output PATH    : dossier racine où déposer les agents simulés
    --reset          : supprime le dossier de sortie avant génération
"""

import os
import argparse
import random
import json
import shutil
from datetime import datetime, timedelta
import hashlib
import zstandard as zstd

# 🧠 Ces trois lignes ajoutent dynamiquement la racine du projet
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 📦 Import SQLAlchemy et settings
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


def generate_timestamp(offset=0):
    base = datetime(2025, 6, 24, 8, 0, 0)
    return (base + timedelta(seconds=offset)).isoformat()


def compute_sha256(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def create_zst_file(content, dest_path):
    cctx = zstd.ZstdCompressor()
    with open(dest_path, "wb") as f:
        f.write(cctx.compress(content.encode("utf-8")))


def insert_expected_job(session, agent_id, entreprise, ville, quartier, db_name):
    job = ExpectedBackupJob(
        year=2025,
        company_name=entreprise,
        city=ville,
        neighborhood=quartier,
        database_name=db_name,
        agent_id_responsible=agent_id,
        agent_deposit_path_template=f"/mnt/agents/{agent_id}/databases",
        agent_log_deposit_path_template=f"/mnt/agents/{agent_id}/log",
        final_storage_path_template=f"/mnt/storage/{entreprise}/{ville}/{quartier}",
        is_active=True
    )
    session.add(job)


def generate_report(agent_id, base_names, zst_paths, output_log):
    report = {
        "operation_start_time": generate_timestamp(0),
        "operation_end_time": generate_timestamp(1800),
        "agent_id": agent_id,
        "databases": {}
    }

    for base_name, zst_path in zip(base_names, zst_paths):
        hash_value = compute_sha256(zst_path)
        size = os.path.getsize(zst_path)
        report["databases"][base_name] = {
            "BACKUP": {
                "status": "True",
                "start_time": generate_timestamp(0),
                "end_time": generate_timestamp(10),
                "sha256": hash_value,
                "size": str(size)
            },
            "COMPRESS": {
                "status": "True",
                "start_time": generate_timestamp(800),
                "end_time": generate_timestamp(820),
                "sha256": hash_value,
                "size": str(size // 4)
            },
            "TRANSFER": {
                "status": "True",
                "start_time": generate_timestamp(1600),
                "end_time": generate_timestamp(1602),
                "error_message": "null"
            },
            "staged_file_name": zst_path
        }

    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_filename = f"{now}_{agent_id}.json"
    full_path = os.path.join(output_log, report_filename)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)
    print(f"📄 Rapport JSON généré : {report_filename}")


def generate_agents(n_agents, n_bases, output_root, reset):
    if reset and os.path.exists(output_root):
        shutil.rmtree(output_root)
    os.makedirs(output_root, exist_ok=True)

    print(f"\n🚀 Génération de {n_agents} agents dans : {output_root}\n")
    session = SessionLocal()

    for i in range(n_agents):
        base = AGENT_BASES[i % len(AGENT_BASES)]
        entreprise, ville, quartier = base
        agent_id = f"{entreprise}_{ville}_{quartier}"
        agent_folder = os.path.join(output_root, agent_id)
        log_folder = os.path.join(agent_folder, "log")
        db_folder = os.path.join(agent_folder, "databases")
        os.makedirs(log_folder, exist_ok=True)
        os.makedirs(db_folder, exist_ok=True)

        base_names = []
        zst_paths = []

        for j in range(n_bases):
            db_name = f"{entreprise}_{ville}_{quartier}_{2025}_{j+1}"
            base_names.append(db_name)
            zst_name = f"{db_name}.zst"
            zst_path = os.path.join(db_folder, zst_name)
            create_zst_file(f"Fake data for {db_name}", zst_path)
            zst_paths.append(zst_path)

            insert_expected_job(session, agent_id, entreprise, ville, quartier, db_name)

        generate_report(agent_id, base_names, zst_paths, log_folder)
        print(f"✅ Agent simulé : {agent_id} → {n_bases} base(s) ajoutée(s) en BDD\n")

    session.commit()
    session.close()
    print("🎯 Tous les jobs ont été enregistrés en base.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agents", type=int, default=4, help="Nombre d'agents à générer")
    parser.add_argument("--bases", type=int, default=1, help="Nombre de bases par agent")
    parser.add_argument("--output", type=str, default="./realistic_agents", help="Dossier de sortie")
    parser.add_argument("--reset", action="store_true", help="Nettoie le dossier avant génération")

    args = parser.parse_args()
    generate_agents(args.agents, args.bases, os.path.abspath(args.output), args.reset)
