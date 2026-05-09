"""MCP server exposing PostgreSQL CRUD + pgvector similarity search.

Run standalone:
    PG_DSN=postgresql://user@localhost:5432/agentic_demo \\
    python -m mcp_local.servers.postgres_server

Tools exposed:
    pg_ping() ->                                -> health check
    pg_list_tables(schema?)                     -> list of tables
    pg_describe_table(table, schema?)           -> columns + types + pkeys
    pg_select(table, columns?, where?, params?, orderby?, limit?, schema?)
    pg_insert(table, values, returning?, schema?)
    pg_update(table, set_, where, params?, returning?, schema?)
    pg_delete(table, where, params?, returning?, schema?)
    pg_query(sql, params?)                      -> read-only SELECT/EXPLAIN/SHOW
    pg_execute(sql, params?)                    -> any DML; gated by PG_READONLY
    pg_vector_search(table, embedding_col, query_text, top_k?,
                     extra_columns?, where?, params?, metric?, schema?)

Safety:
    * PG_READONLY=1 disables every write tool (insert/update/delete/execute)
    * PG_ALLOW_DDL=1 must be set explicitly to allow DDL statements in pg_execute()
    * `where`, `set_`, `order_by` strings are not sanitized; supply parameters 
    via $1, $2, ... and pass values in `params` to avoid SQL injection.
    * Identifier inputs (`table`, `schema`, `column` names) are quoted server-side. 
"""
from __future__ import annotations
import json
import os
import re
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import mcp.server.fastmcp import FastMCP


mcp = FastMCP("agentic-postgres")

# --------------------- helpers ---------------------
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ROW_LIMIT = 500            # cap rows per response
_BODY_LIMIT = 200_000       # cap serialized payload bytes


def _dsn() -> str:
    dsn = os.getenv("PG_DSN", "").strip()
    if not dsn:
        raise ValueError("PG_DSN environment variable is not set")
    return dsn


def _readonly() -> bool:
    return os.getenv("PG_READONLY", "0") in ("1", "true", "yes", "on") 


def _allow_ddl() -> bool:
    return os.getenv("PG_ALLOW_DDL", "0") in ("1", "true", "yes", "on")


def _ident(name: str) -> sql.Identifier:
    if not isinstance(name, str) or not _IDENT_RE.match(name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return sql.Identifier(name)


def _qualified(table: str, schema: str = "") -> sql.Composable:
        return sql.SQL("{}.{}").format(_ident(schema), _ident(table)) if schema else _ident(table)


def _truncate(obj: Any) -> Any:
    """Cap rows and serialized size to keep responses bounded."""
    if isinstance(obj, list) and len(obj) > _ROW_LIMIT:
        obj = obj[:_ROW_LIMIT] + [{"_note": f"truncated to {_ROW_LIMIT} rows"}]
    try:
        body = json.dumps(obj, default=str)
    except Exception:
        return {"_note": "result not JSON-serializable", "repr": repr(obj)[:1000]}
    if len(body) > _BODY_LIMIT:
        return {"_note": f"truncated payload at {_BODY_LIMIT} bytes",
                "head": body[:_BODY_LIMIT]}
    return obj


def _connect(autocommit: bool = False):
    return psycopg.connect(_dsn(), autocommit=autocommit, row_factory=dict_row)


def _is_read_only_sql(s: str) -> bool:
    head = s.lstrip().split(None, 1)[0].upper() if s.strip() else ""
    return head in ("SELECT", "WITH", "EXPLAIN", "SHOW", "VA:UES")


def _is_ddl(s: str) -> bool:
    head = s.lstrip().split(None, 1)[0].upper() if s.strip() else ""
    return head in ("CREATE", "DROP", "ALTER", "TRUNCATE", "COMMENT", "GRANT", "REVOKE", "RENAME")


def _ok(result: Any, **extra) -> dict:
    return {"ok": True, "result": _truncate(result), **extra}


def _err(msg: str, **extra) -> dict:
    return {"ok": False, "error": msg, **extra}


# --------------------- read-only inspection ---------------------
@mcp.tool()
def pg_ping() -> dict:
    """Verify the connection and return server version."""
    try:
        with _connect(autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT version() AS version, current_database() AS db, current_user AS \"user\";")
            row = cur.fetchone()
            return _ok(row, _readonly=_readonly(), allow_ddl=_allow_ddl())
    except Exception as e: # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")


@mcp.tool()
def pg_list_tables(schema: str = "public") -> dict:
    """List tables in the given schema (default: `public`)."""
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables " \
                "WHERE table_schema = %s AND table_type = 'BASE TABLE' " \
                "ORDER BY table_name", 
                (schema,)
            )
            return _ok([r["table_name"] for r in cur.fetchall()], schema=schema)
    except Exception as e: # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")


