# Image de base Python
FROM python:3.9-slim

# Copie d'abord uniquement les fichiers nécessaires pour les dépendances
WORKDIR /monitoring
COPY requirements.txt .
COPY config ./config
RUN pip install --upgrade pip==25.1.1
RUN pip install -r requirements.txt

# Création des répertoires basée sur settings.py
RUN python3 -c "from config.settings import settings; \
    import os; \
    os.makedirs(settings.BACKUP_STORAGE_ROOT, exist_ok=True); \
    os.makedirs(settings.VALIDATED_BACKUPS_BASE_PATH, exist_ok=True); \
    os.makedirs(os.path.dirname(settings.DATABASE_URL.replace('sqlite:///', '')), exist_ok=True)"

# Copie du reste du code
COPY . .

# Port de l'application
EXPOSE 8000

# Démarrage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

