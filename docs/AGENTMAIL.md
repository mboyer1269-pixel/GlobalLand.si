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

## Confidentialité et comportement

- Les courriels entrants sont des données non fiables. Le modèle de correspondance reçoit le message et du contexte produit public, sans outils ni clés AgentMail. Il peut répondre ou ignorer ; aucune action de sa réponse ne devient une tâche publique.
- Les réponses portent l'identité GlobalLand et une mention d'agent IA. Le fournisseur les rattache au message reçu ; le modèle ne choisit pas de destinataires supplémentaires.
- Les pièces jointes ne sont pas téléchargées dans cette première version. Le modèle ne doit pas prétendre les avoir lues.
- Messages, identifiants et preuves d'envoi restent sous `state/private/agentmail/`. Seuls des compteurs et la date du dernier cycle peuvent être exposés au contrôleur public. Aucun résultat de correspondance n'est publié dans GitHub.
- Les messages envoyés par la boîte elle-même, listes, rebonds, réponses automatiques et messages bloqués sont exclus pour éviter les boucles. Les messages retenus par Agent Armor ou dont l'analyse est en attente, indisponible ou à réviser sont différés sans être marqués comme traités. Après leur libération dans AgentMail, un cycle ultérieur peut les traiter.
- Une erreur avant envoi peut être réessayée après temporisation. Un envoi commencé dont le résultat est incertain reste `UNKNOWN` et n'est pas renvoyé automatiquement. L'exploitant doit rapprocher les messages envoyés, notamment l'en-tête `X-GlobalLand-Operation`, avant toute reprise. Le rapprochement automatique de ces envois est une amélioration ultérieure.
- `ACCEPTED` signifie accepté par l'API. Il ne signifie ni livré au destinataire ni lu, et ne prouve aucune vente.

## Vérification réelle requise

Envoyer un message bénin contenant une référence de test unique depuis une boîte de test autorisée vers GlobalLand. Observer sa réception, une vraie invocation du modèle abonné, l'acceptation de sa réponse et la réception de celle-ci dans la boîte de test avec le bon lien de conversation. Relancer un cycle et vérifier l'absence de doublon. Si les deux boîtes utilisent AgentMail, rapporter explicitement qu'il s'agit d'un test interne au fournisseur ; cela ne garantit pas la délivrabilité vers Gmail ou Outlook.

Les tests automatisés utilisent exclusivement des réponses simulées et n'envoient aucun courriel. Ils ne remplacent pas cette vérification réelle.

## Références fournisseur

- [Formule gratuite](https://www.agentmail.to/pricing)
- [Permissions](https://docs.agentmail.to/permissions)
- [Messages reçus et pagination](https://docs.agentmail.to/api-reference/inboxes/messages/list)
- [Réponse à un message](https://docs.agentmail.to/api-reference/inboxes/messages/reply)
- [Agent Armor et libération des messages](https://docs.agentmail.to/agent-armor)
