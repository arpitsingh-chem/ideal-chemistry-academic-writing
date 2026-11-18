"""SQLite persistence for the research layer.

Why SQLite: the corpus a single researcher synchronises is small (10^3–10^5
records), the deployment target is a laptop or a CI runner, and a zero-server
database keeps the base install dependency-free. PostgreSQL is not needed to
satisfy any requirement in the brief, so it is not used.

Guarantees
----------
* **Idempotent**: re-ingesting the same record changes nothing (keyed on
  ``work_id``; the stored fingerprint decides whether an UPDATE is needed).
* **Provenance-preserving**: every raw provider payload is kept verbatim in
  ``provenance``, separate from the normalised row.
* **Auditable**: merges and sync runs are recorded, never silently dropped.
* **Migratable**: ``schema_meta.version`` plus an ordered migration list.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

from ..providers.base import utcnow
from .schema import WorkRecord

SCHEMA_VERSION = 1

_MIGRATIONS: list[str] = [
    # v1 -- initial schema
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS works (
        work_id      TEXT PRIMARY KEY,
        fingerprint  TEXT NOT NULL,
        doi          TEXT,
        title        TEXT,
        year         INTEGER,
        venue        TEXT,
        verification TEXT NOT NULL DEFAULT 'unverified',
        retraction   TEXT NOT NULL DEFAULT 'unknown',
        payload      TEXT NOT NULL,
        first_seen   TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_works_doi   ON works(doi);
    CREATE INDEX IF NOT EXISTS idx_works_year  ON works(year);
    CREATE INDEX IF NOT EXISTS idx_works_venue ON works(venue);
    CREATE TABLE IF NOT EXISTS work_ids (
        work_id TEXT NOT NULL,
        scheme  TEXT NOT NULL,
        value   TEXT NOT NULL,
        PRIMARY KEY (work_id, scheme, value)
    );
    CREATE INDEX IF NOT EXISTS idx_work_ids_value ON work_ids(scheme, value);
    CREATE TABLE IF NOT EXISTS provenance (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        work_id      TEXT NOT NULL,
        provider     TEXT NOT NULL,
        url          TEXT,
        retrieved_at TEXT,
        sha256       TEXT,
        license      TEXT,
        raw          TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_prov_work ON provenance(work_id);
    CREATE TABLE IF NOT EXISTS merges (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        kept_id    TEXT NOT NULL,
        merged_id  TEXT NOT NULL,
        verdict    TEXT NOT NULL,
        score      REAL NOT NULL,
        reasons    TEXT NOT NULL,
        decided_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS sync_runs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        provider    TEXT NOT NULL,
        query       TEXT,
        started_at  TEXT NOT NULL,
        finished_at TEXT,
        status      TEXT NOT NULL,
        requested   INTEGER DEFAULT 0,
        inserted    INTEGER DEFAULT 0,
        updated     INTEGER DEFAULT 0,
        unchanged   INTEGER DEFAULT 0,
        duplicates  INTEGER DEFAULT 0,
        errors      TEXT,
        stats       TEXT
    );
    CREATE TABLE IF NOT EXISTS provider_state (
        provider            TEXT PRIMARY KEY,
        last_attempt_at     TEXT,
        last_success_at     TEXT,
        consecutive_failures INTEGER NOT NULL DEFAULT 0,
        last_error          TEXT,
        retry_after         REAL
    );
    """,
]


@dataclass
class UpsertResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    duplicates_merged: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"inserted": self.inserted, "updated": self.updated,
                "unchanged": self.unchanged, "duplicates_merged": self.duplicates_merged}


