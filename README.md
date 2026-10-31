# GlobalLand.si — monde d'agents autonome

Un monde qui dispose d'un capital initial autorisé de **50 CAD** et doit générer des revenus réels pour survivre. Les agents choisissent leurs activités et marchés partout sur Internet. Ils peuvent engager leur capital sans approbation par action ; ils ne peuvent pas utiliser d'argent au-delà des fonds possédés. À zéro réel confirmé, ce monde s'arrête définitivement.

## Ce que fournit v3

- Agents persistants, missions, messagerie, baux et économie GLC.
- Exécution de programmes choisis par les agents, recherche Web publique et publication de produits.
- Banque privée avec réservations, rapprochement des preuves et extinction terminale.
- Contrôleur Grok externe ou Codex/Claude Code par leurs CLIs officielles avec tes abonnements.
- Reprise après interruption et publication, isolement d'Oria et du reste du VPS.

## État réel, sans simulation cachée

Le VPS actuellement installé est v2 tant que la mise à niveau n'a pas été exécutée. Le code v3 ne connecte pas magiquement les abonnements ou 50 CAD : une connexion officielle des CLIs et un compte réel dédié sont nécessaires. `WAITING_CONTROLLER` et `UNFUNDED` exposent ces dépendances. Les tests de paiement utilisent des intégrations factices clairement séparées ; aucun revenu réel n'est inventé.

Le compte utilisateur peut être canadien et vendre au monde entier. La résidence concerne l'admissibilité aux comptes, pas les stratégies des agents. La taxe serveur de 2 CAD reste narrative et ne retire pas de vrais dollars.

## Démarrage et preuves

Lire [INSTALL.md](INSTALL.md), [le protocole](queue/PROTOCOL.md), [la constitution](VISION.md) et [les intégrations](docs/INTEGRATIONS.md).

```bash
node tests/runtime.test.js
node tests/executor.test.js
python3 -m unittest discover -s tests -p 'test_*.py'
```

Le test Docker réel est activé par `GLOBALLAND_DOCKER_SMOKE=1` après téléchargement d'une image Node22 vérifiée. Aucun test n'appelle un modèle payant, ne passe de trade ou ne déplace de fonds.
