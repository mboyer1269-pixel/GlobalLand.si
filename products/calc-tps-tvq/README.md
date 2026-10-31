# Calculateur TPS/TVQ pour facture Quebec

Status: PROTOTYPE

## Ce que c'est

Petit outil statique en francais pour pigistes, travailleurs autonomes et micro-entreprises du Quebec. Il permet de saisir des lignes de facture en montants hors taxes (HT) ou toutes taxes comprises (TTC), puis de calculer :

- sous-total HT ;
- TPS a 5 % ;
- TVQ a 9,975 % ;
- total TTC ;
- resume copiable ou imprimable.

Le prototype est volontairement simple : HTML, CSS et JavaScript local, sans dependance, sans actif externe et sans stockage.

## Hypothese de monetisation

Hypothese non validee : proposer l'outil gratuitement pour attirer des travailleurs autonomes quebecois, puis vendre un petit pack payant de modeles de facture en francais ou afficher un lien de contribution volontaire. Aucune vente, metrique ou demande client n'est revendiquee a ce stade.

## Deploiement gratuit possible

- **GitHub Pages** : publier le dossier `products/calc-tps-tvq/` comme site statique depuis une branche ou un workflow existant, sans service payant.
- **Cloudflare Pages** : connecter le depot et configurer ce dossier comme sortie statique, avec build vide ou commande no-op.

Verifier les politiques et quotas gratuits avant publication. Aucun compte de paiement ou service payant n'est requis pour ouvrir le fichier localement.

## Tester

```bash
node products/calc-tps-tvq/test.js
```

## Note fiscale

Le seuil de petit fournisseur de 30 000 $ sur quatre trimestres civils consecutifs est presente comme information generale seulement. Les utilisateurs doivent verifier leur situation avec Revenu Quebec ou un professionnel.
