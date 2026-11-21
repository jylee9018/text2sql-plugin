"""속도 점검: 올리스트 크기(주문·고객 약 10만, 주문 상품 약 11만)의 SQLite 에서 엔진이 만든 SQL 이 몇 초 안에 끝나고,
실행 계획 점검(Database.slow_parts)이 그 SQL 은 통과시키고 행마다 큰 표를 다시 읽는 SQL 은 잡는지 본다.

묶음이 수만 개일 때 묶음마다 다시 읽는 계산은 30초를 넘겼다(평가셋 hard-006·hard-022). 같은 실수가 다시 들어오면 여기서 걸린다.
"""
import sqlite3
import time

import pytest

from conftest import FIXTURE_SQL
from t2s.db import Database, _repeats
from t2s.measures import rewrite

N = 100_000  # 주문·고객 수. 주문 상품은 12% 더 많다(한 주문에 상품 둘)
LIMIT_S = 10  # 실측 1초 안팎. 묶음마다 다시 읽으면 수십 초가 넘는다

BULK = f"""
WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < {N})
INSERT INTO customers (customer_id, customer_unique_id, customer_state) SELECT 'bc' || i, 'bu' || (i % 95000), 'S' || (i % 27) FROM n;
WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < {N})
INSERT INTO orders (order_id, customer_id, order_status, order_purchase_timestamp)
SELECT 'bo' || i, 'bc' || i, CASE WHEN i % 50 = 0 THEN 'canceled' ELSE 'delivered' END, datetime('2017-01-01', '+' || (i % 600) || ' days') FROM n;
WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < {N * 112 // 100})
INSERT INTO order_items (order_id, order_item_id, product_id, price, freight_value)
SELECT 'bo' || ((i - 1) % {N} + 1), (i - 1) / {N} + 1, 'p' || (i % 2 + 1), i % 300, 5 FROM n;
"""


@pytest.fixture(scope="module")
def big(tmp_path_factory):
    path = tmp_path_factory.mktemp("speed") / "olist_big.db"
    con = sqlite3.connect(path)
    con.executescript(FIXTURE_SQL + BULK)
    con.commit()
    con.close()
    return Database(f"sqlite:///{path}")


def timed(db: Database, sql: str) -> float:
    """LIMIT_S 안에 끝나야 한다. 넘으면 DB 가 멈춰 오류로 실패한다."""
    db.timeout_s = LIMIT_S
    start = time.monotonic()
    db.execute(sql)
    return time.monotonic() - start


MANY_GROUPS = {  # 고객 10만 묶음. 앞의 둘은 2층(AGG), 뒤의 둘은 3층(compile)
    "agg_fan_out": "SELECT o.customer_id, AGG(o.order_count) AS n FROM order_items AS i JOIN orders AS o ON i.order_id = o.order_id GROUP BY o.customer_id",
    "agg_beside_subquery": "SELECT o.customer_id, AGG(o.order_count) AS n, (SELECT 1) AS one FROM orders AS o GROUP BY o.customer_id",
    "compile_dataset_metric": (["order_count"], ["orders.customer_id"]),
    "compile_cross_dataset": (["revenue"], ["orders.customer_id"]),
}


@pytest.mark.parametrize("case", MANY_GROUPS)
def test_many_groups_fast(big, model, case):
    q = MANY_GROUPS[case]
    sql = rewrite(q, model, read="sqlite")["sql"] if isinstance(q, str) else model.compile(*q, limit=None, allow_draft=True)
    assert big.slow_parts(sql) == []  # 실행 전 점검이 막지 않는다
    assert timed(big, sql) < LIMIT_S


@pytest.mark.parametrize("sql, table", [
    # 고객마다 주문 표 전체를 다시 읽는 상관 하위 쿼리(10만 × 10만)
    ("SELECT c.customer_id, (SELECT COUNT(*) FROM orders AS o WHERE o.customer_id = c.customer_id AND o.order_status = 'canceled') AS n FROM customers AS c",
     "orders"),
    # 같다(=)가 아닌 조인 조건: 주문마다 주문 상품 표 전체를 읽는다
    ("SELECT COUNT(*) FROM orders AS a JOIN order_items AS b ON a.order_purchase_timestamp < b.shipping_limit_date", "order_items"),
])
def test_slow_plan_caught(big, sql, table):
    parts = big.slow_parts(sql)
    assert [p["table"] for p in parts] == [table] and parts[0]["times"] * parts[0]["rows"] >= 1e8


def test_streaming_lookup_not_caught(big):
    """정렬·묶음 없이 LIMIT 만 있는 조회는 앞 행을 찾는 대로 멈춘다. 몇 번 돌지 모르므로 막지 않는다."""
    lookup = "SELECT o.order_id FROM orders AS o WHERE EXISTS (SELECT 1 FROM order_items AS i WHERE i.price > length(o.order_id)) LIMIT 101"
    assert big.slow_parts(lookup) == []
    assert big.slow_parts(lookup.replace(" LIMIT 101", " ORDER BY 1 LIMIT 101")) != []  # 정렬하면 끝까지 읽는다


@pytest.mark.parametrize("plan", [
    [(2, 0, 0, "SCAN c"), (5, 0, 0, "CORRELATED SCALAR SUBQUERY 1"), (11, 5, 0, "SCAN o"),
     (26, 5, 0, "SEARCH p USING AUTOMATIC COVERING INDEX (order_id=?)")],
    # SQLite 3.36 이전 표기. 표 이름 뒤에 별칭이 붙는다
    [(2, 0, 0, "SCAN TABLE customers AS c"), (5, 0, 0, "CORRELATED SCALAR SUBQUERY 1"), (11, 5, 0, "SCAN TABLE orders AS o"),
     (26, 5, 0, "SEARCH TABLE order_payments AS p USING AUTOMATIC COVERING INDEX (order_id=?)")],
])
def test_plan_wording(plan):
    """고객마다 주문 표 전체를 다시 읽는 계획. SQLite 판에 따라 계획 문구가 달라도 같은 곳을 잡는다."""
    size = {"c": 99441, "o": 99441}.get
    assert _repeats(plan, size) == [{"table": "o", "times": 99441, "rows": 99441}]
