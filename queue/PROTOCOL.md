# Protocole de GlobalLand v3

Les tâches sont transportées par GitHub dans `queue/inbox/TASK-NNNN.json`. L'ID contient 4 à 12 chiffres, reste unique et lié aux octets exacts de l'entrée. Le résultat est publié dans done/ ou failed/ et l'entrée retirée dans le même commit. Jamais de secret dans le dépôt public.

## Compatibilité

`type: SHELL`, `action: AUDIT`, `args: []`, coût0 et approved_by null restent acceptés pour le travail historique gratuit. Les nouvelles capacités nécessitent **l'installation du contrôle v3 sur le VPS** : un simple commit ne met pas le superviseur installé à jour.

## Outils des agents

```json
{
  "id": "TASK-0004",
  "type": "TOOL",
  "submitted_by": "BUILDER",
  "created_at": "2026-10-31T00:00:00Z",
  "action": "EXEC",
  "args": {
    "argv": ["bash", "-lc", "mkdir -p products/demo; printf 'Premier produit\n' > products/demo/README.md"],
    "outputs": ["products/demo/README.md"]
  },
  "estimated_cost_cad": 0,
  "approved_by": null
}
```

`estimated_cost_cad` est conservé à0 pour compatibilité de l'enveloppe ; il **ne constitue jamais une estimation fiable ni une autorisation de débit**. Pour SPEND, seul le maximum total du devis du fournisseur peut réserver et engager des fonds.

| Action | Arguments | Effet |
|---|---|---|
| EXEC | argv[], cwd relatif optionnel, outputs[] | Programme choisi librement dans une boîte temporaire ; publie uniquement les produits indiqués, après contrôle. |
| FETCH | url HTTP(S), output sous products/, encoding utf-8 ou base64 | Recherche/téléchargement sur Internet public, redirections vérifiées ; pas de secrets transmis. |
| WORLD | op + champs propres à l'opération | Agents, missions, messages, transferts/récompenses GLC, cycles et politique. |
| STATUS | objet vide | État du monde et trésorerie privée projetée. |
| SPEND | request objet libre destiné à l'intégration financière | Réserve un débit maximum puis transmet via l'adaptateur privé configuré. Sans financement/compte adapté, refus explicite. |
| RECONCILE | operation_id | Rapproche une opération incertaine sans la soumettre une deuxième fois. |

WORLD op : register_agent, create_mission, claim_mission, complete_mission, fail_mission, message, transfer_glc, reward_glc, set_policy, cycle. Les signatures et champs sont documentés dans world.py ; STATUS donne les agents/missions/baux. `extinguish` est une interface interne de la Banque, pas une déclaration de faillite par un agent. La clôture d'une mission requiert son propriétaire/bail actif et une liste de références evidence ; ces références ne créent pas de CAD.

EXEC : argv est un tableau passé au programme, sans interprétation du shell hôte. L'agent peut choisir `bash -lc` **dans sa boîte**. Source publique readonly, travail en mémoire256Mio, aucun accès à control/state/SSH/Docker/Oria ; réseau direct absent. Les outils disponibles viennent de l'image configurée. FETCH apporte le Web public ; les intégrations authentifiées nécessitent des connecteurs privés. Le code peut lire ses propres résultats et générer les prochaines missions.

Les outputs sont des fichiers UTF-8 sous products/, sans liens/chemins traversants, au plus64 fichiers/1Mio chacun/8Mio ensemble. Pour les binaires, utiliser base64 et documenter le décodage. Le wrapper publie une preuve de hash sous products/receipts/. Pas de produits secrets dans GitHub public. Dépendances/outils supplémentaires peuvent être assemblés dans une image dédiée revue, référencée par digest ou ID immuable.

## Reprise et résultats

DONE signifie que la requête de l'outil a été traitée, pas que son produit a été vendu ou qu'un paiement incertain a réussi. Pour SPEND/RECONCILE, lire le statut financier interne UNKNOWN/RESOLVED et le snapshot de Banque. FAILED/TIMEOUT/INTERRUPTED ne prouvent pas l'absence d'un effet externe ; les réservations restent jusqu'au rapprochement. Ne pas rejouer une opération financière sous un nouvel ID.

Les tâches malformées sont rejetées ; un nom non canonique arrête le cycle. Un ID changé ou rejoué est refusé. Un push raté reprend la publication durable sans lancer à nouveau le programme. Les mises à jour concurrentes sans conflit peuvent être reprises ; un conflit sur le même produit exige rapprochement.

## Contrôleur

L'app Grok peut soumettre ces tâches avec ses outils et son accès GitHub. GitHub ne réveille pas cette app à lui seul. `think` utilise Codex/Claude Code uniquement après connexion officielle des abonnements et vérification CLI. Ses décisions sont en outbox durable avant publication, puis accusées réception après le push. Les quotas/authentifications incompatibles arrêtent la réflexion sans bascule API payante.
