# Cookies -- consentement

## Constat reel

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
de mesure d'audience non essentielle). La banniere existe par
transparence envers le visiteur, pas parce que c'etait une obligation
legale manquante.

## Composant

`frontend/components/CookieBanner.tsx` -- etat initial `false`
partout (identique cote serveur et cote client), verification de
`localStorage` deplacee dans un `useEffect` post-montage. Stocke
l'accuse de reception dans `localStorage`, un seul bouton "Compris".
Monte dans `frontend/app/layout.tsx`.

## Historique du bug d'hydratation (resolu)

Deux versions precedentes ont reellement crashe en production avec
une erreur d'hydratation React #418 (le rendu serveur ne correspondait
pas au premier rendu client). Le composant avait ete retire du layout
par prudence le temps du diagnostic.

Un nouveau test, avec la meme version de code que celle qui avait
crashe, n'a reproduit aucune erreur ni en developpement local, ni sur
un vrai serveur de production local (`next build` + `next start`),
ce qui indiquait que la cause n'etait probablement pas le composant
lui-meme mais un etat de test contamine (deploiements Vercel
successifs trop rapproches, et/ou un onglet de navigateur garde en
emulation mobile 375px d'un test de responsive precedent).

**Verifie en direct sur la production reelle** (`https://rag-saas-platform.vercel.app/login`,
commit `00d8786`), sur plusieurs rechargements avec parametre
anti-cache et apres interaction (clic sur "Compris" puis rechargement) :
aucune erreur #418, `localStorage` persiste correctement l'accuse de
reception entre les rechargements.

## Statut

Deploye et fonctionnel en production. Bug clos.
