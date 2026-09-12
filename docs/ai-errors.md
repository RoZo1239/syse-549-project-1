# Where the assistant was wrong

Required material for the written analysis. One entry per error: what it
claimed, what was actually true, and how we found out.

---

### 1. Internal calls routed through the public campus URL

**Claimed:** the RP should find the Verifier through the endpoint list in
`team.json` — one config source for every lookup, which reads like good practice.

**Actually:** `team.json` holds the *public* URLs the probe uses from outside.
Using them for the RP → Verifier introspection call sent traffic from the host
out to the campus network and back, put the design's load-bearing edge on an
untrusted wire, and — because that host was not reachable from the development
machine — made `POST /session` hang for five seconds and then fail closed with
`503`.

**Found by:** running the two services as real processes and driving the flow
with `curl`. The unit tests all passed, because they set `LAB1_VERIFIER_URL`
explicitly and never exercised the default.

**Fixed in:** `shared/config.py` (`internal_endpoint_for`) and
`services/rp/app.py:50`. Introspection now goes to loopback; the public URL is
used only for the `authenticate_at` hint in the `401`, where the reader really is
outside.

**Lesson for the presentation:** the assistant optimised for tidiness (one
config source) over a trust-boundary question (which side of the boundary is
this call on?). A test suite that mocks the boundary cannot catch it.

---

### 2. A confident "timing leak" that was its own rate limiter

**Claimed:** after measuring, the assistant reported that an unknown identifier
returned in 1 ms against 40 ms for a wrong secret on a real account — an account
enumeration oracle in the timing, despite the equalising code written
specifically to prevent it.

**Actually:** the measurement loop sent six requests from one address, which
tripped the Verifier's own rate limiter on the sixth; the "1 ms" was a `429`
short-circuit, not a fast denial. Re-measured with a fresh source address per
attempt: 46.2 ms unknown against 48.1 ms wrong, a 1.9 ms difference on a ~47 ms
baseline. The equalising code was working the whole time.

**Found by:** noticing that the follow-up probes in the same sweep also failed,
in a way that only made sense if the Verifier was refusing everything.

**Lesson:** an assistant reports a measurement with the same confidence whether
or not the measurement measures what it says. The second reading is not optional.
The episode did surface a genuine finding, though — see entry 3.

---

### 3. Rate limiting tuned as if the attacker were somewhere else

**Claimed:** five failed attempts per client address per minute, "a reasonable
default".

**Actually:** all four services run on one host, and the Subject agent — which
makes every legitimate authentication attempt in the system — runs there too.
Every request, honest or hostile, arrives from the same address. A five-attempt
limit is therefore mostly a way for a probe run to lock itself out, and only
incidentally a defence. Raised to ten, cleared on success and on `POST /reset`,
and named as a weakness in `docs/analysis.md` rather than presented as a control.

**Lesson:** a control copied from a normal deployment can be worse than useless
in an unusual one. The question is never "is this a good default", it is "what
does this default do *here*".

---

### 4. NIST citations cannot be verified from this environment

**Claimed:** nothing yet — this is a standing constraint rather than a specific
error, and it is logged because it is the one most likely to produce one.

**Actually:** SP 800-63-4 and its companion volumes are not reachable from the
environment the assistant runs in, so no section number it produces has been
checked against the document. SP 800-63B-3 was withdrawn in August 2025 and
Revision 4 reverses its best-known password guidance, so a fluent, plausible
citation is exactly the failure mode to expect.

**Consequence:** every NIST reference in `docs/decisions.md` and
`docs/analysis.md` is marked for checking against the PDF before it reaches a
slide. The two claims we are prepared to defend as written are RFC 9110 §15.5.2
(a `401` must carry `WWW-Authenticate`) and the prohibition on knowledge-based
authentication — and both still get read out of the source before the
presentation.

---

### 5. Two provided scripts were broken, and the assistant nearly reported their output as ours

**Claimed:** initially, that `smoke.sh` was reporting our `/transcript`
endpoints as invalid JSON.

**Actually:** the script's `/transcript` check piped the response into
`python3 - <<'PY'`, where the here-document and the pipe both claim stdin. The
here-document wins, so the program always read an empty payload and every
service — ours, anyone's — was reported as invalid JSON. The same pattern broke
the step-coverage check under `--full`. Separately, `attack_curls.sh` invoked
`curl` through an unquoted `$@`, which split `-H 'Authorization: Bearer ...'`
into three words, so the "forged token" probe sent an empty header and tested
nothing.

**Found by:** checking our own `/transcript` output by hand after the script
disagreed with the unit tests.

**Fixed in:** `.claude/skills/lab1-conformance/scripts/smoke.sh` (payload passed
through the environment) and `.claude/skills/lab1-adversary/scripts/attack_curls.sh`
(`"$@"`), with both `dist/skills/*.skill` packages rebuilt.

**Lesson:** the tool disagreeing with your tests is a hypothesis about your code,
not a verdict on it.
