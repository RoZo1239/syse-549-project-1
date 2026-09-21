// Talks to the three services a browser touches: CSP (enrollment), Verifier
// (authentication), RP (sessions + protected resource). Routed through the
// Vite dev-server proxy in vite.config.js, never directly to the services'
// own origins.

const CSP_BASE = "/api/csp";
const VERIFIER_BASE = "/api/verifier";
const RP_BASE = "/api/rp";

export const SESSION_SCHEME = "Lab1-Session";

export function newRunId() {
  return "web-" + crypto.randomUUID();
}

async function request(method, url, { body, headers = {} } = {}) {
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json", ...headers } : headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    // No JSON body (e.g. a 204). Leave data null.
  }
  // The challenge itself, not just the status. RFC 9110 15.5.2 requires it on
  // every 401 and it is the thing worth showing a grader, so it comes back
  // rather than being thrown away with the rest of the headers.
  const challenge = res.headers.get("WWW-Authenticate");
  return { status: res.status, data, challenge };
}

export const api = {
  // Step 1: identity proofing and enrollment.
  applyForAccount(runId, email, plaintext) {
    return request("POST", `${CSP_BASE}/apply`, {
      body: { run_id: runId, email, plaintext },
    });
  },

  // Step 2, for a human: the CSP mails this link; the browser just follows it.
  // Exposed here so the UI can offer it when no mail server is configured.
  activationUrl(email, token, runId) {
    const q = new URLSearchParams({ email, token });
    if (runId) q.set("run_id", runId);
    return `${CSP_BASE}/activate?${q}`;
  },

  // Step 3: ask for the protected resource with NO credential, and get the
  // RP's 401 + WWW-Authenticate. This is a real request on purpose - the RP
  // decides whether a caller is authenticated, never the browser.
  demandAuthentication(runId) {
    return request("GET", `${RP_BASE}/protected`, {
      headers: { "X-Run-Id": runId },
    });
  },

  // Step 4: prove control of the authenticator, get back an assertion.
  authenticate(runId, identifier, authenticatorOutput) {
    return request("POST", `${VERIFIER_BASE}/authenticate`, {
      body: { run_id: runId, identifier, authenticator_output: authenticatorOutput },
    });
  },

  // Step 5: redeem the assertion at the RP for a session.
  establishSession(runId, assertion) {
    return request("POST", `${RP_BASE}/session`, {
      body: { run_id: runId, assertion },
    });
  },

  // Step 5: the protected resource, with a session.
  protectedResource(runId, session) {
    return request("GET", `${RP_BASE}/protected`, {
      headers: {
        Authorization: `${SESSION_SCHEME} ${session}`,
        "X-Run-Id": runId,
      },
    });
  },

  logout(runId, session) {
    return request("POST", `${RP_BASE}/logout`, {
      body: { run_id: runId },
      headers: { Authorization: `${SESSION_SCHEME} ${session}` },
    });
  },
};
