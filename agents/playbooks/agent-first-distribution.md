# Playbook: sell to AI agents, not only to people

Adapted for GlobalLand from the distribution of [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) (MIT). See THIRD_PARTY.md.

## Why
AI agents (Claude Code, Codex, OpenClaw...) now choose and run tools for their users. A tool an agent can find, install and call without a human is distributed by every agent that reads about it. Agent-Reach (ranked #1 repository of the day on Trendshift, per its README) installs from one sentence users paste to their agent: "install from this URL".

## Do
- Give each product an agent-readable entry point: a short llms.txt or install.md that an agent can follow alone (what it does, one example call, inputs, outputs, limits, price).
- Return clean structured output (JSON with stable fields), never HTML to parse; say which fields can be empty.
- Prefer channels agents already call: Apify Actors are reachable through Apify's MCP server and API.
- One tool, one job, one verb: "read X", "search Y". Agents pick tools by name and description.
- Order fallbacks inside the product (primary source, then a public backup) so a site change degrades instead of breaking; report which source answered.

## Measure
Runs started by API/MCP vs by humans in ACTOR_STATS; repeat runs per user.
