"""t2s 명령이 DB와 Graph MCP의 활성 정의로 JSON을 내는지."""
import json
import sqlite3

import pytest
import yaml
from sqlalchemy.exc import OperationalError

from tests.conftest import GOLDEN, MODEL, make_db, set_ext
from t2s import cli


@pytest.fixture
def env(tmp_path, monkeypatch):
    con = make_db(str(tmp_path / "demo.sqlite"))
    con.executescript("CREATE TABLE payments_pii (card_no TEXT);")
    con.close()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'demo.sqlite'}")
    monkeypatch.setattr(cli, "fetch_model", lambda model=None: {
        "version_id": "published-v1", "definition": yaml.safe_load(MODEL.read_text(encoding="utf-8"))
    })
    return monkeypatch


def t2s(capsys, *argv, code=None):
    if code is None:
        cli.main(list(argv))
    else:
        with pytest.raises(SystemExit) as e:
            cli.main(list(argv))
        assert e.value.code == code
    return json.loads(capsys.readouterr().out)


def test_draft_preview_and_local_definition_ignored(env, capsys):
    """승인 전 지표는 미리 보기로만 실행되고 로컬 정의 경로는 조회에 영향을 주지 않는다."""
    assert t2s(capsys, "compile", "avg_delivery_days", "--run", code=1)["error"]["code"] == "metric_not_approved"
    out = t2s(capsys, "compile", "avg_delivery_days", "--allow-draft", "--run")
    assert out["preview"] is True and out["result"]["rows"] == [[7.5]] and any(w["kind"] == "preview" for w in out["warnings"])
    env.setenv("SEMANTIC_MODEL", "nope.yaml")
    assert t2s(capsys, "context")["definition"]["version_id"] == "published-v1"


def test_setup_errors(env, capsys):
    """주소·드라이버·인자 오류도 traceback 없이 JSON 오류 하나다."""
    env.setenv("DATABASE_URL", "foo://x/y")
    assert t2s(capsys, "context", code=1)["error"]["kind"] == "db"
    assert t2s(capsys, "values", code=1)["error"]["kind"] == "bad_args"


def test_context_and_schema(env, capsys):
    out = t2s(capsys, "context")
    assert out["dialect"] == "sqlite" and out["catalog"].startswith("정의 olist_sales")
    assert out["tables"] == ["customers", "order_items", "order_payments", "order_reviews", "orders", "product_category_name_translation", "products", "sellers"]
    listed = t2s(capsys, "schema")["tables"]
    assert "orders" in listed and "payments_pii" not in listed
    assert "price" in t2s(capsys, "schema", "order_items")["describe"]


def test_validate(env, capsys):
    rows = "SELECT o.order_id, i.price FROM order_items i JOIN orders o ON i.order_id = o.order_id"
    out = t2s(capsys, "validate", rows)
    assert out["ok"] and out["joins"] == [{"left": "order_items.order_id", "right": "orders.order_id"}]
    for sql, kind in [
        ("DELETE FROM orders", "policy"),
        ("SELECT nope FROM orders", "unknown_column"),
        ("SELECT * FROM orders o JOIN products p ON o.order_id = p.product_id", "unknown_join"),
    ]:
        out = t2s(capsys, "validate", sql)
        assert not out["ok"] and out["problems"][0]["kind"] == kind, sql
    env.setenv("SEMANTIC_MODEL", "nope.yaml")
    assert not t2s(capsys, "validate", "SELECT SUM(price) FROM order_items")["ok"]


def test_run(env, capsys):
    out = t2s(capsys, "run", "SELECT o.order_id, i.price FROM order_items i JOIN orders o ON i.order_id = o.order_id")
    assert out["ok"] and len(out["rows"]) == 5 and "elapsed_ms" in out
    err = t2s(capsys, "run", "SELECT SUM(price) FROM order_items", code=1)["error"]
    assert err["kind"] == "policy" and err["retryable"] is False
    err = t2s(capsys, "run", "SELECT * FROM nope", code=1)["error"]
    assert err["kind"] == "unknown_table" and err["retryable"] is True
    out = t2s(capsys, "run", "SELECT order_id::TEXT FROM orders LIMIT 1", "--read", "duckdb")  # :: 는 SQLite 에 없다
    assert out["ok"] and len(out["rows"]) == 1 and "CAST(" in out["executed_sql"]


def test_compile(env, capsys):
    out = t2s(capsys, "compile", "revenue")
    assert "SUM" in out["sql"] and out["metrics"] == ["revenue"]
    assert t2s(capsys, "compile", "nope", code=1)["error"]["code"] == "unknown_metric"


def test_compile_run(env, capsys):
    out = t2s(capsys, "compile", "revenue", "--by", "products.product_category_name", "--order=-revenue", "--run")
    assert out["result"]["ok"] and out["result"]["rows"] == [["beleza", 130.0], ["esporte", 70.0]]
    assert out["metrics"] == ["revenue"] and "elapsed_ms" in out["result"]


