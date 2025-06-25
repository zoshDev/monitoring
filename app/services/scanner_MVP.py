import os
import json
import sys
import logging
from app.core.logging_config import get_formatted_message

from app.services.notifier import notify_backup_status_change, NotificationError

# Ajoute le dossier racine 'monitoring' au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.stagged_file_name_filter import extraire_nom_fichier

import shutil
from datetime import datetime, timezone

# Importations de l'application
from app.utils.crypto import calculate_file_sha256
from app.utils.is_valid_backup_report import is_valid_backup_report
from app.models.models import ExpectedBackupJob, BackupEntry
from config.settings import settings  # Pour BACKUP_STORAGE_ROOT et VALIDATED_BACKUPS_BASE_PATH

# Configuration du logger
logger = logging.getLogger('scanner')

# ------------------------------------------------------------------------------
# Création automatique des ExpectedBackupJob
# ------------------------------------------------------------------------------
def create_expected_jobs_from_report(report, db_session):
    """
    Crée automatiquement les ExpectedBackupJob pour les bases de données déclarées dans le rapport
    si elles n'existent pas déjà, en respectant la contrainte d'unicité.
    
    Args:
        report (dict): Le rapport JSON validé
        db_session: La session de base de données active
    """
    try:
        agent_id = report.get("agent_id")
        if not agent_id:
            print("⚠️ Agent ID manquant dans le rapport")
            return

        # Extraction des composants de l'agent_id (format attendu: COMPANY_CITY_LOCATION)
        agent_parts = agent_id.split("_")
        if len(agent_parts) < 3:
            print(f"⚠️ Format d'agent_id invalide: {agent_id}")
            return

        agent_company = agent_parts[0]
        agent_city = agent_parts[1]
        agent_neighborhood = agent_parts[2]  # Le quartier/location depuis l'agent_id

        databases = report.get("databases", {})
        for db_name, db_info in databases.items():
            # Analyse du nom de la base de données pour extraire les composants
            # Format typique: COMPANY_CITY_TYPE_YEAR ou COMPANY_CITY_YEAR
            db_parts = db_name.split("_")
            if len(db_parts) < 2:
                print(f"⚠️ Format de nom de base de données invalide: {db_name}")
                continue

            try:
                # Extraction de l'année depuis le nom de la BD
                year = int(db_parts[-1])  # Dernier élément devrait être l'année
                
                # Construction des composants pour la contrainte d'unicité
                company_name = db_parts[0]  # Premier élément est toujours la compagnie
                city = db_parts[1]  # Deuxième élément est toujours la ville
                
                # Le quartier peut être soit dans le nom de la BD, soit celui de l'agent
                neighborhood = agent_neighborhood
                if len(db_parts) > 3 and not db_parts[-1].isdigit():
                    neighborhood = db_parts[2]

                # Vérification de l'existence avec tous les critères d'unicité
                existing_job = db_session.query(ExpectedBackupJob).filter_by(
                    year=year,
                    company_name=company_name,
                    city=city,
                    neighborhood=neighborhood,
                    database_name=db_name,
                    is_active=True
                ).first()

                if existing_job:
                    print(f"ℹ️ Job existant ignoré: {db_name} ({company_name}/{city}/{neighborhood}/{year})")
                    continue

                # Extraction du chemin de dépôt depuis le rapport
                staged_file_info = db_info.get("staged_file_name", "")
                if staged_file_info:
                    deposit_base_path = os.path.dirname(staged_file_info)
                else:
                    deposit_base_path = os.path.join(settings.BACKUP_STORAGE_ROOT, agent_id, "databases")

                # Construction des chemins templates
                agent_deposit_path = os.path.join(deposit_base_path, f"{db_name}.zst")
                agent_log_path = os.path.join(settings.BACKUP_STORAGE_ROOT, agent_id, "log")
                final_storage_path = os.path.join(settings.VALIDATED_BACKUPS_BASE_PATH, company_name, city, str(year), f"{db_name}.zst")

                # Création du nouveau job avec tous les champs requis
                new_job = ExpectedBackupJob(
                    # Champs d'identification
                    agent_id_responsible=agent_id,
                    database_name=db_name,
                    year=year,
                    city=city,
                    company_name=company_name,
                    neighborhood=neighborhood,
                    
                    # Chemins templates
                    agent_deposit_path_template=agent_deposit_path,
                    agent_log_deposit_path_template=agent_log_path,
                    final_storage_path_template=final_storage_path,
                    
                    # Statut et état
                    current_status='UNKNOWN',
                    is_active=True,
                    
                    # Timestamps automatiques (created_at et updated_at sont gérés par le modèle)
                    last_checked_timestamp=None,
                    last_successful_backup_timestamp=None
                )

                db_session.add(new_job)
                print(f"✅ Nouveau job créé: {db_name} ({company_name}/{city}/{neighborhood}/{year})")

            except ValueError as ve:
                print(f"⚠️ Erreur de format pour la base de données {db_name}: {str(ve)}")
                continue

        # Commit dans un try séparé pour ne pas perdre les logs en cas d'échec
        try:
            db_session.commit()
        except Exception as commit_error:
            print(f"❌ Échec du commit des nouveaux jobs: {str(commit_error)}")
            db_session.rollback()

    except Exception as e:
        print(f"❌ Erreur lors de la création des jobs: {str(e)}")
        db_session.rollback()

