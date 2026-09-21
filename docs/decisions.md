# Design-choice register, and how the project works

Two things live in this file. **Part A** is the decision register: every `[C]`
choice the lab leaves to us, who made it, and why — Partner A's, Partner B's,
and the ones we had to agree on together. **Part B** is the project workflow:
how the four services fit together, how one run travels end to end, how the two
halves were built in parallel without colliding, and what the day-to-day loop
is.

The `[R]` parts come from the contract and from NIST and are not ours to
change. Everything here is.

---

# Part A — The decisions

## A.1 The choices the lab names in §6

The seven the handout explicitly hands to the team.

| Decision | What we chose | Whose call | Why |
|---|---|---|---|
| Language, framework, data store | Python 3. Verifier and RP on `http.server`, standard library only; Subject and CSP on FastAPI + uvicorn; CSP accounts in SQLite, everything else in memory | Both | Runs without sudo on a shared server. The two services carrying the security-critical decisions have no framework debug mode that could leak a stack trace; the two that need a browser-friendly surface get one |
| What identity proofing means here | **Control of an email address.** An applicant posts an address and a chosen password; the CSP mails an activation link there; clicking it finishes the account | Partner A | The evidence is "whoever can read this mailbox". That is honest about what it proves and about what it does not |
| Which IAL we claim | **IAL1, and no higher** | Partner A | IAL1 is self-asserted attributes. We verify one channel and verify no document, so claiming IAL2 would be the more serious error than claiming too little |
| What the authenticator is | **A subscriber-chosen memorized secret**, minimum 15 characters, stored as a salted scrypt record | Partner A, with B enforcing the floor | SP 800-63B-4 §3.1.1.2 sets 15 characters as the floor for a password used as the *sole* authentication factor. There is no second factor anywhere in this system, so the floor applies to every authenticator here. Revision 4 also removes composition rules and periodic rotation, so we impose neither |
| How the assertion travels Verifier → RP | An **opaque, single-use handle** the RP redeems by calling `POST /introspect` on the Verifier | Partner B | It makes `skip_verifier` impossible *by construction* rather than merely rejected: the handle carries no identity, so forging one gains nothing, and the RP has no other way to learn an identifier. A signed JWT is equally defensible, but hands us key management, `alg` confusion and clock skew to defend as well |
| How sessions end | Expiry (`LAB1_SESSION_TTL_SECONDS`, default 600s), explicit revocation on `POST /logout`, and total loss on `POST /reset` | Partner B | The replay scenario needs revocation to be real, not cosmetic. Expiry bounds a stolen credential even when nobody logs out |
| What the protected resource is | The subscriber's own account record, at `GET /protected` | Partner B | Personal data about one subscriber: a plausible reason to protect it, and the natural thing an authenticated subscriber comes to the RP for |
| How the first administrator comes to exist | There is none, deliberately | Both | This lab authenticates only — no authorization roles. The real bootstrap problem here is the **shared token between services**: both tokens are generated at deployment and written to `.env`, so whoever can write that file is the trust anchor. We name that rather than inventing an admin account the lab told us not to build |

## A.2 Partner A's decisions — the enrollment side

Subject agent (`services/subject/`), CSP (`services/csp/`), frontend
(`frontend/`).

