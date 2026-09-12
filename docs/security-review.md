# Six-question security review — Partner B's services

The review in `PROJECT_WORKFLOW.md` §12 stage 7, run against `services/verifier`
and `services/rp` as they stand. Partner A's Subject agent and CSP are not
implemented yet and are not reviewed here; where an answer depends on them, that
is said rather than assumed.

---

**Q1. Separation of roles**

  Verdict:  PASS
  Evidence: `services/rp/app.py:139` — `self.verifier_url + "/introspect"` is
            the only route by which the RP learns an identifier; there is no
            import of the Verifier's module and no shared store anywhere in
            `services/rp/app.py`.
            `tests/test_no_secret_logging.py:50` asserts the strings
            `authenticator_output`, `verify_secret` and `pwhash` do not appear
            in the RP's source at all.
  The three services hold separate state in separate processes and speak only
  over HTTP, and the RP has no code that could handle an authenticator secret.

**Q2. Verification is real**

  Verdict:  PASS
  Evidence: `services/rp/app.py:153` —
            `if status != 200 or body.get("active") is not True or not isinstance(identifier, str):`
            followed by `return 401, DENIAL, ...` at `:159`; the identifier used
            for the session at `:161`-`:170` comes from `body`, the Verifier's
            introspection response, never from the request.
  Trace: `POST /session` accepts only an opaque handle, calls the Verifier, and
  the only branch that reaches `self._sessions[token] = {...}` (`:165`) is the one where
  the Verifier answered `active: true` with an identifier — an unreachable
  Verifier returns `503` at `services/rp/app.py:149`, so there is no fail-open
  path either. Confirmed against the probe's question directly: a self-asserted
  identity, a forged handle, an empty body and a redeemed handle all return
  `401` with no session (`tests/test_rp.py:test_denies_a_self_asserted_identity`).

**Q3. Secret handling**

  Verdict:  PASS
  Evidence: `shared/pwhash.py:33` — `hashlib.scrypt(...)` with a per-record
            16-byte salt from `secrets.token_bytes`, compared with
            `hmac.compare_digest` at `shared/pwhash.py:81`.
            `services/verifier/app.py:169` — `verify_secret(output, binding["record"])`
            is the only use of the presented output; it is never stored,
            returned, or passed to a transcript.
  Every `detail=` written to a transcript is a literal string, enforced
  statically by `tests/test_no_secret_logging.py:43` and at the writer by
  `shared/transcript.py:DETAIL_RE`; the canary was absent from every transcript
  in a live run.

**Q4. Denial behavior**

  Verdict:  PASS
  Evidence: `services/verifier/app.py:45` — one `DENIAL` body,
            `{"error": "authentication_failed"}`, returned at `:155`, `:167`
            and `:174`, i.e. for a malformed request, an unknown identifier and
            a wrong secret alike, each with
            `{"WWW-Authenticate": CHALLENGE}`.
            `services/verifier/app.py:162` — `burn_equivalent_work(output)`
            equalises the unknown-identifier path (measured 46.2 ms against
            48.1 ms for a wrong secret).
            `shared/service.py:handle` returns `{"error": "internal_error"}`
            and prints the traceback to stderr, so no stack trace, path or
            framework banner reaches a response.
  A live sweep returned `400` for garbage JSON, `404` for an unknown path and
  `405` for a wrong method, each a bare JSON error.

**Q5. Input validation**

  Verdict:  PASS
  Evidence: `shared/validate.py:IDENTIFIER_RE` — `^[a-z0-9][a-z0-9._-]{2,63}$`,
            applied at `services/verifier/app.py:103` and `:148` before the
            identifier is used as a key; `shared/service.py:MAX_BODY_BYTES`
            caps a request body at 16 KB and rejects a non-object JSON body.
  There is no dynamic query anywhere — state is a dictionary keyed by validated
  strings — so there is no injection path into a store to close.

**Q6. Session credentials**

  Verdict:  CONCERN
  Evidence: `services/rp/app.py:162` — `token = secrets.token_urlsafe(32)`;
            `services/rp/app.py:217` — `_lookup_session` refuses a revoked,
            expired, or wrong-address credential.
  The credential itself is sound: cryptographic source, expiring, revocable, and
  pinned to the address it was issued to. The concern is what it is — a bearer
  credential sent in a header over plain HTTP, because the lab is deployed
  without TLS. Anyone who can read one request can replay it from the same
  address, and in this deployment every legitimate request comes from that same
  address. Pinning raises the cost; it does not remove the exposure.

---

**Suggested band: 10** — the roles are genuinely separate, no path lets the RP
see an authenticator secret or decide "authenticated" without the Verifier, and
denials are uniform and quiet. The Q6 concern is a property of the deployment
the lab prescribes (plain HTTP), not of the code, and it is named rather than
hidden.

## Judging the review

Two of these verdicts deserve less confidence than the format gives them.

**Q2 is the one that matters and the one an automated pass under-reports**, because
answering it honestly means tracing control flow rather than matching on names.
The PASS above is only worth something because the structure makes the failure
impossible rather than merely unhandled: the assertion is an opaque handle, so
there is nothing for the RP to trust *except* the Verifier's answer. If we had
chosen a signed JWT, the same review would have produced the same PASS from the
same reading, and it would have been worth much less — the interesting failure
would have moved into signature verification and `alg` handling, where a
name-matching review does not look. When the review and the `skip_verifier`
probe result disagree, the probe is the better evidence; here they agree, and
the reason they agree is architectural.

**Q4 and Q5 are where an automated review over-reports**, and where this one is
softer than it looks. A generic pass would likely have flagged the `429` from
the rate limiter as an information leak — it does tell an attacker they have
been noticed — and would probably have flagged `authenticate_at` in the `401`
body as leaking internal topology. Neither is a flaw: the first is the visible
half of a control we chose deliberately, and the second is the address of a
service that is published in `team.json` anyway. Conversely the same review
style would not notice the thing that actually weakens Q4 here, which is that
the rate limit is nearly useless in a deployment where every request shares one
source address. Telling a real finding from a plausible-looking one is the skill
being assessed, and the difference in both directions is judgement about *this*
deployment, not about the pattern.
