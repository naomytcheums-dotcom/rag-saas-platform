# 07 — Facturation, crédits, paiements

État de départ : `main` `6619bc5` (PR n°20 fusionnée avec R1–R7, BILL-011/013/014/015/017/020). Détail des transitions : `audit-reports/radiographie-2026-10-10/09_BILLING_PAYMENTS.md`. **Aucun paiement réel, aucune clé de fournisseur, aucune base distante** : tout est testé avec des fournisseurs simulés.

## Revérification des constats historiques
| Constat | Statut aujourd'hui | Preuve |
|---|---|---|
| Achat de crédits Paystack | **PARTIAL / BLOCKED_EXTERNAL** : plus de 500 (501 propre, BILL-013) ; l'achat n'est pas implémenté | `PaystackProvider` hérite de `BillingProvider.create_credit_pack_checkout` (NotImplementedError → 501), test `tests/test_p2_bill013_paystack_credit_pack.py` |
| Remboursements | **VERIFIED non implémentés** (BILL-016) : route admin 501 ; événements `charge.refunded`/litiges ignorés ; état `refunded` inexistant pour les factures | `api/routers/admin_subscriptions.py` |
| Devises | **PARTIAL** : le pack porte maintenant la devise réellement facturée et l'interface l'affiche (`578a524`) ; plans en EUR et packs en USD subsistent | `tests/test_p2_bill018_pack_currency.py` |
| Dépassement de crédits en concurrence | **FIXED** (BILL-011) : verrou de ligne sur ajout/remboursement/allocation/recharge, montants négatifs refusés ; preuve sur PostgreSQL jetable (40 crédits + 40 débits concurrents : solde stable) | `tests/test_postgres_credits_concurrency.py` (dans le nouveau job CI) |
| Variables influençant paiements et abonnements | **documentées et épinglées** : `docs/devops/SENSITIVE_SETTINGS.md`, `tests/test_sensitive_settings.py` | valeurs de production NOT_VERIFIED |
| Preuve de bout en bout avec les fournisseurs | **NOT_RUN / BLOCKED_EXTERNAL** | aucune clé de test fournie |
| Idempotence des achats de crédits | **FIXED** (BILL-014) : une attribution par session de checkout (`credit_pack_session:<id>`), paiements différés gérés, devise vérifiée | `tests/test_p2_bill014_checkout_idempotence.py` |
| Webhooks : signature, rejeu, ordre | signature (SDK Stripe / HMAC Paystack), `claim_payment_event` par id d'événement, gardes d'événements tardifs (Stripe, Paystack), événements mal formés ignorés (BILL-015) | tests `test_p1_bill*`, `test_p2_bill015_*` |

## Séparation comptable demandée vs architecture actuelle
| Objet demandé | Où il vit aujourd'hui | Écart |
|---|---|---|
| Paiements/transactions du fournisseur | `payment_events` (id d'événement fournisseur, type, résumé) ; `payment_customers` | pas de table « paiement » avec montant/devise/statut ; seul l'événement est tracé |
| Factures et abonnements | `invoices`, `invoice_lines` (devise par facture), `subscriptions` | OK ; la facture n'est pas reliée à l'identifiant de paiement fournisseur de façon structurée (référence texte pour les règlements manuels) |
| Registre de crédits | `credit_transactions` (type, montant, `balance_after`, raison) ; `credits.balance` | le solde et le registre coexistent ; **aucune colonne de devise ni de montant payé** sur les achats |
| Événements de webhook | `payment_events` (clé primaire = idempotence) | OK |
| Remboursements | absents | à concevoir (ci-dessous) |
| Écritures comptables et traçabilité | audit log chaîné (`billing_*` actions, `request_id`) | pas de grand livre (double entrée) : hors périmètre sans décision |
Migrer vers « registre comme source de vérité, solde dérivé » (somme du registre) est possible sans casser l'API (le solde resterait servi) mais demande une migration de données et une vérification d'égalité solde = somme ; **non fait** (risque de régression sur des données de production inconnues).

## Politique de remboursement : options (aucune règle commerciale n'a été inventée)
| Option | Comportement | Conséquences techniques | Tests nécessaires |
|---|---|---|---|
| A. Aucun remboursement automatique (statu quo) | la route reste 501 ; remboursement manuel chez le fournisseur ; l'équipe ajuste les crédits via la remise de crédits (V2) avec ligne de registre | rien à développer ; trace manuelle seulement | documenter la procédure manuelle |
| B. Remboursement déclenché par le superadmin | appel API fournisseur (Stripe `Refund`) **puis** webhook `charge.refunded` qui écrit le registre (`refund`) et l'état de la facture/pack | état `refunded` (facture) ; idempotence par id de remboursement ; débit de crédits plafonné au solde ; pas de marquage avant confirmation fournisseur | double demande, partiel/total, échec fournisseur, événement tardif/dupliqué, solde insuffisant |
| C. Politique par type (pack consommé / non consommé, abonnement au prorata) | B + règles de calcul | à spécifier juridiquement | idem + tableaux de cas |
Décision attendue de la propriétaire ; en attendant, comportement **non** modifié. Le paramétrage (`REFUND_POLICY`) n'a pas été ajouté pour ne pas simuler une capacité absente.

## Devises : état et recommandation
Plans EUR (`BILLING_CURRENCY`, catalogue Stripe créé en `eur`), factures EUR (`INVOICE_CURRENCY`), packs `CREDIT_PACK_CURRENCY` (usd), landing page : montants **convertis pour l'affichage** (`DISPLAY_CURRENCY_*`), jamais pour la facturation. Montants en unités mineures entières partout (bon). Manque : devise enregistrée sur les achats de crédits, et une règle (« une devise de facturation » ou « prix par devise »). Éligibilité Paystack/Stripe pour le pays du compte marchand : **NOT_VERIFIED** (dépend du compte).

## Tests de la session
`tests/test_p2_bill018_pack_currency.py` (3) ; suites facturation relancées : 41 passés. Les scénarios paiement réussi/refusé/en attente, webhook répété/invalide/désordonné, double soumission, débit concurrent, achat+remboursement, échec fournisseur et incompatibilité de devise sont couverts par les tests existants **sauf remboursement (non implémenté)** et « échec fournisseur après réservation interne » (couvert pour l'annulation et la synchro Stripe, pas pour l'achat de pack). Suite complète : voir `10-test-results.md`.
