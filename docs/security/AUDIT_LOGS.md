# Journal d'audit -- verification en direct

## Teste reellement (2026-09-19)

Connexion au compte de test, navigation vers
`/dashboard/security` -> onglet "Journal d'audit". 5 evenements reels
affiches, correspondant EXACTEMENT aux actions effectuees par ce
compte au cours de la session (pas des donnees de demonstration) :

```
conversation_created   129.0.60.178 - 9/18/2026, 6:49:51 PM - succes
api_key_created        129.0.60.178 - 9/18/2026, 5:36:25 PM - succes
agent_created           129.0.60.178 - 9/18/2026, 5:34:41 PM - succes
document_uploaded      129.0.60.178 - 9/18/2026, 5:17:19 PM - succes
document_uploaded      129.0.60.178 - 9/18/2026, 4:58:22 PM - succes
```

Chaque entree porte une adresse IP, un horodatage precis, et un statut
(succes/echec). Export CSV disponible (bouton "Exporter en CSV",
present, non teste dans cette passe).

## Conclusion

Le journal d'audit HMAC (`AUDIT_LOG_HMAC_SECRET_KEY`) fonctionne
reellement en production, pas seulement en theorie -- confirme par une
verification directe, pas une lecture de code. Chaque action sensible
testee dans cette session (creation de document, d'agent, de cle API,
de conversation) a bien produit une entree consultable.

## Non teste

Integrite HMAC non verifiee cryptographiquement (aurait demande
d'acceder directement a la base de donnees pour comparer la signature
stockee) ; couverture d'AUTRES actions sensibles (changement de mot de
passe, changement d'email, suppression de compte) non verifiee car non
declenchees dans cette session.

## Statut

Verifie fonctionnel en conditions reelles pour les actions testees.
