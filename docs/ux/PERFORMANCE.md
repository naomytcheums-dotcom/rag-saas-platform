# Taille du bundle frontend

## Methode

`npm run build` (production, Turbopack), puis inspection directe de
`.next/static/chunks/*.js` (`du -h`, triees par taille) et
identification des plus gros fichiers par leurs signatures de code
(noms de bibliotheque, motifs de chaines reconnaissables -- ce build
ne conserve pas les chemins `node_modules/...` en clair).

## Constats reels et corrections

1. **`components/Flag.tsx` importait les 265 drapeaux de
   `country-flag-icons`** (`import * as Flags from
   "country-flag-icons/react/3x2"`) alors que l'application n'en
   affiche jamais que 12 (`lib/voiceConfig.ts`'s `VOICE_LANGUAGES`).
   Corrige en imports nommes (`{ CN, DE, ES, FR, IT, JP, NL, PL, PT,
   RU, SA, US }`) -- le plus gros chunk apres `recharts` et
   `react-dom` (~256 Ko) a disparu du top 10 apres correction.
   Verifie visuellement : `/voice-demo` affiche toujours les bons
   drapeaux (build de production reel, pas dev).

2. **`components/analytics/AnalyticsDashboard.tsx` importait
   statiquement `TechnicalMetrics` et `DashboardBuilder`**, deux
   onglets qui ne s'affichent que sur clic explicite, alors que
   `BusinessMetrics`/`ProductMetrics` (l'onglet "Vue d'ensemble" par
   defaut) tirent deja `recharts` (~390 Ko, le plus gros chunk du
   projet) via `MetricChart`. Resultat reel avant correction : visiter
   `/dashboard/analytics` sans jamais cliquer sur "Technique" ou
   "Tableaux de bord" chargeait quand meme leur code. Corrige avec
   `next/dynamic` (`loading: () => <LoadingState fullScreen={false}
   />`) -- ces deux composants ne se chargent plus qu'au clic reel sur
   leur onglet.

3. **`recharts` (analytics, A/B tests) et le reste des pages
   dashboard** : deja correctement isoles par le decoupage
   automatique par route du App Router -- chaque `page.tsx` est son
   propre point d'entree, et aucune bibliotheque lourde n'est importee
   depuis un layout partage (`app/dashboard/layout.tsx`,
   `app/layout.tsx`). Verifie explicitement : `grep` de tous les
   consommateurs de `recharts` et `country-flag-icons` confirme
   qu'aucun n'est importe depuis un fichier partage entre plusieurs
   routes.

## Verification

`npx tsc --noEmit`, `npx eslint .` (0/0), `npm run build` (38 routes,
reussi), `npx vitest run` (77/77). Pas d'outil `@next/bundle-analyzer`
installe dans ce projet -- l'inspection ci-dessus s'est faite
directement sur les fichiers compiles, une methode plus lente mais qui
n'ajoute pas de dependance de build supplementaire pour un usage
ponctuel.

## Non fait

Pas de budget de taille de bundle automatise en CI (ex. via
`next/bundle-analyzer` + un seuil qui echoue le build) -- deciderait
d'un seuil arbitraire sans historique de mesures pour le justifier.
