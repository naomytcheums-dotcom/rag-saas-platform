# Phase 0 — Priorités de risque

1. P0 : sauvegarde/restauration hébergée non prouvée (REM-017) ; isolation tenant dépendant du code seul (RLS inerte tant que le rôle contourne) ; aperçu local qui héritait du `.env` réel (corrigé).
2. P1 : worker/beat non vérifiés ; remboursements et Paystack crédits absents ; IDOR par identifiant non audité (REM-021).
3. P2 : dérive ORM ↔ schéma (155 écarts), dépendances en retard, 125 constats non vérifiés.
Détail : `../01-findings-register.csv`.
