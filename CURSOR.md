# Instructions de travail — GlobalLand autonome

Pour le travail de développement avec le fondateur, lire et appliquer le [mandat commun de développement](docs/MANDAT-DEVELOPPEMENT.md), également référencé par AGENTS.md et CLAUDE.md. Ce cadre préserve le choix stratégique des agents et guide les collaborateurs ; il ne configure pas le VPS.

Lire VISION.md, AGENTS.md, CODE.md, SECURITY.md et queue/PROTOCOL.md. Le mandat permanent du CEO du 2026-10-31 remplace les anciens veto par transaction et le verrou des 50 CAD.

Les agents choisissent activités, marchés mondiaux, outils, programmes et investissements. Ils peuvent créer des missions et sous-agents, publier du travail et engager le capital réellement disponible via la passerelle financière. Aucune validation humaine systématique d'une niche, d'un prix, d'une dépense ou d'un outil n'est requise.

Le plafond est l'argent de GlobalLand, y compris les revenus encaissés et hors engagements déjà réservés. Aucun dépassement, recharge personnelle, dette non financée ou utilisation d'Oria. Ne jamais confondre une déclaration de ledger, une simulation, des GLC et des fonds vérifiés. Ne fabriquer aucune preuve, aucun coût nul ni aucune approbation.

Grok peut travailler avec ses outils et GitHub. Le VPS expose les actions du protocole v3 après installation administrateur de ce contrôle ; modifier le dépôt ne met pas automatiquement à jour le VPS. Ne pas annoncer une autonomie active tant que le contrôleur ne s'exécute pas réellement. Ne pas annoncer une trésorerie financée sans rapprochement du dépôt.

Le dépôt est privé (API GitHub : `"private": true`, vérifié le 2026-11-01) et peut devenir public à tout moment : écrire comme s'il l'était déjà, donc aucun token, carte, clé privée, reçu personnel ou credential. Privé implique que GitHub Actions consomme des minutes facturées : un job rouge en quelques secondes peut venir de la facturation (annotation « spending limit »), pas du code ; ne jamais hausser la limite sans décision d'argent. Les agents peuvent modifier leurs produits et règles de travail dans GitHub ; les contrôles hôte et intégrations bancaires restent séparés du code exécuté dans leurs boîtes pour protéger le plafond et Oria.

Tests : node tests/runtime.test.js ; node tests/executor.test.js ; python3 -m unittest discover -s tests -p 'test_*.py'. Après une mise à jour de Codex : `GLOBALLAND_CLI_CONTRACT=1 python3 -m unittest tests.test_cli_contract -v` (sans login ni coût). Les tests utilisent des fixtures, jamais le ledger vivant. Préserver les journaux durables et données privées ; ne pas les supprimer pour masquer une erreur ou rejouer une opération incertaine.
