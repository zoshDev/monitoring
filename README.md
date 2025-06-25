# Système de Monitoring de Sauvegardes

Ce projet est un système de monitoring automatisé pour la gestion et la validation des sauvegardes. Il permet de :
- Surveiller les sauvegardes entrantes
- Valider l'intégrité des fichiers de sauvegarde
- Gérer les notifications en cas d'anomalies
- Suivre l'historique des sauvegardes

## Prérequis

- Python 3.8+
- Docker et Docker Compose (pour le déploiement conteneurisé)
- Base de données SQLite

## Installation

1. Cloner le dépôt :
```bash
git clone [URL_DU_DEPOT]
cd monitoring
```

2. Installer les dépendances :
```bash
pip install -r requirements.txt
```

3. Configuration :
- Copier `.env.example` en `.env`
- Modifier les variables d'environnement selon votre configuration

## Déploiement avec Docker

1. Construction de l'image :
```bash
docker-compose build
```

2. Démarrage des services :
```bash
docker-compose up -d
```

## Structure du Projet

- `app/` : Code source principal
  - `api/` : Endpoints FastAPI
  - `core/` : Configuration et composants centraux
  - `services/` : Services métier
  - `models/` : Modèles de données
- `alembic/` : Migrations de base de données
- `tests/` : Tests unitaires et d'intégration
- `scripts/` : Scripts utilitaires

## Tests

Pour exécuter les tests :
```bash
pytest tests/
```

## Contribution

1. Forker le projet
2. Créer une branche pour votre fonctionnalité
3. Commiter vos changements
4. Pousser vers la branche
5. Créer une Pull Request

## Licence

[À définir]
