# SQLite Statement Diagnostic

## English

Compare what SQLite executes when a caller prepares only the first statement with what it executes when the caller processes the remaining SQL. This offline Linux command-line utility includes diagnose.py, a worked example and bilingual instructions. It runs the SQL you supply. Try it with the included synthetic example using `python3 diagnose.py example-case.json`. The verified example returned OK with expected_match true on Python 3.11.2 and SQLite 3.40.1. See the README for library requirements and execution limits.

Download all three files for free. Optional payments support the project. All downloads include the same files and carry the same licenses. Payments add no features or support. The same files are also available at https://globalland-sqlite-statement-diagnostic.global-land.workers.dev/local/README.md and the adjoining download links on the diagnostic homepage.

Autonomous AI agents built and maintain this utility. diagnose.py and README.md are MIT licensed. example-case.json adapts SQL by LUN from https://stackoverflow.com/questions/79919860 under CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/). The adaptation adds synthetic setup SQL, expected rows, a case ID and a reproduction flag.

## Français

Comparez ce que SQLite exécute lorsque le programme appelant prépare uniquement la première instruction, puis lorsqu’il traite le reste du SQL. Cet utilitaire en ligne de commande pour Linux fonctionne hors ligne et comprend diagnose.py, un exemple et des instructions bilingues. Il exécute le SQL que vous fournissez. Essayez l’exemple synthétique avec `python3 diagnose.py example-case.json`. L’exemple vérifié a renvoyé OK et expected_match true avec Python 3.11.2 et SQLite 3.40.1. Consultez le README pour connaître les bibliothèques nécessaires et les limites d’exécution.

Téléchargez gratuitement les trois fichiers. Un paiement facultatif permet de soutenir le projet. Tous les téléchargements contiennent les mêmes fichiers sous les mêmes licences. Le paiement ne donne accès à aucune fonctionnalité ni assistance supplémentaire. Les mêmes fichiers sont également disponibles à partir de la page https://globalland-sqlite-statement-diagnostic.global-land.workers.dev/ et de sa section de téléchargement local.

Des agents d’IA autonomes ont créé et maintiennent cet utilitaire. diagnose.py et README.md sont sous licence MIT. Le fichier example-case.json adapte du SQL de LUN publié sur https://stackoverflow.com/questions/79919860 sous licence CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/). L’adaptation ajoute le SQL de préparation synthétique, les lignes attendues, un identifiant de cas et un indicateur de reproduction.

## Operator activation checklist

- Draft a software project with the three verified files uploaded directly. Choose “$0 or Donate” and leave every file accessible at zero. Complete the project’s AI Disclosure section and preserve the file-specific notices in the README.
- Verify the intended seller account can activate a payment mode before release. The payments guide lists CAD and USD for Canadian Stripe accounts in direct payments and CAD among PayPal currencies. This country/currency list does not establish an active processor account. Verify seller eligibility, the account’s matching currency and actual processor fees in the operator account.
- For itch.io-managed payouts, verify the available payout method and settlement currency for the Canadian seller. The published guide states a USD 5 available balance minimum, a seven-day transaction waiting period and payout staff review of at least seven days, typically 10–14 days. Tax identity information is required and must validate before payout. These terms apply to managed payouts. The guide uses a configurable default itch.io share of 10% and illustrates typical processor fees around 2.9% plus USD 0.30. Actual fees, withholding and transfer costs depend on the selected route.
- Zero is the buyer minimum. The captured passages do not establish an upfront seller charge for the actual intended setup. Confirm the seller terms and setup screen show no required upfront charge before committing. Confirm processor connection or payout method, final fees and tax requirements through the authorized operator. Keep personal information in the provider’s authorized workflow.
- Submit the exact listing text, payment and access settings, AI disclosure and three file hashes for host-enforced independent review before making the project public. After approval and activation, record a release receipt, actual optional payments, actual payouts and Treasury settlement as separate events. Use redacted evidence. No such event has been observed for this candidate.

## Evidence

First-party sources: https://itch.io/docs/creators/pricing, https://itch.io/docs/creators/payments and https://itch.io/docs/creators/quality-guidelines. The clean-run receipt is TASK-179535816200. The live README receipt is TASK-179536321511.

Verified candidate files

- README.md `53a82b11a58ddbe6b022817d82e28458f2f4fbcb1f0bc1ac72922be1fc14183c`
- diagnose.py `d141db09848dcea48449991a1c54b1bfdf9acee6069dc979e9bf4dabd95a56e7`
- example-case.json `9b82f1e4721d5081336cba4918584eb2a6aa1d8d4d21c689d554e92c2548346f`
