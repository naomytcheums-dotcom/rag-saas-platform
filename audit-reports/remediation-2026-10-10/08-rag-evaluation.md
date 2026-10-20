# 08 — Évaluation RAG

**Aucune métrique de qualité (Recall@k, MRR, NDCG, EM, F1, abstention, citations) n'a été mesurée dans cette session. Statut : NOT_RUN.** Ce qui a été fait : outillage, protocole, correction de l'intégrité des datasets.
Protocole détaillé : `docs/evaluation/RAG_EVALUATION.md`.

## État revérifié du code
| Élément | Constat | Preuve |
|---|---|---|
| Calculs Recall@1/3/5/10, MRR, NDCG, Precision | présents, au niveau **document** (`expected_documents=[{document_id, relevance_score}]`) | `api/services/retrieval_metrics.py`, `ground_truth_documents.py`, tests existants (`test_retrieval_metrics.py` : réussis dans cette session) |
| Eval Lab (datasets, questions, jobs, comparaisons, régressions) | présent | routes `/organizations/{org_id}/datasets`, `/datasets/{id}/evaluate`, `/jobs/{id}/…` |
| Import de dataset | JSON/CSV ; **n'exigeait ni forme ni existence des documents de vérité terrain** | corrigé (ci-dessous) |
| SQuAD 2.0 | **aucun adaptateur**, aucune gestion des questions sans réponse, pas d'EM/F1 | corrigé (ci-dessous) |
| Chemin de recherche de production | **NOT_VERIFIED** : le sous-agent d'audit l'a décrit comme incertain (cosinus numpy en mémoire vs index HNSW créé par migration) ; non tranché dans cette session | voir plan ci-dessous |

## Corrigé
1. **Correspondance dataset ↔ documents réels** (REM-009, FIXED) : forme toujours contrôlée (`document_id` requis) ; option `verify_documents` (paramètre de requête, défaut `false` = comportement historique) rejette les lignes dont les documents n'existent pas dans l'organisation du dataset ou sont supprimés. 4 tests + 77 tests Eval Lab relancés.
2. **Outillage SQuAD 2.0** (REM-010, PARTIAL) : `api/services/squad_eval.py`
   - validation stricte du format (v2.x, ids uniques, `is_impossible` cohérent avec les réponses, contexte non vide) ;
   - conservation de **tous** les identifiants SQuAD et de **toutes** les réponses de référence ;
   - un document par contexte distinct (clé stable sha256) ; les lignes de dataset ne sont construites qu'à partir d'**identifiants de documents réels** (un contexte non ingéré est une erreur, pas une ligne perdue) ; questions sans réponse ⇒ aucun document attendu, `category=squad2:unanswerable` ;
   - métriques : normalisation officielle, EM, F1, meilleur score sur toutes les réponses de référence, précision/rappel/F1 d'abstention, `citation_support` (une citation ne compte que si le passage cité contient une réponse de référence), prédiction manquante = erreur ;
   - 17 tests sur un mini fichier **synthétique** (explicitement non-benchmark).
3. **Séparation retrieval / génération / citations / abstention** : définie dans le protocole (5 questions), non exécutée.

## Limites (à lire avant toute interprétation)
- SQuAD 2.0 est un benchmark Wikipédia de compréhension de lecture : il ne dit rien sur les PDF, tableaux, OCR, le français, les documents d'entreprise, les droits d'accès ou la latence.
- La récupération est évaluée **au niveau document** ; le niveau passage (`answer_start` → chunk) n'est pas implémenté.
- Une citation qui pointe vers un document existant ne justifie pas forcément la réponse : `citation_support` mesure seulement « le passage cité contient la réponse » ; l'annotation de **support factuel** exige une méthode (humain ou LLM-juge) à définir avant de publier un chiffre.
- `import_questions` ne stocke qu'une seule `expected_answer` ; toutes les références restent dans le fichier SQuAD.
- Le dataset métier synthétique n'est pas généré (BACKLOG) ; il devra être étiqueté synthétique et séparé du benchmark public.

## Plan pour obtenir de vrais résultats (aucune dépense engagée)
1. Décider du modèle de génération (local gratuit ou budget approuvé) et de l'embedder ; vérifier que le modèle d'embedding est disponible hors ligne (sinon téléchargement ~90 Mo à approuver).
2. Télécharger le fichier **dev** SQuAD 2.0 (~4 Mo ; vérifier licence), fixer un sous-ensemble d'articles (liste enregistrée).
3. Base **jetable** + `scripts/run_local_preview.py` ; ingérer `corpus_documents`, importer avec `verify_documents=true`, lancer l'Eval Lab (retrieval), puis le générateur (EM/F1/abstention), calculer `score_predictions`.
4. Rapport avec : SHA, dataset+version+sous-ensemble, nombre d'exemples réellement évalués, configuration retriever/générateur, résultats bruts et agrégés, erreurs, durée/coût mesurés, limites, commandes.
5. Comparaison à configuration identique des variantes **effectivement branchées** (le chunking avancé annoncé comme « non câblé » dans `api/config.py` ne doit pas être présenté comme évalué).

## Pipeline de recherche : points à trancher (non faits)
- Quel chemin sert la production : tracer `retrieval_pipeline.search()` avec `EXPLAIN` sur PostgreSQL jetable (index HNSW utilisé ?) ; tests pgvector sur PostgreSQL (le nouveau job CI en offre le cadre, pas encore de test de recherche) ; comportement si l'embedder est indisponible ; dimensions : colonne fixe 384, autres dimensions = JSON sans ANN (pas de plan de migration écrit : **backlog**, ne rien supprimer sans plan).
