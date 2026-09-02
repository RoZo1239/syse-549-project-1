---
name: nist-63-cite
description: Citation discipline for NIST SP 800-63-4 and its companion volumes (63A-4 proofing, 63B-4 authentication, 63C-4 federation), plus SP 800-207 and RFC 9110. Use whenever a claim is about to be made about what NIST requires, allows, or prohibits — password rules, authenticator types, identity proofing, IAL/AAL/FAL, assertions, sessions — and whenever a section number is about to be written down. Assistants are fluent and confident about the WITHDRAWN Revision 3 of 800-63B and invent section numbers that do not exist, so run every 800-63 claim through this before it reaches code, a comment, the written analysis, or the presentation.
---

# Citing SP 800-63 without getting it wrong

The rule: **quote or it does not exist.** For any claim about what 800-63 says, produce the sentence from the actual document, then the section it came from — in that order. A section number without a quotable sentence is a hallucination, and a graded presentation is an expensive place to discover that.

Extract the text from the PDF and search it. Do not reconstruct from memory, and do not accept a citation just because it is formatted plausibly.

## The trap that catches everyone

**SP 800-63B-3 was withdrawn in August 2025.** Revision 4 reverses its best-known password guidance:

| Withdrawn Rev 3 advice | Revision 4 |
|---|---|
| Periodic rotation | Do not require it |
| Composition rules (uppercase + digit + symbol) | Do not impose them |
| 8-character minimum | Longer minimum; the single-factor password minimum is 15 characters |

If a recommendation includes "must contain an uppercase letter and a number" or "expire every 90 days", it is quoting a superseded document. Check §3.1.1.2 of 63B-4 before writing any password rule, and quote what it actually says.

Knowledge-based authentication ("what was your first pet") is **prohibited** — do not design a recovery flow around it.

## Which volume answers which question

| Question | Volume |
|---|---|
| The model, Figure 3, the four services, the five steps | SP 800-63-4 |
| Identity proofing, enrollment, IAL 1/2/3 | SP 800-63A-4 |
| Authenticators, authentication, AAL, sessions, password rules | SP 800-63B-4 (§3.1 catalogs authenticator types) |
| Federation, assertions between organizations, FAL | SP 800-63C-4 — **not used in this lab** |
| Zero trust, PEP/PDP framing | SP 800-207 |
| `401` and the `WWW-Authenticate` header | RFC 9110 §15.5.2 |

## Distinctions that get blurred

- **Identity proofing** (is this a real person, and are they who they claim?) lives in step 1 and is governed by 63A-4. **Authentication** (does this claimant control the authenticator bound to that account?) lives in step 4 and is governed by 63B-4. They are different questions with different failure modes; conflating them is the most common misreading.
- **Authenticator** is the thing possessed or known. **Credential** is the record binding it to a subscriber account. 800-63 does not call an authenticator a "credential" — using the words interchangeably will be corrected in Q&A.
- **Applicant / Subscriber / Claimant** are positions in the identity lifecycle, not authorization roles like admin or viewer. This is the most common misreading of Figure 3.
- **Non-federated** means the CSP, Verifier and RP sit inside one trust boundary, one organization. OAuth, OpenID Connect and SAML are federation technologies; they do not belong in this design, and an assistant will nonetheless steer toward them because it is fluent about them.
- **IAL / AAL / FAL** are assurance levels for proofing, authentication and federation respectively. FAL is out of scope here — that is what "non-federated" means.

## Keep the error log

When an assistant gets one of these wrong — a fabricated section number, Rev 3 password advice, an OAuth suggestion — record it in `docs/ai-errors.md` with what it claimed and what the document actually says. That log is required material in the written analysis and is worth credit.