def test_compile_run_db_error(env, capsys):
    def boom(self, sql):
        raise OperationalError(sql, {}, Exception("no such column: price"))

    env.setattr(cli.Database, "execute", boom)
    out = t2s(capsys, "compile", "revenue", "--run", code=1)
    assert out["ok"] is False and out["error"]["kind"] == "missing_object" and "SUM" in out["sql"]


def test_compile_expr_run(env, capsys):
    """지표 조합(DERIVABLE): 매출 200 / 주문 3건, 묶음 기준이 있으면 그 컬럼도 함께 나온다."""
    out = t2s(capsys, "compile", "revenue", "orders.order_count", "--expr", "revenue / order_count", "--run")
    assert out["expr"] == "revenue / order_count" and out["result"]["columns"] == ["value"]
    assert round(out["result"]["rows"][0][0], 2) == 66.67
    out = t2s(capsys, "compile", "revenue", "freight", "--by", "customers.customer_state", "--expr", "revenue + freight", "--run")
    assert out["result"]["columns"] == ["customer_state", "value"] and sorted(out["result"]["rows"]) == [["RJ", 33.0], ["SP", 187.0]]


def test_values(env, capsys, tmp_path):
    out = t2s(capsys, "values", "customers.customer_state")
    assert out["kind"] == "categorical" and out["values"] == [{"value": "SP", "count": 2}, {"value": "RJ", "count": 1}]
    assert not out["truncated"] and t2s(capsys, "values", "customers.customer_state", "--limit", "1")["truncated"]
    assert t2s(capsys, "values", "customers.customer_state", "--like", "s")["values"] == [{"value": "SP", "count": 2}]
    assert t2s(capsys, "values", "customers.customer_city")["values"] == [{"value": None, "count": 3}]
    # --like 문자열은 리터럴 노드라 SQL 로 읽히지 않는다
    for text in ("x') OR 1=1 --", "' OR '1'='1"):
        assert t2s(capsys, "values", "customers.customer_state", "--like", text)["values"] == []
    out = t2s(capsys, "values", "orders.order_purchase_timestamp")
    assert out == {"ref": "orders.order_purchase_timestamp", "table": "orders", "column": "order_purchase_timestamp", "kind": "time",
                   "min": "2018-01-05 10:00:00", "max": "2018-02-10 10:00:00", "non_null": 4, "rows": 4}
    err = t2s(capsys, "values", "customers.nope", code=1)["error"]
    assert err["kind"] == "unknown_column" and err["retryable"]
    assert t2s(capsys, "values", "nope.x", code=1)["error"]["kind"] == "unknown_table"

    doc = yaml.safe_load(MODEL.read_text(encoding="utf-8"))
    field = next(f for d in doc["datasets"] if d["name"] == "customers" for f in d["fields"] if f["name"] == "customer_state")
    set_ext(field, sensitivity="pii")
    (tmp_path / "pii.yaml").write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    env.setattr(cli, "fetch_model", lambda model=None: {"version_id": "published-v2", "definition": doc})
    err = t2s(capsys, "values", "customers.customer_state", code=1)["error"]
    assert err["kind"] == "policy" and "SP" not in json.dumps(err)

    assert t2s(capsys, "values", "payments_pii.card_no", code=1)["error"]["kind"] == "unknown_table"
    assert t2s(capsys, "values", "orders.order_purchase_timestamp")["kind"] == "time"
    assert t2s(capsys, "values", "orders.nope", code=1)["error"]["kind"] == "unknown_column"


def test_check(env, capsys, tmp_path):
    out = t2s(capsys, "check", str(MODEL))
    assert out["ok"] and out["mode"] == "db" and out["definition"]["name"] == "olist_sales" and out["problems"] == []
    assert "revenue (approved): 200.0" in out["samples"]
    assert out["uncovered"] == {"tables": ["payments_pii"], "columns": {}}
    con = sqlite3.connect(tmp_path / "demo.sqlite")
    con.executescript("ALTER TABLE orders ADD COLUMN memo TEXT;")
    con.close()
    assert t2s(capsys, "check", str(MODEL))["uncovered"]["columns"] == {"orders": ["memo"]}

    env.delenv("DATABASE_URL")  # --static 은 DB 가 필요 없다
    doc = yaml.safe_load(MODEL.read_text(encoding="utf-8"))
    doc["relationships"][0]["from_columns"] = ["nope"]
    bad = tmp_path / "bad.ossie.yaml"
    bad.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    out = t2s(capsys, "check", str(bad), "--static")
    assert not out["ok"] and out["mode"] == "static" and "없는 필드 nope" in out["problems"][0] and out["definition"]["path"] == str(bad)
    assert t2s(capsys, "check", str(tmp_path / "none.yaml"), "--static", code=1)["error"]["kind"] == "bad_definition"
    assert t2s(capsys, "check", code=1)["error"]["kind"] == "no_definition"


