#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script : prepare_manual_test_agents.py

Ce script prépare un environnement de test pour valider le comportement du scanner de sauvegardes.
Il permet de simuler 4 cas de figure typiques : SUCCESS, UNCHANGED, FAILED, MISSING.

Fonctionnalités :
    --prepare    : Crée les agents, fichiers .zst, dossiers et rapports JSON simulés
    --clean      : Supprime les agents de test, leurs fichiers, et les entrées en base associées
    --reset      : Exécute un clean complet suivi d’un prepare (réinitialisation totale)
    --agents N   : Définit le nombre d’agents à créer (par défaut 4, 1 par statut)
    --output     : Chemin personnalisé du dossier racine (écrase BACKUP_STORAGE_ROOT)
"""


import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))  # remonte d’un cran vers la racine
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import shutil
import argparse
import hashlib
import json
from datetime import datetime
import zstandard as zstd


from config.settings import settings
from app.models.models import ExpectedBackupJob, BackupEntry
from app.core.database import SessionLocal

AGENT_BASES = [
    ("SIRPACAM", "BAFOUSSAM", "CAMPUS"),
    ("SDMC", "DOUALA", "NDOGBATI"),
    ("ENEO", "YAOUNDE", "BRIQUETERIE"),
    ("CHU", "COTONOU", "HAN")
]


def build_agent_name(base, index):
    entreprise, ville, quartier = base
    return f"{entreprise}_{ville}_{quartier}_{index+1}"


def create_zst_file(path, content):
    cctx = zstd.ZstdCompressor()
    with open(path, 'wb') as f:
        compressed = cctx.compress(content.encode('utf-8'))
        f.write(compressed)


def compute_sha256(file_path):
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def prepare_environment(agent_count):
    os.makedirs(settings.BACKUP_STORAGE_ROOT, exist_ok=True)
    print(f"\n🚀 Préparation de l’environnement de test dans : {settings.BACKUP_STORAGE_ROOT}\n")
    db = SessionLocal()
    statuses = ["SUCCESS", "UNCHANGED", "FAILED", "MISSING"]

    for i in range(agent_count):
        status = statuses[i % 4]
        base = AGENT_BASES[i % len(AGENT_BASES)]
        agent_name = build_agent_name(base, i)
        agent_path = os.path.join(settings.BACKUP_STORAGE_ROOT, agent_name)
        db_path = os.path.join(agent_path, "databases")
        log_path = os.path.join(agent_path, "log")
        os.makedirs(db_path, exist_ok=True)
        os.makedirs(log_path, exist_ok=True)

        db_file = os.path.join(db_path, "test_db.zst")

        if status == "SUCCESS":
            create_zst_file(db_file, "Contenu de test initial")
            hash_value = compute_sha256(db_file)

        elif status == "UNCHANGED":
            create_zst_file(db_file, "Contenu de test initial")
            hash_value = compute_sha256(db_file)

        elif status == "FAILED":
            create_zst_file(db_file, "Contenu corrompu volontairement")
            hash_value = "FAUX_HASH_" + str(i)

        else:  # MISSING
            hash_value = None

        if status != "MISSING":
            report = {
                "agent_id": agent_name,
                "overall_status": "OK",
                "databases": {
                    "DB_TEST": {
                        "BACKUP": {"timestamp": datetime.utcnow().isoformat()},
                        "COMPRESS": {
                            "sha256": hash_value,
                            "filename": "test_db.zst"
                        },
                        "staged_file_name": "test_db.zst"
                    }
                }
            }
        else:
            report = {
                "agent_id": agent_name,
                "overall_status": "OK",
                "databases": {}
            }

        report_path = os.path.join(log_path, "rapport_test.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4)

        job = ExpectedBackupJob(
            agent_id_responsible=agent_name,
            database_name=f"DB_TEST_{i+1}",
            year=2025,
            company_name=base[0],
            city=base[1],
            neighborhood=base[2],
            is_active=True,
            agent_deposit_path_template=f"/mnt/agents/{agent_name}/databases",
            agent_log_deposit_path_template=f"/mnt/agents/{agent_name}/log",
            final_storage_path_template=f"/mnt/storage/{base[0]}/{base[1]}/{base[2]}",
        )



        db.add(job)

        emoji = {"SUCCESS": "✅", "UNCHANGED": "♻️", "FAILED": "❌", "MISSING": "🕳"}[status]
        print(f"{emoji} {agent_name} → statut simulé : {status}")

    db.commit()
    db.close()
    print(f"\n🎯 {agent_count} agents ont été générés.\n")


def clean_environment():
    print("\n🧹 Nettoyage de l’environnement de test…")
    db = SessionLocal()

    for base in AGENT_BASES:
        for i in range(100):
            agent_name = build_agent_name(base, i)
            agent_folder = os.path.join(settings.BACKUP_STORAGE_ROOT, agent_name)
            if os.path.exists(agent_folder):
                shutil.rmtree(agent_folder)
                print(f"🗑️  Dossier supprimé : {agent_folder}")

            jobs = db.query(ExpectedBackupJob).filter(ExpectedBackupJob.agent_id_responsible == agent_name).all()
            for job in jobs:
                db.query(BackupEntry).filter(BackupEntry.expected_job_id == job.id).delete()
                db.delete(job)

    db.commit()
    db.close()
    print("✅ Nettoyage terminé.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prépare un environnement de test manuel pour le scanner.")
    parser.add_argument("--prepare", action="store_true", help="Crée les agents et leurs rapports.")
    parser.add_argument("--clean", action="store_true", help="Supprime tous les agents simulés.")
    parser.add_argument("--reset", action="store_true", help="Réinitialise entièrement (clean + prepare).")
    parser.add_argument("--agents", type=int, default=4, help="Nombre total d’agents à générer (par défaut 4).")
    parser.add_argument("--output", type=str, help="Chemin personnalisé pour BACKUP_STORAGE_ROOT")

    args = parser.parse_args()

    if args.output:
        custom_root = os.path.abspath(args.output)
        settings.BACKUP_STORAGE_ROOT = custom_root
        print(f"\n📁 Dossier de sortie personnalisé : {custom_root}")
    else:
        print(f"\n📁 Dossier de sortie par défaut : {settings.BACKUP_STORAGE_ROOT}")

    if args.reset:
        clean_environment()
        prepare_environment(args.agents)
    elif args.clean:
        clean_environment()
    elif args.prepare:
        prepare_environment(args.agents)
    else:
        parser.print_help()
