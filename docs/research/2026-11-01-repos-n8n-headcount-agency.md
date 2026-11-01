# Trois dépôts open source : ce qu'ils apportent à la survie de GlobalLand

> Analyse du 2026-11-01, sur des clones récents de `n8n-io/n8n` (fichiers racine seulement), `cbrock84/headcount` et `msitarzewski/agency-agents`. Critère unique : est-ce que cela aide GlobalLand à vivre et à se développer économiquement **seul** ?

## Verdict

| Dépôt | Ce que c'est | Licence | Note /10 pour GlobalLand | Décision |
|---|---|---|---|---|
| **headcount** | Une « entreprise d'agents » : un PDG, 16 départements, 172 skills ; règles d'organisation vérifiées par CI | MIT | **8,5** | **Intégré** : règle des deux clés (producteur ≠ auditeur) et trois grilles de décision |
| **agency-agents** | Une bibliothèque de personas d'agents spécialisés (marketing, ventes, tests, finance, etc.) | MIT | **7** | **Intégré** : la rigueur du *Reality Checker* (verdict par défaut NEEDS_WORK) dans la fiche « preuve avant terminé ». Le reste sert de vivier de rôles, déjà utilisé dans `agents/` |
| **n8n** | Plateforme d'automatisation visuelle, plus de 1 500 intégrations, agents IA | **Sustainable Use License** (*fair-code*, pas open source au sens OSI) | **4** comme outil interne, **6** comme marché | **Non installé.** Gardé comme piste de marché |

## 1. headcount — la meilleure source, pour une raison précise

Ce n'est pas le nombre de skills qui compte, mais trois règles d'organisation, éprouvées sur une hiérarchie d'environ 24 agents :

1. **« Le producteur et l'auditeur ne sont jamais le même agent. »** Un agent qui relit son propre travail l'approuve presque toujours. L'AI Village a montré exactement ce défaut : de faux succès, propagés par complaisance entre agents.
2. **Découper le travail par zone d'écriture exclusive, pas par sujet.** Deux agents sur le même fichier ne peuvent être tenus responsables ni l'un ni l'autre.
3. **Un niveau d'autorité par rôle :** autonome, propose ou escalade. Cela recoupe notre `world/blockers.json`, où « escalade » signifie « carte pour le fondateur ».

Il y a aussi des skills directement utiles à l'économie du monde : `saas-idea-validator` (un verdict tranché avant de construire), `business-growth-consultant` (trouver la seule contrainte qui bloque le revenu), `completion-verification` (vérifier avant d'annoncer).

**Intégré dans ce commit :**
- **Règle des deux clés, appliquée par l'hôte.** Une nouvelle opération WORLD `review` (reviewer, sujet `actor:` ou `mission:`, empreinte, verdict APPROVE ou NEEDS_WORK, notes). Une mise en vente **publique** sur Apify exige l'APPROVE de l'empreinte exacte des sources, par un agent autre que celui qui publie. Un NEEDS_WORK plus récent l'annule. Réglage : `apify.require_review`, actif par défaut.
- **Quatre fiches** dans `agents/playbooks/`, injectées en entier à chaque tour (environ 850 mots) : verdict d'idée, contrainte de revenu, preuve avant « terminé », revue à deux clés. Ce sont des adaptations courtes, avec attribution (`THIRD_PARTY.md`, avis MIT complet).

**Non retenu pour l'instant :** installer les plugins headcount dans le conteneur de réflexion. Les tours du courtier désactivent volontairement skills et réglages (`--disable-slash-commands`, `--setting-sources ''`) pour fermer la porte aux personnalisations non contrôlées. Les fiches injectées apportent la substance sans rouvrir cette porte.

## 2. agency-agents — un vivier de rôles

GlobalLand s'en inspirait déjà : les cartes `agents/staff` et `agents/consultants` portent son attribution. Ce qui reste utile :

- **Testing › Reality Checker** et **Evidence Collector** : le verdict par défaut est « NEEDS WORK », et un score parfait est un signal d'alarme. Repris dans `completion-evidence.md`.
- **Runbooks** (`strategy/runbooks.json`, dont `startup-mvp`) : des équipes types par situation. Utile quand les agents créeront leurs propres rôles (`register_agent`).
- **Marketing › developer-community-builder** : pertinent pour Apify, dont le public est développeur.
- **Marketing › reddit-community-builder** et **sales-outbound** : à **ne pas** activer. La prospection non sollicitée par des agents a été perçue comme du spam à l'AI Village, et elle viole la plupart des règles des plateformes.

**Pourquoi ne pas importer les 100+ personas ?** Chaque persona coûte des jetons à chaque tour, et un rôle sans zone d'écriture ni preuve attendue n'est qu'un ton de voix. La règle de headcount s'applique : un agent dont le périmètre ne s'exprime pas en chemins n'est pas un agent.

## 3. n8n — attention à la licence

**Fait :** la *Sustainable Use License* n'autorise l'usage et la modification « que pour vos propres besoins internes, ou à des fins non commerciales ou personnelles », et la redistribution seulement gratuitement et à des fins non commerciales. Les fichiers `.ee.` sont sous licence entreprise.

**Conséquences pour GlobalLand :**
- ❌ Vendre n8n hébergé, ou un service dont le cœur est n8n : interdit.
- ✅ Un usage interne, comme automatiser les opérations de GlobalLand elle-même, est permis.
- ✅ Vendre ses **propres** créations construites *pour* n8n est hors du logiciel n8n lui-même. Ce sont des modèles de workflows (JSON) ou des Actors Apify utilisables depuis n8n. **À valider** avant de vendre : les conditions de la place de marché de modèles de n8n.

**Pourquoi je ne l'installe pas maintenant (note 4/10 comme outil interne) :**
- Il pèse sur la RAM du VPS partagé avec Oria.
- C'est une nouvelle surface d'attaque : interface web, nœuds de code arbitraire, et chaque intégration détient ses propres identifiants.
- Chacune de ses 1 500 intégrations exige de toute façon un compte au nom du fondateur. Le goulot de GlobalLand, ce sont les comptes et la distribution, pas le nombre de connecteurs.
- Notre courtier fait déjà ce dont les agents ont besoin, avec des garde-fous financiers que n8n n'a pas.

**Piste de marché, note 6/10, à tester par les agents eux-mêmes :** la communauté n8n est très large. Un Actor Apify utile *dans* des workflows n8n bénéficie de deux vitrines. Ce n'est qu'une hypothèse ; le verdict passera par la fiche `idea-verdict`.

## 4. Apify : plan gratuit confirmé

Page officielle des tarifs, lue le 2026-11-01 : le plan gratuit donne **5 $ de crédits par mois, sans carte de crédit**, et sur ce plan, « your access to Apify's services will be blocked until the beginning of the next monthly cycle » quand les crédits sont épuisés. C'est **un vrai plafond** : aucune dette possible, ce qui est conforme à la constitution. INSTALL.md recommande donc le plan gratuit sans carte.

## Sources
- [cbrock84/headcount](https://github.com/cbrock84/headcount) (MIT) : `plugins/executive/skills/agent-hierarchy`, `saas-idea-validator`, `business-growth-consultant`, `plugins/technology/skills/completion-verification`
- [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) (MIT) : `testing/testing-reality-checker.md`, `strategy/runbooks.json`
- [n8n-io/n8n](https://github.com/n8n-io/n8n) : `LICENSE.md` (Sustainable Use License 1.0), `README.md`
- [Apify, tarifs](https://apify.com/pricing)
