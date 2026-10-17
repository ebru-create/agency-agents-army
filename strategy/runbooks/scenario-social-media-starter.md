# Runbook: Five-Agent Social Media Campaign

**Mode:** NEXUS-Micro · **Duration:** one campaign cycle · **Team:** five existing specialists, loaded per phase.

Brief → Strategy → Content → Instagram adaptation → Brand review → User approval → Publishing handoff → Analytics.

This is a portable instruction workflow, not an autonomous publishing service. The host assistant coordinates sequentially when delegation is unavailable. Installation does not create credentials, scheduling, persistent memory, or platform access. No sixth publishing agent is needed: the strategist prepares the execution handoff; the user or an explicitly authorized connector executes it.

## Install the team

Run from the repository root. This installs only the five agents for the selected tool:

```bash
python3 -c 'import json; r=next(r for r in json.load(open("strategy/runbooks.json"))["runbooks"] if r["slug"]=="social-media-starter"); print("\n".join(a for g in r["roster"] for a in g["agents"]))' > /tmp/social-media-starter-team.txt
./scripts/install.sh --tool claude-code --agents-file /tmp/social-media-starter-team.txt --dry-run
./scripts/install.sh --tool claude-code --agents-file /tmp/social-media-starter-team.txt
```

Choose your supported tool ID in place of `claude-code`. Keep the runbook and campaign artifacts available to the host; installable personas include their own workflow boundaries, but the installer does not copy runbooks.

## Shared brief

Store one versioned brief. All agents use the same revision. Ask for missing material facts; draft around nonblocking assumptions only when clearly labeled. Never invent an offer, account, testimonial, permission, price, or result.

| Field | Required context |
|-------|------------------|
| Identity | campaign ID, brief revision, brand, destination account(s) |
| Outcome | business objective, audience, offer, CTA and verified destination |
| Brand | voice, examples, prohibited language, colors and supplied asset references |
| Context | locale, timezone, campaign window, resources and spend cap (zero by default) |
| Evidence | approved claims and sources, image/music rights, required disclosures |
| Measurement | baseline period, source, metric definitions/denominators, target rationale |
| Authority | named user approver and allowed actions; default draft-only |
| Open questions | each unknown, owner, assumptions, blocked dependent work |

## Responsibilities and gates

| Phase / owner (canonical ID) | Input | Output / acceptance gate |
|--------------------------------|-------|--------------------------|
| Strategy / `marketing-social-media-strategist` | shared brief | strategy, content slots, objective-linked KPI plan; material questions resolved |
| Content / `marketing-content-creator` | brief + strategy | versioned captions/scripts/slide text, CTA, claim/source list, asset requests and alt text |
| Platform / `marketing-instagram-curator` | content package | format adaptation, cover/safe-area guidance, timezone-aware schedule proposal; feature availability checked or explicitly unverified |
| Review / `design-brand-guardian` | exact adapted revision + actual assets | PASS/FAIL/UNTESTED against brief, evidence, rights and accessibility; list findings, never invent a defect quota |
| Approval / user, coordinated by strategist | review PASS + final package | explicit authorization bound to revision, account, action, schedule/timezone and spend cap |
| Execution / authorized connector or user | matching approval | receipt identifying action, account, revision, platform ID and execution time; otherwise unperformed manual handoff |
| Analysis / `support-analytics-reporter` | actual exports/receipts + KPI plan | source-backed report with period/denominators, missing data and next experiment; never simulated results presented as real |

The brand reviewer cannot certify legal compliance; unresolved regulated claims require qualified review before approval. An asset brief is not a finished image. Text-only work can pass its own scoped review, but missing final assets keep publication review UNTESTED. No platform access means drafting can continue while execution remains unperformed.

Use the orchestrator's [task states](../../specialized/agents-orchestrator.md#task-state-contract): three implementation submissions total, dependency-aware blocking, and QA evidence for the current revision. Independent work may continue; blocked required work prevents overall success. When the brief or content changes, invalidate affected downstream reviews and approvals. Re-check authorization immediately before each external action. A receipt for scheduling proves scheduling, not eventual publication. Do not retry an ambiguous external action until its platform status has been reconciled, to avoid duplicate posts or spend.

## Handoff format

Every transfer carries the following fields. Reference real artifact paths or IDs rather than repeating the entire conversation:

```json
{
  "campaign_id": "studio-intro",
  "brief_revision": "brief-v1",
  "task_id": "adapt-carousel",
  "from": "marketing-content-creator",
  "to": "marketing-instagram-curator",
  "content_id": "intro-carousel",
  "revision": "intro-carousel-v2",
  "status": "ready_for_qa",
  "dependencies": ["write-carousel"],
  "dependency_revisions": {"write-carousel": "intro-carousel-v1"},
  "artifacts": ["campaign/content-v2.md"],
  "acceptance_criteria": ["CTA matches verified brief destination", "All claims have sources"],
  "evidence": [],
  "open_questions": ["Final images still required"],
  "next_action": "Adapt copy; keep final asset review UNTESTED"
}
```

No handoff grants external-action permission. Record a separate approval with `revision`, `account`, `action` (`publish`, `schedule`, `reply`, `dm`, or `spend`), `scheduled_at` (ISO 8601 with UTC offset), `timezone` (IANA name), `spend_cap`, and `user_evidence` referencing the actual user instruction. For immediate actions use the agreed execution time/window and re-confirm if it expires. Any scope mismatch requires fresh authorization. Budget zero permits no paid action.

## Start prompt

```text
Use the Five-Agent Social Media Campaign runbook. Load specialists only for their current phase. Start by checking my brief for material gaps. Produce a strategy, versioned content package, Instagram adaptation, and brand review. Stop at a reviewable publishing handoff until I authorize the exact revision, account, action and schedule. Use real analytics only; if unavailable, provide a measurement plan. Record task states, attempts, dependencies, and evidence in campaign artifacts.
```

## Example and evaluation

See the [fictional campaign](../../examples/workflow-social-media-starter.md) and its [machine-readable artifact](../../examples/social-media-starter/campaign.json). Validate a snapshot with `python3 scripts/check-social-workflow.py PATH`. This checks recorded consistency; it does not authenticate approvals, inspect media, enforce platform permissions, schedule tasks, or execute external actions.

Use the [scenario evaluation guide](../../evaluations/social-media/README.md) to assess actual assistant behavior separately from artifact validation.
