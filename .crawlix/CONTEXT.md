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

## Parcours utilisateurs à tester

1. Inscription / Connexion (`/auth/register`, `/auth/login` côté API ;
   pages `/register`, `/login` côté frontend)
2. Upload de documents (`/dashboard/documents`)
3. Création d'un agent (`/dashboard/agents`)
4. Conversation avec un agent (`/dashboard/chat` ou équivalent)
5. Configuration du widget embarqué (`/dashboard/widget`)
6. Gestion des clés API (paramètres développeur de l'organisation)
7. Facturation (`/dashboard/billing`)
8. Administration (`/dashboard/admin`)
9. Marketplace de plugins (`/dashboard/marketplace`)
10. Analytics (`/dashboard/analytics`)
11. Fine-tuning (`/dashboard/fine-tuning`)
12. Agents autonomes (`/dashboard/autonomous-agents`)

## Notes pour les personas

- L'application nécessite une inscription réelle (email + mot de passe)
  pour accéder au tableau de bord — chaque persona doit créer son
  propre compte de test avec un email unique.
- Le thème est clair uniquement (pas de mode sombre).
- Certaines fonctionnalités avancées (fine-tuning, agents autonomes,
  facturation réelle) peuvent dépendre de clés API tierces non
  configurées dans cet environnement de test — un échec gracieux
  (message d'erreur clair) est attendu plutôt qu'un plantage.
