import { useState } from "react";
import { Link } from "react-router-dom";
import { api, newRunId } from "../api.js";
import Card from "../Card.jsx";

// NIST SP 800-63B-4 SS3.1.1.2: a password used as the sole authentication
// factor SHALL be at least 15 characters. The CSP enforces this server-side
// (shared/validate.py); this is just an earlier, friendlier version of the
// same rule.
const MIN_LENGTH = 15;

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (password.length < MIN_LENGTH) {
      setError(`Your password must be at least ${MIN_LENGTH} characters.`);
      return;
    }

    setBusy(true);
    try {
      const runId = newRunId();
      const { status, data } = await api.applyForAccount(runId, email, password);
      if (status === 201) {
        // The CSP returns the enrollment token in the response as well as
        // mailing it. That is deliberate: the graded contract is
        // machine-to-machine and must not need a working SMTP account. It also
        // means this page can offer the activation link directly when no mail
        // server is configured, instead of leaving step 2 a dead end.
        setResult({ email, token: data?.token, runId, emailSent: data?.email_sent === true });
      } else if (status === 409) {
        setError("An account for this email already exists.");
      } else if (status === 400 && data?.error === "invalid_password") {
        setError(
          `Password must be between ${data.min_length} and ${data.max_length} characters.`,
        );
      } else {
        setError("Sign up failed. Check the email address and try again.");
      }
    } catch {
      setError("Something went wrong. Please try again in a moment.");
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <Card>
        <h1>Check your email</h1>
        {result.emailSent ? (
          <p>
            We sent a confirmation link to <strong>{result.email}</strong>.
            Clicking it is Figure 3 step 2 — the authenticator gets bound to
            your account and the Verifier is handed the record.
          </p>
        ) : (
          <p>
            <strong>No mail server is configured on this deployment</strong>, so
            nothing was sent to {result.email}. Use the link below instead — it
            is the same one the email would have carried, and following it is
            Figure 3 step 2: the authenticator gets bound to your account and
            the Verifier is handed the record.
          </p>
        )}
        {result.token && (
          <p>
            <a href={api.activationUrl(result.email, result.token, result.runId)}>
              Activate this account
            </a>
          </p>
        )}
        <p className="small-text">
          run_id <code>{result.runId}</code> — see it with{" "}
          <code>python3 scripts/trace.py {result.runId}</code>
        </p>
        <p className="small-text">
          Already confirmed your account? <Link to="/login">Log in</Link>
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <h1>Create your account</h1>
      <p>Sign up for SYSE 549 Drive</p>

      {error && <div className="banner error">{error}</div>}

      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
          <p className="hint">At least {MIN_LENGTH} characters.</p>
        </div>
        <button className="btn" type="submit" disabled={busy}>
          {busy ? "Signing up..." : "Sign up"}
        </button>
      </form>

      <p className="small-text">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </Card>
  );
}
