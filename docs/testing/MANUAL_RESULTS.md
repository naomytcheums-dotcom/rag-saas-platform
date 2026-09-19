# Tests manuels des 12 parcours du dashboard client

Tests reels effectues dans un navigateur, contre la production
(`https://rag-saas-platform.vercel.app` et son alias de preview
`https://rag-saas-platform-git-main-naomytcheums-dotcoms-projects.vercel.app`,
API `https://rag-saas-api-sjsm.onrender.com`), avec un compte de test cree
via l'API (`celery-test-1789746965@example.com`).

## 1. Inscription / Connexion -- BUG CRITIQUE, non corrige

Statut : ECHEC sur le domaine principal, OK sur l'alias de preview.

Sur `https://rag-saas-platform.vercel.app` (domaine de production
principal) : "Echec de la connexion" affiche. Reseau :
`POST http://localhost:8000/auth/login [FAILED: net::ERR_BLOCKED_BY_CLIENT]`.

Cause : `frontend/lib/api.ts:6` retombe sur `http://localhost:8000` quand
`NEXT_PUBLIC_API_URL` n'est pas defini au build. Ce domaine a ete buildé
sans cette variable -- contrairement a l'alias de preview
(`...git-main-...`), deja corrige plus tot dans cette session, qui
fonctionne correctement.

**Impact : authentification cassee sur le lien que verraient de vrais
clients en priorite (le domaine principal), pas seulement un detail.**

Action requise (acces Vercel necessaire, non disponible depuis cette
session) :
1. Vercel -> Project Settings -> Environment Variables
2. Verifier que `NEXT_PUBLIC_API_URL=https://rag-saas-api-sjsm.onrender.com`
   est coche pour l'environnement **Production** (pas seulement Preview).
3. Redeployer pour que le domaine principal recupere la variable.

Les parcours 2 a 12 ci-dessous ont ete testes sur l'alias de preview
(fonctionnel) pour ne pas rester bloques par ce bug.

## 2. Upload de document -- OK

Documents deja uploades pendant les tests Celery (`test-doc.txt`,
`test-doc-2.txt`) s'affichent avec leur vrai statut (`completed` /
`failed`), coherent avec l'API. Interface de drop/upload presente et
correctement rendue.

## 3. Creation d'agent -- OK

Formulaire teste en reel : creation de "Agent Test Celery" reussie,
apparait dans la liste avec statut "active", options "Mettre en pause" /
"Supprimer" disponibles.

## 4. Conversation -- OK avec reserve qualite

