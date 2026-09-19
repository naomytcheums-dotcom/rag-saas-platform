# Strategie de recherche par defaut -- reranking

## Decision (audit, 2026-09-19)

La strategie par defaut reste `hybrid` (BM25 + recherche vectorielle,
fusion RRF), **sans** reranking par cross-encoder. `hybrid_reranked`
reste disponible, activable par organisation
(`organization_settings.retrieval_strategy`), mais n'est pas le
defaut.

## Pourquoi ce n'est pas change dans cette session

Le reranking par cross-encoder (`CrossEncoder.predict`, voir
`docs/testing/MANUAL_RESULTS.md`) charge un DEUXIEME modele
`sentence-transformers` en memoire, en plus du modele d'embedding deja
charge pour toute recherche. Etant donne le probleme memoire reel et
non resolu documente dans `docs/devops/MEMORY.md` (OOM confirme sur le
tier gratuit Render des le premier appel de chat, avec le SEUL modele
d'embedding deja charge), activer le reranking par defaut
**aggraverait** directement ce probleme au lieu de l'ameliorer -- un
deuxieme modele en memoire sur une instance qui manque deja de RAM.

## Recommandation

Garder `hybrid` comme defaut tant que le probleme memoire n'est pas
resolu (upgrade d'instance ou externalisation de l'embedding, voir
`docs/devops/MEMORY.md`). Une fois la contrainte memoire levee,
`hybrid_reranked` peut redevenir le defaut si la qualite de recherche
mesuree (voir Partie 7, Evaluation Lab, deja complete dans ce projet)
montre un gain suffisant pour justifier le cout.

## Statut

Choix assume et documente, pas change. Non teste en direct dans cette
session (aucun changement de comportement a verifier).
