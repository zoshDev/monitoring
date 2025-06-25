import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(log_directory="logs"):
    """
    Configure le système de logging centralisé.
    
    Args:
        log_directory (str): Le dossier où stocker les logs
    """
    # Création du dossier de logs s'il n'existe pas
    log_dir = Path(log_directory)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Nom du fichier de log avec la date
    log_file = log_dir / f"monitoring_{datetime.now().strftime('%Y%m%d')}.log"

    # Configuration du format
    log_format = '%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(log_format, date_format)

    # Handler pour le fichier avec rotation (max 10MB par fichier, garde 30 fichiers)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=30,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    # Handler pour la console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Configuration du logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Supprime les handlers existants pour éviter les doublons
    root_logger.handlers.clear()
    
    # Ajoute les nouveaux handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Crée des loggers spécifiques pour chaque composant
    loggers = {
        'scanner': logging.getLogger('scanner'),
        'backup': logging.getLogger('backup'),
        'validation': logging.getLogger('validation'),
        'notification': logging.getLogger('notification'),
        'api': logging.getLogger('api'),
    }

    # Configure chaque logger spécifique
    for logger in loggers.values():
        logger.setLevel(logging.INFO)
        logger.propagate = True  # Propage au logger root

    return loggers

# Emojis pour les différents types de logs
LOG_EMOJIS = {
    'START': '📂',
    'END': '✅',
    'ERROR': '❌',
    'WARNING': '⚠️',
    'INFO': 'ℹ️',
    'SUCCESS': '✅',
    'PROCESS': '🔄',
    'DATABASE': '📝',
    'FILE': '📄',
    'HASH': '🔐',
    'COPY': '📦',
    'NOTIFICATION': '📧',
    'VALIDATION': '✔️',
    'AGENT': '➡️',
    'STATS': '📊',
}

def get_formatted_message(emoji_key, message):
    """
    Formate un message de log avec l'emoji approprié.
    """
    emoji = LOG_EMOJIS.get(emoji_key, '')
    return f"{emoji} {message}" if emoji else message 