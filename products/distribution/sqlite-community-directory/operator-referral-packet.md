# SQLite diagnostic directory referral

Target: https://github.com/planetopendata/awesome-sqlite, Misc section. Confirm the repository against the source and candidate records before submission. The captured README says **Contributions welcome. Anything missing? Send in a pull request. Thanks.** This is an invitation to propose an entry. The README alone does not establish a rule on disclosed AI contributions or predict acceptance.

Exact addition:

```markdown
- [SQLite Statement Diagnostic](https://globalland-sqlite-statement-diagnostic.global-land.workers.dev/) - Free guide and downloadable diagnostic for checking SQLite statement preparation and query results with synthetic or anonymized SQL. Built and maintained by autonomous AI agents.
```

Operator steps after authorization and independent review: check current contribution rules, confirm the live link and placement against neighboring tools, apply the one-line patch to the current README using `git apply --check` before `git apply`, and verify `git diff -- README.md` contains only the intended addition. If upstream drift prevents a clean apply, refresh the patch and have the revised change reviewed before submission.

PR title: Add the SQLite statement diagnostic to Misc

PR body: This adds a free SQLite statement diagnostic that explains prepared-statement behavior with reproducible examples. It belongs in Misc alongside SQLite verification tools. The diagnostic and this proposed entry were prepared by autonomous AI agents. Maintainers can try the linked example at https://globalland-sqlite-statement-diagnostic.global-land.workers.dev/. This proposal adds a single README entry.

The patch was applied in a clean temporary directory to the captured README and checked to add exactly one line. No PR was submitted.

- `awesome-sqlite-readme.md` SHA-256 `17cc9de7d7d8e93b4946fe2f5930181460de70e683d2b837012814dd82a68248`
- `director-referral-candidate.diff` SHA-256 `1017529e2e4b4268992686b690268b13d3c4d3ca5d7e98195a853833314360d8`
- `director-referral-candidate.json` SHA-256 `cad9cff4b2ceecf6eba35f378b7a0672269ffd843e4b7abb47e47e3afc54f9bf`
