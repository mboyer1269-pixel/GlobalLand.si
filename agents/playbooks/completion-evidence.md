# Playbook: evidence before "done"

Adapted for GlobalLand from `completion-verification` in [cbrock84/headcount](https://github.com/cbrock84/headcount) (MIT, © 2026 Chris Brock) and the Reality Checker in [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) (MIT, © 2025 AgentLand Contributors). See THIRD_PARTY.md.

## Rules
- A mission is complete only when its evidence exists as files under products/ and the original goal is met, not when a step ran.
- Run the check, read the output, then claim. Never report a result you have not observed in this world's files or task results.
- Default verdict for a first version is NEEDS_WORK. First implementations usually need two or three revisions.
- Treat perfect scores and "zero issues" as a red flag; cross-check the claim against the actual files.
- Never invent contacts, partners, users, revenue or test results. Unknown stays unknown.
