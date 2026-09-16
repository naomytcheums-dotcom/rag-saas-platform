# RAG SaaS Platform — Contexte pour les tests par personas IA

## URL de l'application

- Frontend (à tester) : http://localhost:3011
- API backend : http://localhost:8000 (docs interactives : http://localhost:8000/docs)

## Description

RAG SaaS Platform est une plateforme multi-tenant pour construire des
produits RAG (retrieval-augmented generation) : ingestion de documents,
recherche hybride, chat avec citations, agents, agents autonomes,
workflows, fine-tuning, analytics, facturation, marque blanche, et une
surface complète d'administration/sécurité.

Stack : FastAPI (backend), Next.js/React/TypeScript (frontend),
PostgreSQL, Redis, Celery.

## Parcours utilisateurs à tester (chemins réels vérifiés dans le code frontend)

1. Inscription / Connexion (`/auth/register`, `/auth/login` côté API ;
   pages `/register`, `/login` côté frontend)
2. Upload de documents (`/dashboard/documents`)
3. Création d'un agent (`/dashboard/agents`)
4. Conversation avec un agent (`/chat`)
5. Configuration du widget embarqué (`/dashboard/settings/widget`)
6. Gestion des clés API (`/dashboard/settings/api-keys`)
7. Facturation (`/dashboard/billing`)
8. Administration (`/admin`)
9. Marketplace de plugins (`/dashboard/marketplace`)
10. Analytics (`/dashboard/analytics`)
11. Fine-tuning (`/dashboard/fine-tuning`)
12. Agents autonomes (`/dashboard/autonomous-agents`)
13. Médiathèque (`/dashboard/media`)

## Notes pour les personas

- Un compte de test persistant existe pour ces campagnes ciblées par
  parcours (évite de payer le coût token d'une inscription complète à
  chaque test) : `crawlix.persona@example.com` / `CrawlixTest9!Secure`.
  Chaque objectif de test commence par "connecte-toi avec ce compte,
  puis...".
- Le thème est clair uniquement (pas de mode sombre).
- Certaines fonctionnalités avancées (fine-tuning, agents autonomes,
  facturation réelle) peuvent dépendre de clés API tierces non
  configurées dans cet environnement de test — un échec gracieux
  (message d'erreur clair) est attendu plutôt qu'un plantage.
