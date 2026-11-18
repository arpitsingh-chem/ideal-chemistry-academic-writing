"""Provider transport layer.

Every external scholarly source is reached through :class:`HttpClient`, which
owns the concerns that must never be duplicated across adapters:

* timeouts, bounded retries and exponential backoff with jitter;
* ``Retry-After`` honouring (OpenAlex answers a spent IP budget with a JSON
  error body and ``retryAfter`` seconds rather than a bare 429);
* a per-provider minimum request interval (politeness, not scraping);
* uniform error taxonomy so one dead provider cannot abort a synchronisation.

No third-party HTTP dependency is required: ``urllib`` is sufficient for the
query/response pattern used here and keeps the base install small.
"""
from __future__ import annotations

import gzip
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

USER_AGENT_TEMPLATE = "PaperForge/{version} (academic metadata client; +{url})"

DEFAULT_TIMEOUT = 20.0
DEFAULT_TRIES = 3
DEFAULT_INTERVAL = 0.0


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProviderError(RuntimeError):
    """Base class for every provider failure (never leaks a raw urllib error)."""

    def __init__(self, provider: str, message: str, *, status: int | None = None,
                 retry_after: float | None = None, url: str = "") -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.message = message
        self.status = status
        self.retry_after = retry_after
        self.url = url


class ProviderUnavailable(ProviderError):
    """The provider could not be reached, or refused this client."""


class RateLimited(ProviderUnavailable):
    """Quota exhausted. ``retry_after`` is seconds, when the provider says so."""


class NotFound(ProviderError):
    """The provider answered authoritatively that the record does not exist."""


class MalformedResponse(ProviderError):
    """The provider answered with something that is not the documented shape."""


# ---------------------------------------------------------------------------
# Cache / budget bookkeeping
# ---------------------------------------------------------------------------


@dataclass
class CallStats:
    """Per-client counters, surfaced in coverage reports."""

    requests: int = 0
    retries: int = 0
    failures: int = 0
    not_modified: int = 0
    bytes_downloaded: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "requests": self.requests,
            "retries": self.retries,
            "failures": self.failures,
            "not_modified": self.not_modified,
            "bytes_downloaded": self.bytes_downloaded,
        }


@dataclass
class RawResponse:
    """A provider payload plus the provenance a coverage report needs."""

    url: str
    status: int
    payload: Any
    retrieved_at: str
    from_cache: bool = False
    headers: dict[str, str] = field(default_factory=dict)


