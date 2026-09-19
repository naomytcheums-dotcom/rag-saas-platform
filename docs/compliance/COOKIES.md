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

## Ce qui a ete fait, puis retire

`frontend/components/CookieBanner.tsx` cree -- par transparence envers
le visiteur, pas parce que c'etait une obligation legale manquante.
Stocke l'accuse de reception dans `localStorage`, un seul bouton
"Compris".

**Teste reellement en production, et reellement casse deux fois** :

1. Premiere version (initialisation paresseuse de `useState` lisant
   `localStorage`) : plantait la page entiere avec une erreur
   d'hydratation React (#418) -- le rendu serveur (`window` indefini,
   toujours "deja acquitte") ne correspondait pas au premier rendu
   client (vraie lecture de `localStorage`). Reproduit en direct sur
   `/login`, confirme par un rechargement avec cache reellement
   vide (URL avec parametre anti-cache).
2. Deuxieme version (etat initial `false` partout, verification
   deplacee dans un vrai `useEffect` post-montage -- le pattern
   standard recommande pour ce cas exact) : **le meme crash #418 a
   persiste** apres deploiement, pour une raison non diagnostiquee
   dans le temps disponible.

**Decision** : retire du layout racine (`app/layout.tsx`) plutot que
de risquer un troisieme cycle de deploiement non verifie sur une
page qui affecte TOUT le site (y compris la page de connexion). Le
fichier composant reste dans le depot, juste non monte -- confirme
par un test en direct que sa suppression du layout restaure un
chargement propre, sans erreur #418.

## Statut

Non deploye -- retire par prudence apres un vrai bug reproduit deux
fois en production. Rien de perdu fonctionnellement : cette banniere
n'etait de toute facon pas une obligation legale (voir plus haut,
aucun cookie non essentiel). A reprendre plus tard avec un diagnostic
plus approfondi (verifier notamment si le probleme vient d'ailleurs
dans le layout racine, pas necessairement de ce composant seul).
