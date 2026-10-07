# Guide white-label

Ce guide décrit le support white-label réellement présent dans l'application. Il est limité au code et aux routes existants, sans supposer une mise en œuvre côté plateforme non vérifiée.

## 1. Composants visibles dans le code

Les endpoints de white-label sont dans `api/routers/white_label.py`.

Les fonctions exposées incluent :
- lecture et mise à jour de la configuration globale
- activation/désactivation du branding
- configuration d'un domaine personnalisé
- vérification DNS du domaine
- configuration e-mail de l'organisation
- upload de logo et de favicon

Les anciennes routes plus courtes `GET/PATCH /organizations/{org_id}/white-label` coexistent avec la surface plus complète `.../whitelabel/...`.

## 2. Rôle et permissions

Les routes de configuration white-label utilisent des dépendances de permission réelles. Les routes de lecture / écriture correspondent à la logique de sécurité des organisations et aux permissions du plan.

Dans le code, les routes de configuration avancée sont autorisées à des niveaux d'accès plus larges que les routes plus anciennes et plus restrictives liées à `Owner` uniquement.

## 3. Configuration d'un domaine personnalisé

Le modèle exposé dans le code porte sur :
- domaine personnalisé
- validation DNS
- mode d'installation du certificat / domaine

Les valeurs de configuration de domaine sont gérées dans les utilitaires de white-label et `api/config.py` contient des paramètres de cible de domaine et de timeout DNS.

## 4. Branding

Le branding est modelé comme un jeu de paramètres d'organisation (nom, logo, favicon, masque du branding de la plateforme, etc.).

Le code déclare explicitement que la configuration est destinée à être utilisée par les expériences embarquées et les écrans d'authentification / marketing, mais les intégrations visuelles exactes restent à valider côté front-end.

## 5. Email de marque

Le code permet de configurer :
- nom de l'expéditeur
- adresse e-mail de l'expéditeur

Cela reste un mécanisme de configuration de l'application et ne garantit pas la délivrabilité réelle sans validation de l'infrastructure mail associée.

## 6. Limites de vérification

Les éléments suivants sont signalés comme non vérifiés en conditions réelles :
- propagation DNS et certificate validation en production
- stockage final du logo/favicon sur un backend objet réel
- délivrabilité email réelle à partir d'un domaine personnalisé
- rendu front-end final de la page de marque et du widget
