---
name: lab1-adversary
description: Attack your own NIST SP 800-63-4 Figure 3 system before someone else does — the required adversarial hour, the negative test suite, and the written-analysis question "how does an attacker defeat two of the five steps without breaking any cryptography". Use when asked to red-team, break, stress, or find the weakest point in the lab's enrollment, authentication, assertion, session, or account-recovery paths; when writing denial tests; and when preparing the presentation's chosen-topic segment. Attacks target only your own team's claimed ports, never another team's.
---

# Attack your own system

Real breaches rarely break cryptography. They convince a help desk to reset the wrong account, phish a credential, steal a session token, or walk in through an account-recovery path that quietly bypasses every control the front door had. All four of those live in the five steps of this lab. The goal here is to find yours before the presentation.

**Scope rule:** only the endpoints your team claimed. Probing another team's ports needs their written permission and the instructor's — without both, do not send the request.

## The adversarial hour

Roughly an hour with `curl`, against your own deployment. Start with these:

```bash
sh .claude/skills/lab1-adversary/scripts/attack_curls.sh team.json
```

The script runs the five probes the lab names — a made-up token at `/protected`, a direct call to the Verifier with an identifier that was never issued, binding an authenticator to somebody else's account, a duplicate enrollment, and a valid session replayed from a different client. Adapt the request bodies to your own API; the script prints what it sent and what came back so a surprising result is easy to spot.

"We tried this and it failed to break, and here is why" is a good result. "We tried this and it worked, and here is what we would change" is a better one. Bring the most interesting one to the presentation either way.

## Attacks that need no cryptography

Work these against your *process*, not just your code — this is the material the written analysis asks for.

**Step 1, proofing and enrollment.** What evidence does enrollment actually require, and what would it cost an attacker to produce it? If enrollment is an invite code, how is the code delivered, who can request one, and what stops someone enrolling twice under a near-identical identifier? The cheapest attack on most enrollment steps is social, not technical: a plausible request to whoever issues the codes.

**Step 2, issuance.** Can an authenticator be bound to an account that is not the requester's? Is the binding endpoint authenticated at all, or does it trust the identifier in the request body?

**Step 3, the authentication request.** Can the claimant be sent somewhere the RP did not intend? Anything that lets an attacker choose where authentication happens is a phishing primitive.

**Step 4, the authentication process.** Does a failure reveal whether the account exists? Does anything rate-limit guessing? A one-time password does not resist phishing — a relayed code authenticates the relayer just as well.

**Step 5, the assertion and session.** Bearer credentials are convenient because anyone holding one is treated as the subject; that is also the entire problem. Can a session credential be used from a different client? Does it expire? Does logout actually revoke it, or just delete a cookie?

**Account recovery — the real front door.** Most systems put real controls on login and almost none on reset. If a recovery path exists, ask what it requires and whether that is weaker than the authentication it bypasses. If none exists yet, say so plainly rather than inventing one late.

## Using an assistant as the adversary

This is where an assistant is most valuable, and the framing matters:

- Paste the enrollment handler and ask for the **cheapest social-engineering attack against the process it implements** — the process, not the code.
- Have it role-play an attacker who knows a subscriber's identifier but holds none of their authenticators, and list what they would try first, in order.
- Ask what compromising the **CSP versus the Verifier versus the RP** each buys an attacker, and which compromise would be hardest to detect.
- Ask it to design an account-recovery flow, then ask it to break the flow it just designed. It usually can, and the exchange makes a strong six minutes of presentation.

## Turning findings into tests

Every finding worth keeping becomes a denial test with **one comment sentence naming the attack it defends against**. If the attack cannot be named, the test may not be needed — or the attack is not yet understood, which is more interesting.

Test the clock by injecting it or minting an already-expired credential; never `sleep()`. Tests run from one command and never touch the live store.

## Naming the weakest point

The written analysis asks for the weakest point in your own system, named plainly. Every system has one. Naming yours accurately earns more credit than claiming there is not one — and an examiner who finds it first will ask why you did not.
