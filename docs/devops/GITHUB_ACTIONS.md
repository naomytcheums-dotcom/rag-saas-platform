# Alertes GitHub Actions -- quota

## Incident reel qui motive ce document

Le quota Actions gratuit (2000 min/mois) a ete entierement consomme par
un ancien workflow de tests ("Tests and retrieval regression check",
n'existe plus dans le depot) qui a tourne en echec des dizaines de fois
entre le 8 et le 11 septembre 2026 -- decouvert seulement quand le
worker Celery planifie a commence a echouer, plusieurs jours plus tard.
Personne ne surveillait ce quota. Voir `docs/deployment/GITHUB_ACTIONS.md`
pour l'historique complet.

## Action recommandee (a faire manuellement, reglage de compte)

GitHub n'expose pas d'API pour configurer les alertes de facturation --
c'est un reglage de compte, dans l'interface web uniquement :

1. `github.com/settings/billing/budgets`
2. "Manage spending limit" -- meme a 0$ (pour rester strictement
   gratuit), GitHub envoie un e-mail quand l'usage approche la limite
   incluse, PAS seulement quand elle est depassee.
3. Verifier que l'adresse e-mail de notification est bien celle
   surveillee activement.

## Pourquoi ce n'est pas fait automatiquement dans cette session

Reglage de compte utilisateur (pas de depot), nécessitant une action
dans l'interface web GitHub avec les identifiants du proprietaire du
compte -- hors de portee d'une session automatisee sans acces au
compte GitHub lui-meme (au-dela des operations `gh` deja autorisees
sur le depot).

## Statut

Non configure dans cette session -- necessite une action manuelle du
proprietaire du compte, documentee ici avec les etapes exactes.
