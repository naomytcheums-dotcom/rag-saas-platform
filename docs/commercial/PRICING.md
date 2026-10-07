# Grille de tarification

Cette grille est construite à partir des plans et limites réellement visibles dans le code, sans inventer de niveaux non présents dans l'application.

## 1. Plans observés

Le dépôt contient des concepts de quotas et de limites par organisation dans `api/config.py` et dans les modèles de quotas/usage. Les valeurs par défaut montrent un modèle de plan d'entreprise et de consommation qui n'est pas exposé sous des nomenclatures commerciales complètes, mais les éléments suivants sont présents :

- quota d'utilisateurs
- quota d'espaces de travail
- quota de documents
- quota de stockage
- quota de requêtes / mois
- quota de requêtes / jour
- quota d'appels API
- quota d'agents
- quota de taille de connaissance (KB)

## 2. Modèle de facturation implicite

Les limites sont traitées comme des quotas server-side par organisation et sont révisables dans l'API. Aucune grille de prix fixe n'est publiée dans le dépôt, mais l'architecture laisse clairement supposer un modèle basé sur :

- nombre d'utilisateurs
- nombre de documents / stockage
- volume de requêtes et d'appels API
- nombre d'agents ou d'espaces de travail

## 3. Exercé de tarification honnête

Le dépôt ne fournit pas un plan de tarification finalisé. Il est donc préférable de le traiter comme un plan de référence technique, pas comme une proposition de vente finalisée.

### Option de base
- quotas standards par organisation
- plafonds documentaires et de stockage
- limites de requêtes 

### Option entreprise
- quotas plus élevés sur les ressources critiques
- davantage d'agents / d'espaces / de capacité
- observabilité plus avancée et intégration de services externes

## 4. Limite de portée

Les montants, devis et formulaires de vente n'existent pas dans le dépôt. La tarification ci-dessous doit être utilisée comme cadre de discussion, non comme prix contractual.
