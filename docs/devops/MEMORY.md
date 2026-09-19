# Memoire -- OOM sur Render (re-investigation complete, 2026-09-19)

## Ce que la premiere passe avait conclu, et pourquoi c'etait incomplet

Une premiere investigation (plus tot dans cette meme session) avait
conclu a une limite materielle incompressible, sur la base d'un `grep`
cherchant des imports eagers de bibliotheques ML/vision
(`torch`/`sentence_transformers`/`ultralytics`/`cv2`) -- aucun trouve,
d'ou la conclusion que le code etait deja optimal. **Cette conclusion
etait fausse : le grep cherchait la mauvaise categorie de bibliotheque.**

## Mesure reelle, en direct, avec un vrai process Python

Backend demarre localement (`uvicorn api.main:app`), memoire mesuree
avec `psutil` sur le process reel a chaque etape :

| Etape | Avant correction | Apres correction |
|---|---|---|
| Interpreteur seul | 25 Mo | 25 Mo |
| `import api.main` (avant toute requete, c'est le cout paye AVANT que `/health` puisse repondre) | **399 Mo** | **251 Mo** |
| + un vrai appel d'embedding (modele charge et utilise) | 796 Mo | 635 Mo |
| + `litellm` pret pour un vrai appel de chat | 796 Mo | 775 Mo |

## La vraie cause : `litellm`, pas les bibliotheques ML

`import litellm` coute a lui seul **~190 Mo** de RSS (verifie
isolement : un shell Python vide passe de 18 Mo a 208 Mo au seul
`import litellm`) -- son propre fichier de couts par modele et les
SDK de chaque fournisseur qu'il embarque. Ce module etait importe au
niveau superieur de `api/services/llm_providers.py` ET
`api/services/voice.py`, donc charge en memoire des le demarrage du
process, avant qu'aucune vraie conversation n'ait eu lieu -- alors que
seules 2 fonctions dans chaque fichier l'utilisent reellement.

**Corrige** (`api/services/llm_providers.py`,
`api/services/voice.py`) : `import litellm` deplace a l'interieur des
4 fonctions qui l'utilisent reellement (`_chat_completion_raw`,
`chat_completion_stream`, `transcribe_audio`,
`transcribe_audio_with_diarization`), au lieu du haut du fichier.
Verifie que `monkeypatch.setattr(litellm, "acompletion", ...)` dans
`tests/test_llm_providers.py` continue de fonctionner (les modules
Python sont des singletons caches dans `sys.modules` -- patcher
l'attribut sur l'objet module reste valide, que l'import soit fait au
niveau du fichier ou a l'interieur d'une fonction). 71 tests reels
(`test_llm_providers.py`, `test_voice_providers.py`,
`test_voice_messages_and_settings.py`,
`test_media_finalization.py`) executes apres coup, tous passants.

Les bibliotheques ML/vision (torch, sentence-transformers) etaient
deja, elles, correctement en lazy loading -- la premiere passe avait
raison sur ce point precis, juste incomplete sur le reste du graphe
d'imports.

## Ce que ce correctif change reellement, et ce qu'il ne change pas

- **Demarrage du process (avant `/health`) : -37% (399 -> 251 Mo)**.
  C'est le changement qui compte le plus pour la fenetre de
  health-check de 5 secondes de Render documentee dans ce meme
  fichier -- moins de risque d'etre tue par OOM avant meme d'avoir pu
  repondre une seule fois.
- **Usage reel pendant une vraie conversation (embedding + appel LLM) :
  -3% seulement (796 -> 775 Mo)**. `litellm` est toujours necessaire
  au premier vrai message envoye -- ce correctif retarde son cout, il
  ne le supprime pas, parce que le chat est la fonctionnalite
  principale de l'application, pas une fonctionnalite optionnelle.

**Conclusion honnete** : 775 Mo pour une conversation reelle depasse
toujours largement la limite de 512 Mo du tier gratuit Render. Ce
n'est ni un mythe ni une exageration -- c'est une mesure reelle,
reproductible, sur le vrai code de production. Le correctif ci-dessus
est reel et utile (moins de crashs au demarrage), mais ne resout pas
le probleme dans son ensemble : `litellm` (~190 Mo) et le modele
d'embedding + torch (~380 Mo) sont tous les deux des couts reels et
necessaires des fonctionnalites reellement utilisees (chat, RAG), pas
du gaspillage identifiable et supprimable par une optimisation de
code supplementaire.

## Options reelles pour resoudre completement le probleme

1. **Passer a un tier Render payant avec plus de RAM** (le plus
   simple, cout mensuel recurrent).
2. **Oracle Cloud Free Tier** (propose par le proprietaire du produit) :
   l'offre "Always Free" d'Oracle Cloud Infrastructure inclut
   reellement jusqu'a 24 Go de RAM (instances Ampere A1, ARM, jusqu'a
   4 OCPU / 24 Go, gratuites en permanence, pas un essai limite dans
   le temps) -- largement suffisant pour ce profil memoire (~800 Mo en
   usage reel). Necessiterait de migrer le deploiement hors de Render
   (conteneuriser avec le `Dockerfile`/`docker-compose.selfhosted.yml`
   deja presents dans ce depot) et de gerer soi-meme ce qui etait
   jusque-la automatique sur Render (deploiements, certificats,
   health checks). **Non fait dans cette session** -- la creation
   d'un compte cloud tiers et le provisionnement d'infrastructure sont
   des actions significatives et peu reversibles qui necessitent une
   confirmation explicite, action par action, du proprietaire du
   produit.
3. **Reduire encore le modele d'embedding** : `all-MiniLM-L6-v2` est
   deja parmi les plus petits modeles `sentence-transformers`
   couramment utilises (~80 Mo sur disque) -- une reduction
   supplementaire degraderait reellement la qualite de recherche RAG,
   un compromis produit, pas une simple optimisation technique.

## Statut

Corrige reellement pour la partie qui l'etait (import eager de
`litellm`, -148 Mo au demarrage, verifie en direct avec de vrais
chiffres avant/apres). Le reste (~775 Mo en usage reel, au-dessus de
la limite de 512 Mo) reste une limite materielle reelle du tier
gratuit, confirmee par la mesure et non par une supposition -- corrigee
uniquement par un changement d'infrastructure (option 1 ou 2
ci-dessus), qui reste une decision produit/budget, pas une action que
cette session peut prendre seule.