def test_warnings(env, capsys, tmp_path):
    out = t2s(capsys, "run", "SELECT order_id FROM orders WHERE order_purchase_timestamp <= '2018-01-20'")
    assert out["rows"] == [["o1"]] and [w["kind"] for w in out["warnings"]] == ["date_literal"]  # o2(1/20 10시)가 빠진다
    assert "< '2018-01-21'" in out["warnings"][0]["message"]
    out = t2s(capsys, "run", "SELECT SUM(price) FROM order_items WHERE 1 = 1", code=1)
    assert out["warnings"] == []
    half_open = "SELECT order_id FROM orders WHERE order_purchase_timestamp >= '2018-01-20' AND order_purchase_timestamp < '2018-01-21'"
    assert t2s(capsys, "validate", half_open)["warnings"] == []
    out = t2s(capsys, "compile", "revenue", "--where", "orders.order_purchase_timestamp = '2018-01-05'")
    assert [w["kind"] for w in out["warnings"]] == ["date_literal"]
    assert t2s(capsys, "compile", "revenue")["warnings"] == []

    env.setenv("SEMANTIC_MODEL", "nope.yaml")
    assert t2s(capsys, "context")["definition"]["source"] == "graph_mcp"


def test_usage_log(env, capsys, tmp_path):
    log = tmp_path / "t2s.jsonl"
    env.setenv("T2S_LOG", str(log))
    sql = "SELECT order_id FROM orders"
    t2s(capsys, "run", sql)
    t2s(capsys, "run", "SELECT * FROM nope", code=1)
    t2s(capsys, "compile", "revenue", "--by", "customers.customer_state", "--limit", "5", "--run")
    t2s(capsys, "compile", "revenue", "orders.order_count", "--expr", "revenue / order_count")
    t2s(capsys, "context")
    lines = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    keys = {"ts", "cmd", "ok", "executed", "sql", "call", "expr", "preview", "error_kind"}
    assert all(set(x) == keys for x in lines)
    run_ok, run_bad, comp, comp_expr, ctx = lines
    assert run_ok["ok"] and run_ok["executed"] and run_ok["sql"] == sql and run_ok["error_kind"] is None
    assert not run_bad["ok"] and run_bad["executed"] and run_bad["error_kind"] == "unknown_table"  # 가드 거절도 실행 시도
    assert comp["ok"] and comp["executed"] and "SUM" in comp["sql"]
    assert comp["call"] == {"metrics": ["revenue"], "dimensions": ["customers.customer_state"], "where": [], "order_by": [], "limit": 5}
    assert "limit" not in comp_expr["call"] and comp_expr["expr"] == "revenue / order_count" and not comp_expr["executed"]
    assert ctx["cmd"] == "context" and ctx["ok"] and ctx["sql"] is None
    env.setenv("T2S_LOG", str(tmp_path / "no" / "dir" / "x.jsonl"))  # 쓰기 실패는 무시한다
    assert t2s(capsys, "run", sql)["ok"]



def test_sql(env, capsys):
    """2층 SQL: AGG 는 정의대로, 정의 밖 집계는 계산하되 notes 에 적는다."""
    out = t2s(capsys, "sql", "SELECT c.customer_state, AGG(o.order_count) AS n FROM orders AS o JOIN customers AS c ON o.customer_id = c.customer_id GROUP BY 1 ORDER BY 1")
    assert out["result"]["rows"] == [["RJ", 1], ["SP", 2]] and out["notes"] == []
    out = t2s(capsys, "sql", "SELECT SUM(i.price) AS s FROM order_items AS i")
    assert out["undefined"] == ["SUM(i.price)"] and "정의 안 된 계산" in out["notes"][0]
    assert t2s(capsys, "sql", "SELECT AGG(o.avg_delivery_days) FROM orders AS o", code=1)["error"]["code"] == "metric_not_approved"


def test_sql_rejects_physical_table_and_reports_execution_error(env, capsys):
    """2층 SQL 은 데이터셋만 읽고 실행 오류를 다른 명령과 같은 위치에 돌려준다."""
    err = t2s(capsys, "sql", "SELECT order_id FROM main.orders", code=1)["error"]
    assert err["code"] == "unknown_relation"
    with sqlite3.connect(cli.os.environ["DATABASE_URL"].removeprefix("sqlite:///")) as con:
        con.execute("ALTER TABLE orders ADD COLUMN internal_secret TEXT DEFAULT 'hidden'")
    out = t2s(capsys, "sql", "SELECT internal_secret FROM ORDERS", code=1)
    assert out["ok"] is False and out["error"]["kind"] == "missing_object"
    out = t2s(capsys, "sql", "SELECT SUM(nope) FROM orders", code=1)
    assert out["ok"] is False and out["error"]["kind"] == "missing_object"


def test_context_uses_graph_version(env, capsys):
    env.setenv("SEMANTIC_MODEL", "nope.yaml")
    out = t2s(capsys, "context")
    assert out["definition"]["version_id"] == "published-v1"
    assert out["definition"]["source"] == "graph_mcp"
    env.setenv("GRAPH_VERSION_ID", "other-version")
    assert t2s(capsys, "context", code=1)["error"]["kind"] == "graph_unavailable"
