# Authentification à deux facteurs (2FA / TOTP)

## Backend

`api/routers/two_factor.py` (`/auth/2fa/*`) -- complet et fonctionnel :
`/setup`, `/enable`, `/disable`, `/recovery-codes/regenerate`,
`/recovery-codes/status`, `/verify-login`, `/verify-recovery-code`,
`/lockout-recovery/request`, `/lockout-recovery/confirm`.

**Verifie en direct de bout en bout** (compte jetable cree puis
supprime dans cette session, contre la vraie base de donnees) :
inscription -> `/setup` (vrai secret + QR code) -> `/enable` avec un
vrai code TOTP calcule via `pyotp` -> `totp_enabled: true` confirme sur
`/account/me` -> `/recovery-codes/status` (10/10) -> regeneration ->
`/auth/login` renvoie bien `mfa_required` une fois la 2FA active ->
`/auth/2fa/verify-login` avec un vrai code -> `/disable` -> retour a
`totp_enabled: false` -> compte nettoye.

## Frontend

Gap reel trouve par l'audit initial : le backend etait entierement
fonctionnel mais aucune interface n'existait pour l'activer. Corrige :

`frontend/app/dashboard/profile/page.tsx` (`TwoFactorSection`, onglet
Securite du profil utilisateur -- 2FA est un attribut du compte, pas
de l'organisation) :

- Etat desactive : bouton "Activer l'authentification a deux facteurs".
- Etape configuration : appelle `/auth/2fa/setup`, affiche le QR code
  (`<img>` sur le `data:` URI renvoye par le backend) et la cle en
  texte pour saisie manuelle, plus un champ pour le code a 6 chiffres.
- Confirmation : `/auth/2fa/enable`, puis affichage unique des 10 codes
  de recuperation (grille + lien de telechargement `.txt`), avec un
  bouton explicite "J'ai enregistre ces codes" avant de revenir a l'etat
  normal.
- Etat active : badge vert, compteur "X / 10 codes de recuperation
  restants" (`/auth/2fa/recovery-codes/status`), boutons "Regenerer les
  codes de recuperation" et "Desactiver", chacun derriere une
  confirmation par code TOTP actuel (memes endpoints que le backend
  exige deja).

La connexion elle-meme (`/login`, saisie du code apres
`mfa_required`) existait deja avant cette session -- seule la gestion
du compte (activer/desactiver/regenerer) manquait.

**Teste en direct dans un vrai navigateur**, contre un backend local
reellement demarre (pas de mock) : activation complete (QR code affiche,
code TOTP reel calcule et valide, 10 codes de recuperation affiches et
confirmes), puis desactivation complete (code TOTP reel valide, retour
a l'etat desactive). Le compte de test utilise pour ce parcours UI a
ete remis exactement dans son etat d'origine (2FA desactivee) apres le
test.

## Bug decouvert et corrige en cours de route

`api/services/admin_monitoring.py` importe `psutil` directement, mais
ce paquet etait absent de `requirements-api.txt` -- decouvert en
demarrant l'API localement pour ce test (`ModuleNotFoundError` a
l'import de `api.main`, qui casserait le demarrage complet de l'API,
pas seulement les routes admin, sur tout environnement ou ce paquet
n'est pas deja present par effet de bord d'une autre dependance).
Ajoute a `requirements-api.txt`.

## WebAuthn

Non teste dans cette session (backend et frontend) -- necessite un
authenticateur materiel ou une emulation de plateforme que
l'environnement de test actuel ne fournit pas.