| Decision | What | Why |
|---|---|---|
| Enrollment is two steps, not one | `POST /apply` creates the account and issues a token; `POST /subscribe` (or `GET /activate`) redeems it | It puts the Applicant → Subscriber transition on a specific line. One-step enrollment would make the role change invisible, which is the thing this lab exists to make visible |
| Proofing evidence | An activation link mailed to the claimed address (`services/csp/email_service.py`) | The cheapest proofing that proves anything at all. Without a mailed step, "proofing" is a typed string |
| The email is best-effort | Missing `EMAIL_USERNAME`/`EMAIL_PASSWORD` logs a warning and skips the send; enrollment still returns the token in the response body | The graded contract is machine-to-machine. A grader must not need a working SMTP account, and the Subject agent drives step 2 through JSON, never through a mailbox |
| One code path finishes enrollment | `/subscribe` (JSON) and `/activate` (HTML) both call `_complete_subscription()` | Two paths into the same state is two places for the Verifier binding to be skipped. There is one |
| Duplicate applications are refused outright | `POST /apply` refuses any identifier that already has an account, activated or not | Refusing only *activated* ones left an account pre-hijacking path — see A.6, the sharpest finding on the project |
| A chosen password, not an issued random secret | The applicant picks the secret; the probe's `canary` is simply what a scripted applicant picks | Makes it a system a person can log into, and makes §3.1.1.2 apply for real rather than as a quotation |
| Accounts in SQLite, parameterised queries only | `shared/user_database.py` | Accounts must survive a restart; transcripts need not. No query anywhere is built by string concatenation |
| Scenarios live outside the web layer | `services/subject/flow.py` is standard library only; `main.py` is the HTTP surface and nothing else | It is the part with the interesting behaviour, so it has to be testable without a web server in the way. `tests/test_subject_flow.py` drives it directly |
| The frontend proxies, it does not CORS | Vite proxies `/api/csp`, `/api/verifier`, `/api/rp` (`frontend/vite.config.js`) | The backends are a minimal `http.server` subclass with no `OPTIONS` handling. Adding CORS means editing the code the probe grades; a dev proxy keeps the browser same-origin and the graded surface untouched |
| The frontend is opt-in everywhere | Not started by `run_all.sh` unless named; not part of the contract | The default output has to stay exactly "4 of 4 up" — that is what `docs/deployment.md` says to screenshot |
| One denial message in the UI | `"Invalid email or password."` whatever actually failed | The Verifier and RP do not distinguish unknown-identifier from wrong-secret. A helpful UI would hand that distinction straight back to an attacker |

## A.3 Partner B's decisions — the authentication and access side

Verifier (`services/verifier/`), Relying Party (`services/rp/`), `shared/`, and
the scripts.

| Decision | What | Why |
|---|---|---|
| Secret storage | `hashlib.scrypt`, 16-byte random salt per record, N=2^14, r=8, p=1 (`shared/pwhash.py`) | A password hashing function, as the review prompt requires. A bare SHA-256 store is brute-forceable at speed once stolen |
| Where the secret is hashed | At the CSP; the Verifier only ever holds the record | Keeps the number of services touching a plaintext secret at the minimum the model allows — the CSP once at issuance, the Verifier once per check |
| Authenticating the CSP → Verifier edge | Shared token in `X-Lab1-Binding-Token`, from `.env`, compared with `secrets.compare_digest` | Without it, anyone who can reach the Verifier can bind an authenticator to any identifier and become that subscriber. The Verifier trusts the CSP for bindings, so that trust needs a credential behind it |
| Authenticating the RP → Verifier edge | Shared token in `X-Lab1-Introspect-Token` | An unauthenticated introspection endpoint leaks subscriber identifiers and lets an outsider burn valid assertions |
| Where service-to-service calls go | Loopback via `config.internal_endpoint_for()`, never the public URL in `team.json` | All four run on one host. Sending the assertion across the campus network and back puts the load-bearing edge of the design on an untrusted wire — and when we got this wrong it also hung five seconds per request |
| The RP never calls the CSP | `config.endpoint_for("csp")` produces a URL for the 401 body; nothing in `services/rp/app.py` issues a request to it | Figure 3 has no RP → CSP arrow, and neither do the federated variants in Figures 4 and 5. An RP that could query the CSP would be reaching into another service's store, which is the first question the code review asks. A signpost is not a connection |
| Challenge scheme on the 401 | `WWW-Authenticate: Lab1-Session realm="lab1-rp"` (RP), `Lab1-Authenticator realm="lab1-verifier"` (Verifier) | RFC 9110 §15.5.2 requires a challenge on a 401. The scheme name is ours: `Bearer` belongs to OAuth, and this is the non-federated model |
| Quiet denials | One status and one body for every authentication failure, plus equal work on the unknown-identifier path (`burn_equivalent_work`) | A failure must not reveal whether the account existed — including through the clock. Measured: 46.2 ms unknown identifier against 48.1 ms wrong secret |
| Rate limiting | 10 attempts per client address per 60s window on `POST /authenticate`, cleared on success | Keyed on the address rather than the identifier, so knowing a subscriber's identifier cannot lock them out. Loose on purpose, and weak here: every legitimate request in this deployment comes from the same host an attacker's would. `docs/analysis.md` says so rather than claiming otherwise |
| Session credentials | `secrets.token_urlsafe(32)`, expiring, revocable, pinned to the issuing address (`LAB1_RP_PIN_SESSION_TO_CLIENT`) | A cryptographic random source is required. Pinning costs a stolen bearer credential most of its value; it is a setting because a client whose address changes mid-session would be logged out |
| Transcript `step_name` values | The five strings `conformance_probe.py` itself uses, in one table (`shared/transcript.py`) | Only the step *numbers* are fixed by the contract. Matching the probe's strings costs nothing, and one table means four services cannot drift apart |
| Transcript `detail` | Literal strings only, never a request field | Log decisions, never inputs. Enforced twice: the writer rejects a detail that is not a plain description, and `tests/test_no_secret_logging.py` fails the build if any `detail=` is built from a runtime value |
| Timestamps | ISO 8601 UTC, **microseconds** (`shared/timeutil.py`) | See A.5 — milliseconds cost us `H-ORD` |
| Configuration is bilingual | `shared/config.py::setting()` reads `LAB1_X`, then falls back to `X` | Partner A's services already read `TEAM`, `HOST`, `<SVC>_PORT`. One `.env` drives all four rather than two files that disagree |
| Secrets fail closed | `config.require_secret()` refuses to start a service whose token is missing | A default token that "works" in development is a token that ships |

