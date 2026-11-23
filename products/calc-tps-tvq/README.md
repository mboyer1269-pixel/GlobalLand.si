# Calculateur TPS/TVQ et facture (Québec)

Statut : PROTOTYPE

> **Outil informatif, pas un avis fiscal.** Ce calculateur ne remplace ni Revenu Québec, ni l’Agence du revenu du Canada, ni un professionnel. Les règles résumées ici sont simplifiées ; chaque utilisateur doit vérifier sa propre situation.

## Ce que fait l’outil

Page statique en français pour pigistes, travailleurs autonomes et petites entreprises qui facturent au Québec. HTML, CSS et JavaScript locaux : aucune dépendance, aucun actif externe, aucun stockage, aucun suivi, aucun appel réseau.

- Lignes de facture (description, quantité, prix unitaire), rabais par prix unitaire négatif, note de crédit quand le total est négatif.
- Prix saisis avant taxes ou taxes incluses.
- TPS 5 % et TVQ 9,975 % calculée sur le prix avant TPS, sous-total et total.
- Case « Facturer la TPS et la TVQ » à décocher pour un fournisseur non inscrit, qui ne doit pas facturer ces taxes.
- Coordonnées facultatives : vendeur, numéros de TPS et de TVQ, client, numéro et date de facture, notes.
- Aperçu de la facture à imprimer ou à enregistrer en PDF (l’impression ne contient que la facture), à télécharger en fichier HTML autonome, ou à copier en texte.

| Fichier | Rôle |
| --- | --- |
| `calc.js` | Calculs en cents entiers et lecture des montants fr-CA/en-CA |
| `invoice.js` | Facture en arbre d’éléments, rendue en texte, en HTML échappé (téléchargement) ou en nœuds DOM (aperçu) |
| `app.js` | Comportement de la page |
| `index.html` | Page et styles |
| `test.js` | Tests `node:test`, sans dépendance |

## Méthode de calcul

- Tous les montants sont des cents entiers (`BigInt`) : aucune erreur de virgule flottante, y compris avec une quantité décimale (0,29 × 0,50 $ = 0,145 $, arrondi à 0,15 $).
- Arrondi au cent le plus proche, la demi-cent s’éloignant de zéro : une note de crédit est l’exact opposé de la facture correspondante.
- Les taxes sont calculées une seule fois sur le sous-total de la facture. Additionner des taxes arrondies ligne par ligne peut facturer un cent de trop : trois lignes de 0,10 $ donnaient 0,03 $ de TPS au lieu de 0,02 $.
- Prix taxes incluses : la TPS et la TVQ sont extraites du total par la méthode de la fraction de taxe (5/114,975 et 9,975/114,975) et le sous-total est la différence ; les parties s’additionnent toujours au total. Quand un prix avant taxes donne exactement ce total, la méthode le retrouve (vérifié exhaustivement dans `test.js`). Environ 13 % des totaux au cent près ne correspondent à aucun prix avant taxes : la TPS ou la TVQ peut alors différer de 0,01 $ du taux appliqué au sous-total, et la page le signale.
- Saisie acceptée : virgule ou point décimal, espaces (y compris insécables) entre les milliers, symbole `$` ou `CAD`, signe moins. Une écriture ambiguë comme `1,500` est refusée plutôt que devinée. Deux décimales au maximum ; montants limités à 999 999 999,99 $.

## Petit fournisseur : résumé affiché dans la page

