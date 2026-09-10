"""The provider schema, indexed once and served from disk.

FR-SCH-01: completion, hover and snippets are answered from here, never from an
in-session `tofu init`. Ingesting the AWS provider is slow enough to notice once
and fast enough to forget afterwards, which is the whole point of doing it once
per provider version rather than once per session.

What this index does not carry is as important as what it does. The schema has
no force-replacement flag and no default; see `docs/findings/001-...`. Nothing
here invents either, because a workbench that guesses teaches people wrong.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS providers (
    id       INTEGER PRIMARY KEY,
    address  TEXT NOT NULL,
    version  TEXT NOT NULL,
    UNIQUE (address, version)
);

CREATE TABLE IF NOT EXISTS resources (
    id          INTEGER PRIMARY KEY,
    provider_id INTEGER NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    type        TEXT NOT NULL,
    UNIQUE (provider_id, kind, type)
);

CREATE TABLE IF NOT EXISTS attributes (
    id          INTEGER PRIMARY KEY,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    path        TEXT NOT NULL,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL,
    required    INTEGER NOT NULL DEFAULT 0,
    optional    INTEGER NOT NULL DEFAULT 0,
    computed    INTEGER NOT NULL DEFAULT 0,
    sensitive   INTEGER NOT NULL DEFAULT 0,
    deprecated  INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS nested_blocks (
    id          INTEGER PRIMARY KEY,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    path        TEXT NOT NULL,
    name        TEXT NOT NULL,
    nesting     TEXT NOT NULL,
    min_items   INTEGER,
    max_items   INTEGER
);

CREATE INDEX IF NOT EXISTS attributes_by_resource ON attributes(resource_id, path);
CREATE INDEX IF NOT EXISTS resources_by_type ON resources(type);

-- FR-SCH-08: find a resource by what it does when you do not know its name.
CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(
    subject, kind, body, tokenize = 'porter'
);
"""


@dataclass(frozen=True)
class Attribute:
    """One argument of a resource, exactly as the provider declares it."""

    name: str
    path: str
    type: str
    required: bool
    optional: bool
    computed: bool
    sensitive: bool
    deprecated: bool
    description: str

    @property
    def address(self) -> str:
        return f"{self.path}.{self.name}" if self.path else self.name

    @property
    def type_label(self) -> str:
        """The type as a person would write it, rather than as JSON."""
        return _type_label(json.loads(self.type))

    @property
    def is_read_only(self) -> bool:
        """Computed and not settable: worth completing as a reference, never as an argument."""
        return self.computed and not (self.required or self.optional)


@dataclass(frozen=True)
class NestedBlock:
    """A block inside a resource, like `ingress` or `timeouts`."""

    name: str
    path: str
    nesting: str
    min_items: int | None
    max_items: int | None


@dataclass(frozen=True)
class Resource:
    """A resource or data source type, and which provider version declared it."""

    type: str
    kind: str
    provider: str
    provider_version: str


def _type_label(declared: Any) -> str:
    """Renders the schema's type encoding as something readable."""
    if isinstance(declared, str):
        return declared
    if isinstance(declared, list) and declared:
        head = declared[0]
        if head in ("list", "set", "map") and len(declared) > 1:
            return f"{head}({_type_label(declared[1])})"
        if head == "object" and len(declared) > 1 and isinstance(declared[1], dict):
            return f"object({len(declared[1])} attributes)"
        return str(head)
    return "unknown"


def location(home: Path | None = None) -> Path:
    """Where a built index lives.

    The user's cache directory: it is derived from providers already on disk,
    it can be rebuilt from them, and nothing is lost by deleting it — which is
    exactly what a cache is.
    """
    if home is not None:
        return Path(home) / ".cache" / "backsight" / "schema.sqlite"
    root = os.environ.get("XDG_CACHE_HOME")
    base = Path(root) if root else Path.home() / ".cache"
    return base / "backsight" / "schema.sqlite"


def open_if_built(home: Path | None = None) -> SchemaIndex | None:
    """The index if it has been built, and None if it has not.

    An absent index is the ordinary state before anything has been indexed.
    Raising here would make the whole window fail to open over a cache file.
    """
    path = location(home)
    if not path.is_file():
        return None
    try:
        return SchemaIndex(path)
    except sqlite3.Error:
        # A truncated or corrupt cache is worth nothing and must not be fatal.
        return None


