"""Configuration loading, shared by every service.

Two sources, in this order: the process environment (optionally seeded from a
`.env` file that is never committed) and `team.json`, which holds only the
team name and the four public endpoint URLs.

Shared tokens have no default. A service that cannot find its token refuses to
start rather than falling back to a value an attacker could read in this file.
"""

import json
import os
from typing import Dict, Optional

SERVICES = ("subject", "csp", "verifier", "rp")
PORT_OFFSETS = {"subject": 0, "csp": 1, "verifier": 2, "rp": 3}
SPEC_VERSION = "1.0"

# Bind on every interface: a service bound to 127.0.0.1 works on the server and
# is invisible from campus, which is the second most common way to fail the probe.
DEFAULT_BIND_HOST = "0.0.0.0"
DEFAULT_PORT_BLOCK = 4100

_ENV_LOADED = False


class ConfigError(Exception):
    """Configuration is missing or malformed; the service must not start."""


def load_env_file(path: str = ".env") -> None:
    """Seed os.environ from a KEY=value file, without overriding real env vars."""
    global _ENV_LOADED
    if _ENV_LOADED or not os.path.exists(path):
        _ENV_LOADED = True
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))
    _ENV_LOADED = True


def load_team_config(path: str = "team.json") -> Dict[str, object]:
    if not os.path.exists(path):
        return {"team": os.environ.get("LAB1_TEAM", "unset-team"), "endpoints": {}}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            config = json.load(handle)
    except ValueError as exc:
        raise ConfigError("team.json is not valid JSON: %s" % exc) from None
    if not isinstance(config, dict):
        raise ConfigError("team.json must contain a JSON object")
    config.setdefault("team", "unset-team")
    config.setdefault("endpoints", {})
    return config


def team_name() -> str:
    load_env_file()
    return os.environ.get("LAB1_TEAM") or str(load_team_config().get("team", "unset-team"))


def port_for(service: str) -> int:
    """Port for `service`: an explicit override, else block + the fixed offset."""
    load_env_file()
    if service not in PORT_OFFSETS:
        raise ConfigError("unknown service %r" % (service,))
    override = os.environ.get("LAB1_%s_PORT" % service.upper())
    if override:
        return _as_port(override, "LAB1_%s_PORT" % service.upper())
    block = _as_port(
        os.environ.get("LAB1_PORT_BLOCK", str(DEFAULT_PORT_BLOCK)), "LAB1_PORT_BLOCK"
    )
    return block + PORT_OFFSETS[service]


def bind_host() -> str:
    load_env_file()
    return os.environ.get("LAB1_BIND_HOST", DEFAULT_BIND_HOST)


def endpoint_for(service: str, config: Optional[Dict[str, object]] = None) -> str:
    """Base URL of a peer service: env override, else team.json, else localhost."""
    load_env_file()
    if service not in SERVICES:
        raise ConfigError("unknown service %r" % (service,))
    override = os.environ.get("LAB1_%s_URL" % service.upper())
    if override:
        return override.rstrip("/")
    endpoints = (config or load_team_config()).get("endpoints", {})
    if isinstance(endpoints, dict) and endpoints.get(service):
        return str(endpoints[service]).rstrip("/")
    return "http://127.0.0.1:%d" % port_for(service)


def internal_endpoint_for(service: str) -> str:
    """Base URL for a *service-to-service* call, inside the trust boundary.

    All four services run on one host, so the Verifier -> RP edge has no reason
    to leave it: the default is the loopback address, not the public URL in
    team.json. Sending an assertion out across the campus network and back
    would put the load-bearing edge of the design on an untrusted wire.
    """
    load_env_file()
    if service not in SERVICES:
        raise ConfigError("unknown service %r" % (service,))
    override = os.environ.get("LAB1_%s_URL" % service.upper())
    if override:
        return override.rstrip("/")
    return "http://127.0.0.1:%d" % port_for(service)


def require_secret(name: str) -> str:
    """Read a shared token, or refuse to start."""
    load_env_file()
    value = os.environ.get(name, "").strip()
    if len(value) < 16:
        raise ConfigError(
            "%s is missing or too short. Copy .env.example to .env and fill it in "
            "with a value of at least 16 characters (see README.md)." % name
        )
    return value


def int_setting(name: str, default: int, *, minimum: int = 1) -> int:
    load_env_file()
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError("%s must be an integer, got %r" % (name, raw)) from None
    if value < minimum:
        raise ConfigError("%s must be >= %d" % (name, minimum))
    return value


def bool_setting(name: str, default: bool) -> bool:
    load_env_file()
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _as_port(raw: str, name: str) -> int:
    try:
        port = int(raw)
    except ValueError:
        raise ConfigError("%s must be a port number, got %r" % (name, raw)) from None
    if not (1 <= port <= 65535):
        raise ConfigError("%s out of range: %d" % (name, port))
    return port
