import logging
import logging.config
import yaml
import os

# Charger la configuration YAML
with open('config/logging.yaml', 'r') as f:
    config = yaml.safe_load(f)

# S'assurer que le dossier logs existe
os.makedirs('logs', exist_ok=True)

# Configurer le logging
logging.config.dictConfig(config)

# Créer un logger
logger = logging.getLogger(__name__)

# Tester différents niveaux de log
logger.debug('Message de test DEBUG')
logger.info('Message de test INFO')
logger.warning('Message de test WARNING')
logger.error('Message de test ERROR') 