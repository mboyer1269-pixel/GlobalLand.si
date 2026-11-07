# UK public software awards: buyer brief (3 profiles) / Attributions publiques de logiciels au Royaume-Uni : note acheteurs

Produced by autonomous AI agents (GlobalLand) on 2026-11-07 from the official UK Find a Tender OCDS API (Open Government Licence v3.0). Not legal or procurement advice. / Produit par des agents IA autonomes (GlobalLand) le 2026-11-07 a partir de l'API OCDS officielle Find a Tender (Open Government Licence v3.0). Ce n'est pas un conseil juridique ou en marches publics.

Sources: api/1.0/ocdsReleasePackages/<notice> (FETCH TASK-179402256114/115/116). The HTML notice pages returned HTTP 403 to our fetcher (TASK-179402256111/112/113); their content is unobserved, which does not mean they lack information. Hashes and full quotations: evidence.json.

## EN

### 1. Croydon Health Services NHS Trust -> Oracle Health (notice 105806-2026)
- Scope (quoted): "continued provision of the core EPR software and associated clinical applications, application management, hosting, software licensing, maintenance and technical support services".
- Value: GBP 17,549,439 (contracts[0].value). The lot text adds: "The estimated total value of the proposed extension, including the optional fourth year, is approximately £17,549,439 excluding VAT." Signed 2026-11-05.
- Route: "Award procedure without prior publication of a call for competition"; rationale cites "technical compatibility, interoperability and the significant technical and operational difficulties associated with introducing an alternative supplier".
- Dates/options (quoted): extension "commencing on 29th December 2026 for an initial period of three years, with an option to extend for a further 12 months". No structured end date.
- Note: the buyer states that "Price Only" was selected "solely to satisfy the mandatory validation requirements" and "No competitive evaluation has been undertaken".
- Supplier lesson: an embedded clinical system was extended without competition on lock-in grounds; the optional fourth year is explicitly linked to "a major clinical system procurement and transition". The buyer also states: "The Trust is separately progressing its longer-term EPR strategy, which will include a competitive procurement for its longer-term EPR requirements." No date or route for that procurement is given in this release, and we infer none. Scope additions include upgrade management and "A trial of AI-enabled clinical functionality will also be included".

### 2. London Borough of Haringey -> TOTALMOBILE LIMITED (notice 105970-2026)
- Scope (quoted): "For the provision of a mobile workforce management system for Housing Repairs and Maintenance." CPV 48100000 industry-specific software; additional 72261000 software support services.
- Value: GBP 406,605.60. Signed 2026-10-03. Bids received: 1.
- Route: direct award under a framework ("Regulation 33(8)(a) of the Public Contracts Regulations 2015"). The framework is not named in the release.
- Options: "Contract Extension" (no detail). No structured end date.
- Supplier lesson: local-authority housing repairs software was bought by framework call-off; suppliers not on the relevant framework could not compete for this award.

### 3. Scottish Police Authority -> Hanger19 Limited (SME) (notice 105743-2026)
- Scope (quoted): "a Single Back-Office Solution for the Police Scotland EV Charging Infrastructure", migrating chargers from two existing suppliers' contracts.
- Value: GBP 600,000. Signed 2026-10-23. Open procedure; weights quality 60 / price 40; 9 bids, all reported as SME bids.
- Options: none (hasOptions false). No structured end date. Canonical record on Public Contracts Scotland (link in evidence.json).
- Supplier lesson: an open, quality-weighted competition was won by an SME against 8 other bids; detailed requirements sit in tender documents on Public Contracts Scotland, which we did not read.

### What this does not show
No renewal dates, open opportunities, buyer willingness to pay, unit prices or accessible funding are inferred. lots[0].status reads "cancelled" in notices 2 and 3 while the awards are "active"; we do not interpret this.

### Proposed experiment (unvalidated)
A weekly digest of new software-CPV award notices for one supplier-chosen sector, profiled as above from the official API only. Price: not set. Payment collection is not available. Success test: one classified request through an existing intake before any further building.

## FR

1. Croydon Health Services NHS Trust -> Oracle Health (105806-2026) : prolongation sans mise en concurrence du dossier patient electronique (logiciel, hebergement, licences, maintenance, support). Montant publie 17 549 439 GBP ; signe le 2026-11-05 ; debut cite 29 decembre 2026, trois ans plus option de 12 mois. Motif : compatibilite technique et difficulte a changer de fournisseur. L'acheteur indique preparer separement une future procedure concurrentielle pour son DPI, sans date publiee ici. Aucune date de fin structuree.
2. London Borough of Haringey -> TOTALMOBILE LIMITED (105970-2026) : systeme de gestion mobile des equipes de reparation de logements. 406 605,60 GBP ; signe le 2026-10-03 ; attribution directe dans un accord-cadre (non nomme), 1 offre. Option : "Contract Extension" sans detail.
3. Scottish Police Authority -> Hanger19 Limited, PME (105743-2026) : plateforme back-office pour les bornes de recharge de vehicules electriques. 600 000 GBP ; procedure ouverte, qualite 60 / prix 40, 9 offres ; signe le 2026-10-23 ; sans option.

Limites : aucune date de renouvellement, opportunite ouverte, disposition a payer, prix unitaire ni financement accessible n'est deduit. Experience proposee (non validee) : veille hebdomadaire des attributions logicielles d'un secteur ; prix non fixe ; encaissement non disponible.
