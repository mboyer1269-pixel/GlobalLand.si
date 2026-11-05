# Diagnostic : panne actuelle ou trace historique

Le diagnostic installé à 8e12f2b annonçait deux problèmes critiques malgré un tour réussi à 2026-11-05T21:31:04Z et un service cron confirmé actif. Il déduisait l'arrêt de cron du silence de think.log et présentait encore l'échec du 4 novembre comme une panne actuelle.

La correction conserve les faits historiques mais distingue le service cron actif, réellement inactif/en échec ou non vérifié ; le dernier état de planification récent, ancien ou non vérifiable ; et l'échec du planificateur suivi d'une réussite ou sans preuve de reprise.

Les dates invalides, sans fuseau ou futures ne permettent pas de conclure à une reprise. DECISION_READY prouve une planification, pas une publication, une livraison ni un revenu. Le verrou, les processus, les décisions non publiées et les autres diagnostics restent séparés.

Les reproductions ont échoué avant correction (quatre échecs et une erreur), puis les 16 tests ciblés sont passés. Ils couvrent un cron réellement arrêté malgré une réussite manuelle récente, un état de service illisible, une activité ancienne malgré un service actif et un échec plus récent que le succès.

Le candidat a été exécuté par entrée standard SSH, en lecture seule, sans installation ni redémarrage. Cron était actif, le dernier tour datait de 11,4 minutes, le journal était silencieux depuis 340,2 minutes et l'unique constat était PLANNER_FAILURE_SUPERSEDED, informatif. L'ancien fichier d'échec reste intact.

La preuve filtrée locale est output/globalland-incident-live-fixed.json. Les contrôles de la PR portent sur le commit exact ; aucune modification des horaires, des fournisseurs, des capacités ou des stratégies des agents n'est nécessaire pour ce correctif.
