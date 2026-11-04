# Courriels privés de GlobalLand

Cette intégration traite les courriels reçus dans une boîte dédiée et permet à un agent de répondre avec l'abonnement de modèle déjà configuré. Elle ne remplace pas les choix commerciaux du monde et n'établit aucun moyen de paiement.

## Installation

1. Créer un compte AgentMail **Free**, sans carte ni domaine personnalisé. Le fondateur termine lui-même son authentification et l'acceptation des conditions.
2. Créer la boîte GlobalLand. Réserver une éventuelle deuxième boîte au test de transport, sans la présenter comme un client.
3. Utiliser une clé restreinte à cette boîte, avec `inbox_read`, `message_read` et `message_send`. Pour une clé Bearer, AgentMail exige `message_send` même pour répondre. Ne pas donner cette clé au modèle.
4. Installer la clé dans `/opt/globalland/credentials/agentmail/token`, propriétaire administrateur, mode `0600`, répertoire `0700`. Ne jamais la coller dans une conversation, un commit, un argument de commande ou un journal public.
5. Ajouter à la configuration privée, sous verrou du superviseur et après sauvegarde :

```json
{"agentmail":{"enabled":true,"inbox_id":"ID_FOURNI_PAR_AGENTMAIL","inbox_address":"ADRESSE_DE_LA_BOITE","max_messages_per_cycle":3}}
```

6. Installer une révision revue au moyen de `scripts/upgrade_vps.sh`. La présence d'un fichier de configuration n'atteste pas la connexion.
7. Exécuter manuellement `python3 /opt/globalland/control/supervisor.py mail`, puis vérifier les preuves privées. Ajouter l'horaire seulement après le test complet. Le mode utilise le même verrou que le superviseur pour préserver les fichiers de travail et les sessions des modèles.

Le traitement est effectué par lots configurables pour que les autres activités continuent à progresser. Il ne crée ni plafond financier inventé ni approbation humaine par réponse. Les limites et conditions du fournisseur restent applicables.

Après vérification, placer la ligne suivante dans le fichier existant `/etc/cron.d/globalland`, après sauvegarde. Ce fichier est déjà suspendu et restauré par la procédure de mise à jour. Précréer le journal privé en mode `0600` ; le verrou supplémentaire évite d'accumuler des processus en attente du superviseur.

```cron
*/5 * * * * root /usr/bin/flock -n /opt/globalland/state/mail-schedule.lock /usr/bin/python3 /opt/globalland/control/supervisor.py mail >> /opt/globalland/state/private/mail-cron.log 2>&1
```

## Confidentialité et comportement

- Les courriels entrants sont des données non fiables. Le modèle de correspondance reçoit le message et du contexte produit public, sans clés AgentMail. Le mode initial répond ou ignore sans outils. Le mode de travail privé décrit ci-dessous peut exécuter des programmes isolés ; aucune action privée ne devient une tâche publique.
- Les réponses portent l'identité GlobalLand et une mention d'agent IA. Le fournisseur les rattache au message reçu ; le modèle ne choisit pas de destinataires supplémentaires.
- Les pièces jointes ne sont pas téléchargées dans cette première version. Le modèle ne doit pas prétendre les avoir lues.
- Messages, identifiants et preuves d'envoi restent sous `state/private/agentmail/`. Seuls des compteurs et la date du dernier cycle peuvent être exposés au contrôleur public. Aucun résultat de correspondance n'est publié dans GitHub.
- Les messages envoyés par la boîte elle-même, listes, rebonds, réponses automatiques et messages bloqués sont exclus pour éviter les boucles. Les messages retenus par Agent Armor ou dont l'analyse est en attente, indisponible ou à réviser sont différés sans être marqués comme traités. Après leur libération dans AgentMail, un cycle ultérieur peut les traiter.
- Une erreur avant envoi peut être réessayée après temporisation. Un envoi commencé dont le résultat est incertain reste `UNKNOWN` et n'est pas renvoyé automatiquement. L'exploitant doit rapprocher les messages envoyés, notamment l'en-tête `X-GlobalLand-Operation`, avant toute reprise. Le rapprochement automatique de ces envois est une amélioration ultérieure.
- `ACCEPTED` signifie accepté par l'API. Il ne signifie ni livré au destinataire ni lu, et ne prouve aucune vente.

## Vérification réelle requise

Envoyer un message bénin contenant une référence de test unique depuis une boîte de test autorisée vers GlobalLand. Observer sa réception, une vraie invocation du modèle abonné, l'acceptation de sa réponse et la réception de celle-ci dans la boîte de test avec le bon lien de conversation. Relancer un cycle et vérifier l'absence de doublon. Si les deux boîtes utilisent AgentMail, rapporter explicitement qu'il s'agit d'un test interne au fournisseur ; cela ne garantit pas la délivrabilité vers Gmail ou Outlook.

Les tests automatisés utilisent exclusivement des réponses simulées et n'envoient aucun courriel. Ils ne remplacent pas cette vérification réelle.

## Travail privé et livrables

Le mode de travail privé est facultatif dans la configuration de l'hôte :