- En règle générale, on est un petit fournisseur si ses fournitures taxables (y compris détaxées) effectuées dans le monde, additionnées à celles de ses associés, ne dépassent 30 000 $ ni au cours d’un seul trimestre civil, ni au total des quatre derniers trimestres civils consécutifs.
- Un petit fournisseur n’est pas obligé de s’inscrire aux fichiers de la TPS et de la TVQ, mais peut le faire volontairement. Tant qu’il n’est pas inscrit, il ne doit pas facturer ces taxes.
- Le moment où l’inscription devient obligatoire dépend de la façon dont le seuil est dépassé (en un seul trimestre ou sur quatre trimestres).
- Des règles particulières s’appliquent, notamment aux organismes de services publics (seuil de 50 000 $) et aux services de taxi ou de transport rémunéré de personnes, qui doivent s’inscrire quel que soit leur chiffre d’affaires.
- Au Québec, Revenu Québec administre généralement la TPS et la TVQ.
- L’outil vise les fournitures effectuées au Québec. Ailleurs au Canada, d’autres taxes comme la TVH peuvent s’appliquer, et certaines fournitures sont exonérées ou détaxées.

La première version ne citait que le critère des quatre trimestres. Ce résumé et le lien vers Revenu Québec ont été rédigés sans accès réseau : ils doivent être confirmés sur les sources officielles avant toute publication.

## Hypothèse de monétisation (non validée)

Aucune vente, aucun visiteur, aucune métrique et aucun revenu ne sont revendiqués. L’hypothèse : un calculateur gratuit, exact au cent et qui produit une facture propre peut attirer des travailleurs autonomes québécois ; une offre payante (modèles de facture, contribution volontaire) pourrait ensuite être testée.

Freins connus :

- Marché saturé : de nombreux calculateurs TPS/TVQ et générateurs de factures gratuits existent déjà, y compris dans les logiciels comptables. L’avantage de cet outil n’est pas démontré.
- Rien n’est mesurable aujourd’hui : la page n’est pas publiée et ne contient aucun suivi d’audience. Mesurer l’usage exigerait de la publier puis d’ajouter une mesure, en mettant à jour l’avis de confidentialité.
- Encaisser des ventes exige un compte chez un prestataire de paiement, avec une identité réelle. Les ventes peuvent aussi créer des obligations de TPS/TVQ pour le vendeur au-delà du seuil de petit fournisseur.
- La trésorerie de GlobalLand est non financée (`UNFUNDED` dans `bank/status.json`) : ce prototype ne prévoit ni n’engage aucune dépense.

## Publication

- **Local** : ouvrir `index.html` dans un navigateur suffit, sans serveur ni réseau.
- **GitHub Pages** : gratuit pour un dépôt public ; ce dépôt était privé lors de cette révision, et Pages sur un dépôt privé exige un forfait GitHub payant. Publié depuis une branche, Pages ne sert que la racine du dépôt ou `docs/` : servir seulement ce dossier demanderait un workflow Pages, donc une action d’administrateur qui n’a pas été faite.
- **Cloudflare Pages** ou tout hébergeur statique : la page n’utilise que des chemins relatifs et aucune étape de construction. Un compte est nécessaire ; vérifier les conditions et quotas gratuits en vigueur.

## Tester

```bash
node products/calc-tps-tvq/test.js
```

Les tests couvrent la lecture des montants, les arrondis, les taxes calculées sur le sous-total, l’aller-retour exhaustif des prix taxes incluses, l’échappement de la facture, les dates dans plusieurs fuseaux horaires et des vérifications statiques de la page (pas d’`innerHTML`, pas d’appel réseau, champs étiquetés, avertissement présent). Le flux de CI du dépôt n’exécute pas encore ce fichier.

## Limites connues

- Aucune sauvegarde : tout disparaît à la fermeture de la page (choix de confidentialité).
- Sur iPhone, le pavé décimal n’a pas de touche moins : saisir un rabais (prix négatif) y est malcommode. Un bouton « Ajouter un rabais » réglerait ce point.
- Deux décimales au maximum pour les quantités et les prix.
- La facture téléchargée interdit tout script (politique CSP) ; la page elle-même n’a pas encore de politique CSP, à ajouter lors de la publication.
- Une seule devise (CAD) et un seul territoire (Québec), sans TVH ; le format des numéros de TPS et de TVQ n’est pas vérifié.
