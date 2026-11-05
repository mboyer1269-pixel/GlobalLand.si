# Ville : projection réelle vérifiée localement

Branche fondée sur le contrôle installé `8e12f2bc81eb446d3b18cb61eb8ece7a29803383`. La carte approuvée est importée par fichiers sélectionnés ; aucun ancien historique de prototype n'est repris.

## Défaut et réparation

Sur la révision publique `ded1c4d983bd02702e65d6ab0a6c64be407f6584`, l'ancien lecteur exigeait un fichier d'une mission fixée dans le code et refusait tout l'instantané. Sa source abrégée contenait 24 missions, contre 40 dans les pages. Il omettait notamment le résultat du courtier `TASK-179390958120`.

Le nouveau lecteur restitue à cette même révision les 40 missions et 100 résultats de sa fenêtre, dont cette tâche et la mission récente de catalogue Shopify. Un second instantané, `d6edfeb2cd2b92a13659ccbb92d35c29c6da7f93`, affiche 41 missions et 100 résultats dans le navigateur.

## Vérifications

Les tests Python utilisent de vrais dépôts Git temporaires : pagination complète, monde vide, courtier et file, empreinte incorrecte, attribution absente, fichier remplacé après livraison, refus, demande en attente, pages incohérentes ou sans version, demandes/résultats mal formés et dossier présenté comme fichier. Les tests HTTP vérifient le contrat JSON, les refus Host/chemin, l'erreur initiale et la conservation du dernier instantané.

Les échecs ont été observés avant les corrections : `StopIteration` sur un monde valide, attribution d'une demande mal formée, pages sans version acceptées, statut invalide interrompant toute lecture, dossier présenté comme fichier. Les cas correspondants passent après correction.

Le contrôle Playwright local a passé 15 assertions sur le second instantané : mission récente et tâche du courtier présentes ; parcours agent → mission → fichier avec SHA dans le lien ; navigation clavier ; filtre et focus conservés au rafraîchissement ; instantané mal formé et HTTP 503 conservant la vue ; monde vide sans activité inventée ; texte de mission traité comme texte ; largeur mobile 390 × 844 sans débordement horizontal ; nouvelle destination positionnée à son titre ; aucune erreur JavaScript. Les captures ordinateur et mobile ont été examinées. L'erreur réseau 503 volontaire apparaît dans la console, conformément au test.

Suite Linux complète : **711 tests Python, 11 ignorés**, suites Node du runtime et de l’exécuteur réussies, syntaxe JavaScript et scripts shell valides. Les tests ignorés nécessitent notamment Docker et des droits système ; ils restent couverts séparément par les contrôles GitHub.

## Limites

La fenêtre de résultats est bornée et annoncée. Les liens externes pointent vers GitHub ; ce contrôle n'effectue aucun achat ou publication. Le navigateur a testé une largeur mobile, pas un téléphone connecté au réseau. Le serveur reste local : l'hébergement authentifié, l'observation d'une mise à jour au rythme normal depuis cet hébergement et le rendu du graphe Graphify sont des vérifications distinctes, non établies ici.

Cette correction améliore l'observation de l'activité. Elle ne constitue ni une nouvelle capacité commerciale des agents, ni une preuve de client, de vente ou d'encaissement.
