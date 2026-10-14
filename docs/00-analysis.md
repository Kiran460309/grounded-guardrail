# 00 — Hackathon analysis

## Facts (from the official page + rules, updated Oct 9 2026)
- Organizer: AWS, on AWS Builder Center. Online. Launch Oct 16; due **Oct 23, 11:59 PM PT**
  (= Oct 24, 12:29 PM IST). Gate 1 week of Oct 26 (AI + human, top 100). Gate 2 week of Nov 2
  (AWS expert panel, 3 winners). Winners week of Nov 9.
- Prize: 3 winners x ($5,000 AWS credits + ~$600 swag + certificate). Pool $16,800.
- Eligibility: 18+, builder.aws.com profile, not in excluded countries (India is NOT excluded),
  not Amazon/AWS employee or household member. One entry per person.
- Qualification is PASS/FAIL: (1) article on Builder Center, (2) public repo with OSI license,
  agent source + >=1 clearly labelled reusable Decider decision pattern, (3) public demo video
  < 3 min (YouTube/Vimeo/Facebook/Youku). Plus tags #strands-decider-2b + one pattern tag.
- Rubric: Creativity 30 | Effective use of Decider + Bedrock (incl. pattern quality; measured
  latency/cost = bonus) 30 | Communication 25 | Originality 15.
- Strands Decider 2B: small open experimental model, no text generation; takes state + typed
  question, returns choice / yes-no / score with calibrated confidence (latency measured in /eval; official docs report ~153 ms median warm on Apple M3 Pro, unmeasured on other hardware).
  **We have not verified its interface. Stage 0 spike does that.**
- Judges: AWS SAs / developer advocates (Sunil Divvela, Raghuram, Hardik Mody,
  Elizabeth Fuentes, Mike Chambers). They value reusable patterns, honest engineering, clear demos.

## Landscape (visible in discussion feed, ~60 posts at time of analysis)
| Typical entry | Weakness |
|---|---|
| Domain apps (fraud, medical RAG, waste sorting, cost explainer) | Decider bolted on; pattern is an afterthought |
| Tool-selection triage bot (copied latency claim) | Most crowded pattern; unmeasured claims |
| Human-approval queue (AgentGuard) | Needs human in loop; Java SDK |
| Voice/education assistants | Weak decision pattern |

Registrants (~4.4k) != submissions. Many are team-seekers. Expect a small fraction to clear the gate.

## Our position
Pattern: **#guardrails** (AWS's own example: verify tool-call args are grounded in what the user said).
Because AWS wrote that example, the idea alone is NOT original. We differentiate through:
1. **Provenance-aware grounding** — tool outputs / pasted content / retrieved docs can't ground an
   argument (defeats prompt-injection recipient swaps).
2. **Multi-turn resolution** — "send it to her" grounded against whole user history.
3. **Layer separation** — grounding != authorization; deterministic policy first.
4. **Measured proof** — 150-200 case eval, 5 baselines, threshold curve, honest failures.
5. **A reusable library of typed questions**, not one.

## Top risks
| Risk | Mitigation |
|---|---|
| Decider interface/hardware unknown | Stage 0 spike; adapter; kill criterion end Oct 17 -> fallback #policy |
| Guard too strict (false blocks) or too loose (missed blocks) | Track both; threshold curve; clarify path |
| Not better than regex/LLM-judge | Benchmark cheap baselines; report truthfully; pitch the tradeoff (speed/cost/calibration) |
| Late artifacts fail gate | Video Oct 21, article Oct 22, buffer Oct 23 |
| Bedrock access denied | Test Oct 13-15; us-east-1 / us-west-2 |
| Unmeasured claims | AGENTS.md rule 2 |
