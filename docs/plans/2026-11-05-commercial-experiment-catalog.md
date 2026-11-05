# Raccordement des observations aux experiences

Le lecteur commercial utilise encore l'apercu des missions et les repertoires
de produits dans work/, alors que le superviseur publie des pages et conserve
les produits dans le catalogue Git. Le mandat reste VISION.md et
docs/MANDAT-DEVELOPPEMENT.md : permettre aux agents d'apprendre, sans imposer
une activite ni transformer une interpretation en preuve de vente.

## Task 1: restaurer la decouverte coherente

- Reproduire par tests une mission hors apercu et un site uniquement dans Git.
- Lire les pages missions du meme snapshot, avec validation des enveloppes,
  limites explicites et refus des versions melangees.
- Lister les noms de sites depuis PublicSource, sans charger leurs contenus,
  en respectant la revision publiee et sans repli sur work/ si Git est invalide.
- Conserver les fixtures historiques hors installation et le plafond de 100
  associations dans le contexte; signaler toute lecture incomplete.
- Verifier le chemin observation privee -> projection du directeur.

Expected: les deux associations sont proposees et conservees comme
MODEL_INFERRED; aucune recette ni identite client verifiee n'est inventee.
Tests: tests/test_commercial_catalog.py, test_commercial.py puis suite complete.

## Review Focus

Verifier le changement de revision entre pages, les chemins et fichiers
malformes, les catalogues absents/corrompus, les limites explicites, la
separation avec les preuves financieres et l'absence d'effets externes.
Une revue finale independante precede la preparation de la PR.
Installation et fusion restent une decision distincte.