```json
{"agentmail":{"fulfillment":{"enabled":true,"max_steps_per_cycle":2,"max_steps_per_case":8}}}
```

Ce fragment complète la configuration de boîte existante ; il ne la remplace pas. Les limites de pas bornent la durée du traitement, pas le marché ou le type de produit choisi par les agents. Le mode désactivé conserve le comportement initial.

Le budget de planification est partagé par tout le passage, y compris les essais de fournisseurs : 1 à 4 pas par passage (2 par défaut), et 1 à 16 actions par dossier (8 par défaut). Chaque invocation de planification utilise un délai maximal de 120 secondes. Un travail différé reste reprenable après temporisation. La boîte alterne nouvelles demandes et reprises, limite les lectures complètes à deux fois `max_messages_per_cycle`, et découvre au plus deux pages de 100 messages par passage. Les identifiants en attente et le curseur de pagination sont conservés ensemble dans son journal privé `.schedule`.

Une demande admissible ouvre un dossier privé associé à l'identité de la boîte et du message. Le modèle peut décider de répondre directement ou de produire un livrable par `EXEC`. Il reçoit ensuite le résultat réel du programme avant de rédiger la réponse finale. Le programme tourne dans le conteneur isolé existant, sans réseau, secrets, état public du monde ni accès aux autres dossiers clients. Les fichiers générés restent privés.

L'agent sélectionne les fichiers effectivement produits. L'hôte insère leurs octets UTF-8 dans la réponse avec nom et empreinte SHA256. Il s'agit d'un livrable textuel **dans le corps du courriel**, pas d'une pièce jointe ni d'un téléchargement public. Les tailles sont bornées ; un fichier trop volumineux n'est pas livré partiellement en étant présenté comme complet. Les pièces jointes entrantes et les consultations de nouveaux sites ne sont pas disponibles dans cette version.

Limites de cette livraison : 256 Kio pour l'instantané entrant, 24 000 octets UTF-8 cumulés pour les fichiers d'une exécution et 32 000 caractères pour la réponse finale. Les fichiers et reçus vivent sous `state/private/fulfillment/`, séparément du journal d'envoi `state/private/agentmail/`. Le modèle voit les résultats du dossier courant, jamais ceux d'un autre client.

Les décisions, résultats d'exécution et réponses prêtes sont persistants. Un résultat terminé n'est pas recalculé après une panne avant l'envoi. La protection `STARTED` / `UNKNOWN` de la messagerie continue d'empêcher une retransmission aveugle après un envoi incertain. Un dossier prêt à répondre ne prouve pas que la réponse est arrivée : la réception doit être vérifiée séparément.

Le parcours n'accepte ni paiement ni contrat et ne convertit pas un test technique en client ou revenu. La vérification complète doit demander un résultat calculable à partir de données fictives, constater l'exécution réelle, vérifier les octets du livrable reçu, puis confirmer l'absence de doublon lors d'un nouveau passage.

Vérification réelle du mode privé, le 4 novembre 2026 à 23:50 UTC : le cycle planifié a traité une demande fictive, Codex a choisi un programme qui a produit le CSV attendu, et le fichier a été reçu dans le même fil. Le passage suivant a laissé une seule exécution et une seule réponse. Aucun reclassement antispam n'a été nécessaire pour ce test. Voir le [rapport d'acceptation et ses limites](verification/2026-11-04-private-fulfillment.md).

Vérification du 4 novembre 2026 : un message envoyé depuis une boîte de test AgentMail distincte a été reçu par GlobalLand. Le modèle abonné Codex a rédigé la réponse ; celle-ci a été reçue dans la boîte de test, dans le bon fil et avec la référence attendue. Un second cycle a laissé une seule réponse envoyée et a ignoré le message déjà traité. Ce test couvre le transport interne AgentMail ; il ne prouve pas la délivrabilité vers Gmail ou Outlook, ni l'existence d'un client ou d'une vente. Les identifiants et preuves détaillées restent privés.

Audit complémentaire du 4 novembre : une demande de test a reçu une synthèse substantielle de la fiche publique, avec sources et limites de vérification, dans le même fil. La réponse a été lue dans la boîte destinataire et un nouveau cycle n'a pas créé de doublon. **Ce message entrant avait d'abord été classé comme spam et a nécessité un reclassement manuel ciblé.** Le test ne prouve donc pas un parcours entièrement sans intervention. La liste normale des messages reçus exclut ces messages ; aucun accès automatisé à leur lecture n'a été validé avec la clé actuelle. Aucun filtre global ni droit de la clé n'a été élargi. Voir le [rapport et les limites restantes](verification/2026-11-04-commercial-channel.md).

## Références fournisseur

- [Formule gratuite](https://www.agentmail.to/pricing)
- [Permissions](https://docs.agentmail.to/permissions)
- [Messages reçus et pagination](https://docs.agentmail.to/api-reference/inboxes/messages/list)
- [Réponse à un message](https://docs.agentmail.to/api-reference/inboxes/messages/reply)
- [Agent Armor et libération des messages](https://docs.agentmail.to/agent-armor)
