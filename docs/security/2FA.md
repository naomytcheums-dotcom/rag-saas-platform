# 2FA / WebAuthn -- verification en direct

## Teste reellement (2026-09-19)

Backend TOTP appele directement en production avec un vrai token
d'authentification (compte de test `celery-test-1789746965@example.com`) :

```
POST /auth/2fa/setup
-> 200, {"secret": "NRYKKGJV5QCSH2MOSFFZHOPB2XECE7TU", "qr_code_data_uri": "data:image/png;base64,..."}
```

Un vrai secret TOTP et un vrai QR code (PNG valide, decode-able) sont
retournes. Le backend 2FA fonctionne reellement.

## Gap reel trouve

**Aucune interface frontend n'appelle ces endpoints.** L'onglet
"Securite" de la page Profil (`/dashboard/profile`, verifie en direct
dans un navigateur) affiche le changement de mot de passe et les
sessions actives, mais aucune section pour activer le 2FA ou
enregistrer une cle WebAuthn -- malgre un backend complet et
fonctionnel (`api/routers/two_factor.py` : `/setup`, `/enable`,
`/disable`, `/recovery-codes/*`, `/verify-login`,
`/verify-recovery-code`, `/lockout-recovery/*`, plus
`api/routers/webauthn.py` separement).

## WebAuthn

Non teste directement (necessite un vrai authenticateur materiel ou une
simulation de plateforme -- hors de ce qui est possible depuis un
navigateur automatise sans support WebAuthn virtuel configure dans
cette session).

## Recommandation

Construire l'interface manquante (formulaire d'activation avec
affichage du QR code, saisie du code de verification, affichage des
codes de recuperation) -- le backend n'a besoin d'aucun changement,
tout existe et fonctionne deja. Effort reel estime : UI seule, pas de
travail backend.

## Statut

Backend verifie fonctionnel en direct. Frontend absent -- gap reel
documente, non construit dans cette session (portee UI substantielle,
hors du temps disponible pour cette passe de corrections).
