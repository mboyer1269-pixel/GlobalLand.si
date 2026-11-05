# Installation initiale verifiable

Spec : VISION.md, docs/MANDAT-DEVELOPPEMENT.md et le critere C1 de l'audit.
Le test existant reconstruit des fixtures; il ne prouve pas la sequence des vrais
scripts d'installation sur un hote propre. Aucun changement du moteur ou des
choix commerciaux n'est necessaire pour verifier ce contrat.

## Task 1: executer le bootstrap dans un runner jetable

- Ajouter un test d'integration reserve explicitement a GitHub-hosted Linux,
  root et une installation absente. Refuser toute racine ou horaire preexistant.
- Executer setup_vps.sh depuis un checkout propre du commit exact; verifier
  les copies du controle, modes prives, backups et absence de cron/inference.
- Executer finalize_setup.sh contre un transport Git local de test, sans
  credential GitHub, puis verifier la source bare et le SHA.
- Executer le statut installe : World initialise et banque UNFUNDED.
- Appliquer la maintenance avec les vrais services/outils et les verrous de
  queue/daily detenus pour empecher tout cycle; verifier puis retirer uniquement
  les horaires crees par ce test avant de liberer les verrous.
- Verifier l'idempotence de maintenance et le refus d'une seconde installation.
- CI dediee avec image Node resolue par digest. Aucun redemarrage WSL/VPS.

Expected : le job bootstrap-install doit echouer si une etape reelle ne produit
pas son contrat. Les autres controles restent verts. Une revue independante
verifie la restriction du test, le nettoyage des horaires et la portee des preuves.

## Review Focus

Execution accidentelle hors runner jetable, horaires susceptibles de demarrer
un cycle, remplacement de fichiers preexistants, fuite de cles generees,
substitution du vrai bootstrap par une fixture et surestimation des preuves.

Limites : prerequis systeme prepares par CI; transport Git local, pas nouvelle
authentification GitHub ni Claude/Codex; aucune sauvegarde privee de production
copiee et aucune restauration financiere testee. La restauration apres perte
du VPS reste une verification distincte.
