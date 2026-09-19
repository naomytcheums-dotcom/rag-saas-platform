# Memoire (OOM sur le tier gratuit Render)

## Ce qui a ete verifie, honnetement, avant toute conclusion

L'audit du 2026-09-19 emettait l'hypothese que des modeles ML lourds
(torch, sentence-transformers, et potentiellement ultralytics/opencv)
etaient charges de facon EAGER (au demarrage du process, pas a la
demande), et proposait un chargement paresseux comme correction. Cette
hypothese a ete verifiee point par point dans cette session -- et
**elle s'est reveler fausse** :

- Aucun import de niveau module (`^import torch`, `^from torch`,
  `^import sentence_transformers`, `^import ultralytics`, `^import cv2`)
  n'existe nulle part dans `api/` (`grep` exhaustif, zero resultat).
- Tous les usages reels (`_get_embedder`, `_get_reranker` dans
  `api/services/retrieval_pipeline.py`, et l'equivalent dans
  `api/security/documents.py`) importent DEJA ces bibliotheques a
  l'interieur de la fonction elle-meme, au moment du premier appel --
  exactement le pattern de chargement paresseux recommande.
- Ces memes fonctions mettent DEJA le modele charge en cache
  (`_EMBEDDER_CACHE`/`_RERANKER_CACHE`, des dictionnaires module-level)
  -- aucun rechargement redondant a chaque appel.
- `torch==2.13.0+cpu` (`requirements-api.txt` ligne 145, avec
  `--extra-index-url https://download.pytorch.org/whl/cpu`) -- deja la
  variante CPU-only, pas le build CUDA (qui serait bien plus lourd).
- Le modele d'embedding par defaut (`all-MiniLM-L6-v2`) est deja l'un
  des plus petits modeles `sentence-transformers` disponibles (~80MB).

**Conclusion honnete : il n'y avait aucun vrai bug de "chargement non
paresseux" a corriger.** Le code suivait deja les bonnes pratiques
disponibles avant cet audit.

## La vraie cause

`torch` + `sentence-transformers`, meme charges une seule fois, meme en
version CPU-only et avec le plus petit modele raisonnable, ont un cout
memoire reel incompressible de l'ordre de 300-400MB une fois vraiment
en memoire (poids du modele + runtime torch + allocations internes) --
un fait connu et documente de l'ecosysteme, pas une inefficacite de ce
code. Ajoute a la base de gunicorn + FastAPI + les autres dependances
deja residentes (~100-150MB), un vrai appel de chat (qui declenche
`generate_embeddings` pour la premiere fois dans le process) fait
depasser le plafond de 512MB du tier gratuit Render -- confirme
directement par l'evenement Render lui-meme : *"Ran out of memory (used
over 512MB) while running your code."*

## Options reelles restantes (aucune appliquee dans cette session)

1. **Externaliser l'embedding** (appel a une API d'embedding externe --
   OpenAI, Cohere, ou l'API d'embedding d'un des fournisseurs LLM deja
   integres -- au lieu d'un modele local) : supprimerait entierement le
   besoin de charger torch/sentence-transformers dans LE MEME processus
   que le serveur web. **Refonte architecturale reelle, hors perimetre
   d'un correctif d'audit** -- touche le chunking a l'indexation ET la
   recherche, change un cout d'infra (RAM) en cout recurrent (appels
   API payants).
2. **Upgrade du tier Render** (minimum 1GB RAM recommande pour ce
   profil de dependances) -- la solution la plus directe, necessite un
   budget, decision produit/business, pas technique.
3. **Processus separe pour l'embedding** (un service dedie, appele par
   HTTP depuis l'API principale) -- deplace le cout memoire ailleurs
   sans le supprimer ; n'a de sens que si ce second processus tourne
   sur une instance differente avec sa propre RAM.

## Statut

Non resolu dans cette session -- c'est une limite d'infrastructure
reelle, pas un defaut de code identifiable ou corrigible sans l'une des
3 options ci-dessus (budget ou refonte architecturale), toutes hors du
perimetre de correctifs de code de cet audit.
