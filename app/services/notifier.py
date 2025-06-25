import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import Optional, Any, Dict
from datetime import datetime

from config.settings import settings
from app.models.models import ExpectedBackupJob, BackupEntry, JobStatus, BackupEntryStatus
from app.core.logging_config import get_formatted_message

# Configuration du logger
logger = logging.getLogger('notification')

class NotificationError(Exception):
    """Exception personnalisée pour les erreurs de notification."""
    pass

def format_datetime(dt: Any) -> str:
    """Formate une date ou retourne 'N/A' si None."""
    try:
        if hasattr(dt, 'strftime'):
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        return 'N/A'
    except:
        return 'N/A'

def format_size(size: Any) -> str:
    """Formate une taille ou retourne 'N/A' si None."""
    try:
        if size is not None:
            return f"{size} octets"
        return 'N/A'
    except:
        return 'N/A'

def get_smtp_config() -> Dict[str, str]:
    """Récupère et valide la configuration SMTP."""
    config = {
        'host': str(getattr(settings, 'EMAIL_HOST', '')),
        'port': str(getattr(settings, 'EMAIL_PORT', '')),
        'username': str(getattr(settings, 'EMAIL_USERNAME', '')),
        'password': str(getattr(settings, 'EMAIL_PASSWORD', '')),
        'sender': str(getattr(settings, 'EMAIL_SENDER', ''))
    }
    return config

def send_email(subject: str, body: str, recipient: str) -> bool:
    """
    Envoie un email via SMTP.
    """
    try:
        logger.info(get_formatted_message('START', f"Envoi d'email à {recipient}"))
        
        # Récupération de la configuration SMTP
        smtp_config = get_smtp_config()
        
        # Vérification des paramètres requis
        if not all(smtp_config.values()):
            logger.error(get_formatted_message('ERROR', "Configuration SMTP incomplète"))
            return False
        
        # Configuration du message
        msg = MIMEMultipart()
        msg['From'] = smtp_config['sender']
        msg['To'] = recipient
        msg['Subject'] = subject
        
        # Ajout du corps du message
        msg.attach(MIMEText(body, 'plain'))
        
        # Connexion au serveur SMTP
        with smtplib.SMTP(smtp_config['host'], int(smtp_config['port'])) as server:
            server.starttls()
            server.login(smtp_config['username'], smtp_config['password'])
            
            # Envoi du message
            server.send_message(msg)
            logger.info(get_formatted_message('SUCCESS', "Email envoyé avec succès"))
            return True
            
    except Exception as e:
        logger.error(get_formatted_message('ERROR', f"Erreur lors de l'envoi de l'email: {str(e)}"))
        return False

def notify_backup_status_change(
    job: ExpectedBackupJob,
    backup_entry: BackupEntry,
    expected_hash: Optional[str]
):
    """
    Envoie une notification pour un changement de statut de backup.
    """
    try:
        logger.info(get_formatted_message('START', f"Préparation notification pour {job.database_name}"))
        
        # Ne pas notifier si le statut est SUCCESS
        if str(getattr(backup_entry, 'status', '')).upper() == "SUCCESS":
            logger.info(get_formatted_message('INFO', f"Pas de notification nécessaire pour {job.database_name} (SUCCESS)"))
            return True
        
        # Construction du sujet
        subject = f"🚨 ALERTE BACKUP - {job.database_name} - {backup_entry.status}"
        
        # Construction du message
        message = f"""
⚠️ ALERTE : Anomalie détectée sur la sauvegarde

📊 Informations du Job :
------------------------
• Base de données : {job.database_name}
• Agent responsable : {job.agent_id_responsible}
• Société : {job.company_name}
• Ville : {job.city}
• Statut global : {job.current_status}

📝 Détails de l'anomalie :
-------------------------
• Statut : {backup_entry.status}
• Date de détection : {format_datetime(getattr(backup_entry, 'timestamp', None))}
• Hash attendu : {expected_hash}
• Hash calculé (Serveur) : {getattr(backup_entry, 'server_calculated_staged_hash', 'N/A')}
• Message : {backup_entry.message}

🔍 Informations complémentaires :
-------------------------------
• Dernier backup réussi : {format_datetime(getattr(job, 'last_successful_backup_timestamp', None))}
• Taille du fichier : {format_size(getattr(backup_entry, 'server_calculated_staged_size', None))}

⚡ Actions requises :
------------------
1. Vérifier l'état de l'agent de backup
2. Contrôler les logs de l'agent
3. Valider l'intégrité des données
4. Relancer la sauvegarde si nécessaire

Cordialement,
Système de Surveillance des Sauvegardes
"""
        
        # Envoi de l'email
        if settings.ADMIN_EMAIL_RECIPIENT:
            if send_email(subject, message, settings.ADMIN_EMAIL_RECIPIENT):
                logger.info(get_formatted_message('SUCCESS', f"Notification envoyée pour {job.database_name}"))
                return True
            else:
                logger.error(get_formatted_message('ERROR', f"Échec de l'envoi de la notification pour {job.database_name}"))
                return False
        else:
            logger.warning(get_formatted_message('WARNING', "Aucun destinataire configuré"))
            return False
            
    except Exception as e:
        logger.error(get_formatted_message('ERROR', f"Erreur lors de la notification: {str(e)}"))
        raise NotificationError(f"Erreur lors de l'envoi de la notification: {str(e)}")
