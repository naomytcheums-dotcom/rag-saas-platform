# Contexte RAG transmis au LLM -- troncature

## Probleme trouve (audit, 2026-09-19)

`context` (le texte des chunks recuperes, injecte dans le prompt envoye
au LLM) etait construit par une simple concatenation
(`"\n\n".join(chunk["content"] for chunk in citation_chunks)`), sans
aucune limite de longueur. Une organisation avec des chunks nombreux
et/ou longs aurait pu depasser silencieusement la fenetre de contexte
reelle du modele LLM configure.

## Correction

`build_llm_context()` (nouveau, `api/services/retrieval_pipeline.py`) :
tronque au budget `settings.RAG_CONTEXT_MAX_TOKENS` (3000 par defaut),
mesure avec le meme tokenizer HuggingFace deja mis en cache pour le
chunking (`get_tokenizer`, `api/services/sentence_chunking.py`) -- pas
une estimation par nombre de caracteres. Les chunks les moins pertinents
(la fin de la liste, deja triee par pertinence) sont exclus en premier ;
le tout premier chunk est toujours garde meme s'il depasse a lui seul le
budget, pour ne jamais renvoyer un contexte vide a cause d'un seul
chunk long.

Utilisee aux deux points d'appel reels : `api/routers/chat_stream.py`
et `api/services/public_api.py::handle_public_chat`.

## Verification

3 tests unitaires ajoutes (`tests/test_retrieval_pipeline.py`) :
absence de chunks -> `None` ; concatenation normale sous le budget ;
troncature reelle verifiee avec un budget artificiellement petit (le
second chunk, plus court, est bien exclu). Les 3 passent.

Non teste en conditions reelles de production (un vrai appel de chat
avec un volume de documents suffisant pour declencher la troncature
n'a pas pu etre execute -- le compte de test de cette session n'a
qu'un seul chunk indexe au total, voir `docs/testing/MANUAL_RESULTS.md`).