class SchemaIndex:
    """A built index, opened for reading."""

    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self._connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> SchemaIndex:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def providers(self) -> list[tuple[str, str]]:
        rows = self._connection.execute(
            "SELECT address, version FROM providers ORDER BY address, version"
        )
        return [(r["address"], r["version"]) for r in rows]

    def resource(
        self, type_: str, *, kind: str = "resource", provider_version: str | None = None
    ) -> Resource | None:
        rows = self._connection.execute(
            """
            SELECT r.type, r.kind, p.address, p.version
              FROM resources r JOIN providers p ON p.id = r.provider_id
             WHERE r.type = ? AND r.kind = ?
               AND (? IS NULL OR p.version = ?)
             ORDER BY p.version DESC
            """,
            (type_, kind, provider_version, provider_version),
        ).fetchall()
        if not rows:
            return None
        row = rows[0]
        return Resource(
            type=row["type"],
            kind=row["kind"],
            provider=row["address"],
            provider_version=row["version"],
        )

    def attributes(
        self,
        type_: str,
        *,
        kind: str = "resource",
        path: str = "",
        provider_version: str | None = None,
    ) -> list[Attribute]:
        """Every attribute at one level of a resource, required ones first."""
        rows = self._connection.execute(
            """
            SELECT a.* FROM attributes a
              JOIN resources r ON r.id = a.resource_id
              JOIN providers p ON p.id = r.provider_id
             WHERE r.type = ? AND r.kind = ? AND a.path = ?
               AND (? IS NULL OR p.version = ?)
             ORDER BY a.required DESC, a.name
            """,
            (type_, kind, path, provider_version, provider_version),
        )
        return [_attribute(r) for r in rows]

    def attribute(
        self,
        type_: str,
        name: str,
        *,
        kind: str = "resource",
        path: str = "",
        provider_version: str | None = None,
    ) -> Attribute | None:
        for found in self.attributes(
            type_, kind=kind, path=path, provider_version=provider_version
        ):
            if found.name == name:
                return found
        return None

    def nested_blocks(
        self, type_: str, *, kind: str = "resource", path: str = ""
    ) -> list[NestedBlock]:
        rows = self._connection.execute(
            """
            SELECT b.* FROM nested_blocks b
              JOIN resources r ON r.id = b.resource_id
             WHERE r.type = ? AND r.kind = ? AND b.path = ?
             ORDER BY b.name
            """,
            (type_, kind, path),
        )
        return [
            NestedBlock(
                name=r["name"],
                path=r["path"],
                nesting=r["nesting"],
                min_items=r["min_items"],
                max_items=r["max_items"],
            )
            for r in rows
        ]

    def resource_types(
        self, prefix: str = "", *, kind: str = "resource", limit: int = 50
    ) -> list[str]:
        rows = self._connection.execute(
            """
            SELECT DISTINCT type FROM resources
             WHERE kind = ? AND type LIKE ? ORDER BY type LIMIT ?
            """,
            (kind, f"{prefix}%", limit),
        )
        return [r["type"] for r in rows]

    def search(self, text: str, *, limit: int = 20) -> list[tuple[str, str]]:
        """FR-SCH-08: find something by what it does when you do not know its name."""
        cleaned = " ".join(f'"{word}"' for word in text.split() if word)
        if not cleaned:
            return []
        rows = self._connection.execute(
            "SELECT subject, kind FROM search WHERE search MATCH ? ORDER BY rank LIMIT ?",
            (cleaned, limit),
        )
        return [(r["subject"], r["kind"]) for r in rows]

    def counts(self) -> dict[str, int]:
        """What the index holds. Written out rather than built from a table name,
        because a query assembled by string is one rename away from being one
        assembled from somebody's input."""
        row = self._connection.execute(
            """
            SELECT (SELECT count(*) FROM providers)     AS providers,
                   (SELECT count(*) FROM resources)     AS resources,
                   (SELECT count(*) FROM attributes)    AS attributes,
                   (SELECT count(*) FROM nested_blocks) AS nested_blocks
            """
        ).fetchone()
        return dict(row)


