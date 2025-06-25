from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from config.settings import settings
import logging
from sqlalchemy.ext.declarative import declarative_base
from app.core.logging_config import get_formatted_message

import os

print(f"Chemin absolu de la base principale : {os.path.abspath(settings.DATABASE_URL)}")

# Configuration du logger
logger = logging.getLogger('database')

# Moteur pour la base principale
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

try:
    logger.info(get_formatted_message('START', "Initialisation de la connexion à la base de données"))
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        echo=True,
        connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
    )
    logger.info(get_formatted_message('SUCCESS', "Moteur de base de données créé"))
    
    # Moteur pour la base de test
    TEST_DATABASE_URL = "sqlite:///./data/db/test_sql_app.db"  # ✅ Base séparée pour les tests
    test_engine = create_engine(
        TEST_DATABASE_URL,
        echo=False,  # Moins de logs pour les tests
        connect_args={"check_same_thread": False} if "sqlite" in TEST_DATABASE_URL else {}
    )
    
    # Sessions pour base principale et tests
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    # Déclaration des modèles
    Base = declarative_base()
    logger.info(get_formatted_message('SUCCESS', "Base déclarative initialisée"))
    
except Exception as e:
    logger.error(get_formatted_message('ERROR', f"Erreur d'initialisation de la base de données: {str(e)}"))
    raise

# Fonction pour obtenir une session de la base principale
def get_db():
    """
    Fournit une session de base de données.
    """
    db = SessionLocal()
    #if db.bind.dialect.name == "sqlite":
    if db.bind is not None and db.bind.dialect.name == "sqlite":
        db.execute(text("PRAGMA foreign_keys=ON"))
    try:
        logger.debug(get_formatted_message('START', "Ouverture d'une nouvelle session de base de données"))
        yield db
        logger.debug(get_formatted_message('SUCCESS', "Session de base de données fermée avec succès"))
    except Exception as e:
        logger.error(get_formatted_message('ERROR', f"Erreur lors de l'utilisation de la session: {str(e)}"))
        raise
    finally:
        db.close()

# Fonction pour obtenir une session de la base de test
def get_test_db():
    db = TestSessionLocal()
    if db.bind is not None and db.bind.dialect.name == "sqlite":
        db.execute(text("PRAGMA foreign_keys=ON"))
    try:
        yield db
    finally:
        db.close()
