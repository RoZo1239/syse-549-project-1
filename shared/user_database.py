import os
import sys
import sqlite3

from typing import Optional
from pydantic import BaseModel
import bcrypt

class User(BaseModel):
    email: str
    password_hash: str
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
                    password_hash TEXT,
                    subscriber_token TEXT NOT NULL,
                    subscribed BOOLEAN
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def reset(self):
        self._init_db(reset=True)

    def add_user(self, email, subscriber_token):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (email, password_hash, subscriber_token, subscribed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    subscriber_token = excluded.subscriber_token,
                    subscribed = excluded.subscribed
                WHERE users.subscribed = FALSE
                """,
                (email, None, subscriber_token, False),
            )

    def get_user(self, email: str) -> Optional[User]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            else:
                return User(
                    email=row[0],
                    password_hash=row[1],
                    subscriber_token=row[2],
                    subscribed=row[3]
                )

    def subscribe_user(self, email, token):
        user = self.get_user(email)

        if(user is None):
            return False

        if user.subscribed:
            return False
        
        if(token != user.subscriber_token):
            return False

        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET subscribed = TRUE WHERE email = ?",
                (email,)
            )
        
        return True

    def verify_login(self, email, password_hash):
        user = self.get_user(email)

        if user is None:
            return False
        
        if bcrypt.checkpw(password_hash, user.password_hash):
            return True
        
        return False

    def user_exists(self, email) -> bool:
        return self.get_user(email) is not None