def utcnow() -> str:
    """ISO-8601 UTC timestamp, second resolution, ``Z`` suffix."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


class HttpClient:
    """Small, polite JSON client used by every adapter.

    Parameters
    ----------
    provider:
        Adapter name, used in error messages and log lines.
    base_headers:
        Extra headers (e.g. ``Accept``) merged into each request.
    min_interval:
        Minimum seconds between two requests to this provider.
    """

    def __init__(self, provider: str, *, app_version: str = "0",
                 contact_url: str = "https://github.com/arpitsingh-chem/ideal-chemistry-academic-writing",
                 base_headers: dict[str, str] | None = None,
                 timeout: float | None = None, tries: int | None = None,
                 min_interval: float | None = None, sleeper: Callable[[float], None] = time.sleep) -> None:
        self.provider = provider
        self.timeout = timeout if timeout is not None else _env_float("PF_HTTP_TIMEOUT", DEFAULT_TIMEOUT)
        self.tries = tries if tries is not None else int(_env_float("PF_HTTP_TRIES", DEFAULT_TRIES))
        self.min_interval = min_interval if min_interval is not None else _env_float("PF_HTTP_INTERVAL", DEFAULT_INTERVAL)
        self.headers = {
            "User-Agent": USER_AGENT_TEMPLATE.format(version=app_version, url=contact_url),
            "Accept": "application/json",
        }
        self.headers.update(base_headers or {})
        self.stats = CallStats()
        self._last_call = 0.0
        self._sleep = sleeper

    # -- public ------------------------------------------------------------
    def get_json(self, url: str, params: dict[str, Any] | None = None,
                 *, allow_404: bool = False) -> RawResponse:
        """GET ``url`` and decode JSON, retrying transient failures."""
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                sep = "&" if urllib.parse.urlsplit(url).query else "?"
                url = f"{url}{sep}{urllib.parse.urlencode(clean, doseq=True)}"
        last: Exception | None = None
        for attempt in range(max(1, self.tries)):
            self._throttle()
            try:
                return self._once(url, allow_404=allow_404)
            except RateLimited as exc:
                # honour the provider's own back-off hint; do not hammer
                last = exc
                self.stats.failures += 1
                if attempt + 1 >= self.tries:
                    raise
                wait = exc.retry_after if exc.retry_after is not None else 2 ** attempt
                # a daily budget will not reset inside a CLI run
                if exc.retry_after is not None and exc.retry_after > 120:
                    raise
                self._sleep(min(wait, 60.0))
            except ProviderUnavailable as exc:
                last = exc
                self.stats.failures += 1
                if attempt + 1 >= self.tries:
                    raise
                self.stats.retries += 1
                self._sleep(min(2 ** attempt + random.random(), 30.0))
        raise last  # pragma: no cover - loop always raises or returns

    # -- internals ---------------------------------------------------------
    def _throttle(self) -> None:
        if self.min_interval <= 0:
            return
        delta = time.monotonic() - self._last_call
        if delta < self.min_interval:
            self._sleep(self.min_interval - delta)
        self._last_call = time.monotonic()

    def _once(self, url: str, *, allow_404: bool) -> RawResponse:
        self.stats.requests += 1
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 (fixed https URLs)
                body = resp.read()
                if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                    body = gzip.decompress(body)
                self.stats.bytes_downloaded += len(body)
                headers = {k.lower(): v for k, v in resp.headers.items()}
                status = resp.status
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read() if hasattr(exc, "read") else b""
            retry_after = _retry_after(exc.headers.get("Retry-After") if exc.headers else None)
            detail = _error_detail(raw)
            if status == 404:
                if allow_404:
                    return RawResponse(url=url, status=404, payload=None, retrieved_at=utcnow())
                raise NotFound(self.provider, detail or "no such record", status=404, url=url) from exc
            if status == 429 or (status in (403, 400) and "budget" in detail.lower()):
                payload = _safe_json(raw)
                if isinstance(payload, dict):
                    retry_after = retry_after or _as_float(payload.get("retryAfter"))
                    detail = payload.get("message") or detail
                raise RateLimited(self.provider, detail or "rate limited", status=status,
                                  retry_after=retry_after, url=url) from exc
            if status in (500, 502, 503, 504):
                raise ProviderUnavailable(self.provider, f"server error {status}: {detail}",
                                          status=status, retry_after=retry_after, url=url) from exc
            raise ProviderUnavailable(self.provider, f"HTTP {status}: {detail}", status=status, url=url) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderUnavailable(self.provider, f"network error: {exc}", url=url) from exc

        try:
            payload = json.loads(body.decode("utf-8", "replace")) if body else None
        except json.JSONDecodeError as exc:
            raise MalformedResponse(self.provider, f"not JSON: {body[:120]!r}", status=status, url=url) from exc
        return RawResponse(url=url, status=status, payload=payload, retrieved_at=utcnow(), headers=headers)

    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        """GET a non-JSON resource (Atom/XML, e.g. arXiv)."""
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                sep = "&" if urllib.parse.urlsplit(url).query else "?"
                url = f"{url}{sep}{urllib.parse.urlencode(clean, doseq=True)}"
        self._throttle()
        self.stats.requests += 1
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                body = resp.read()
                self.stats.bytes_downloaded += len(body)
                return body.decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFound(self.provider, "no such record", status=404, url=url) from exc
            if exc.code == 429:
                raise RateLimited(self.provider, "rate limited", status=429, url=url) from exc
            raise ProviderUnavailable(self.provider, f"HTTP {exc.code}", status=exc.code, url=url) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderUnavailable(self.provider, f"network error: {exc}", url=url) from exc


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _error_detail(raw: bytes) -> str:
    payload = _safe_json(raw)
    if isinstance(payload, dict):
        for key in ("message", "error_description", "error", "title"):
            if isinstance(payload.get(key), str):
                return payload[key]
    text = raw.decode("utf-8", "replace").strip().replace("\n", " ")
    return text[:200]
