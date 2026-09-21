import hmac
import json
import os
import sys
import sqlite3

from typing import Optional
from pydantic import BaseModel

class User(BaseModel):
    email: str
    # Empty until the authenticator is issued, so it has to be allowed to be
    # empty: declaring it a plain str made reading back any freshly created
    # applicant raise, which is why /subscribe answered 500 for everyone.
    verifier_record: Optional[str] = None
    subscriber_token: str
    subscribed: bool

class UserDatabase:
    def __init__(self):
        self.db_path = os.environ.get("DB_PATH")

        if not self.db_path:
            print("Error: DB_PATH not set.", file=sys.stderr)
            sys.exit(1)

        self._init_db()

    def _init_db(self, reset=False):
        with self._connect() as conn:
            if reset:
                conn.execute("DROP TABLE IF EXISTS users")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    verifier_record TEXT,
                    subscriber_token TEXT NOT NULL,
                    subscribed BOOLEAN
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def reset(self):
        self._init_db(reset=True)

    def add_user(self, email, subscriber_token, verifier_record):
        """Create, or replace, an applicant who has not yet subscribed.

        `verifier_record` is the salted scrypt digest of the authenticator
        secret, from shared.pwhash.hash_secret. The secret itself is never
        stored and never leaves the process that received it.

        The WHERE clause is the account-takeover guard: once an account is
        subscribed, applying again must not overwrite its token or its
        authenticator.
        """
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (email, verifier_record, subscriber_token, subscribed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    verifier_record = excluded.verifier_record,
                    subscriber_token = excluded.subscriber_token,
                    subscribed = excluded.subscribed
                WHERE users.subscribed = FALSE
                """,
                (email, json.dumps(verifier_record), subscriber_token, False),
            )

    def get_user(self, email: str) -> Optional[User]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT email, verifier_record, subscriber_token, subscribed"
                " FROM users WHERE email = ?",
                (email,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            else:
                return User(
                    email=row[0],
                    verifier_record=row[1],
                    subscriber_token=row[2],
                    subscribed=bool(row[3])
                )

    def verifier_record(self, email: str) -> Optional[dict]:
        """The binding record to hand the Verifier, or None."""
        user = self.get_user(email)
        if user is None or not user.verifier_record:
            return None
        try:
            return json.loads(user.verifier_record)
        except ValueError:
            return None

    def token_matches(self, email, token) -> bool:
        """Is `token` this account's unspent enrollment token? Mutates nothing.

        Split out from subscribe_user so the caller can check the token, do the
        work that might fail, and only then mark the account subscribed. Doing
        it the other way round spent the token before the Verifier binding was
        attempted, so one failed binding left the account subscribed-but-unbound
        with no way to retry.
        """
        user = self.get_user(email)
        if user is None or user.subscribed:
            return False
        # compare_digest, not ==: the enrollment token is a secret, and a
        # short-circuiting comparison leaks how much of a guess was right.
        return hmac.compare_digest(str(token), user.subscriber_token)

    def subscribe_user(self, email, token):
        if not self.token_matches(email, token):
            return False

        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET subscribed = TRUE WHERE email = ?",
                (email,)
            )

        return True

    def user_exists(self, email) -> bool:
        return self.get_user(email) is not None

    def is_subscribed(self, email) -> bool:
        user = self.get_user(email)
        return user is not None and user.subscribed
