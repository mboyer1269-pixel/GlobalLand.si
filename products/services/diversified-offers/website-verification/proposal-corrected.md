# Corrected proposal: vibe-coded website cleanup (r/forhire 1xp9pdj) - NOT SENT

Prepared by autonomous AI agents (BUILDER), 2026-11-09, mission WEBSITE-CLEANUP-OFFER-VERIFICATION. Supersedes item 2 of operator-batch.md and offer `vibecoded-site-cleanup` in prospect-offers-v2.json for operator consideration; those originals are preserved unchanged. No operator has reviewed or approved this text. Nothing has been sent.

## Source (verified from saved official Reddit RSS)
- URL: https://www.reddit.com/r/forhire/comments/1xp9pdj/hiring_i_vibecoded_a_website_on_chatgpt_now_i/
- RSS artifact products/services/diversified-offers/raw/forhire-hiring.rss, sha256 2c61181177f16671f873337c5d1977b1764eef70b0c1e87a69c8be1a4930af95 (FETCH TASK-179424786111, 2026-11-09). The RSS entry contains the complete self-text (ends with "submitted by /u/Fatsquirrel666"), so no extra FETCH was used.
- Title: "[HIRING] i vibecoded a website on chatgpt, now I need someone to fixup the code for me"; published 2026-11-06T10:38:30Z.
- Requested outcome (quote): "I would like someone making it smoother in transiction, and just generallg less laggy and clean."
- Rate (quote): "name your price. I am not looking to invest hundreds into it. 15$/h." Currency is written as "$" only; USD is an assumption to confirm.
- Invitation: the [HIRING] flair in r/forhire asks for applicants, but the post itself names no contact method. Replying by comment or DM is the subreddit convention, not an explicit route stated in the post.
- Availability: this is a dated advertisement observed 3 days after posting. Whether it is still open, already filled, or the code size/framework/hosting are all UNKNOWN.

## Corrections versus the original offer
1. Removed "GPU-friendly CSS (transform/opacity)": transform/opacity changes can avoid layout work but do not guarantee GPU compositing or smoother rendering.
2. Removed "HTML/CSS well-formedness checks": no HTML or CSS validator or parser is installed (no tidy, xmllint, vnu, jsdom, parse5, css-tree, html5lib, lxml, tinycss2; Python html.parser is lenient and does not establish validity). See capability-and-source-check.json.
3. Removed pre-committed changes (moving transitions, removing layout-thrashing JS and duplicate CSS, adding prefers-reduced-motion) before anyone has seen the code. The offer is now diagnosis first, changes chosen by the buyer second.
4. Added an availability question, a currency confirmation and an explicit no-speed-up-promise statement.

## Deliverable (only after scope and payment route are agreed)
Input: buyer-pasted static HTML/CSS/JS as text, up to about 60 KB total; no backend, build system, credentials, attachments or private data.
1. Diagnosis: a list of specific code locations that are likely causes of lag (for example animated layout properties, scroll handlers that read and write layout, heavy repeated work), each with a proposed change and reasoning. Labelled as likely causes from reading the code, not measured.
2. Changes: only those the buyer selects, returned inline with a full change list.

## Verification we can actually run (node v22.23.4 present)
- `node --check` on each delivered JavaScript file (syntax only; does not prove behaviour).
- Byte diff between supplied and returned files, so every edit is listed.
- NOT verifiable by us: HTML/CSS validity, visual correctness, real-browser smoothness or frame rate, GPU use, cross-browser behaviour. No browser exists in the sandbox. The buyer tests in their own browser before paying.

## Acceptance criteria
Buyer confirms in their own browser that the pages load and nothing they care about broke, and judges smoothness themselves. Every edit appears in the change list. Delivered JS passes `node --check`.

## Price (proposal, not a buyer budget)
USD 30 fixed for diagnosis plus selected changes (about 2 h at the stated 15/h), payable only after the buyer accepts the result. If the code is larger than about 60 KB or uses a framework/build step, re-quote or decline.

## Effort and costs
Estimate 1-2 agent-hours plus about 20 minutes of operator QA; elapsed time depends on buyer response. Incremental cash cost 0 observed; subscription, labour, fees and taxes unknown. No profitability claim.

## Remaining prerequisites (existing blockers)
- Sending any reply: founder-approved AI-disclosed Reddit account and operator approval of the exact message below (blocker NO-COMMUNITY-ANSWER-ACCOUNT).
- Paid acceptance: a payment route compatible with the buyer (buyer location unknown; only operator-administered Interac CAD exists, foreign compatibility unverified; no USD route), then administrative order creation/acceptance and founder-attested deposit (blocker SERVICE-PAYMENT-COLLECTION). Without a compatible route, decline at quote stage.
- Delivery: buyer code would arrive via Reddit, which agents cannot read; operator would have to relay it as text. No such path is established.

## Exact message for operator consideration (not approved, not sent)
```
Hi! I saw your 6 Nov post about making your ChatGPT-built site smoother and less laggy. Disclosure first: I represent GlobalLand, where autonomous AI agents do the code work and a human operator oversees it. Is this still open? If so, and the site is plain HTML/CSS/JS with no backend or build step, you could paste the files as text. We would first send a short diagnosis: the specific lines in your transitions, animations and scripts that are likely causes of lag, each with a proposed change and why. You then pick which changes you want, and we return only those, with a list of every edit. Limits: we can confirm your JavaScript still parses, but we have no browser, so we cannot see the page, measure smoothness or confirm visual results; you would test it yourself before paying. We do not promise a specific speed-up. Proposed price: USD 30 fixed for the diagnosis plus the changes you choose, paid only if you accept the result. Before any commitment: roughly how many files/lines is the site, is your $15/h figure in USD, and which payment methods can you use? Nothing is agreed or scheduled by this message.
```
