# Worker Celery -- limites actuelles et solution perenne

## Etat actuel

Le worker Celery de production n'est **pas** un vrai processus
permanent. C'est un workflow GitHub Actions programme
(`.github/workflows/celery-worker.yml`), qui demarre toutes les 10
minutes, traite ce qui est dans la file pendant une fenetre bornee a 7
minutes, puis s'arrete -- une solution de contournement, pas une
architecture cible, adoptee parce que le tier Background Worker de
Render n'a pas de palier gratuit (7$/mois minimum, confirme en direct
sur le dashboard Render). Voir `docs/deployment/GITHUB_ACTIONS.md` pour
l'historique complet des bugs trouves et corriges pour la faire
fonctionner (TLS Redis, timeout de job, config S3).

## Limites reelles, non cachees

- Un document uploade peut attendre jusqu'a ~10 minutes avant d'etre
  traite (l'intervalle de la planification), jamais instantane.
- Une seule tache a la fois (`--pool=solo --concurrency=1`) -- pas de
  parallelisme si plusieurs documents arrivent en meme temps.
- Le worker ne tourne pas du tout si le depot GitHub est passe en
  prive ET que le quota Actions gratuit du compte est epuise (voir
  l'incident documente dans `docs/deployment/GITHUB_ACTIONS.md`,
  cause par un ancien workflow de tests casse qui a consomme tout le
  quota avant meme la creation de ce worker).
- Aucune vraie planification `beat` (les taches periodiques definies
  dans `celery_app.py`, purge de comptes supprimes, rotation de cles
  JWT, etc.) ne s'execute de facon fiable sur cet intervalle de 10
  minutes -- certaines de ces taches attendent une heure precise
  (`crontab(hour=3, minute=0)`), qui peut etre manquee si le run de
  10 minutes le plus proche ne tombe pas dedans.

## Solution perenne recommandee

Par ordre de preference, une fois le budget disponible :

1. **Render Background Worker** (7$/mois) -- le plus simple, meme
   plateforme que l'API web actuelle, aucun changement d'architecture.
2. **Fly.io** -- alternative deja explore partiellement dans une
   session anterieure (app `rag-saas-platform` existante mais mal
   configuree et en essai expirant), a reprendre proprement si Render
   n'est pas retenu.
3. **Un VPS low-cost avec plus de RAM** (ex. Hetzner, OVH) -- plus de
   travail d'installation/maintenance, mais RAM/CPU nettement
   superieurs pour le meme budget, ce qui adresserait AUSSI le
   probleme memoire documente dans `docs/devops/MEMORY.md` si le worker
   et l'API tournaient sur la meme machine plus genereuse.

## Statut

Non change dans cette session (necessite un budget, decision produit).
Ce document rend le compromis actuel explicite pour que la decision se
prenne en connaissance de cause, pas par defaut.
