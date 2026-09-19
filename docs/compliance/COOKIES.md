# Cookies -- consentement

## Constat reel (audit, 2026-09-19)

Aucun script de tracking/publicite n'existe dans le frontend (`grep`
exhaustif : zero occurrence de `gtag`, `google-analytics`,
`GA_MEASUREMENT`, `fbq(`). Seuls 2 cookies sont reellement poses par
l'application :

1. `UI_LANGUAGE_COOKIE_NAME` (`lang`) -- preference de langue,
   `api/routers/i18n.py`, `POST /i18n/language`.
2. Le cookie de refresh-token (httpOnly), `api/routers/auth.py` --
   necessaire au maintien de la session de connexion.

Les deux sont des cookies **strictement necessaires/fonctionnels**.
Sous RGPD/ePrivacy, ce type de cookie ne requiert pas legalement de
banniere de consentement (contrairement aux cookies publicitaires ou
de mesure d'audience non essentielle).

## Ce qui a ete fait quand meme

`frontend/components/CookieBanner.tsx` cree et monte dans
`app/layout.tsx` -- par transparence envers le visiteur, pas parce que
c'etait une obligation legale manquante. Stocke l'accusé de reception
dans `localStorage` (pas un cookie lui-meme), un seul bouton "Compris".

## Verification

`npx tsc --noEmit` et `eslint` passent sur le composant (un vrai bug
trouve et corrige au passage : `setState` appele de facon synchrone
dans un `useEffect`, remplace par une initialisation paresseuse de
`useState`). Non teste dans un vrai navigateur en production dans
cette session (voir la limite de temps documentee dans
`docs/audit/AUDIT_CORRECTIONS.md`).

## Statut

Fait, au-dela de ce qui est legalement requis vu l'absence de cookies
non essentiels.