Le chat repond reellement (pas d'erreur), mais a une question posee en
francais ("Bonjour, quel est ton document de test ?"), la reponse est
generique, en anglais, sans section "SOURCES" -- contrairement a l'exemple
de demo pre-rempli affiche au premier chargement (qui, lui, cite 2 sources
avec numeros de page). Suggere que la question n'a pas declenche de vraie
recuperation (retrieval) sur les documents indexes de l'organisation, ou
qu'un mecanisme de secours generique a repondu a la place. A investiguer
cote backend (agent_orchestrator / recherche vectorielle) -- non
diagnostique plus en profondeur faute de temps dans cette passe.

## 5. Widget -- OK

Page de personnalisation (nom, message de bienvenue, logo, couleurs,
position, theme) s'affiche et se charge correctement.

## 6. Cles API -- OK

Testee en reel : creation d'une cle avec scopes `chat:read` +
`search:read`, cle affichee une seule fois (`pk_...`), listee ensuite avec
ses scopes, actions "Renouveler" / "Revoquer" disponibles.

## 7. Facturation -- OK (fausse alerte initiale)

Semblait bloquee sur "Chargement..." indefiniment au premier essai --
en realite juste lente (probablement cold start Render), resolue apres
quelques secondes supplementaires. Affiche correctement : Forfait Free,
1000 credits disponibles, aucune facture (coherent avec un compte de test
neuf).

## 8. Admin -- Comportement correct (pas un bug)

`/admin` affiche "Acces restreint -- Cette section est reservee aux
administrateurs de la plateforme. Votre compte n'a pas ce role." Controle
d'acces qui fonctionne comme prevu pour un compte proprietaire
d'organisation (pas super-admin plateforme). Non testable plus en
profondeur sans un vrai compte super-admin.

## 9. Marketplace -- OK

Liste un plugin reel ("My Live Test Plugin", issu d'un test anterieur dans
cette meme session), recherche et filtres presents et fonctionnels a
l'affichage.

## 10. Analytics -- OK, mais absent de la navigation

Accessible directement via `/dashboard/analytics`, fonctionne (onglets
Vue d'ensemble/Metier/Produit/Technique/Tableaux de bord, gating correct
"Business metrics are only visible to platform administrators", donnees
reelles affichees -- "No data for this period" pour ce compte neuf, ce qui
est correct). **Absent du menu lateral** -- aucun lien "Analytics" dans la
sidebar testee, un vrai client ne trouverait jamais cette page sans en
connaitre l'URL exacte.

## 11. Fine-tuning -- OK, mais absent de la navigation et sans action de creation visible

Accessible directement via `/dashboard/fine-tuning`, affiche 3 compteurs
(Jeux de donnees, Taches, Modeles) tous a 0 pour ce compte neuf -- coherent.
**Absent du menu lateral**, comme Analytics. Aucun bouton "Creer" visible
sur la page pour amorcer un jeu de donnees ou une tache -- possible lacune
UI (fonctionnalite en lecture seule cote frontend, ou action existante
mais non trouvee dans cette passe).

## 12. Agents autonomes -- OK, mais absent de la navigation et formulaire en anglais

Accessible directement via `/dashboard/autonomous-agents`. Teste en reel :
creation de "Agent Autonome Test" reussie, apparait avec statut "idle",
"Step 0/20". **Absent du menu lateral**, comme Analytics et Fine-tuning.
Le formulaire de creation est entierement en anglais ("Agent name",
"Description (optional)", "Goal — what should this agent achieve?", "Max
steps", "Create agent") alors que tout le reste de l'interface testee est
en francais -- incoherence i18n reelle, pas juste cosmetique vu que le
reste du produit est localise.

## Synthese (etat au premier passage)

- 1 bug critique non corrige : authentification cassee sur le domaine de
  production principal (variable d'environnement Vercel a corriger, acces
  non disponible depuis cette session).
- 1 reserve qualite non resolue : reponses du chat pas clairement ancrees
  sur les documents malgre des documents indexes disponibles.
- 3 pages fonctionnelles mais invisibles dans la navigation (Analytics,
  Fine-tuning, Agents autonomes) -- un vrai client ne les decouvrirait
  jamais sans lien direct.
- 1 incoherence i18n (formulaire Agents autonomes en anglais).
- Tous les autres parcours testes (Documents, Agents, Widget, Cles API,
  Facturation, Admin, Marketplace) fonctionnent correctement.

---

## Session de correction du 2026-09-18/19 -- les 4 points demandes

### 1. Chat sans citations -- cause racine trouvee et corrigee (verification live bloquee par une limite d'infra)

Deux bugs reels empiles, tous deux corriges dans le code :

**a) Le chat tournait entierement sur un mock local**
(`frontend/lib/mockChat.ts`, desormais supprime) -- 3 reponses anglaises
codees en dur (`CANNED_REPLIES`), jamais connecte au vrai backend, malgre
un commentaire affirmant a tort que "login n'est pas encore branche".
Remplace par `frontend/lib/useRealChat.ts`, un vrai hook branche sur
`POST /chat/stream` (SSE), un vrai agent et une vraie conversation
persistee.

**b) Meme le vrai backend ne transmettait jamais le contenu recupere au LLM**
Verifie dans `api/services/agent_orchestrator.py` (`run_agent` et
`stream_response`) : les deux acceptent bien un parametre `context` qui
est injecte dans le prompt envoye au LLM (`messages.append({"role": "user",
"content": f"Context:\n{context}"})`). Mais aucun des deux points d'entree
reels (`api/services/public_api.py::handle_public_chat`,
`api/routers/chat_stream.py::_stream_response`) ne construisait ce
`context` a partir des chunks recuperes par `search_with_context` --
`citation_chunks` etait passe uniquement pour l'affichage des citations
et le calcul de metriques de qualite apres coup, jamais pour le prompt
lui-meme. Un appel pouvait donc afficher des citations pour un contenu
que le LLM n'avait en realite jamais vu. Corrige aux deux endroits :
`context = "\n\n".join(chunk["content"] for chunk in citation_chunks)`,
transmis a `run_agent`/`stream_response`. `chat_stream.py` n'appelait
meme pas la recherche du tout ; ajoute (meme appel a
`search_with_context` que `public_api.py`).

