# `src/` -- statut legacy

## Decision (2026-09-19, suite audit)

`src/` est le prototype original mono-tenant (pipeline RAG + dashboard
Streamlit), anterieur au vrai backend SaaS multi-tenant `api/`. Il n'a
aucune notion d'organisation et duplique certaines constantes deja
presentes dans `api/` (voir `docs/CAHIER_DES_CHARGES.md` ligne 136 pour
le detail exact des valeurs dupliquees/divergentes).

**Verifie avant toute action** : aucun module de `api/` ni du frontend
n'importe quoi que ce soit depuis `src/` (`grep` complet, zero resultat).
`src/` est genuinement independant du produit reel.

**Decision prise : ne PAS deplacer/supprimer physiquement `src/` dans
cette session.** Deux raisons reelles qui rendent le deplacement plus
risque que la valeur qu'il apporte dans l'immediat :

1. **7 fichiers de tests** (`tests/test_*.py`) importent directement
   depuis `src/` (via `sys.path.insert`) et testent son pipeline
   original -- les deplacer sans casser silencieusement leur collecte
   demande une verification fichier par fichier, pas une simple
   commande de deplacement.
2. Le `Dockerfile` a la racine (distinct de `Dockerfile.api`, jamais
   touche cette session) construit encore une image autour de
   `src/app.py` (le dashboard Streamlit). Rien ne confirme qu'un
   service de production l'utilise encore aujourd'hui, mais le
   supprimer sans le confirmer serait irreversible et non verifie.

**Ce qui est fait a la place** : ce document sert de marqueur explicite
-- `src/` est officiellement legacy/reference, ne doit recevoir aucune
nouvelle fonctionnalite (tout developpement reel se fait dans `api/`),
et son eventuelle suppression physique doit etre une decision separee,
deliberee, prise avec confirmation que `Dockerfile` (racine) n'est
reellement plus deploye nulle part.

## Ce qui duplique quoi (etat au 2026-09-19)

| Constante | `src/` | `api/` |
|---|---|---|
| Taille/chevauchement de chunk | `CHUNK_SIZE_TOKENS=512` (`src/indexing.py`) | Configurable par organisation (`organization_settings`) |
| Modele d'embedding | Duplique dans `src/indexing.py` ET `src/retrieval.py` | `api/services/embedding_config.py`, resolu par organisation |
| Modele de reranking | `CROSS_ENCODER_MODEL_NAME`/`FINAL_TOP_K=5` (`src/retrieval.py`) | `reranker_model` resolu par organisation |
| Modele LLM | `claude-sonnet-5` (`src/generation.py`) | `claude-3-sonnet-20240229` (defaut `api/`, **different**) |
| Max tokens | `MAX_TOKENS=1024`/`AGENT_MAX_TOKENS=1024` (`src/generation.py`/`src/agent.py`) | `4096` (defaut `api/`, **different**) |
