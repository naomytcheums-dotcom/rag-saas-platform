# Accessibilite

## Corrections reelles faites dans cette session (2026-09-19)

### Labels non associes a leur champ (WCAG 1.3.1 / 4.1.2)

Recherche systematique de tous les `<label>` du dashboard et des
composants (`grep -rn "<label"` sur `app/dashboard` et `components`,
37 occurrences dans 15 fichiers) :

- Quand un `<label>` enveloppe directement son `<input>`/`<textarea>`
  (ex. checkboxes), l'association est deja implicite -- rien a
  changer, verifie au cas par cas.
- Les autres (`<label>` suivi d'un champ separe, sans `htmlFor`/`id`)
  ont tous ete corriges avec une paire `htmlFor`/`id` reelle : profil
  utilisateur (nom, entreprise, langue), politiques de securite
  (expiration de session, tentatives max, liste blanche IP), widget de
  chat (nom, message d'accueil, couleurs), `ColorPicker`,
  `CustomCSSEditor`, `CustomJSEditor`, `ABTestVariantSelector` (id
  derive du libelle pour rester unique avec plusieurs instances sur la
  meme page).
- Deux `<label>` qui n'etiquetaient aucun champ unique (juste du texte
  statique, ou un groupe de boutons non-formulaire -- "Position",
  "Thème" du widget) ont ete changes en `<p>`/`role="group"
  aria-labelledby` -- un `<label>` sans `for` et sans wrapping n'est
  pas un usage HTML valide.

### Champs avec seulement un `placeholder`, sans label

Un `placeholder` seul n'est pas un substitut fiable a un nom
accessible (il disparait des la saisie et certains lecteurs d'ecran ne
le lisent pas comme libelle). Trouve et corrige avec un `aria-label`
reel : mots de passe du profil, formulaire de creation d'agent
autonome, formulaire de publication de plugin (nom, description,
categorie, version, point d'entree, tarification, prix), champs de
code 2FA (configuration/desactivation/regeneration).

### Focus clavier invisible (WCAG 2.4.7)

`outline-none` est utilise 58 fois dans le projet -- verifie
individuellement que 56/58 sont accompagnes d'un remplacement visible
(`focus:border-accent`, un changement de couleur de bordure reel au
focus). Les 2 restants n'avaient AUCUN indicateur de focus visible :
`RenameConversation.tsx` (bordure deja `accent` en permanence, donc le
focus etait litteralement invisible) et le textarea d'edition de
message dans `MessageBubble.tsx`. Les deux ont recu un vrai
`focus:ring-2` visible.

**Verifie en direct au clavier** dans un vrai navigateur (`/login`) :
`Tab` deplace bien le focus dans l'ordre logique (email -> mot de
passe -> ...), avec un indicateur visuel clair a chaque etape,
confirme a la fois visuellement (capture d'ecran) et via
`document.activeElement`.

## Ce qui etait deja correct (verifie, pas suppose)

- Le flux chat (`CopyButton.tsx`, `FeedbackButtons.tsx`,
  `VoiceOutput.tsx`, `ChatSidebar.tsx`, `PushToTalkButton.tsx`,
  `VoiceInput.tsx`) a deja un `aria-label` reel sur chaque bouton
  icone-seule.
- Aucune image (`<img>`/`<Image>`) sans `alt` dans le dashboard ou les
  composants -- verifie par recherche exhaustive.
- Aucun bouton icone-seule utilisant une police d'icones ou un SVG
  brut sans libelle n'a ete trouve en dehors du flux vocal (deja
  couvert).

## Ce qui n'a toujours PAS ete audite exhaustivement

- Contraste des couleurs (WCAG 2.1 AA, ratio 4.5:1 minimum) --
  necessite un outil dedie (axe-core, Lighthouse) pour verifier chaque
  combinaison de couleurs de theme.
- Test reel avec un lecteur d'ecran (NVDA/VoiceOver/JAWS) -- seule la
  structure DOM/ARIA a ete verifiee, pas le rendu vocal reel.
- Pieges de focus dans les modales/dialogues (le focus reste-t-il bien
  a l'interieur d'un dialogue ouvert ? revient-il au bon endroit a la
  fermeture ?).

## Recommandation

Avant toute vente a un client avec des obligations d'accessibilite
(secteur public, grands comptes), commander un audit WCAG 2.1 AA
dedie avec un outil automatise en premiere passe puis une verification
manuelle au clavier et au lecteur d'ecran -- les categories corrigees
ici (labels, placeholders seuls, focus invisible) etaient les
manquements les plus mecaniques et les plus faciles a rater sans outil
dedie ; le contraste et le comportement des lecteurs d'ecran demandent
un outillage que cette session n'a pas.

## Statut

Deux categories de bugs reels (association label/champ, focus clavier
invisible) trouvees par une recherche systematique du code source et
corrigees integralement partout ou elles apparaissaient dans
`app/dashboard` et `components`. Contraste et lecteur d'ecran restent
a auditer avec un outillage dedie.