## A.4 The interfaces we had to agree on

The edges where one partner's code calls the other's. They were written down
here **before** either side was built, which is why integration took an
afternoon rather than a week.

1. **`POST /apply` on the CSP** — `{run_id, email, plaintext}` → `201 {token}`.
   Records **step 1 with `actor: "applicant"`**, the only place that role
   appears and the one `H-ROL` reads.
2. **`POST /subscribe` on the CSP** — `{run_id, email, token}` → `200`. Records
   **step 2**, which `H-ST2` looks for at the CSP, not at the Verifier.
3. **`POST /binding` on the Verifier** — called by the CSP at enrollment, with
   `X-Lab1-Binding-Token` and `{run_id, identifier, verifier_record}`, where
   `verifier_record` is the output of `shared.pwhash.hash_secret(...)`. Answers
   `201`, `409` if the identifier is already bound, `401` without the token.
4. **`POST /authenticate` on the Verifier** — `{run_id, identifier,
   authenticator_output}` → `200 {assertion}` or `401`. Records **step 4** with
   `actor: "claimant"`.
5. **`POST /session` on the RP** — `{run_id, assertion}` →
   `201 {session, expires_at, identifier}`.
6. **`Authorization: Lab1-Session <token>`** on `GET /protected` and
   `POST /logout`.
7. **`X-Run-Id` on `GET /protected`**, because that request has no body and
   step 3 still has to land under the right run.
8. **Identifiers** match `^[a-z0-9][a-z0-9._+@-]{2,253}$` and are case-folded
   (`shared/validate.py`). The `@` and `+` are there because the CSP identifies
   subscribers by email; folding is there because `Alice@` and `alice@` must
   not become two accounts for one person.

If any of these has to change, it changes **here first, then in code** —
`PROJECT_WORKFLOW.md` §13's integration rule.

## A.5 On timestamp precision

`shared/timeutil.py` emits **microseconds**, not milliseconds. The probe sorts
events by the timestamp *string* alone, with a stable sort, so two events a
fraction of a millisecond apart — the CSP recording step 2 and the Subject
recording step 3 — tie, and the tie is broken by the order the probe collected
the transcripts in, which is not chronological. At millisecond precision that
inversion failed `H-ORD` on most runs, showing up as the step sequence
`[1,1,2,3,2,4,3,4,5,5,5]`.

It was caught by `tests/test_subject_flow.py`, not by reasoning about it.
`scripts/trace.py` now sorts exactly the way the probe does, so the table we
look at is the order that gets graded.

## A.6 On a duplicate application, before the first one is activated

`POST /apply` refuses **any** identifier that already has an account, whether
or not it has been activated. Refusing only the activated ones looked
equivalent and was not; the cross-review test in
`tests/test_partner_a_negative.py` found the difference the first time it had a
live CSP to talk to.

The attack it left open is account pre-hijacking:

1. Alice applies. A row is created with her password hash, and an activation
   link is mailed to her. She has not clicked it yet.
2. Mallory applies for `alice@example.com` with a password Mallory chose. The
   row is overwritten — Mallory's hash, a fresh token — and that token is
   mailed to Alice, because the CSP only ever mails the address on the
   application.
3. Alice clicks the link in her own mailbox and activates an account whose
   password belongs to Mallory.

Every request in that sequence is well-formed, no cryptography is involved, and
the victim performs the final step herself.

