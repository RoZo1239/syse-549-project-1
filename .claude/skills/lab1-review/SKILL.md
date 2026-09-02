---
name: lab1-review
description: Run the six-question security review used to grade the NIST SP 800-63-4 Figure 3 lab, and scan the archive for secrets before submitting. Use when asked to review, audit, self-check, or "see if this would pass" for any of the four services; before packaging the zip; and after finishing any service that touches secrets, assertions, sessions, or denial paths. Also use when someone wants to know whether the RP can be tricked into accepting an unverified identity, or whether a failure message leaks whether an account exists. Judge the review's own output afterwards — that critique is worth credit.
---

# The six-question review

This is the exact review the work is graded against. Answer these six and nothing else — do not comment on style, performance, or anything outside the list; noise here buries the findings that matter.

1. **Separation of roles.** Are the CSP, Verifier and RP genuinely separate, or does one reach into another's data or responsibilities? Specifically: does the RP ever see or handle the authenticator secret? It must not.
2. **Verification is real.** Trace the path by which the RP decides a subject is authenticated. Can that decision be reached without the Verifier having actually checked an authenticator? Quote the exact lines that make the decision.
3. **Secret handling.** Are authenticator secrets stored salted and hashed with a password hashing function (`scrypt`, `argon2`, `pbkdf2` — not a bare SHA-256 or MD5)? Do secrets appear in logs, transcripts, error messages, URLs, or committed files?
4. **Denial behavior.** On failed authentication, does the system reveal whether the account existed? Are failures returned as `401` with a `WWW-Authenticate` header? Do error responses leak stack traces, file paths, or SQL?
5. **Input validation.** Are identifiers and request bodies validated before use? Is there any injection path into the data store?
6. **Session credentials.** Are they generated from a cryptographic random source (`secrets`, `os.urandom`, `crypto.randomBytes`) rather than a predictable one? Do they expire? Can they be revoked?

## Output format

For each question, exactly:

```
Q<n>. <question name>
  Verdict:  PASS / CONCERN / FAIL
  Evidence: <file>:<line> — <the relevant code, quoted>
  <one sentence of explanation>
```

Then a suggested band with one sentence of justification:

- **10** — clean separation, no secret exposure, denials correct and quiet
- **7** — works and is comprehensible, one or two real weaknesses
- **4** — functional but one significant flaw (bypassable check, logged secret, leaked internal error)
- **0** — not reviewable, or credentials stored in plaintext

**Rules:** cite file and line for every claim · if evidence cannot be found, write "no evidence found" rather than inferring · do not speculate about code you were not shown · do not award a band higher than the evidence supports.

## Then judge the review

An automated review is a set of hypotheses, not a verdict. Two known biases, worth stating in the written analysis:

- **Questions 4 and 5 get over-reported** — deliberate design choices get flagged as flaws.
- **Question 2 gets under-reported**, and it is the one that matters most, because answering it honestly means tracing control flow rather than pattern-matching on names. If the review says PASS on question 2, check it against the `skip_verifier` probe result. When the two disagree, the probe is the better evidence.

Write one paragraph on where the review was wrong. Telling a real finding from a false positive is the actual skill being assessed, and it is strong material for the presentation's chosen-topic segment.

## Archive hygiene — before zipping

```bash
sh .claude/skills/lab1-review/scripts/hygiene_scan.sh .
```

A signing key, a real `.env`, or a live database file in the archive is an automatic deduction. Ship `.env.example` with placeholder values instead. Also confirm: no virtual environment, no `node_modules`, under 25 MB, and `result.json` present from a run against the deployed system.
