"""Ossie 공식 적합성 사례를 t2s 엔진으로 돌린다. OSSIE_DIR 에 apache/ossie 저장소 경로를 주면 돈다(없으면 건너뛴다).

OSSIE_DIR=~/ossie uv run pytest tests/test_ossie_compliance.py

- compliance/wide_table(3층 넓은 표 질의): strict=True 로 돌린다. 규격 밖 계산 없이 규격 그대로 답하거나 같은 오류 코드를 내야 한다.
  데이터는 SQLite 메모리 DB 를 스키마 이름(retail, stores)으로 붙여(ATTACH) 싣는다.
- compliance/query(2층 SQL 의 AGG): t2s.measures.rewrite 로 바꾼 SQL 을 DuckDB 에서 돌린다. 사례가 DuckDB 문법(ROLLUP, GROUP BY ALL)을 쓴다.
  duckdb 패키지가 있어야 돈다: OSSIE_DIR=~/ossie uv run --with duckdb pytest tests/test_ossie_compliance.py
- 사례의 정의 파일에는 승인 상태가 없어 승인 전 지표·연결도 쓴다(t2s 의 미리 보기와 같다).
"""
import json
import math
from decimal import Decimal
import os
import re
import sqlite3
from pathlib import Path

import pytest
import sqlglot

from t2s.engine import SemanticModel
from t2s.measures import rewrite
from t2s.ossie import EngineError, read_yaml

OSSIE = Path(os.environ.get("OSSIE_DIR", "/nonexistent")).expanduser()
WIDE = OSSIE / "compliance" / "wide_table"
QUERY = OSSIE / "compliance" / "query"
QUERY_CASES = sorted(p.name for p in (QUERY / "cases").iterdir()) if (QUERY / "cases").is_dir() else []
WIDE_CASES = sorted(p.name for p in (WIDE / "cases").iterdir()) if (WIDE / "cases").is_dir() else []
FIXTURES = {
    "retail": ("retail/retail.sql", "retail/retail_model.ossie.yaml"),
    "stores": ("stores/stores.sql", "stores/stores_model.ossie.yaml"),
    "stores_ambiguous": ("stores/stores.sql", "stores/stores_ambiguous_model.ossie.yaml"),
}


def load_sql(path: Path) -> sqlite3.Connection:
    """사례 데이터 SQL 을 SQLite 에 싣는다. 스키마는 같은 이름의 메모리 DB 를 붙여 흉내 낸다."""
    text = path.read_text(encoding="utf-8")
    con = sqlite3.connect(":memory:")
    for schema in re.findall(r"(?m)^CREATE SCHEMA (\w+);", text):
        con.execute(f"ATTACH ':memory:' AS {schema}")
    con.executescript(re.sub(r"(?m)^(DROP|CREATE) SCHEMA .*;$", "", text))
    return con


def _cell(got, want) -> bool:
    """NULL 끼리 같다. 정확한 수는 같아야 하고, 근삿값(float)이 끼면 상대 1e-9 안에서 같다(compliance/query/README.md)."""
    if got is None or want is None:
        return got is None and want is None
    num = (int, float, Decimal)
    if isinstance(want, num) and not isinstance(want, bool):
        if not isinstance(got, num) or isinstance(got, bool):
            return False
        if isinstance(got, float) or isinstance(want, float):
            return math.isclose(float(got), float(want), rel_tol=1e-9, abs_tol=1e-9)
        return Decimal(got) == Decimal(want)
    return got == want


def same_rows(got: list, want: list) -> bool:
    """순서 없이 같은 행들인지. 숫자는 1e-9 안에서 같으면 같다."""
    rest = [tuple(r) for r in got]
    for w in want:
        hit = next((i for i, g in enumerate(rest) if len(g) == len(w) and all(map(_cell, g, w))), None)
        if hit is None:
            return False
        rest.pop(hit)
    return not rest


@pytest.mark.parametrize("case", WIDE_CASES)
def test_wide_table(case):
    folder = WIDE / "cases" / case
    query = json.loads((folder / "query.json").read_text(encoding="utf-8"))
    want = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    sql_file, model_file = FIXTURES[want.get("fixture", "retail")]
    model = SemanticModel(read_yaml(WIDE / model_file))
    try:
        out = model.query(query, "sqlite", allow_draft=True, draft_joins=True, strict=True)
    except EngineError as e:
        assert e.ossie == want.get("error"), f"{e.code}/{e.ossie}: {e}"
        return
    assert "error" not in want, out["sql"]
    assert out["columns"] == want["columns"] and out["portable"]
    rows = load_sql(WIDE / sql_file).execute(out["sql"]).fetchall()
    assert same_rows(rows, want["rows"]), (rows, out["sql"])


@pytest.mark.parametrize("case", QUERY_CASES)
def test_query(case):
    duckdb = pytest.importorskip("duckdb")
    folder = QUERY / "cases" / case
    sql = (folder / "query.ossie.sql").read_text(encoding="utf-8")
    model = SemanticModel(read_yaml(QUERY / "scott" / "scott_model.ossie.yaml"))
    out = rewrite(sql, model, read="duckdb", dialect="duckdb", allow_draft=True)
    con = duckdb.connect()
    con.execute((QUERY / "scott" / "scott.sql").read_text(encoding="utf-8"))
    got = con.execute(out["sql"]).fetchall()
    want = con.execute((folder / "expected.sql").read_text(encoding="utf-8")).fetchall()
    if sqlglot.parse_one(sql, read="duckdb").args.get("order"):  # ORDER BY 가 있으면 순서도 같아야 한다
        assert len(got) == len(want) and all(len(g) == len(w) and all(map(_cell, g, w)) for g, w in zip(got, want)), (got, want, out["sql"])
    else:
        assert same_rows(got, want), (got, want, out["sql"])