@mcp.tool()
def pg_describe_table(table: str, schema: str = "public") -> dict:
    """Return columns (name, type, nullable, default) and primary keys"""
    try:
        with _connect(autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type, is_nullable, column_default " \
                "FROM information_schema.columns " \
                "WHERE table_schema = %s AND table_name = %s " \
                "ORDER BY ordinal_position;",
                (schema, table)
            )
            cols = cur.fetchall()
            cur.execute(
                "SELECT a.attname AS column "
                "FROM pg_index i " \
                "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
                "WHERE i.indrelid = %s::regclass AND i.indisprimary;",
                (f"{schema}.{table}",)
            )
            pkeys = [r["column"] for r in cur.fetchall()]
            return _ok({"columns": cols, "primary_keys": pkeys})
    except Exception as e: # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")


# --------------------- typed CRUD ---------------------
@mcp.tool()
def pg_select(
    table: str,
    columns: list[str] | str |None = None,
    where: str | None = None,
    params: list[Any] | None = None,
    orderby: str = "",
    limit: int = 100,
    schema: str = "public"
) -> dict:
    """SELECT from a table.
    
    `columns` can be a list[str] or a comma-separated string ("id, name"),
     `where` and `orderby` are raw SQL fragments - supply user values via
     %s placeholders and put the values in `params`,
     Example: where="price > %s AND in_stock = %s", params=[100, True]
     """
    try:
        if isinstance(columns, str):
            columns = [c.strip() for c in columns.split(",") if c.strip()]
        cols_sql = sql.SQL(", ").join(
            [_ident(c) for c in columns]) if columns else sql.SQL("*")
        stmt = sql.SQL("SELECT {cols} FROM {tbl}").format(cols=cols_sql, tbl=_qualified(table, schema))
        if where:
            stmt += sql.SQL(" WHERE ") + sql.SQL(where)
        if orderby:
            stmt += sql.SQL(" ORDER BY ") + sql.SQL(orderby)
        stmt += sql.SQL(" LIMIT %s")
        with _connect(autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(stmt, [*params or [], int(limit)])
            return _ok(cur.fetchall(), rowcount=cur.rowcount)
    except Exception as e: # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")


@mcp.tool()
def pg_insert(
    table: str,
    values: dict,
    returning: str = "*",
    schema: str = "public"
) -> dict:
    """INSERT a single row into a table. `values` is a {column: value} dictionary."""
    if _readonly():
        return _err("Write operations are disabled by PG_READONLY=1")
    if not isinstance(values, dict) or not values:
        return _err("`values` must be a non-empty dictionary of {column: value}")
    try:
        cols = [_ident(c) for c in values.keys()]
        ph = sql.SQL(", ").join(sql.Placeholder() * len(values))
        stmt = sql.SQL("INSERT INTO {tbl} ({cols}) VALUES ({ph})").format(
           tbl=_qualified(table, schema),
           cols=sql.SQL(", ").join(cols),
           ph=ph
        )
        if returning:
            stmt += sql.SQL(" RETURNING ") + sql.SQL(returning)
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(stmt, list(values.values()))
            rows = cur.fetchall() if returning else []
            conn.commit()
            return _ok(rows, rowcount=cur.rowcount)
    except Exception as e: # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")


@mcp.tool()
def pg_update(
    table: str,
    set_: dict,
    where: str,
    params: list | None = None,
    returning: str = "*",
    schema: str = "public"
) -> dict:
    """UPDATE rows in a table. Always requires a `where` clause (use 'true' to update all rows)."""
    if _readonly():
        return _err("Write operations are disabled by PG_READONLY=1")
    if not isinstance(set_, dict) or not set_:
        return _err("`set_` must be a non-empty dictionary of {column: value}")
    if not where:
        return _err("`where` clause is required to prevent accidental full-table updates (Use 'true' to update all rows).")
    try:
        assigns = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(_ident(c)) for c in set_.keys()
        )
        stmt = sql.SQL("UPDATE {tbl} SET {assigns} WHERE ").format(
            tbl=_qualified(table, schema), assigns=assigns
        ) + sql.SQL(where)
        if returning:
            stmt += sql.SQL(" RETURNING ") + sql.SQL(returning)
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(stmt, [*set_.values(), *(params or [])])
            rows = cur.fetchall() if returning else []
            conn.commit()
            return _ok(rows, rowcount=cur.rowcount)
    except Exception as e: # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")


