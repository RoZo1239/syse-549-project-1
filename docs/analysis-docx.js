const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  BorderStyle, LevelFormat, convertInchesToTwip,
} = require("docx");
const fs = require("fs");

const BODY = "Calibri";
const MONO = "Courier New";
const HEADF = "Cambria";
const INK = "1A1F35";
const NAVY = "1E2761";
const GREY = "5A6379";

// ---- helpers ---------------------------------------------------------------
const p = (runs, opts = {}) => new Paragraph({
  spacing: { after: opts.after ?? 120, line: opts.line ?? 252 },
  alignment: opts.align,
  ...opts.extra,
  children: (Array.isArray(runs) ? runs : [runs]).map(r =>
    typeof r === "string"
      ? new TextRun({ text: r, font: BODY, size: opts.size ?? 21, color: INK })
      : new TextRun({ font: BODY, size: opts.size ?? 21, color: INK, ...r })),
});

const b = t => ({ text: t, bold: true });
const code = t => ({ text: t, font: MONO, size: 18 });

const h1 = t => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 260, after: 120 },
  children: [new TextRun({ text: t, font: HEADF, size: 26, bold: true, color: NAVY })],
});

// Diagram lines: monospace, tight, no paragraph spacing.
const dia = t => new Paragraph({
  spacing: { after: 0, line: 200 },
  children: [new TextRun({ text: t, font: MONO, size: 15, color: INK })],
});

const bullet = runs => new Paragraph({
  numbering: { reference: "bul", level: 0 },
  spacing: { after: 80, line: 252 },
  children: (Array.isArray(runs) ? runs : [runs]).map(r =>
    typeof r === "string"
      ? new TextRun({ text: r, font: BODY, size: 21, color: INK })
      : new TextRun({ font: BODY, size: 21, color: INK, ...r })),
});

// ---- content ---------------------------------------------------------------
const children = [];

// title block
children.push(new Paragraph({
  spacing: { after: 40 },
  children: [new TextRun({
    text: "Building NIST SP 800-63-4, Figure 3",
    font: HEADF, size: 34, bold: true, color: NAVY,
  })],
}));
children.push(new Paragraph({
  spacing: { after: 40 },
  children: [new TextRun({
    text: "The non-federated digital identity model — written analysis",
    font: BODY, size: 22, color: GREY,
  })],
}));
children.push(new Paragraph({
  spacing: { after: 200 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "C7CEDE", space: 6 } },
  children: [new TextRun({
    text: "Hayagreeva Sundareswaran and Jonathan Christensen  ·  SYSE 549  ·  team hayagreeva-jonathan  ·  ports 4100–4103",
    font: BODY, size: 18, color: GREY,
  })],
}));

// 1 -------------------------------------------------------------------------
children.push(h1("1.  What we built, mapped to Figure 3"));
children.push(p([
  "We implemented the diagram literally: four processes, one per box, inside a single trust boundary — one host, one organisation, no external identity provider. The Subject is a program rather than a person, which is the lab's teaching device and buys us one real thing: the two role transitions become specific lines of code instead of something implied.",
]));

[
  "       Applicant  -->  Subscriber  -->  Claimant    (one person, three roles)",
  "           |              |               |",
  "    (1) apply      (2) activate     (4) prove control",
  "           v              v               v",
  "  +----------------------+        +--------------------+",
  "  |   CSP         :4101  |--(2b)->|  Verifier    :4102 |",
  "  |   proofing,          | scrypt |  holds the record  |",
  "  |   enrollment,        | record |  DECIDES yes / no  |",
  "  |   hashes the secret  |        +--------------------+",
  "  +----------------------+            |  (5)    ^ introspect",
  "                                      v         |",
  "  +---------------------------------------------------+",
  "  |  Relying Party  :4103                             |",
  "  |  (3) no session -> 401 + WWW-Authenticate         |",
  "  |  (5) session    -> the subscriber's record        |",
  "  +---------------------------------------------------+",
  "   Subject agent :4100 drives all five as a script.",
].forEach(l => children.push(dia(l)));
children.push(p([""], { after: 100 }));

