# Requirements checklist

Every requirement in the lab handout and the rubric, against what is actually
in this repository. Kept honest on purpose: a row marked **missing** is worth
more to us than a row marked done that isn't.

Status: **done** · **partial** · **missing** · **not ours** (instructor or
Canvas side).

---

## 1. The frozen contract (lab §5)

| # | Requirement | Where | Status |
|---|---|---|---|
| 5.1 | `GET /health` on all four, correct `service`, `team`, `spec_version` | all four services | done |
| 5.1 | `GET /transcript` with the frozen event shape | `shared/transcript.py`, one writer for all four | done |
| 5.1 | `step` 1–5 matching the §3 table | `STEP_NAMES` in `shared/transcript.py` | done |
| 5.1 | `actor` one of the six allowed values | `ACTORS` in `shared/transcript.py` | done |
| 5.1 | `outcome` is `success` or `denied` | enforced by the writer | done |
| 5.1 | Sub-second `ts` | **microseconds**, `shared/timeutil.py` | done |
| 5.1 | Never an authenticator secret in a transcript | `DETAIL_RE` rejects non-literal details; `tests/test_no_secret_logging.py` scans the sources with the AST | done |
| 5.1 | `POST /reset` returns 200 or 204 | all four | done |
| 5.2 | RP `GET /` returns 200 with no credential | `services/rp/app.py` | done |
| 5.2 | RP `GET /protected` returns 401 without a session | same | done |
| 5.2 | That 401 carries `WWW-Authenticate` (RFC 9110 §15.5.2) | `CHALLENGE` constant | done |
| 5.2 | 200 with the protected content when a session is presented | same | done |
| 5.3 | Subject `POST /run` with the four-field response | `services/subject/main.py` + `flow.py` | done |
| 5.3 | `run_id` tagged on events in **all four** services | every `transcript.record` call; `X-Run-Id` header carries it onto `GET /protected` | done |
| 5.4 | `happy_path` → success | `flow.py` | done |
| 5.4 | `wrong_authenticator` → denied, no successful step 5 | `flow.py` | done |
| 5.4 | `unenrolled_claimant` → denied, no successful step 5 | `flow.py` | done |
| 5.4 | `replay` → denied on reuse | `flow.py`, RP revokes on logout | done |
| 5.4 | `skip_verifier` → denied, no successful step 5 | unreachable by construction: the RP's only source of an identifier is `/introspect` | done |

## 2. Ports and the server (lab §4)

| Requirement | Status | Note |
|---|---|---|
| Four consecutive ports claimed on the Canvas discussion | done | `hayagreeva-jonathan`, 4100–4103 |
| `team.json` and `.env.example` carry the claimed block | done | |
| Bind `0.0.0.0`, not `127.0.0.1` | done | `.env.example` default, with the reason written next to it |
| Each partner owns at least two running services | done | A: subject + CSP. B: verifier + RP |
| Both partners can explain all four | **partial** | the rehearsal where each presents the other's two has not happened |
| Reachable from campus on the claimed ports | **open** | the server's firewall notes admit `4000:4009`; whether 4100–4103 are directly reachable or must go through nginx is the question for the instructor, `docs/deployment.md` step 2.0 |

## 3. Testing (lab §7)

| Requirement | Where | Status |
|---|---|---|
| Probe run early and often | `conformance_probe.py`, plus `scripts/diagnose.py` to read the result | done |
| Suite runs from a single command | `python3 -m unittest discover -s tests -t .` — 88 tests | done |
| Suite does not touch the live database | every test uses ephemeral ports and in-process state | done |
| Positive tests: enrollment, verification, session | `test_verifier.py`, `test_rp.py`, `test_subject_flow.py` | done |
| Wrong authenticator rejected without revealing the account exists | `test_verifier.py` | done |
| Expired session rejected, without `sleep()` | `_mint_session` test seam mints an already-expired one | done |
| Tampered assertion rejected | `test_rp.py` | done |
| RP rejects an assertion it cannot attribute to our Verifier | `test_rp.py` | done |
| Duplicate and malformed enrollment rejected | `test_partner_a_negative.py` | done |
| Rate limiting actually engages | `test_shared.py` | done |
| One sentence per denial test naming the attack | every `test_denies_*` | done |
| The adversarial hour | `docs/adversarial.md`, 13 probes | done |

## 4. Deliverables (lab §9)

| Requirement | Status | What is left |
|---|---|---|
| `lab1-hayagreeva-jonathan.zip`, under 25 MB | **missing** | `sh scripts/package.sh` once `result.json` exists — it refuses to build until the archive would be correct |
| Source for all four services | done | |
| `README.md`: four URLs with ports | done | |
| `README.md`: how to run from a clean checkout | done | |
| `README.md`: the single test command | done | |
| `README.md`: who built what | done | |
| Test suite in the archive | done | |
| `result.json` from the **deployed** system | **missing** | the blocker for the archive; last deployed run was 21 of 24 and the three failures are not yet identified |
| No virtualenvs, `node_modules`, database files | done | all in `.gitignore`; `frontend/node_modules` is excluded |
| No secrets: no keys, no real `.env`, no live hashes | done | `.env.example` has placeholders only; verify again with `sh .claude/skills/lab1-review/scripts/hygiene_scan.sh` before zipping |
| Written analysis, 2–3 pages | **partial** | `docs/analysis.md` is complete in content; it has not been exported to PDF |
| — a diagram of what we built, mapped to Figure 3 | done | `docs/analysis.md` §1 |
| — the design decisions and why | done | §2, full register in `docs/decisions.md` |
| — two of five steps defeated without breaking cryptography | done | §3: step 1 (enrollment fraud) and step 5 (bearer-credential theft), plus step 4 by relay |
| — the weakest point, named plainly | done | §4 |
| — where an AI assistant misled us | done | §6, detail in `docs/ai-errors.md` |