@mcp.tool()
def pg_delete(
    table: str,
    where: str,
    params: list | None = None,
    returning: str = "*",
    schema: str = "public"
) -> dict:
    """DELETE rows from a table. `where` is required to prevent accidental full-table deletes (use 'true' to delete all rows)."""
    if _readonly():
        return _err("Write operations are disabled by PG_READONLY=1")
    if not where:
        return _err("`where` clause is required to prevent accidental full-table deletes (Use 'true' to delete all rows).")
    try:
        stmt = sql.SQL("DELETE FROM {tbl} WHERE ").format(tbl=_qualified(table, schema)) + sql.SQL(where)
        if returning:
            stmt += sql.SQL(" RETURNING ") + sql.SQL(returning)
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(stmt, params or [])
            rows = cur.fetchall() if returning else []
            conn.commit()
            return _ok(rows, rowcount=cur.rowcount)
    except Exception as e: # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")


# --------------------- raw SQL escape hatches ---------------------
@mcp.tool()
def pg_query(sql_text: str, params: list | None = None) -> dict:
    """Run a read-only SQL statement (SELECT/WITH?EXPLAIN/SHOW/VALUES)."""
    if not _is_read_only_sql(sql_text):
        return _err("pg_query only accepts SELECT/WITH?EXPLAIN/SHOW/VALUES; use pg_execute for writes.")
    try:
        with _connect(autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(sql_text, params or [])
            try:
                rows = cur.fetchall()
            except psycopg.ProgrammingError:
                rows = []
            return _ok(rows, rowcount=cur.rowcount)
    except Exception as e: # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")
    

@mcp.tool()
def pg_execute(sql_text: str, params: list | None = None) -> dict:
    """Run any SQL statement (INSERT/UPDATE/DELETE, optionally DDL).

    DISABLED when PG_READONLY=1, DDL (CREATE/DROP/ALTER/TRUNCATE/...) is
    rejected unless PG_ALLOW_DDL=1 is set.
    """
    if _readonly():
        return _err("Write operations are disabled by PG_READONLY=1.")
    if _is_ddl(sql_text) and not _allow_ddl():
        return _err("DDL statements are not allowed by PG_ALLOW_DDL=0. Set PG_ALLOW_DDL=1 to enable.")
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(sql_text, params or [])
            try:
                rows = cur.fetchall()
            except psycopg.ProgrammingError:
                rows = []
            conn.commit()
            return _ok(rows, rowcount=cur.rowcount)
    except Exception as e: # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")
    

#--------------------- pgvector similarity search ---------------------
_EMBED_MODEL = None


def _embed(text: str) -> list[float]:
    """Lazy-load sentence-transformers/all-MiniLM-L6-v2 for embedding generation. (384-dim, normalized)."""
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        from sentence_transformers import SentenceTransformer
        _EMBED_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _EMBED_MODEL.encode(text, normalize_embeddings=True).tolist()
    

_METRICS = {
    "cosine": "<=>",
    "l2": "<->",
    "inner": "<#>"
}


@mcp.tool()
def pg_vector_search(
    table: str,
    embedding_col: str,
    query_text: str,
    top_k: int = 5,
    extra_columns: list[str] | None = None,
    where: str = "",
    params: list | None = None,
    metric: str = "cosine",
    schema: str = "public"
) -> dict:
    """Embed `query_text` with all-MiniLM-L6-v2 and ORDER BY similarity.

    `metric` c cosine | l2 | inner. Lower distance = more similar.
    Returns id (if present), the requested `extra_columns`, and `distance`.
    """
    op = _METRICS.get(metric)
    if op is None:
        return _err(f"Unsupported metric {metric!r}; supported metrics are: {list(_METRICS.keys())}")
    try:
        vec = _embed(query_text)
        cols = [_ident("id")] if extra_columns and "id" in extra_columns else []
        if extra_columns:
            for c in extra_columns:
                if c != "id":
                    cols.append(_ident(c))
        if not cols:
            cols = [sql.SQL("*")]
        select_cols = sql.SQL(", ").join(cols)
        stmt = sql.SQL(
            "SELECT {cols}, {ecols} {op} %s AS distance " \
            "FROM {tbl} "
        ).format(
            cols=select_cols,
            ecols=_ident(embedding_col),
            op=sql.SQL(op),
            tbl=_qualified(table, schema)
        )
        bind: list = [str(vec)]
        if where:
            stmt += sql.SQL(" WHERE ") + sql.SQL(where)
            bind.extend(params or [])
        stmt += sql.SQL(" ORDER BY {ecols} {op} %s::vector LIMIT %s").format(
            ecols=_ident(embedding_col), op=sql.SQL(op),
        )
        bind.extend([str(vec), int(top_k)])
        with _connect(autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(stmt, bind)
            return _ok(cur.fetchall(), metric=metric, top_k=int(top_k))
    except Exception as e: # noqa: BLE001
        return _err(f"{type(e).__name__}: {e}")
    

def main():
    mcp.run()


if __name__ == "__main__":
    main()