children.push(p([
  b("The five steps as they run. "),
  "(1) The Applicant posts an email address and a chosen password to the CSP, which hashes it with scrypt on arrival and mails an activation link. (2) Clicking that link makes them a Subscriber, and the CSP hands the Verifier the salted digest — never the secret. (3) The Subscriber asks the Relying Party for ",
  code("/protected"),
  " with no session and gets ",
  code("401"),
  " with a ",
  code("WWW-Authenticate"),
  " header, which RFC 9110 §15.5.2 requires; that refusal is what makes them a Claimant. (4) The Claimant proves control to the Verifier, which mints an opaque single-use handle. (5) The RP redeems that handle by calling the Verifier's ",
  code("/introspect"),
  ", and only the identifier in that response can become a session.",
]));
children.push(p([
  b("Two absences are as deliberate as anything drawn. "),
  "There is no arrow from the Relying Party to the CSP — Figure 3 has none, and neither do the federated variants in Figures 4 and 5. An RP that could query the CSP would be reaching into another service's store, and the question a review of this system asks hardest is whether the RP can conclude \"authenticated\" without the Verifier. It cannot, because ",
  code("/introspect"),
  " is the only way it ever learns an identifier. What it does do is hand a stranger two URLs — ",
  code("enroll_at"),
  " and ",
  code("authenticate_at"),
  " — so someone unenrolled has somewhere to go. A signpost is not a connection. There is no arrow to the Applicant either: the RP meets the subject only as a Subscriber or a Claimant.",
]));
children.push(p([
  "Ordering is provable rather than asserted: every event carries a UTC timestamp with microsecond precision from one shared helper, so merging the four transcripts reconstructs the run. Microseconds are not fussiness — at millisecond precision two events written in the same millisecond keep collection order rather than time order, and we observed exactly that inversion before changing it.",
]));

// 2 -------------------------------------------------------------------------
children.push(h1("2.  The design decisions that mattered"));
children.push(p([
  "Proofing here means control of an email address and nothing more, which is IAL1 — self-asserted attributes with one confirmable channel — and we claim no more than that. The authenticator is a subscriber-chosen memorized secret with a 15-character floor, because SP 800-63B-4 §3.1.1.2 sets that floor for a password used as the sole authentication factor and this system has no second factor anywhere. Revision 4 also removes composition rules and periodic rotation, so we impose neither. Secrets are stored as scrypt records with a 16-byte random salt. There is no administrator account, deliberately; the real bootstrap problem here is the shared token between services, so whoever can write the environment file is the trust anchor. Three choices carried the rest of the design.",
]));
children.push(p([
  b("The assertion is an opaque single-use handle, not a token that carries identity. "),
  "This is the whole answer to the verifier-bypass scenario. A signed JWT would have been equally defensible on paper, but then the RP's decision rests on verifying a signature correctly, and the interesting failures — algorithm confusion, a skipped expiry check, the wrong key — move inside our own code. With a handle there is nothing to forge: the RP cannot learn an identifier except by asking the Verifier, so \"the RP concluded authenticated without the Verifier checking anything\" is not a bug we avoided, it is a state the program cannot reach.",
]));
children.push(p([
  b("Service-to-service calls stay on loopback. "),
  "The Verifier-to-RP edge is the load-bearing one and has no reason to leave the host all four services run on. We learned this the hard way: the first version resolved the Verifier through the public campus URL, which sent internal traffic out across the network and back, and hung for five seconds when that host was unreachable.",
]));
children.push(p([
  b("Denials are uniform, including in the clock. "),
  "One status and one body for a wrong secret, an unknown identifier and a malformed request — and the unknown-identifier path does the same scrypt work as a real check before refusing. Measured on the deployed services: 46.2 ms for an identifier that does not exist against 48.1 ms for a wrong secret on one that does.",
]));

// 3 -------------------------------------------------------------------------
children.push(h1("3.  Defeating two of the five steps without breaking cryptography"));
children.push(p([
  b("Step 1 — identity proofing and enrollment. "),
  "Nothing here is cryptographic to begin with, which is why it is the cheapest step to defeat. An applicant claims an address, the CSP mails a link there, and clicking it finishes the account. An attacker does not break anything; they enroll. Strengthening the model — an invite code, an out-of-band token — does not make the attack cryptographic, it makes it social: work out who can cause a code to be issued, and send them a plausible request. Every control downstream then works perfectly, on an identity nobody verified. This is the enrollment-fraud path, and it is how real breaches usually start.",
]));
children.push(p([
  b("Step 5 — the authenticated session. "),
  "The session credential is a bearer credential: whoever holds it is treated as the subscriber, and reading one off the wire is enough, because this lab is deployed over plain HTTP by design so the traffic is readable in a packet capture. No cryptography is involved in the theft — the attacker copies a string. We pin each session to the address it was issued to, which is a real cost to an attacker elsewhere on campus and none at all to one on the same host or behind the same NAT. Logout revokes and the TTL expires, but both only bound the window; neither prevents the copy.",
]));
children.push(p([
  "A third, briefly: ",
  b("step 4 by relay"),
  ". The authenticator is a secret the claimant sends to the Verifier, so anything that persuades a claimant to send it somewhere else authenticates the relayer just as well — and no cryptography has been broken there either.",
]));

