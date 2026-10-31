# GlobalLand.si

Expérience d'agents et de comptabilité : capital initial déclaré **50 CAD**, réserve verrouillée **50 CAD**, disponible sans CEO **0 CAD**, cible **100 CAD**. Aucun paiement n'est effectué par ce dépôt.

Le canal VPS a été réduit à une action gratuite et explicite : `AUDIT`. Les cartes dans `agents/` décrivent des rôles ; elles ne provisionnent aucun agent. Les tâches de code payantes sont désactivées, même si le JSON contient `approved_by: CEO` ou une signature.

## Architecture

GitHub → superviseur installé et revu sur l'hôte → export sans `.git` → conteneur Node 22 hors réseau → journal durable hôte → commit de résultats autorisés → GitHub.

Le conteneur voit seulement l'export et le code de contrôle en lecture seule. Il n'exécute aucun script téléchargé du dépôt. Les scripts cron pointent vers `/opt/globalland/control`, jamais vers le dépôt. Le Git de publication et la clé SSH restent hors des montages.

## Vérifications locales

```bash
node tests/runtime.test.js
python3 -m unittest discover -s tests -p 'test_*.py'
node scripts/audit.js
```

Aucune dépendance npm. Node 22+, Python 3.12+, Git, Docker Compose v2 sur le VPS.

Lire [INSTALL.md](INSTALL.md) avant installation : commit complet, image identifiée par digest, clé de déploiement dédiée, test manuel puis cron. L'installeur ne démarre ni conteneur ni cron.

## Documents

- [VISION.md](VISION.md) : constitution et objectifs.
- [CODE.md](CODE.md) : état financier et architecture actuelle.
- [SECURITY.md](SECURITY.md) : garanties, frontière de confiance et limites.
- [queue/PROTOCOL.md](queue/PROTOCOL.md) : schéma actuel, incompatible avec les anciennes commandes shell libres.

La taxe serveur reste narrative. Elle ne débite pas le capital réel. Un résultat d'audit ne prouve ni un encaissement bancaire ni la rentabilité d'un produit. Aucun mécanisme ne détruit le serveur ou n'archive le dépôt.
