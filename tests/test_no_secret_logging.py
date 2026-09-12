"""A static check that Partner B's services cannot log an authenticator secret.

The canary check (X-CAN) is a runtime grep, so it only catches a leak on a path
a test happened to exercise. This test reads the source instead: if every
`detail=` written to a transcript is a literal string, no request field can
reach a transcript on any path, exercised or not.
"""

import ast
import pathlib
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
PARTNER_B_SERVICES = ["services/verifier/app.py", "services/rp/app.py"]

# Field names that must not appear in a transcript event or a response body.
SECRET_BEARING_NAMES = ("password", "passwd", "secret", "token", "canary")


class NoSecretLoggingTestCase(unittest.TestCase):
    def transcript_calls(self, path: pathlib.Path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "record"
            ):
                yield node

    def test_every_transcript_detail_is_a_literal(self):
        # Defends against the commonest way a secret is logged: interpolating a
        # request field into an otherwise harmless-looking detail string.
        for relative in PARTNER_B_SERVICES:
            path = REPO / relative
            calls = list(self.transcript_calls(path))
            self.assertTrue(calls, "no transcript calls found in %s" % relative)
            for call in calls:
                details = [k.value for k in call.keywords if k.arg == "detail"]
                self.assertTrue(details, "%s:%d records without a detail"
                                % (relative, call.lineno))
                for value in details:
                    self.assertIsInstance(
                        value,
                        ast.Constant,
                        "%s:%d builds detail from a runtime value"
                        % (relative, value.lineno),
                    )

    def test_the_rp_never_touches_an_authenticator_output(self):
        # Defends against the architecture's one unforgivable failure: the RP is
        # the service that must never see the authenticator secret.
        source = (REPO / "services/rp/app.py").read_text(encoding="utf-8")
        self.assertNotIn("authenticator_output", source)
        self.assertNotIn("verify_secret", source)
        self.assertNotIn("pwhash", source)

    def test_no_secret_bearing_field_names_in_responses_or_events(self):
        # Defends against the hygiene check that looks for secret-shaped field
        # names as well as secret values. Only JSON body keys are checked:
        # anything containing a dash is an HTTP header name, not a body field.
        for relative in PARTNER_B_SERVICES:
            tree = ast.parse((REPO / relative).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                for key in node.keys:
                    if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                        continue
                    if "-" in key.value:
                        continue
                    for banned in SECRET_BEARING_NAMES:
                        self.assertNotIn(
                            banned,
                            key.value.lower(),
                            "%s:%d body field %r looks secret-bearing"
                            % (relative, key.lineno, key.value),
                        )


if __name__ == "__main__":
    unittest.main()
