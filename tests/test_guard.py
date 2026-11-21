"""가드의 컬럼·연결 검사가 골든셋 대조 SQL 을 막지 않는지, shape 가 구조를 읽는지."""
import pytest
import yaml

from tests.conftest import GOLDEN
from t2s.guard import UnsafeSQL, lint, policy, prepare, shape

GOLD = [g for g in yaml.safe_load(GOLDEN.read_text(encoding="utf-8")) if g.get("sql")]


def _columns(model):
    cols = {}
    for d, n in model.fields:
        cols.setdefault(d, set()).add(n.lower())
    return cols


@pytest.mark.parametrize("gold", GOLD, ids=lambda g: str(g["id"]))
def test_gold_sql_passes(model, gold):
    # 지표 엔진이 만든 SQL 은 실제 호출에서도 컬럼·연결 검사를 다시 하지 않는다.
    rules = {} if gold["path"] == "metric" else {"columns": _columns(model), "edges": model.edges}
    prepare(gold["sql"], "sqlite", model.tables(), 100, allow_aggregates=True, **rules)


def test_anonymous_aggregates_rejected(model):
    """sqlglot 이 AggFunc 로 보지 않는 집계(TOTAL, EVERY, JSONB_AGG)도 행 조회 정책에서 막는다."""
    kw = dict(columns=_columns(model), edges=model.edges, allow_aggregates=False)
    for sql, dialect in (("SELECT TOTAL(price) FROM order_items", "sqlite"), ("SELECT EVERY(price > 0) FROM order_items", "postgres"),
                         ("SELECT JSONB_AGG(price) FROM order_items", "postgres")):
        with pytest.raises(UnsafeSQL):
            prepare(sql, dialect, model.tables(), 100, **kw)
    prepare("SELECT price FROM order_items", "sqlite", model.tables(), 100, **kw)


def test_column_and_join_rejected(model):
    kw = dict(columns=_columns(model), edges=model.edges)
    with pytest.raises(UnsafeSQL) as e:
        prepare("SELECT o.nope FROM orders o", "sqlite", model.tables(), 100, **kw)
    assert e.value.kind == "unknown_column"
    with pytest.raises(UnsafeSQL) as e:
        prepare("SELECT o.order_id FROM orders o JOIN products p ON o.order_id = p.product_id", "sqlite", model.tables(), 100, **kw)
    assert e.value.kind == "unknown_join" and "order_items.order_id = orders.order_id" in str(e.value)


@pytest.mark.parametrize("sql", [
    "SELECT o.order_id FROM orders o JOIN customers c ON 1=1",
    "SELECT o.order_id FROM orders o JOIN customers c ON o.customer_id = c.customer_id OR 1=1",
])
def test_join_requires_approved_key_condition(model, sql):
    with pytest.raises(UnsafeSQL) as e:
        prepare(sql, "sqlite", model.tables(), 100, columns=_columns(model), edges=model.edges)
    assert e.value.kind == "unknown_join"


def test_shape():
    s = shape(next(g["sql"] for g in GOLD if g["id"] == 6), "sqlite")
    assert s["tables"] == ["order_items", "orders", "products"]
    assert len(s["joins"]) == 2 and s["aggregates"] == ["SUM"] and s["limit"] == 1
    assert "order_items.price" in s["columns"] and s["filters"]


def test_lint(model):
    times = {"orders.order_purchase_timestamp"}
    edges = policy(None, model)["edges"]

    def kinds(sql):
        return [w["kind"] for w in lint(sql, "sqlite", time_columns=times, edges=edges)]

    ts = "o.order_purchase_timestamp"
    for cond in (f"{ts} = '2018-01-05'", f"{ts} <= '2018-01-31'", f"'2018-01-31' >= {ts}", f"{ts} BETWEEN '2018-01-01' AND '2018-01-31'"):
        assert kinds(f"SELECT o.order_id FROM orders o WHERE {cond}") == ["date_literal"], cond
    for cond in (f"{ts} >= '2018-01-05' AND {ts} < '2018-01-06'", f"{ts} = '2018-01-05 10:00:00'", "o.order_status = '2018-01-05'"):
        assert kinds(f"SELECT o.order_id FROM orders o WHERE {cond}") == [], cond

    join = " FROM orders o JOIN order_items i ON i.order_id = o.order_id"
    assert kinds("SELECT COUNT(o.order_id)" + join) == ["fan_out"]  # 주문 한 행이 품목 수만큼 반복된다
    assert kinds("SELECT COUNT(DISTINCT o.order_id)" + join) == []
    assert kinds("SELECT SUM(i.price)" + join) == []  # 품목은 N 쪽이라 부풀지 않는다
    assert lint("SELEC nope", "sqlite") == []


@pytest.mark.parametrize("sql, ok", [
    ("WITH t AS (SELECT order_id, customer_id FROM orders) SELECT t.order_id, c.customer_state FROM t JOIN customers c ON t.customer_id = c.customer_id", True),
    ("WITH t AS (SELECT customer_id AS cid FROM orders) SELECT c.customer_state FROM t JOIN customers c ON t.cid = c.customer_id", True),
    ("WITH t AS (SELECT order_id FROM orders) SELECT p.product_category_name FROM t JOIN products p ON t.order_id = p.product_id", False),
    ("WITH a AS (SELECT order_id FROM orders), b AS (SELECT order_id AS k FROM a) SELECT p.product_id FROM b JOIN products p ON b.k = p.product_id", False),
    ("SELECT p.product_id FROM (SELECT order_id FROM orders) s JOIN products p ON s.order_id = p.product_id", False),
    ("WITH t AS (SELECT order_id || 'x' AS k FROM orders) SELECT p.product_id FROM t JOIN products p ON t.k = p.product_id", False),
    # 첫 연결이 틀리고 둘째가 맞아도 거절한다(JOIN 마다 따로 본다)
    ("SELECT o.order_id FROM orders o JOIN products p ON o.order_id = p.product_id JOIN customers c ON o.customer_id = c.customer_id", False),
])
def test_join_through_cte_or_subquery(model, sql, ok):
    """WITH·하위 쿼리 결과를 이을 때도 원래 테이블 컬럼으로 거슬러 승인된 연결인지 본다. 원래 컬럼을 못 찾는 키(계산한 값)는 거절한다."""
    kw = dict(columns=_columns(model), edges=model.edges)
    if ok:
        prepare(sql, "sqlite", model.tables(), 100, **kw)
        return
    with pytest.raises(UnsafeSQL) as e:
        prepare(sql, "sqlite", model.tables(), 100, **kw)
    assert e.value.kind == "unknown_join"
