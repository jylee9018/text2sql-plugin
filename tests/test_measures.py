"""2층 SQL(AGG) 점검: 데이터셋을 표로 쓰고, 조인으로 늘어난 행도 측정은 기본키마다 한 번만 센다. Ossie 공식 사례는 test_ossie_compliance."""
import pytest

from t2s.engine import EngineError
from t2s.measures import rewrite

FAN_OUT = """
SELECT p.product_category_name, AGG(o.order_count) AS n, COUNT(*) AS item_rows
FROM order_items AS i
JOIN orders AS o ON i.order_id = o.order_id
JOIN products AS p ON i.product_id = p.product_id
GROUP BY 1
"""


def test_agg_counts_each_row_once(con, model):
    out = rewrite(FAN_OUT, model, read="sqlite", dialect="sqlite")
    rows = sorted(con.execute(out["sql"]).fetchall())
    by_engine = sorted(con.execute(model.compile(["order_count"], ["products.product_category_name"])).fetchall())
    assert [r[:2] for r in rows] == by_engine  # 3층 엔진과 같은 값. 주문 o1 은 상품이 둘이어도 카테고리마다 한 번
    assert out["measures"] == ["orders.order_count"] and out["undefined"] == ["COUNT(*)"]  # 정의 안 된 계산은 따로 알린다
    assert "ROW_NUMBER" in out["sql"]  # 묶음마다 다시 읽지 않고 행을 한 번만 읽는 방식(묶음이 많아도 느려지지 않는다)
    total = con.execute(rewrite("SELECT AGG(o.order_count) FROM orders AS o WHERE o.order_status = 'nope'", model, "sqlite")["sql"]).fetchall()
    assert total == [(0,)]  # 묶음 없는 질의는 행이 없어도 한 행, COUNT 는 0


@pytest.mark.parametrize("sql, code", [
    ("SELECT AGG(o.nope) FROM orders AS o", "unknown_measure"),
    ("SELECT AGG(o.avg_delivery_days) FROM orders AS o", "metric_not_approved"),  # 승인 전 지표
    ("SELECT AGG(o.order_count + o.order_count) FROM orders AS o", "invalid_agg"),
    ("SELECT AGG(order_count) FROM orders AS a JOIN orders AS b ON a.order_id = b.order_id", "unknown_measure"),  # 어느 쪽인지 모름
    ("SELECT 1; DROP TABLE orders", "invalid_sql"),
])
def test_agg_rejected(model, sql, code):
    with pytest.raises(EngineError) as e:
        rewrite(sql, model, read="sqlite")
    assert e.value.code == code


ITEMS = "FROM order_items AS i JOIN orders AS o ON i.order_id = o.order_id JOIN products AS p ON i.product_id = p.product_id"


def test_rollup_counts_each_row_once(con, model):
    """ROLLUP 의 소계·합계 행도 측정을 기본키마다 한 번 센다(규격 7.4). 묶음 모음마다 첫 행 번호를 따로 붙여 한 번에 읽는다."""
    duckdb = pytest.importorskip("duckdb")
    from conftest import FIXTURE_SQL
    db = duckdb.connect()
    db.execute(FIXTURE_SQL)
    sql = f"SELECT p.product_category_name AS cat, o.order_status AS st, AGG(o.order_count) AS n {ITEMS} GROUP BY ROLLUP (cat, st)"
    out = rewrite(sql, model, read="duckdb", dialect="duckdb")
    got = sorted(db.execute(out["sql"]).fetchall(), key=repr)
    cat, st = "products.product_category_name", "orders.order_status"
    want = (con.execute(model.compile(["order_count"], [cat, st], limit=None)).fetchall()
            + [(c, None, n) for c, n in con.execute(model.compile(["order_count"], [cat], limit=None)).fetchall()]
            + [(None, None, n) for (n,) in con.execute(model.compile(["order_count"], limit=None)).fetchall()])
    assert got == sorted([tuple(r) for r in want], key=repr)  # 합계는 카테고리 소계의 합이 아니다(o1 은 두 카테고리에 있다)
    assert "ROW_NUMBER" in out["sql"] and "GROUPING" in out["sql"]


def test_subquery_beside_agg(con, model):
    """바깥 SELECT·HAVING 에 하위 쿼리가 있어도 한 번에 읽는다. 하위 쿼리 자신의 표 컬럼은 그대로, 바깥 표 컬럼만 묶음 컬럼으로 바꾼다."""
    sql = f"""SELECT o.customer_id, AGG(o.order_count) AS n,
                     (SELECT COUNT(*) FROM order_items AS x JOIN orders AS y ON x.order_id = y.order_id WHERE y.customer_id = o.customer_id) AS items
              FROM orders AS o GROUP BY customer_id HAVING AGG(o.order_count) >= (SELECT 1)"""
    out = rewrite(sql, model, read="sqlite", dialect="sqlite")
    got = sorted(con.execute(out["sql"]).fetchall())
    counts = dict(con.execute(model.compile(["order_count"], ["orders.customer_id"], limit=None)).fetchall())
    items = dict(con.execute("SELECT o.customer_id, COUNT(*) FROM order_items i JOIN orders o ON i.order_id = o.order_id GROUP BY 1").fetchall())
    assert got == sorted((c, n, items[c]) for c, n in counts.items() if n >= 1)
    assert "ROW_NUMBER" in out["sql"]
