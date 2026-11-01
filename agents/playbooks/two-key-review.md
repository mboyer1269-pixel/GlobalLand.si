# Playbook: producer and auditor are never the same agent

Adapted for GlobalLand from `agent-hierarchy` in [cbrock84/headcount](https://github.com/cbrock84/headcount) (MIT, © 2026 Chris Brock). See THIRD_PARTY.md.

## Rule enforced by the host
A public Apify listing needs a WORLD `review` with verdict APPROVE of the exact `source_digest` returned by the private build, by an agent other than the one publishing. A later NEEDS_WORK on the same digest cancels the approval.

## How to review
- Read the Actor files (read_product) and the private build result.
- Check: README states what it does, for whom, its limits and that it is built and maintained by autonomous AI agents; input schema is clear; prices are justified; a test run or fixture shows real output.
- Write what was checked in `notes`. Approve only what you verified yourself.
- Reviewers do not edit the work they review; send findings with WORLD message instead.
