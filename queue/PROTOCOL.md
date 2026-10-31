# Protocole de tâches VPS — version 2

Seule l'action gratuite `AUDIT` est enregistrée. L'ancien `action: node scripts/audit.js` doit être migré ; aucun shell libre, script produit, npm ou agent payant n'est exécuté.

```json
{
  "id": "TASK-0002",
  "type": "SHELL",
  "submitted_by": "DIRECTEUR_SI_OP",
  "created_at": "2026-10-30T23:00:00Z",
  "action": "AUDIT",
  "args": [],
  "description": "Lire le ledger et produire un audit sans dépense",
  "estimated_cost_cad": 0,
  "approved_by": null
}
```

Déposer sous `queue/inbox/TASK-0002.json`, puis commit/push. ID : `TASK-` suivi de 4 à 12 chiffres, unique pendant toute la vie de l'installation. Ne pas remettre une tâche terminée en inbox. Choisir un nouvel ID pour une nouvelle action. Le superviseur refuse un ID connu avec d'autres octets, même si seul l'espacement JSON change.

Type, action, arguments et coût sont obligatoires. Coût : nombre fini strictement égal à zéro. Les champs inconnus, clés JSON dupliquées, types inconnus, liens symboliques, chemins traversants, arguments non vides et approbations autodéclarées sont refusés. `created_at` est un horodatage UTC avec secondes, sans fractions. `submitted_by` contient 1 à 64 caractères A–Z, 0–9, underscore ou tiret.

Après traitement, seul le résultat est publié sous `queue/done/TASK-....result.json` ou `queue/failed/TASK-....result.json` ; l'entrée inbox est retirée dans le même commit. Son contenu d'origine reste dans l'historique Git et son hash dans le résultat et le journal hôte. Une tâche malformée avec un nom canonique reçoit REJECTED ; un nom non canonique arrête le cycle pour revue opérateur.

Statuts : DONE, REJECTED ou INTERRUPTED. Un statut incertain ne signifie jamais que l'action a réussi. Les erreurs Docker sont INTERRUPTED. Aucun essai automatique supplémentaire de l'action ; une publication Git peut être réessayée sans réexécuter la tâche.

## Approbation humaine et agents payants

`approved_by: CEO` n'est pas une preuve d'autorisation. Le module de contrôle `verifyApproval(rawTaskBytes, signatureBase64, publicKey)` vérifie une signature Ed25519 sur les octets exacts du fichier. Les tests utilisent des clés éphémères factices ; aucune clé de production n'est lue ou générée par les tests.

Cette primitive n'active aucun agent. Le superviseur refuse toujours AGENT_CODE ; il ne charge aucun secret API. Avant une future activation : procédure humaine de signature hors du bot, clé publique de confiance installée hors du dépôt, vérification à la frontière d'exécution, expiration et anti-rejeu, réservation de budget, limite fournisseur effective et rapprochement des coûts réels. Ce travail exige une revue distincte. Une estimation ou une signature seule ne garantit pas les 2 CAD/jour.