// 4 -------------------------------------------------------------------------
children.push(h1("4.  The weakest point, named plainly"));
children.push(p([
  b("Enrollment. "),
  "Steps 2 through 5 are careful — secrets salted and hashed, the assertion unforgeable, sessions expiring and revocable, denials saying nothing — and all of that care is spent enforcing a binding to an identity nobody verified. The strongest authentication in the world answers \"is this the same party who enrolled?\", never \"is this party who they said they were\". An attacker who enrolls as somebody else gets a genuine authenticator, a genuine assertion and a genuine session, and every transcript in the system reads ",
  code("success"),
  ".",
]));
children.push(p([
  "Our own adversarial hour found a sharp instance of this. ",
  code("POST /apply"),
  " refused only identifiers that were already ",
  { text: "activated", italics: true },
  ", so an attacker could apply for an address with an application still pending, replacing the stored password hash with one they chose. The activation link still goes to the real owner, who clicks it and activates an account whose password belongs to the attacker. Four well-formed requests, no cryptography, and the victim performs the decisive step. We now refuse any identifier that already exists — at the cost of letting an attacker squat an unclaimed address, and of an enrollment-time account-existence oracle. We think that trade is right here and we can say why; we have not built pending-application expiry, which would remove the squatting cost, and we say so rather than implying the fix was free.",
]));
children.push(p([
  "Second weakest: the two shared service tokens are static and long-lived, and whoever reads that file can mint bindings at the Verifier — which is to say, become any subscriber. That makes the host filesystem the actual trust anchor. Third: our rate limiting is nearly useless in a deployment where every legitimate request arrives from the same address an attacker's would. The automated six-question review passed it; we do not. And there is deliberately ",
  b("no account recovery path"),
  " — in a real system it would be the front door with the weakest lock, and we would rather say we have not built one than build one late and have it quietly bypass step 4.",
]));

// 5 -------------------------------------------------------------------------
children.push(h1("5.  Where the AI assistant misled us"));
children.push(p([
  "The pattern across all of these is the same: the assistant is most dangerous when it is fluent about something only a measurement can settle. Every one was caught by running something, not by reading.",
]));
children.push(bullet([
  b("It reported a timing leak that was its own rate limiter. "),
  "1 ms against 40 ms looked like a serious oracle. Re-measured per source address it was 46.2 ms against 48.1 ms. The finding was an artefact of how the measurement was taken — and the real finding underneath was the rate-limiting weakness named above.",
]));
children.push(bullet([
  b("It resolved an internal call through the public campus URL. "),
  "That worked in tests and hung in deployment. Running the system found it; reading the code did not.",
]));
children.push(bullet([
  b("It wrote sample output it had never run. "),
  "A deployment document contained a plausible \"all four services up\" transcript that no run had produced. We replaced it with observed output and marked the one line that was not from a run.",
]));
children.push(bullet([
  b("It cannot verify NIST section numbers from its environment. "),
  "Every citation in this document is therefore checked against the published PDF rather than taken on its word — which is the discipline the lab asks for: quote it, or it does not exist.",
]));
children.push(p([
  "Used well, it was most valuable writing negative tests and role-playing an attacker against our own enrollment process — which is how the pre-hijacking defect in §4 was found.",
], { after: 0 }));

// ---- document --------------------------------------------------------------
const doc = new Document({
  creator: "Hayagreeva Sundareswaran and Jonathan Christensen",
  title: "SYSE 549 Lab 1 - Written Analysis",
  numbering: {
    config: [{
      reference: "bul",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "•",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: convertInchesToTwip(0.3), hanging: convertInchesToTwip(0.18) } } },
      }],
    }],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },           // US Letter
        margin: {
          top: convertInchesToTwip(0.85), bottom: convertInchesToTwip(0.85),
          left: convertInchesToTwip(0.9), right: convertInchesToTwip(0.9),
        },
      },
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("lab1-written-analysis.docx", buf);
  console.log("wrote lab1-written-analysis.docx");
});