## 5. Presentation (lab §10)

| Segment | Time | Status |
|---|---|---|
| Architecture mapped onto Figure 3 | 4 min | slides done |
| Live run of five steps + at least two denials | 7 min | `sh scripts/demo.sh` runs the happy path and three denials; **not yet rehearsed against the deployment** |
| Chosen topic | 6 min | **not chosen** — `docs/analysis.md` §3 and §4 are the two strongest candidates |
| Questions | 3 min | — |
| Both partners speaking | — | planned |
| Services running when the slot begins | — | **open**, same as the campus-reachability row above |
| Narrate the authoritative guidance out loud | — | built into `scripts/walkthrough.py`: every step prints its SP 800-63-4 or RFC 9110 line |
| Know what to say while it runs | — | `docs/demo-script.md` — the flow in plain words, the denials, and what to do if it breaks live |

## 6. Rubric rows the handout does not spell out

| Row | Points | Where our evidence is |
|---|---|---|
| Live Demo | 10 | `scripts/demo.sh`, and the guidance narration above |
| Technical Content | 8 | `docs/decisions.md` — the middle column, what we rejected |
| Conformance Testing | 10 | `result.json`, once it exists |
| System Understanding | 7 | the cross-partner rehearsal, **not yet done** |
| Code Review | 10 | `docs/security-review.md` — the six questions, run on ourselves |
| System Architecture | 5 | `docs/analysis.md` §1 and its diagram |

---

## What is actually left

Ordered by what blocks what. Items 1–3 are one afternoon on campus and they
unblock everything else.

### Blocking — nothing else in §9 can finish without these

1. **Get `result.json` from the deployment.** It is the graded number for the
   Conformance Testing row (10 points) and the archive cannot ship without it.
   From a campus machine or the VPN:
   ```bash
   python3 conformance_probe.py --config team.json --json result.json
   ```
2. **Identify the three checks failing there.** The same code scores 24 of 24
   on one host, so this is a deployment difference, not a code one — do not
   start editing services. Feed the result file to the explainer:
   ```bash
   python3 scripts/diagnose.py result.json
   ```
   Most likely cause, unconfirmed until the IDs are known: one side of the
   deployment is still running pre-merge code, and a Subject sending `canary`
   against a CSP expecting `plaintext` would take the `H-*` and `N-*` groups
   down together. Redeploy both halves from this branch first and re-run.
3. **Settle the campus-reachability question with the instructor.** 4100–4103
   directly, or proxied through nginx? The server's firewall notes admit
   `4000:4009` only. `docs/deployment.md` §2.0 has the test to run and the
   exact `ufw` rule to ask for. Every row in §2 and §5 above waits on this.

### Deliverables, after 1–3

4. **Export `docs/analysis.md` to PDF.** The content is complete — diagram,
   decisions, two steps defeated without cryptography, the weakest point, where
   the AI misled us, and a critique of the automated review. It has never been
   rendered.
5. **Build `lab1-hayagreeva-jonathan.zip`** from a clean checkout. Run
   `sh .claude/skills/lab1-review/scripts/hygiene_scan.sh .` first; the only
   expected complaints are `__pycache__`, `.env` and the scanner matching its
   own search pattern.

### Presentation

6. **Pick the chosen topic** (6 minutes, and it feeds the Technical Content
   row). Three candidates, in order of how much of our own work they draw on:
   - **Account pre-hijacking at enrollment** — our own finding, found by a test
     rather than by reading code, with a fix whose costs we can name. Written
     up in `docs/decisions.md` A.6 and `docs/adversarial.md` §14.
   - **Bearer credentials and what sender-constraining would change** — we
     already pin sessions to an address and can say exactly how little that
     buys on a single-host deployment.
   - **Why the RP never calls the CSP**, and what a self-asserted login would
     cost — `docs/decisions.md` B.3, and it maps onto SP 800-207's PEP/PDP
     split.
7. **Rehearse `sh scripts/demo.sh` against the deployment**, not against
   localhost. Off campus, remember `LAB1_PROBE_CONFIG=team.local.json`.
8. **The cross-partner rehearsal**: each partner walks through the *other*
   partner's two services, and traces one request end to end through all four.
   This is the System Understanding row (7 points), it is scored entirely
   off-script, and it costs one hour.
9. **Update the deck** with what has landed since it was built: the
   pre-hijacking finding, the frontend now driving all five steps, and the
   honest two-number probe story. Also note the deck has never been visually
   rendered — no converter was available — so open it once before the slot.

### Optional, not required

10. **Demo the browser flow as well as the scripts.** It works end to end now,
    and with `VITE_API_HOST` pointed at the server the five steps cross a real
    interface for a Wireshark capture. `docs/deployment.md` §1.5b.
11. **Expire pending applications** in the CSP. It would remove the address
    -squatting cost of the pre-hijacking fix. Named as not-built in
    `docs/decisions.md` A.6 on purpose — a known, stated limitation reads
    better than a silent one.

### Explicitly not ours

- The Canvas port-claim post (done), the nginx configuration, and whether the
  instructor wants proxied URLs in the probe config.