**Tests reels effectues, 3 bugs supplementaires trouves et corriges en
testant en direct** :
- Crash React #310 (hook appele apres un `return` anticipe dans
  `frontend/app/chat/page.tsx`) -- corrige.
- Bug de re-initialisation : le hook ne reessayait jamais une fois
  `org.id` reellement charge (`useRealChat.ts`) -- corrige.
- Deux appels CPU bloquants (`generate_embeddings`, `CrossEncoder.predict`
  dans `api/services/retrieval_pipeline.py`) geles la boucle asyncio
  entiere, provoquant un echec du health check Render et un redemarrage
  force de l'instance en plein streaming -- corriges avec
  `loop.run_in_executor`.
- Timeout par defaut de gunicorn (30s, trop court pour un stream SSE) --
  porte a 130s dans `gunicorn.conf.py` (aligne sur `SSE_TIMEOUT`).

**Blocage final, non corrigeable par du code** : apres ces 4 correctifs,
un nouveau test reel en direct a echoue avec, cette fois, dans les
evenements Render : *"Ran out of memory (used over 512MB) while running
your code."* -- l'instance gratuite (512MB RAM) charge des dependances ML
lourdes (torch, sentence-transformers, et d'apres l'historique du
Dockerfile egalement ultralytics/opencv) au demarrage ; un appel de chat
reel (embedding de la requete + appel LLM en streaming en meme temps)
depasse ce plafond memoire et Render tue l'instance. Ce n'est plus un bug
de code identifiable -- c'est une limite structurelle du tier gratuit face
aux dependances reelles de cette application. Pistes reelles, non
appliquees (hors perimetre de cette session) : charger les modeles ML de
maniere paresseuse/conditionnelle pour reduire l'empreinte memoire de
base, retirer les dependances non utilisees par le chemin de chat
(ultralytics/opencv semblent lies au traitement d'images/documents, pas
au chat lui-meme), ou passer a un tier Render avec plus de RAM.

### 2. Navigation -- OK, verifie en direct

`Analytics`, `Fine-tuning`, `Agents autonomes` ajoutes a
`frontend/app/dashboard/layout.tsx` (section "Espace de travail").
Confirme visible et cliquable en production sur une session authentifiee
reelle.

### 3. Formulaire "Agents autonomes" -- OK, verifie en direct

`frontend/components/autonomous/AgentCreateForm.tsx` traduit en francais
("Nom de l'agent", "Description (facultatif)", "Objectif — que doit
accomplir cet agent ?", "Etapes maximum", "Creer l'agent").

### 4. Limitation i18n a francais + anglais -- OK, verifie en direct

`api/config.py` : `UI_SUPPORTED_LANGUAGES` limite a `["fr", "en"]`,
`UI_DEFAULT_LANGUAGE` passe a `"fr"`. L'application (backend) refuse deja
toute autre langue (`api/routers/i18n.py`, 404/400), aucun changement de
code necessaire la, seule la config a change. `locales/{es,de,pt,ar}`
laisses sur disque (contenu reel, pas supprime), juste plus proposes.

**Bug reel trouve en verifiant ce point** : `frontend/lib/i18n.tsx`
exposait deja un `setLanguage()` fonctionnel, mais **aucun composant ne
l'appelait** -- il n'existait aucun vrai selecteur de langue dans
l'interface avant ce correctif. Cree `frontend/components/LanguageSelector.tsx`
(boutons FR/EN), monte dans le layout du dashboard et l'en-tete de la
page de conversation. Teste en direct : clic sur FR change bien l'etat
actif, aucun crash, requete API confirmee.

### Synthese de cette session

| Point demande | Statut |
|---|---|
| 1. Chat sans citations | Cause racine corrigee (code), verification finale bloquee par une limite memoire du tier gratuit Render |
| 2. Navigation (3 pages) | Termine, verifie en direct |
| 3. Formulaire traduit | Termine, verifie en direct |
| 4. i18n limite a FR/EN | Termine, verifie en direct (selecteur de langue cree au passage, n'existait pas avant) |