class ResearchStore:
    """A single-file research database."""

    def __init__(self, path: str | Path = "research.sqlite3") -> None:
        self.path = Path(path)
        if self.path.parent and str(self.path.parent) not in ("", "."):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.migrate()

    # -- lifecycle ---------------------------------------------------------
    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "ResearchStore":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # -- migrations --------------------------------------------------------
    def migrate(self) -> int:
        current = self.version()
        for index in range(current, len(_MIGRATIONS)):
            self.conn.executescript(_MIGRATIONS[index])
            self.conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES('version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(index + 1),),
            )
            self.conn.commit()
        return self.version()

    def version(self) -> int:
        try:
            row = self.conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
        except sqlite3.OperationalError:
            return 0
        return int(row["value"]) if row else 0

    # -- writes ------------------------------------------------------------
    def upsert(self, records: Iterable[WorkRecord], *, raw_by_work: dict[str, list[dict[str, Any]]] | None = None,
               now: str | None = None) -> UpsertResult:
        """Insert or update records; idempotent on ``work_id`` + fingerprint."""
        stamp = now or utcnow()
        result = UpsertResult()
        raw_by_work = raw_by_work or {}
        with self.transaction() as conn:
            for rec in records:
                work_id = rec.ensure_id()
                fingerprint = rec.fingerprint()
                existing = conn.execute(
                    "SELECT fingerprint FROM works WHERE work_id=?", (work_id,)).fetchone()
                payload = json.dumps(rec.as_dict(), ensure_ascii=False, sort_keys=True)
                if existing is None:
                    conn.execute(
                        "INSERT INTO works(work_id, fingerprint, doi, title, year, venue,"
                        " verification, retraction, payload, first_seen, updated_at)"
                        " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (work_id, fingerprint, rec.doi, rec.title, rec.publication_year,
                         rec.venue, str(rec.verification), str(rec.retraction_status),
                         payload, stamp, stamp))
                    result.inserted += 1
                elif existing["fingerprint"] != fingerprint:
                    conn.execute(
                        "UPDATE works SET fingerprint=?, doi=?, title=?, year=?, venue=?,"
                        " verification=?, retraction=?, payload=?, updated_at=? WHERE work_id=?",
                        (fingerprint, rec.doi, rec.title, rec.publication_year, rec.venue,
                         str(rec.verification), str(rec.retraction_status), payload, stamp, work_id))
                    result.updated += 1
                else:
                    result.unchanged += 1
                    # still refresh provider links/provenance below

                for scheme, value in {**rec.provider_ids,
                                      **({"doi": rec.doi} if rec.doi else {})}.items():
                    conn.execute(
                        "INSERT OR IGNORE INTO work_ids(work_id, scheme, value) VALUES(?,?,?)",
                        (work_id, scheme, str(value)))

                for prov in rec.sources:
                    exists = conn.execute(
                        "SELECT 1 FROM provenance WHERE work_id=? AND provider=? AND sha256=?",
                        (work_id, prov.provider, prov.payload_sha256)).fetchone()
                    if exists:
                        continue
                    raw_items = raw_by_work.get(work_id) or []
                    raw = json.dumps(raw_items[0], ensure_ascii=False, default=str) if raw_items else None
                    conn.execute(
                        "INSERT INTO provenance(work_id, provider, url, retrieved_at, sha256,"
                        " license, raw) VALUES(?,?,?,?,?,?,?)",
                        (work_id, prov.provider, prov.url, prov.retrieved_at,
                         prov.payload_sha256, prov.license, raw))
        return result

    def record_merge(self, kept_id: str, merged_id: str, decision: Any, now: str | None = None) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO merges(kept_id, merged_id, verdict, score, reasons, decided_at)"
                " VALUES(?,?,?,?,?,?)",
                (kept_id, merged_id,
                 getattr(decision.verdict, "value", str(decision.verdict)),
                 float(decision.score), decision.explain(), now or utcnow()))
            conn.execute("DELETE FROM works WHERE work_id=?", (merged_id,))

    def start_sync(self, provider: str, query: str | None) -> int:
        with self.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO sync_runs(provider, query, started_at, status) VALUES(?,?,?,?)",
                (provider, query, utcnow(), "running"))
            return int(cur.lastrowid)

    def finish_sync(self, run_id: int, *, status: str, result: UpsertResult | None = None,
                    errors: list[str] | None = None, stats: dict[str, Any] | None = None,
                    requested: int = 0) -> None:
        result = result or UpsertResult()
        with self.transaction() as conn:
            conn.execute(
                "UPDATE sync_runs SET finished_at=?, status=?, requested=?, inserted=?,"
                " updated=?, unchanged=?, errors=?, stats=? WHERE id=?",
                (utcnow(), status, requested, result.inserted, result.updated,
                 result.unchanged, json.dumps(errors or []), json.dumps(stats or {}), run_id))

    def note_provider(self, provider: str, *, ok: bool, error: str | None = None,
                      retry_after: float | None = None) -> None:
        stamp = utcnow()
        with self.transaction() as conn:
            row = conn.execute("SELECT consecutive_failures FROM provider_state WHERE provider=?",
                               (provider,)).fetchone()
            failures = 0 if ok else ((row["consecutive_failures"] if row else 0) + 1)
            conn.execute(
                "INSERT INTO provider_state(provider, last_attempt_at, last_success_at,"
                " consecutive_failures, last_error, retry_after) VALUES(?,?,?,?,?,?)"
                " ON CONFLICT(provider) DO UPDATE SET"
                "   last_attempt_at=excluded.last_attempt_at,"
                "   last_success_at=COALESCE(excluded.last_success_at, provider_state.last_success_at),"
                "   consecutive_failures=excluded.consecutive_failures,"
                "   last_error=excluded.last_error,"
                "   retry_after=excluded.retry_after",
                (provider, stamp, stamp if ok else None, failures,
                 None if ok else (error or "")[:500], retry_after))

    # -- reads -------------------------------------------------------------
    def get(self, work_id: str) -> WorkRecord | None:
        row = self.conn.execute("SELECT payload FROM works WHERE work_id=?", (work_id,)).fetchone()
        return WorkRecord.from_dict(json.loads(row["payload"])) if row else None

    def find_by_identifier(self, scheme: str, value: str) -> WorkRecord | None:
        value = value.lower() if scheme == "doi" else value
        row = self.conn.execute(
            "SELECT w.payload FROM works w JOIN work_ids i ON i.work_id = w.work_id"
            " WHERE i.scheme=? AND lower(i.value)=? LIMIT 1", (scheme, value)).fetchone()
        return WorkRecord.from_dict(json.loads(row["payload"])) if row else None

    def count(self, where: str = "", params: tuple = ()) -> int:
        sql = "SELECT COUNT(*) AS n FROM works" + (f" WHERE {where}" if where else "")
        return int(self.conn.execute(sql, params).fetchone()["n"])

    def all_works(self, limit: int | None = None) -> list[WorkRecord]:
        sql = "SELECT payload FROM works ORDER BY year DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [WorkRecord.from_dict(json.loads(r["payload"])) for r in self.conn.execute(sql)]

    def search(self, query: str, limit: int = 25) -> list[WorkRecord]:
        """SQL prefilter + Python scoring (portable, no FTS extension needed)."""
        like = f"%{query.lower()}%"
        rows = self.conn.execute(
            "SELECT payload FROM works WHERE lower(COALESCE(title,'')) LIKE ?"
            " OR lower(COALESCE(venue,'')) LIKE ? LIMIT 500", (like, like)).fetchall()
        from .dedup import title_similarity
        scored = []
        for row in rows:
            payload = json.loads(row["payload"])       # dict, not the raw JSON string
            scored.append((title_similarity(query, payload.get("title")), payload))
        scored.sort(key=lambda x: -x[0])
        return [WorkRecord.from_dict(payload) for score, payload in scored[:limit] if score > 0]

    # -- diagnostics -------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        def scalar(sql: str, params: tuple = ()) -> Any:
            row = self.conn.execute(sql, params).fetchone()
            return row[0] if row else None

        providers = self.conn.execute(
            "SELECT provider, COUNT(*) AS n, MAX(retrieved_at) AS last FROM provenance"
            " GROUP BY provider ORDER BY n DESC").fetchall()
        return {
            "path": str(self.path),
            "schema_version": self.version(),
            "works": scalar("SELECT COUNT(*) FROM works") or 0,
            "with_doi": scalar("SELECT COUNT(*) FROM works WHERE doi IS NOT NULL") or 0,
            "venues": scalar("SELECT COUNT(DISTINCT venue) FROM works WHERE venue IS NOT NULL") or 0,
            "year_min": scalar("SELECT MIN(year) FROM works") or None,
            "year_max": scalar("SELECT MAX(year) FROM works") or None,
            "merged_away": scalar("SELECT COUNT(*) FROM merges") or 0,
            "conflicting": scalar("SELECT COUNT(*) FROM works WHERE verification='conflicting'") or 0,
            "cross_checked": scalar("SELECT COUNT(*) FROM works WHERE verification='cross_checked'") or 0,
            "retracted": scalar("SELECT COUNT(*) FROM works WHERE retraction='retracted'") or 0,
            "provenance_rows": scalar("SELECT COUNT(*) FROM provenance") or 0,
            "providers": [dict(r) for r in providers],
            "sync_runs": scalar("SELECT COUNT(*) FROM sync_runs") or 0,
            "last_sync": scalar("SELECT MAX(finished_at) FROM sync_runs WHERE status='ok'"),
            "provider_state": [dict(r) for r in self.conn.execute(
                "SELECT * FROM provider_state ORDER BY provider").fetchall()],
        }
