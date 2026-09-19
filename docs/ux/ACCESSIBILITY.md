# Accessibilite

## Ce qui a ete verifie reellement (2026-09-19)

L'audit initial notait "aria-label present dans ~6% des 203 fichiers
.tsx" comme un indicateur brut. Verification plus fine faite ici :
cette mesure comptait des FICHIERS, pas des boutons -- un bouton avec
un vrai libelle texte visible (ex. "Copier", "Supprimer") n'a PAS
besoin d'un `aria-label` pour etre accessible, seul un bouton
icone-seule en a besoin. Une fois cette distinction faite :

- Le coeur de l'experience chat (le flux le plus utilise du produit)
  a une vraie couverture correcte deja en place : `CopyButton.tsx`,
  `FeedbackButtons.tsx`, `VoiceOutput.tsx` (Play/Pause/Resume/Stop),
  `ChatSidebar.tsx` (bouton fermer), `chat/page.tsx` (bouton menu)
  ont tous deja un `aria-label` reel sur leurs boutons icone-seule.
- Les 3 nouveaux composants crees dans cette session
  (`LanguageSelector.tsx`, `LoadingState.tsx`, `CookieBanner.tsx`)
  utilisent des boutons a texte visible (pas d'icone seule) --
  accessibles par construction, `aria-pressed` ajoute sur
  `LanguageSelector` pour indiquer l'etat actif au lecteur d'ecran.

## Ce qui n'a PAS ete audite exhaustivement

Les ~30 pages du dashboard (Analytics, Fine-tuning, Marketplace,
Facturation, Administration, parametres, etc.) n'ont pas ete revues
fichier par fichier dans cette session -- un audit de ce perimetre
demanderait un passage systematique bouton par bouton, hors du temps
disponible ici. Egalement non verifies dans cette session :
- Contraste des couleurs (WCAG 2.1 AA, ratio 4.5:1 minimum)
- Navigation clavier complete (ordre de tabulation, pieges de focus)
- Test reel avec un lecteur d'ecran (NVDA/VoiceOver/JAWS)

## Recommandation

Avant toute vente a un client avec des obligations d'accessibilite
(secteur public, grands comptes), commander un audit WCAG 2.1 AA
dedie, avec un outil automatise (axe-core, Lighthouse) en premiere
passe puis une verification manuelle au clavier et au lecteur d'ecran.

## Statut

Partiellement verifie : le flux principal (chat) est en bon etat ;
le reste du dashboard reste a auditer serieusement avant toute
certification d'accessibilite.
