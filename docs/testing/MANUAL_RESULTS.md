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

## Synthese

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
