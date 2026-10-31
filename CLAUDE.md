# Instructions de travail — GlobalLand autonome

Lire VISION.md, AGENTS.md, CODE.md, SECURITY.md et queue/PROTOCOL.md. Le mandat permanent du CEO du 2026-10-31 remplace les anciens veto par transaction et le verrou des 50 CAD.

Les agents choisissent activités, marchés mondiaux, outils, programmes et investissements. Ils peuvent créer des missions et sous-agents, publier du travail et engager le capital réellement disponible via la passerelle financière. Aucune validation humaine systématique d'une niche, d'un prix, d'une dépense ou d'un outil n'est requise.

Le plafond est l'argent de GlobalLand, y compris les revenus encaissés et hors engagements déjà réservés. Aucun dépassement, recharge personnelle, dette non financée ou utilisation d'Oria. Ne jamais confondre une déclaration de ledger, une simulation, des GLC et des fonds vérifiés. Ne fabriquer aucune preuve, aucun coût nul ni aucune approbation.

Grok peut travailler avec ses outils et GitHub. Le VPS expose les actions du protocole v3 après installation administrateur de ce contrôle ; modifier le dépôt ne met pas automatiquement à jour le VPS. Ne pas annoncer une autonomie active tant que le contrôleur ne s'exécute pas réellement. Ne pas annoncer une trésorerie financée sans rapprochement du dépôt.

Le dépôt est public : aucun token, carte, clé privée, reçu personnel ou credential. Les agents peuvent modifier leurs produits et règles de travail dans GitHub ; les contrôles hôte et intégrations bancaires restent séparés du code exécuté dans leurs boîtes pour protéger le plafond et Oria.

Tests : node tests/runtime.test.js ; node tests/executor.test.js ; python3 -m unittest discover -s tests -p 'test_*.py'. Les tests utilisent des fixtures, jamais le ledger vivant. Préserver les journaux durables et données privées ; ne pas les supprimer pour masquer une erreur ou rejouer une opération incertaine.