# ------------------------------------------------------------------------------
# Partie Notification
# ------------------------------------------------------------------------------
def send_notification(job, message):
    """
    Envoie une notification pour un job dont le statut n'est pas SUCCESS.
    Cette fonction est un stub à adapter (e.g., envoi d'un e-mail, alerte Slack, etc.).
    """
    # Ici, nous utilisons simplement un print pour la démonstration.
    print(f"[NOTIFICATION] Job ID {job.id} ({job.database_name}) - Statut: {job.current_status} - Message: {message}")
# ------------------------------------------------------------------------------
# Fonctions de base pour charger et archiver les rapports JSON
# ------------------------------------------------------------------------------
def load_json_report(json_path):
    """Charge et renvoie le contenu d'un fichier JSON."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def archive_report(json_path):
    """
    Déplace le fichier JSON traité dans un sous-dossier "_archive" 
    du dossier parent (typiquement le dossier log de l'agent).
    """
    print("**********DEBUT ARCHIVAGE*************")
    archive_folder = os.path.join(os.path.dirname(json_path), "_archive")
    os.makedirs(archive_folder, exist_ok=True)
    archived_path = os.path.join(archive_folder, os.path.basename(json_path))
    shutil.move(json_path, archived_path)

    return archived_path

# ------------------------------------------------------------------------------
# Traitement d'un ExpectedBackupJob individuel
# ------------------------------------------------------------------------------
def process_expected_job(job, databases_data, agent_databases_folder, agent_id, operation_log_file_name, agent_status, db_session):
    """Traite un job de backup attendu."""
    now = datetime.now(timezone.utc)
    computed_hash = None
    staged_file_name = None
    backup_file_path = None
    message = ""

    logger.info(get_formatted_message('DATABASE', f"Base: {job.database_name}"))

    if job.database_name in databases_data:
        data = databases_data[job.database_name]
        staged_file_name = extraire_nom_fichier(data.get("staged_file_name"), [".zst", ".gz", ".db.sql"])
        compress_section = data.get("COMPRESS", {})
        expected_hash = compress_section.get("sha256_checksum") if compress_section.get("sha256_checksum") else compress_section.get("sha256")
        
        if staged_file_name is None:
            staged_file_name = ""
            
        backup_file_path = os.path.join(agent_databases_folder, staged_file_name)
        logger.info(get_formatted_message('FILE', f"Fichier: {staged_file_name}"))

        if os.path.exists(backup_file_path):
            try:
                computed_hash = calculate_file_sha256(backup_file_path)
                logger.info(get_formatted_message('HASH', "Vérification hash:"))
                logger.info(f"         ├─ Attendu:  {expected_hash}")
                logger.info(f"         └─ Calculé:  {computed_hash}")

                if computed_hash != expected_hash:
                    job.current_status = "FAILED"
                    message = "Hash non conforme"
                    logger.error(get_formatted_message('ERROR', "Hash non conforme"))
                else:
                    job.last_successful_backup_timestamp = now
                    if job.previous_successful_hash_global:
                        if computed_hash == job.previous_successful_hash_global:
                            job.current_status = "UNCHANGED"
                            message = "Backup inchangé"
                            logger.info(get_formatted_message('INFO', "Backup inchangé"))
                        else:
                            job.current_status = "SUCCESS"
                            job.previous_successful_hash_global = computed_hash
                            message = "Nouveau backup validé"
                            logger.info(get_formatted_message('SUCCESS', "Nouveau backup validé"))
                            try:
                                validated_path = os.path.join(
                                    settings.VALIDATED_BACKUPS_BASE_PATH,
                                    job.company_name,
                                    job.city,
                                    str(job.year)
                                )
                                job.file_storage_path_template = os.path.join(validated_path, staged_file_name)
                                os.makedirs(validated_path, exist_ok=True)
                                shutil.copy2(backup_file_path, os.path.join(validated_path, staged_file_name))
                                logger.info(get_formatted_message('COPY', f"Copié vers: {validated_path}"))
                            except Exception as copy_err:
                                job.current_status = "FAILED"
                                message = f"Erreur copie: {copy_err}"
                                logger.error(get_formatted_message('ERROR', f"Échec copie: {copy_err}"))
                    else:
                        job.current_status = "SUCCESS"
                        job.previous_successful_hash_global = computed_hash
                        message = "Premier backup validé"
                        logger.info(get_formatted_message('SUCCESS', "Premier backup validé"))
                        try:
                            validated_path = os.path.join(
                                settings.VALIDATED_BACKUPS_BASE_PATH,
                                job.company_name,
                                job.city,
                                str(job.year)
                            )
                            job.file_storage_path_template = os.path.join(validated_path, staged_file_name)
                            os.makedirs(validated_path, exist_ok=True)
                            shutil.copy2(backup_file_path, os.path.join(validated_path, staged_file_name))
                            logger.info(get_formatted_message('COPY', f"Copié vers: {validated_path}"))
                        except Exception as copy_err:
                            job.current_status = "FAILED"
                            message = f"Erreur copie: {copy_err}"
                            logger.error(get_formatted_message('ERROR', f"Échec copie: {copy_err}"))
            except Exception as hash_error:
                job.current_status = "FAILED"
                message = f"Erreur hash: {hash_error}"
                logger.error(get_formatted_message('ERROR', f"Erreur hash: {hash_error}"))
        else:
            job.current_status = "FAILED"
            message = f"Fichier manquant: {staged_file_name}"
            logger.error(get_formatted_message('ERROR', f"Fichier manquant: {staged_file_name}"))
    else:
        job.current_status = "MISSING"
        message = "Base non trouvée dans le rapport"
        logger.error(get_formatted_message('ERROR', "Base non trouvée dans le rapport"))
        expected_hash = "N/A"

    # Mise à jour du job
    job.last_checked_timestamp = now
    
    # Création de l'entrée BackupEntry
    backup_entry = BackupEntry(
        expected_job_id=job.id,
        timestamp=now,
        status=job.current_status,
        message=message,
        expected_hash=expected_hash,
        operation_log_file_name=operation_log_file_name,
        agent_id=agent_id,
        agent_overall_status=agent_status,
        server_calculated_staged_hash=computed_hash or "",
        server_calculated_staged_size=os.path.getsize(backup_file_path) if backup_file_path and os.path.exists(backup_file_path) else None,
        previous_successful_hash_global=job.previous_successful_hash_global,
        hash_comparison_result=True if ((computed_hash == expected_hash) and (computed_hash and expected_hash)) else False,
        created_at=now
    )

    db_session.add(job)
    db_session.add(backup_entry)
    
    if job.current_status in ["MISSING", "UNCHANGED", "FAILED"]:
        try:
            logger.info(get_formatted_message('NOTIFICATION', f"Envoi notification: {job.current_status}"))
            notify_backup_status_change(job, backup_entry, expected_hash)
        except NotificationError as e:
            logger.warning(get_formatted_message('WARNING', f"Échec notification: {e}"))
        except Exception as e:
            logger.error(get_formatted_message('ERROR', f"Erreur notification: {e}"))
            send_notification(job, message)

    logger.info(get_formatted_message('SUCCESS', f"Statut final: {job.current_status}"))

# ------------------------------------------------------------------------------
# Traitement complet d'un rapport JSON pour un agent donné
# ------------------------------------------------------------------------------
def process_agent_report(agent_log_json_path, agent_databases_folder, db_session, agent_name):
    """Traite un rapport JSON d'un agent."""
    try:
        report = load_json_report(agent_log_json_path)
        if not isinstance(report, dict):
            logger.warning(get_formatted_message('WARNING', "Rapport JSON invalide ou vide"))
            archive_report(agent_log_json_path)
            return

        if not is_valid_backup_report(report):
            logger.error(get_formatted_message('ERROR', "Format de rapport non conforme"))
            archive_report(agent_log_json_path)
            return

        logger.info(get_formatted_message('VALIDATION', "Validation du rapport réussie"))

        # Création automatique des ExpectedBackupJob
        try:
            create_expected_jobs_from_report(report, db_session)
        except Exception as e:
            logger.error(get_formatted_message('ERROR', f"Échec création jobs: {str(e)}"))

        databases_data = report.get("databases", {})
        active_jobs = db_session.query(ExpectedBackupJob).filter_by(
            is_active=True, 
            agent_id_responsible=agent_name
        ).all()

        logger.info(get_formatted_message('STATS', f"Traitement de {len(databases_data)} bases de données"))
        logger.info(get_formatted_message('STATS', f"{len(active_jobs)} jobs actifs trouvés"))

        agent_id = report.get("agent_id")
        operation_log_file_name = os.path.basename(agent_log_json_path)
        agent_status = report.get("overall_status")

        for job in active_jobs:
            logger.info(get_formatted_message('PROCESS', f"VALIDATION JOB: {job.database_name}"))
            process_expected_job(
                job,
                databases_data,
                agent_databases_folder,
                agent_id,
                operation_log_file_name,
                agent_status,
                db_session
            )

        db_session.commit()
        logger.info(get_formatted_message('COPY', f"ARCHIVAGE: {operation_log_file_name}"))
        archive_report(agent_log_json_path)
        logger.info(get_formatted_message('SUCCESS', "Traitement du rapport terminé"))

    except Exception as e:
        logger.error(get_formatted_message('ERROR', f"Erreur générale: {str(e)}"))
        if os.path.exists(agent_log_json_path):
            archive_report(agent_log_json_path)

# ------------------------------------------------------------------------------
# Itération sur le dossier racine des agents
# ------------------------------------------------------------------------------
def process_all_agents(db_session):
    """Parcourt et traite tous les agents dans le dossier racine."""
    logger.info(get_formatted_message('START', "DÉBUT DU SCAN GLOBAL"))
    logger.info(get_formatted_message('INFO', f"Dossier racine: {settings.BACKUP_STORAGE_ROOT}"))

    agents = [d for d in os.listdir(settings.BACKUP_STORAGE_ROOT) if os.path.isdir(os.path.join(settings.BACKUP_STORAGE_ROOT, d))]
    logger.info(get_formatted_message('STATS', f"Nombre d'agents détectés: {len(agents)}"))

    for agent_name in agents:
        logger.info(get_formatted_message('AGENT', f"TRAITEMENT AGENT: {agent_name}"))
        agent_path = os.path.join(settings.BACKUP_STORAGE_ROOT, agent_name)
        log_folder = os.path.join(agent_path, "log")
        databases_folder = os.path.join(agent_path, "databases")

        if not os.path.isdir(log_folder) or not os.path.isdir(databases_folder):
            logger.warning(get_formatted_message('WARNING', f"Structure invalide pour l'agent {agent_name}"))
            logger.warning(f"   ├─ Dossier log: {'✅' if os.path.isdir(log_folder) else '❌'}")
            logger.warning(f"   └─ Dossier databases: {'✅' if os.path.isdir(databases_folder) else '❌'}")
            continue

        json_files = [f for f in os.listdir(log_folder) if f.lower().endswith('.json')]
        logger.info(get_formatted_message('STATS', f"   └─ {len(json_files)} fichiers JSON trouvés"))

        for file_name in json_files:
            agent_log_json_path = os.path.join(log_folder, file_name)
            logger.info(get_formatted_message('FILE', f"ANALYSE RAPPORT: {file_name}"))
            process_agent_report(agent_log_json_path, databases_folder, db_session, agent_name)

    logger.info(get_formatted_message('END', "FIN DU SCAN GLOBAL"))

# ------------------------------------------------------------------------------
# Fonction de lancement du scanner en production
# ------------------------------------------------------------------------------
def run_new_scanner():
    """
    Lance le scanner sur l'ensemble des agents en parcourant le dossier racine.
    
    Pour une exécution en production, nous utilisons SessionLocal, qui pointe sur la base de production.
    """
    # Utiliser la SessionLocal en production.
    from app.core.database import SessionLocal
    db_session = SessionLocal()
    try:
        process_all_agents(db_session)

    finally:

        db_session.close()

# ------------------------------------------------------------------------------
# Point d'entrée pour exécution en tant que script
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    run_new_scanner()
