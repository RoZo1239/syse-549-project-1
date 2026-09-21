# Demo script — the flow, start to finish, in plain words

What to say while `scripts/walkthrough.py` is on screen. Written for the
7-minute demo segment, so it is deliberately non-technical where it can be:
the marker's question is whether you understand the model, not whether you can
recite HTTP.

---

## The one-sentence version

> Four programs, each knowing as little as possible. One person moves through
> three roles. Nobody who checks a password is the same service as the one
> that hands out the resource.

## The updated picture

```
                       ONE PERSON, THREE ROLES
              Applicant  ->  Subscriber  ->  Claimant
                   |             |              |
   . . . . . . . . | . . . . . . | . . . . . . .| . . . . . . . . . . .
   .  TRUST BOUNDARY - one host, one organisation, no outside IdP     .
   .               |             |              |                     .
   .    (1) apply  |   (2) activate             |  (4) prove it       .
   .               v             v              v                     .
   .        +--------------------------+   +------------------+       .
   .        |      CSP      :4101      |   | Verifier  :4102  |       .
   .        |   Partner A (Jonathan)   |   | Partner B (Hay.) |       .
   .        |                          |   |                  |       .
   .        |  who are you?            |   |  is it you, now? |       .
   .        |  makes the account       |   |  holds the hash  |       .
   .        |  hashes the password     |-->|  decides yes/no  |       .
   .        +--------------------------+   +------------------+       .
   .           (2b) the HASH crosses here.       |       ^            .
   .                Never the password.          |       |            .
   .                                    (5) "it's| them" |            .
   .                                             v       | introspect .
   .        +---------------------------------------------------+    .
   .        |          Relying Party   :4103   Partner B         |    .
   .        |   the thing you actually wanted                    |    .
   .        |   (3) no session? 401 + "go authenticate there"    |    .
   .        |   (5) session -> here is your record               |    .
   .        +---------------------------------------------------+    .
   . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .
                              ^                     ^
                              |                     |
             Subject agent :4100              Browser  :4133
             Partner A - scripted,            the same five steps,
             what the probe drives            driven by a human
```

**Two absences worth pointing at.** There is no arrow from the Relying Party
to the CSP, and none to the Applicant. The RP only ever meets you once you are
a Subscriber or a Claimant, and it never asks the CSP about you. If it could,
"is this person authenticated?" would have two possible answers, and the one
that skips the Verifier is the one an attacker would use.

---

## Start to finish — the words to say

### Before anything: what each box is for

> **CSP** is the office that signs you up. **Verifier** is the bouncer who
> checks you at the door. **Relying Party** is the room you wanted to get
> into. Three different jobs, three different programs, on purpose.

### Step 1 — signing up (Applicant → CSP)

> I type an email and a password. The CSP makes me an account and mails me a
> link.
>
> Two things happen that matter. The password is **hashed with scrypt the
> instant it arrives** — the CSP never stores what I typed. And I am not
> logged in. I am an *Applicant*: someone who has asked, and not yet proved
> anything.
>
> "Proofing" here means one thing: can you read that mailbox. That is
> Identity Assurance Level 1. We are not checking a passport, and we say so.

### Step 2 — clicking the link (Applicant → Subscriber)

> Clicking the link is the moment I stop being an Applicant and become a
> **Subscriber**. That is a real line in our code, not a figure of speech.
>
> And here is the important bit: the CSP now sends the **hash** of my password
> to the Verifier. Not the password. The CSP will never be asked "is this
> password right?" again — that job belongs to the Verifier from here on.

### Step 3 — hitting the wall (Subscriber → Claimant)

> I go to the protected page. The Relying Party says **401** and, crucially,
> sends a `WWW-Authenticate` header. RFC 9110 §15.5.2 requires that on every
> 401 and almost everyone forgets it.
>
> That refusal is what turns me from a Subscriber into a **Claimant** —
> somebody claiming to be an account holder, with something still to prove.
>
> Notice what the RP does *not* know at this point: whether I have an account
> at all. It has never spoken to the CSP.

### Step 4 — proving it (Claimant ↔ Verifier)

> I send my password to the **Verifier**, not to the RP. The Verifier compares
> it against the hash the CSP handed over in step 2 and decides.
>
> What comes back is not a password and not a name. It is an **opaque
> single-use handle** — a random string that means nothing to anyone who
> steals it.

### Step 5 — getting in (Verifier → RP)

> I hand that handle to the Relying Party. The RP turns around and asks the
> **Verifier** "is this real, and who is it?" Only the Verifier's answer can
> produce a name.
>
> That is the whole architecture in one sentence: **the RP has no other way to
> learn who I am.** It cannot be tricked into believing a name I typed,
> because there is no code path that reads a name from my request.

---

## The denials — and why each one matters

Run at least two. `skip_verifier` is the one the lab is built around.

| Scenario | Say this |
|---|---|
| **wrong password** | "Wrong password. Refused. Watch the exact wording." |
| **account that does not exist** | "Now an account that was never created. **The same refusal, byte for byte.** If they differed, I could use this to find out which email addresses are registered — and that list is worth money." |
| **replay** | "I log in, then log out, then present the same session token again. Refused. A session token is a bearer credential: whoever holds it is treated as me, so it has to actually die when I log out." |
| **skip_verifier** | "Now I go straight to the Relying Party with a handle I made up, and I never talk to the Verifier. Refused — and not because we wrote a check. Because the RP's **only** source of a name is asking the Verifier, and the Verifier never issued this. It fails *by construction*." |

---

## Three lines to land, if you say nothing else

1. **"The service that checks your password is not the service that gives you
   the resource."** That separation is the whole point of Figure 3, and it is
   what makes the last demo fail the way it should.
2. **"The password crosses one boundary, once, as a hash."** CSP to Verifier,
   step 2, and never again.
3. **"Our weakest point is not in the code."** It is step 1: whoever can read
   the mailbox gets the account. No cryptography is broken by that, and no
   amount of good code downstream fixes it.

---

## If something breaks live

Do not debug in front of the room. Say what you expected, show the
transcript, and move on:

```bash
python3 scripts/trace.py --last
```

> "All four services log their own steps. Merged in timestamp order, that is
> the whole run — and it is the evidence the automated probe reads too."

A denial that was *supposed* to happen is a win, not a failure. Say so.
