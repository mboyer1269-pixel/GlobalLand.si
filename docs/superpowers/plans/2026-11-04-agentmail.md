# AgentMail private correspondence implementation plan

**Goal:** Connect the founder's free AgentMail account to GlobalLand and demonstrate an inbound email and an agent-authored reply.

**Authorized scope:** Founder chose AgentMail Free, account setup, connection and receive/reply verification. No upgrade, custom domain purchase, cold outreach or banking change. Implementation choices below are engineering decisions within that request, not a change of commercial strategy.

**Architecture:** A private correspondence cycle uses the existing subscribed brain in a fresh tool-free invocation. It reads one incoming message and current public product context, and chooses a reply or no reply. The host sends only a reply to that incoming message. Message bodies and model outputs never enter the public task queue, WORLD state, product tree or Git publication. Normal strategy cycles remain unchanged; aggregate mail capability/status can be observed without message content.

**Approaches:** Direct vendor MCP inside the existing public planning turn would be quick but mixes private messages with public journals. A separate private correspondence cycle reuses the existing authenticated models and protects customer correspondence by construction. This is the implementation choice; ordinary mail needs no approval for each reply. API polling avoids a new public webhook endpoint.

**Tech stack:** Python standard library, existing Docker subscription brain, AgentMail HTTPS API v0, existing supervisor lock/upgrade process.

## Contracts and review focus

- Host credential `/opt/globalland/credentials/agentmail/token`, owner-only, never mounted into brain or printed. Config `agentmail`: enabled, inbox_id, inbox_address, optional max_messages_per_cycle (default 3).
- `scripts/mail.py`: Client(root, config, transport=None), list_received(), get_message(id), reply(id,text,operation_id), Mailbox(root,config,client=None).cycle(responder) and status(). Responder receives one private message dict and returns `{action: 'reply'|'ignore', text: string}`. Cycle returns fixed aggregate counts only.
- Fixed API origin, percent-encoded path IDs, bounded responses, no credential-bearing redirects, sanitized exceptions. Use only configured inbox. No attachments downloaded in this first connection.
- Persist private journal before sending. A previously STARTED send is UNKNOWN on recovery, never resent automatically. Reconcile using a unique outbound header and sent-message evidence when possible. API acceptance alone is not recipient delivery.
- Received-only processing; no replies to own messages, bounces, auto-replies or spam/blocked mail. Message IDs are opaque and never filesystem paths. Pagination must not starve mail beyond the first page. Per-message persistent state prevents duplicates across cycles.
- No addresses, subjects, bodies or generated prose in public projections. Private model has no tools/public write channel, no AgentMail credential, and output actions are never executed.
- API key should be scoped to the GlobalLand inbox with inbox_read/message_read/message_send. A free fixture inbox may be used only to verify transport, clearly distinguished from a customer.

## Tasks

- [x] Implement `scripts/mail.py` and `tests/test_mail.py`: fake transport tests for receive/reply, duplicate/crash recovery, pagination, encoding, credential privacy, safe errors, filtering and unknown send outcome. Run red then green.
- [x] Implement `scripts/mail_agent.py`: subscribed brain generates private structured reply using current public context; reject invented tool actions, no paid fallback, include AI identity. Test command privacy and parsing without live calls.
- [x] Add supervisor `mail` mode and aggregate capability observation, with tests confirming no public task/mail data leakage and disabled mode makes no API call.
- [x] Review and automated checks: 399 Python tests (5 skipped) and 12 Node tests passed under Linux WSL. Review found an Agent Armor hold bypass; fixed with a red/green regression and 28 mailbox tests passing. Independent review confirms no remaining blocker.
- [ ] Install the reviewed exact revision with backup after the account and credential are ready.
- [ ] Founder finishes account/auth/terms and enters scoped credential privately; validate Free status and configured inbox read access.
- [ ] Verify real inbound receipt, actual subscribed-agent response, receipt at test sender, and duplicate-safe second polling cycle. Install cron only after manual verification. Record evidence without claiming a customer or sale.

## Ledger

- Account sign-up opened; personal authentication/terms handed to founder. No account created by the assistant yet.
- Reusing clean isolated execution worktree, new branch codex/agentmail from current origin/main. No changes to the city checkout or Oria.
