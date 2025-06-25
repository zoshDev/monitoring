# config/settings.py
# Ce fichier définit les paramètres de configuration de l'application en utilisant Pydantic.

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os

class Settings(BaseSettings):
    """
    Classe de configuration de l'application.
    Les paramètres sont chargés à partir des variables d'environnement ou d'un fichier .env.
    """
    
    # Stockage des sauvegardes
    BACKUP_STORAGE_ROOT: str = Field(
        default="test_manuel",
        description="Répertoire racine pour le stockage des sauvegardes"
    )
    
    VALIDATED_BACKUPS_BASE_PATH: str = "validate"
    
    # Configuration de la base de données
    DATABASE_URL: str = Field(
        default="sqlite:///./data/db/sql_app.db",
        description="URL de connexion à la base de données"
    )

    API_V1_STR: str = Field(
        default="/api/v1",
        description="Préfixe pour les routes de l'API v1"
    )

    # Configuration du scanner
    SCANNER_INTERVAL_MINUTES: int = Field(
        default=1,
        description="Intervalle de planification du scanner de sauvegardes en minutes",
        gt=0
    )
    
    SCANNER_REPORT_COLLECTION_WINDOW_MINUTES: int = Field(
        default=60,
        description="Fenêtre de temps en minutes pour la collecte des rapports",
        gt=0
    )

    MAX_STATUS_FILE_AGE_DAYS: int = Field(
        default=1,
        description="Âge maximum en jours d'un fichier STATUS.json",
        gt=0
    )

    APP_TIMEZONE: str = Field(
        default="UTC",
        description="Fuseau horaire par défaut de l'application"
    )

    # Configuration email
    EMAIL_HOST: Optional[str] = Field(
        default=None,
        description="Hôte du serveur SMTP"
    )
    
    EMAIL_PORT: int = Field(
        default=587,
        description="Port du serveur SMTP"
    )

    EMAIL_USERNAME: Optional[str] = Field(
        default=None,
        description="Nom d'utilisateur SMTP"
    )
    
    EMAIL_PASSWORD: Optional[str] = Field(
        default=None,
        description="Mot de passe SMTP"
    )
    
    EMAIL_SENDER: Optional[str] = Field(
        default=None,
        description="Adresse email de l'expéditeur"
    )
    
    ADMIN_EMAIL_RECIPIENT: Optional[str] = Field(
        default=None,
        description="Adresse email du destinataire administrateur"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )

settings = Settings()
