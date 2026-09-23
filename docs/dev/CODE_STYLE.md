# Style de code -- commentaires

## Constat (audit, 2026-09-19)

Le code de ce projet utilise systematiquement des blocs de commentaires
tres detailles (souvent plusieurs paragraphes par fonction), expliquant
le contexte historique, les bugs trouves et corriges, et le
raisonnement derriere chaque decision -- un style deliberement choisi
tout au long du projet, pas une derive. Utile pour la tracabilite
(chaque decision garde sa justification), mais alourdit reellement la
lecture et le diff review pour quelqu'un qui rejoint le projet.

## Decision (audit)

**Pas de reecriture massive dans cette session.** Rediger ce style
partout (des centaines de fonctions, sur l'ensemble d'un projet de
cette taille) serait un chantier enorme, a haut risque (modifier des
commentaires sans toucher au code reel est facile a faire, mais le
faire correctement sur autant de fichiers sans introduire d'erreur
demande une revue humaine, pas un script aveugle).

## Recommandation pour la suite

- **Nouveau code** : suivre la meme regle que le reste de cet audit --
  un commentaire seulement quand le POURQUOI n'est pas evident (un bug
  reel trouve, une contrainte cachee), jamais pour decrire CE QUE fait
  le code (deja lisible par les noms). Les commentaires ajoutes dans
  cette session (XSS, pools DB, context RAG, etc.) suivent deja cette
  regle plus courte.
- **Code existant** : deplacer l'historique des decisions vers un vrai
  `CHANGELOG.md` ou des ADR (Architecture Decision Records) au moment
  ou un fichier est de toute facon modifie pour une autre raison --
  jamais comme un chantier de nettoyage isole qui ne touche a rien de
  fonctionnel.

## Statut

Documente, pas applique retroactivement -- decision assumee, pas un
oubli.
