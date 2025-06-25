# app/utils/file_operations.py
# Ce module fournit des fonctions utilitaires pour la manipulation sécurisée des fichiers
# et des répertoires sur le système de stockage du serveur.

import os
import shutil # Pour des opérations de haut niveau sur les fichiers, comme le déplacement
import logging
from app.core.logging_config import get_formatted_message

# Configuration du logger
logger = logging.getLogger('file_operations')

class FileOperationError(Exception):
    """Exception personnalisée levée en cas d'erreur lors d'une opération sur fichier."""
    pass

def ensure_directory_exists(directory_path):
    """
    S'assure qu'un répertoire existe, le crée si nécessaire.
    """
    try:
        logger.debug(get_formatted_message('START', f"Vérification du répertoire: {directory_path}"))
        if not os.path.exists(directory_path):
            logger.info(get_formatted_message('CREATE', f"Création du répertoire: {directory_path}"))
            os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(get_formatted_message('ERROR', f"Erreur lors de la création du répertoire: {str(e)}"))
        return False

def move_file(source_path, destination_path):
    """
    Déplace un fichier d'un emplacement à un autre.
    """
    try:
        logger.info(get_formatted_message('START', f"Déplacement du fichier de {source_path} vers {destination_path}"))
        
        # Vérification des chemins
        if not os.path.exists(source_path):
            logger.error(get_formatted_message('ERROR', f"Fichier source non trouvé: {source_path}"))
            return False
            
        # Création du répertoire de destination si nécessaire
        dest_dir = os.path.dirname(destination_path)
        if not ensure_directory_exists(dest_dir):
            logger.error(get_formatted_message('ERROR', f"Impossible de créer le répertoire de destination: {dest_dir}"))
            return False
            
        # Déplacement du fichier
        shutil.move(source_path, destination_path)
        logger.info(get_formatted_message('SUCCESS', "Fichier déplacé avec succès"))
        return True
        
    except Exception as e:
        logger.error(get_formatted_message('ERROR', f"Erreur lors du déplacement du fichier: {str(e)}"))
        return False

def create_dummy_file(file_path: str, content: bytes = b"dummy content"):
    """
    Crée un fichier factice avec un contenu donné. Utile pour les tests.

    Args:
        file_path (str): Le chemin complet du fichier à créer.
        content (bytes): Le contenu binaire à écrire dans le fichier.

    Raises:
        FileOperationError: Si la création du fichier échoue.
    """
    try:
        # S'assurer que le répertoire parent existe avant de créer le fichier
        ensure_directory_exists(os.path.dirname(file_path))
        with open(file_path, "wb") as f:
            f.write(content)
        logger.debug(f"Fichier factice créé : {file_path} (taille: {len(content)} octets)")
    except Exception as e:
        logger.error(f"Échec de la création du fichier factice '{file_path}': {e}")
        raise FileOperationError(f"Impossible de créer le fichier factice '{file_path}': {e}")

def copy_file(source_path, destination_path):
    """
    Copie un fichier d'un emplacement à un autre.
    """
    try:
        logger.info(get_formatted_message('START', f"Copie du fichier de {source_path} vers {destination_path}"))
        
        # Vérification des chemins
        if not os.path.exists(source_path):
            logger.error(get_formatted_message('ERROR', f"Fichier source non trouvé: {source_path}"))
            return False
            
        # Création du répertoire de destination si nécessaire
        dest_dir = os.path.dirname(destination_path)
        if not ensure_directory_exists(dest_dir):
            logger.error(get_formatted_message('ERROR', f"Impossible de créer le répertoire de destination: {dest_dir}"))
            return False
            
        # Copie du fichier
        shutil.copy2(source_path, destination_path)
        logger.info(get_formatted_message('SUCCESS', "Fichier copié avec succès"))
        return True
        
    except Exception as e:
        logger.error(get_formatted_message('ERROR', f"Erreur lors de la copie du fichier: {str(e)}"))
        return False

def delete_file(file_path: str) -> None:
    """
    Supprime un fichier.

    Args:
        file_path (str): Le chemin du fichier à supprimer.

    Raises:
        FileOperationError: Si le fichier n'existe pas ou si la suppression échoue.
    """
    logger.debug(f"Tentative de suppression du fichier : {file_path}")
    if not os.path.exists(file_path):
        logger.warning(f"Tentative de suppression d'un fichier non existant : '{file_path}'. Opération ignorée.")
        return # Ne lève pas d'erreur si le fichier n'existe pas déjà pour la suppression.

    try:
        os.remove(file_path)
        logger.info(f"Fichier supprimé : '{file_path}'")
    except OSError as e:
        logger.error(f"Erreur lors de la suppression du fichier '{file_path}' : {e}")
        raise FileOperationError(f"Impossible de supprimer le fichier '{file_path}' : {e}")