The cost of the fix is that an address with a pending application cannot be
re-applied for, so an attacker can squat an address the real owner has not
claimed yet, and a user who mistyped their password before activating has to
wait. Expiring pending applications is the usual remedy; we have not built it,
and say so rather than pretending the fix is free.

It also means `/apply` answers `409` for an address that exists and `201` for
one that does not, which is an enrollment-time account-existence oracle. That
is a deliberate trade: hiding it means answering `201` to everyone and moving
the refusal into the email, which is the right design for a real system and
more machinery than this lab needs. The **authentication** path leaks nothing —
the Verifier's denial is byte-identical for an unknown identifier and a wrong
secret.

---

# Part B — The project workflow

## B.1 The shape of the thing

Four processes, one per box in Figure 3, on one host, inside one trust
boundary. A fifth — the React frontend — sits outside the graded contract and
exists so a person can drive the same flow a browser-shaped way.

```
    frontend :5173        (opt-in, not graded; Vite proxies all three)
         |  /api/csp    /api/verifier    /api/rp
         v        v            v            v
 +--------------+  +--------------+  +--------------+  +--------------+
 | Subject :4100|  |   CSP  :4101 |  |Verifier :4102|  |    RP  :4103 |
 |  Partner A   |  |  Partner A   |  |  Partner B   |  |  Partner B   |
 +--------------+  +--------------+  +--------------+  +--------------+
        |                 |                 ^ ^               |
        |  drives all     | POST /binding   | |  POST         |
        |  five steps     +-----------------+ +--/introspect--+
        |
        +--> POST /apply, /subscribe, /authenticate, /session, GET /protected
```

Every arrow is HTTP with a JSON body, over loopback. Only two edges carry a
shared token — CSP → Verifier and RP → Verifier — and both come from `.env` and
both fail closed.

## B.2 One run, end to end

This is what `python3 scripts/walkthrough.py` shows one screen at a time. A
`run_id` threads through all of it and every service tags its own events with
it, so a grader can isolate one run out of a hundred.

| # | Who | Calls | What changes | Transcript |
|---|---|---|---|---|
| 1 | Applicant | `POST csp/apply` | account row created, password hashed with scrypt, token minted, activation mail sent | CSP writes **step 1**, `actor: applicant` |
| 2 | Applicant | `POST csp/subscribe`, or clicks `/activate` | account marked subscribed | CSP writes **step 2** |
| 2b | CSP | `POST verifier/binding` | Verifier stores `identifier → scrypt record` | Verifier writes **step 2** |
| — | | | **Applicant becomes Subscriber** | |
| 3 | Subscriber | `GET rp/protected`, no session | nothing | RP writes **step 3**, `actor: subscriber`, answers `401` + `WWW-Authenticate` |
| — | | | **Subscriber becomes Claimant** — the 401 is what makes it | |
| 4 | Claimant | `POST verifier/authenticate` | output checked against the record, single-use handle minted | Verifier writes **step 4**, `actor: claimant` |
| 5 | Claimant | `POST rp/session` | RP calls `verifier/introspect`, gets the identifier back, mints a session | Verifier and RP both write **step 5** |
| 5b | Subscriber | `GET rp/protected`, with the session | resource served | RP writes **step 5** |

### The five scenarios, as sequences

`happy_path` is the table above. The other four are the same sequence,
truncated or twisted at one specific point — which is the point each one is
testing.

| Scenario | What changes | Where it stops | Required outcome |
|---|---|---|---|
| `happy_path` | — | reaches `GET /protected` → `200` | `success` |
| `wrong_authenticator` | step 4 presents something other than the enrolled secret | the Verifier answers `401`; `/session` is never called, so **no step 5 succeeds** | `denied` |
| `unenrolled_claimant` | steps 1–2 skipped entirely | the Verifier answers `401` — **byte for byte the same** as the line above, and that sameness is the point | `denied` |
| `replay` | full happy path, then `POST /logout`, then the same credential again | the reuse is `401`. A successful step 5 **earlier in this run is expected and allowed** — what must fail is the reuse | `denied` |
| `skip_verifier` | enrolled and bound, then straight to `POST rp/session` with a self-made handle, no Verifier call | introspection fails, so the RP never learns an identifier | `denied` |

