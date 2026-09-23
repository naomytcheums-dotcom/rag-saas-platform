# Test Stripe -- bloque, honnetement

## Constat verifie (2026-09-19)

`api/config.py` : `STRIPE_SECRET_KEY: str | None = None` (aucune valeur
par defaut). `api/services/billing_stripe.py` leve explicitement une
erreur si cette cle n'est pas configuree : *"Stripe is not configured
on this deployment -- set STRIPE_SECRET_KEY in .env to enable real
payments."*

Verifie sur Render : aucune variable `STRIPE_SECRET_KEY` ni
`STRIPE_WEBHOOK_SECRET` parmi les variables d'environnement du service
de production (liste complete des cles extraite directement du
formulaire Render dans cette session -- absentes).

## Pourquoi ce n'est pas teste dans cette session

Tester le flux complet (creation de checkout, paiement, reception de
webhook, activation d'abonnement) demande un vrai compte Stripe en
mode test, avec ses propres cles API (`sk_test_...`,
`whsec_...`). Aucun compte Stripe n'existe pour ce projet a ce jour --
en creer un et le configurer est une decision/action qui appartient au
proprietaire du produit, pas quelque chose qu'une session d'audit peut
faire a sa place (creation de compte tiers, engagement).

## Ce qu'il faut faire pour debloquer ce point

1. Creer un compte Stripe (ou utiliser un compte existant), activer le
   **mode test**.
2. Recuperer `sk_test_...` (cle secrete) et configurer un endpoint de
   webhook de test pour recuperer `whsec_...`.
3. Ajouter `STRIPE_SECRET_KEY` et `STRIPE_WEBHOOK_SECRET` (nom exact a
   verifier dans `api/services/billing_stripe.py`) comme variables
   d'environnement Render.
4. Tester en direct : creer un forfait, lancer un checkout avec une
   carte de test Stripe (`4242 4242 4242 4242`), confirmer la reception
   du webhook et l'activation reelle de l'abonnement cote base de
   donnees.
5. Tester au moins un cas d'echec (carte refusee : `4000 0000 0000
   0002`) pour confirmer que l'echec est gere proprement (pas
   d'abonnement active a tort).

## Statut

Non teste, bloque par l'absence de compte/cles Stripe reels -- pas un
defaut de code, une dependance externe hors du perimetre de cette
session.