def _attribute(row: sqlite3.Row) -> Attribute:
    return Attribute(
        name=row["name"],
        path=row["path"],
        type=row["type"],
        required=bool(row["required"]),
        optional=bool(row["optional"]),
        computed=bool(row["computed"]),
        sensitive=bool(row["sensitive"]),
        deprecated=bool(row["deprecated"]),
        description=row["description"],
    )


def build(schema: dict[str, Any], database: Path, versions: dict[str, str]) -> None:
    """Writes an index for one `providers schema -json` document.

    `versions` maps a provider address to the version that produced this schema.
    The schema itself does not say — the addresses in it carry no version, and
    the `version` on a resource is its state migration schema, not the provider's.
    """
    missing = sorted(set(schema.get("provider_schemas", {})) - set(versions))
    if missing:
        raise ValueError(f"no version given for {', '.join(missing)}")

    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    try:
        connection.executescript(SCHEMA)
        for address, provider in schema.get("provider_schemas", {}).items():
            _ingest_provider(connection, address, versions[address], provider)
        connection.commit()
    finally:
        connection.close()


def _ingest_provider(
    connection: sqlite3.Connection, address: str, version: str, provider: dict[str, Any]
) -> None:
    cursor = connection.execute(
        "INSERT OR IGNORE INTO providers (address, version) VALUES (?, ?)", (address, version)
    )
    provider_id = (
        cursor.lastrowid
        or connection.execute(
            "SELECT id FROM providers WHERE address = ? AND version = ?", (address, version)
        ).fetchone()[0]
    )

    # The provider's own configuration block is a schema too, and it is where the
    # endpoint list lives. Indexed under its own kind so it cannot collide with a
    # resource type that happens to share the name.
    own = provider.get("provider")
    if own:
        _ingest_entry(connection, provider_id, "provider", address.rsplit("/", 1)[-1], own)

    for kind, key in (("resource", "resource_schemas"), ("data", "data_source_schemas")):
        for type_, entry in (provider.get(key) or {}).items():
            _ingest_entry(connection, provider_id, kind, type_, entry)


def _ingest_entry(
    connection: sqlite3.Connection, provider_id: int, kind: str, type_: str, entry: dict[str, Any]
) -> None:
    resource_id = connection.execute(
        "INSERT INTO resources (provider_id, kind, type) VALUES (?, ?, ?)",
        (provider_id, kind, type_),
    ).lastrowid
    summary: list[str] = []
    for path, name, attribute in _walk(entry.get("block") or {}):
        connection.execute(
            """
            INSERT INTO attributes
                (resource_id, path, name, type, required, optional, computed,
                 sensitive, deprecated, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resource_id,
                path,
                name,
                json.dumps(attribute.get("type", "unknown")),
                int(bool(attribute.get("required"))),
                int(bool(attribute.get("optional"))),
                int(bool(attribute.get("computed"))),
                int(bool(attribute.get("sensitive"))),
                int(bool(attribute.get("deprecated"))),
                attribute.get("description") or "",
            ),
        )
        summary.append(name)
        if attribute.get("description"):
            summary.append(attribute["description"])
    for path, name, block in _walk_blocks(entry.get("block") or {}):
        connection.execute(
            """
            INSERT INTO nested_blocks
                (resource_id, path, name, nesting, min_items, max_items)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                resource_id,
                path,
                name,
                block.get("nesting_mode", "single"),
                block.get("min_items"),
                block.get("max_items"),
            ),
        )
    connection.execute(
        "INSERT INTO search (subject, kind, body) VALUES (?, ?, ?)",
        (type_, kind, " ".join(summary)),
    )


def _walk(block: dict[str, Any], path: str = "") -> Iterator[tuple[str, str, dict[str, Any]]]:
    for name, attribute in (block.get("attributes") or {}).items():
        yield path, name, attribute
    for name, nested in (block.get("block_types") or {}).items():
        inner = f"{path}.{name}" if path else name
        yield from _walk(nested.get("block") or {}, inner)


def _walk_blocks(
    block: dict[str, Any], path: str = ""
) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for name, nested in (block.get("block_types") or {}).items():
        yield path, name, nested
        inner = f"{path}.{name}" if path else name
        yield from _walk_blocks(nested.get("block") or {}, inner)