Two ordering constraints are easy to get wrong and both are graded. Step 3 —
the unauthenticated `GET /protected` — has to happen **before** authentication,
because `H-ORD` sorts by timestamp and a `/protected` call made only at the end
puts step 3 after step 5. And the `run_id` the harness supplies has to be
threaded into every call and every event in **all four** services, or
`H-ST1`–`H-ST5` look under the wrong run and find nothing.

All five are implemented in `services/subject/flow.py` — standard library only,
no FastAPI import — so `tests/test_subject_flow.py` can drive them against the
real Verifier and RP without a web server in the way. `POST /run` is three
lines that call `Flow.run(...)`.

The two role changes are single, findable lines, not implied: they are
commented `ROLE CHANGE` in `services/subject/flow.py`. That is the whole reason
the Subject is a program in this lab rather than a person.

## B.3 Why the RP has no arrow to the CSP or the Applicant

Worth stating, because it looks like a gap and is not.

The RP meets the subject only as a **Subscriber** or a **Claimant**. An
Applicant is someone the RP has never heard of and has no business knowing
about. And the RP never asks the CSP anything: if it could, "is this person
authenticated?" would have two possible answers, and the one that does not
involve the Verifier is the one an attacker would use. The only way the RP ever
learns an identifier is the `/introspect` response, which is why
`skip_verifier` is refused by construction rather than by a check somebody
could forget to write.

What the RP *does* do is hand a stranger two URLs — `enroll_at` and
`authenticate_at`, in both the public page and the 401 body — so someone who
was never enrolled has somewhere to go. No request leaves the RP for either.

## B.4 How the two halves were built in parallel

The split follows the lab's §4.1 suggestion: enrollment with one partner,
authentication and access with the other.

| | Partner A | Partner B |
|---|---|---|
| Services | Subject `:4100`, CSP `:4101` | Verifier `:4102`, RP `:4103` |
| Also | the React frontend | `shared/`, the scripts, the deployment doc |
| Negative tests written | for **B's** services | for **A's** services (`tests/test_partner_a_negative.py`) |

Four working rules kept this from becoming a merge conflict:

1. **`shared/` is jointly owned and changes by agreement.** One transcript
   writer, one timestamp helper, one hashing module, one validator. Two copies
   of the event shape is the drift `PROJECT_WORKFLOW.md` §10 warns about — and
   we carried a stale duplicate of the account store for a while before
   noticing, which is how we know the rule is real.
2. **Interfaces are written in A.4 before they are written in code.** Both
   sides build against the register, not against each other's half-finished
   service.
3. **Each partner writes the *negative* tests for the other's services.** You
   test your own code for what it should do; somebody else has to test it for
   what it should refuse. Every one of those tests carries a one-sentence
   comment naming the attack it defends against.
4. **Both partners can explain all four services.** The rubric's System
   Understanding row is scored off-script, on the two services you did not
   build.

## B.5 The day-to-day loop

```bash
# 1. start everything, one log per service under run/
sh scripts/run_all.sh
sh scripts/run_all.sh subject csp verifier rp frontend   # + the React UI

# 2. watch a run happen, one Figure 3 step per screen
python3 scripts/walkthrough.py                # or --all, or any one scenario

# 3. see what the four transcripts recorded, merged and in probe order
python3 scripts/trace.py --last

# 4. the unit suite: 85 tests, one command, never touches a deployment
python3 -m unittest discover -s tests -t .

# 5. the same script the instructor runs
python3 conformance_probe.py --config team.json --json result.json
python3 scripts/diagnose.py result.json       # a failed check -> the next command

# 6. the whole presentation, in order
sh scripts/demo.sh
```

Step 3 repays the most. `POST /run` answers with a verdict, which is what the
probe wants and the opposite of what a person debugging needs; the transcripts
are where the run actually is.

## B.6 What to do when the halves disagree

1. Reproduce it with `scripts/walkthrough.py`, which shows the failing hop
   rather than the verdict.
2. If the shape of an interface is wrong, fix **A.4 in this file first**, then
   both sides of the code.
3. If a probe check fails, `scripts/diagnose.py --check <ID>` says what that
   check is asking and what to run next, before anyone edits a service.
4. If a cross-review test fails, that is the other partner's service and the
   other partner's fix — and the finding goes into `docs/adversarial.md`
   whether or not it turns out to be exploitable.

## B.7 What is left

Tracked in `docs/requirements-checklist.md`: every requirement in the handout
and the rubric against what is actually in the repository, including the rows
that are still missing.
