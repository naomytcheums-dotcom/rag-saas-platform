# GDPR -- tests en direct

## Export de donnees -- teste reellement, fonctionne (2026-09-19)

```
GET /account/export
-> 200, JSON complet : profil, consentement (horodatage + version des
   conditions), comptes OAuth lies, historique des sessions (IP,
   user-agent, horodatage de creation/derniere activite, statut
   revoque/actif)
```

Reponse reelle recue pour le compte de test, avec des donnees
coherentes avec les actions effectuees dans cette session (sessions
multiples correspondant aux connexions successives). L'export
fonctionne reellement, pas seulement en theorie.

`GET /account/export-csv` existe egalement (variante CSV du meme
export), non testee separement -- meme endpoint sous-jacent probable.

## Suppression de compte -- non testee, deliberement

`DELETE /account/me` existe et est documentee comme ayant un delai de
grace avant purge reelle (`ACCOUNT_DELETION_REMINDER_DAYS_BEFORE`,
tache planifiee `account_purge.py`). **Non declenchee dans cette
session** : la suppression de donnees, meme reversible pendant un
delai de grace, est une action explicitement mise a l'ecart des
actions que cette session effectue de son propre chef sans demande
specifique et explicite pour CETTE action precise -- une regle de
securite generale, pas une limite de ce projet. Peut etre testee
manuellement par le proprietaire du compte de test.

## Consentement -- non teste isolement

`POST /account/consent/withdraw` et
`POST /account/consent/reactivate/request` existent
(`api/routers/account.py`) mais n'ont pas ete exerces separement dans
cette session -- le consentement initial (`consent_given_at`) est deja
confirme present et correct dans l'export ci-dessus.

## Statut

Export verifie fonctionnel en conditions reelles. Suppression et
retrait de consentement non testes (le premier par prudence
deliberee sur une action destructive, le second par manque de temps
dans cette passe).
