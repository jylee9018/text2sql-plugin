"""정의 검사(t2s check 의 findings): 정적 규칙과 실제 DB 대조. LLM 없이 임시 SQLite 로 본다."""
import copy
import json

import pytest
import yaml

from tests.conftest import CUSTOMER_COUNT, MODEL, make_db, set_ext
from t2s.db import Database
from t2s.definition import findings

BASE = yaml.safe_load(MODEL.read_text(encoding="utf-8"))


@pytest.fixture
def db(tmp_path):
    make_db(str(tmp_path / "demo.sqlite")).close()
    return Database(url=f"sqlite:///{tmp_path / 'demo.sqlite'}")


@pytest.fixture
def doc():
    return copy.deepcopy(BASE)


def _dataset(doc, name):
    return next(d for d in doc["datasets"] if d["name"] == name)


def _metric(doc, name):
    return next(m for m in doc["metrics"] if m["name"] == name)


def test_clean_definition(doc, db):
    r = findings(doc, db)
    assert r["ok"] and not r["problems"] and "revenue (approved): 200.0" in r["samples"]
    assert findings(doc) == {"ok": True, "problems": [], "notes": [], "samples": [], "pending": []}  # DB 없으면 정적 검사만


def test_draft_metric_and_bad_link(doc, db):
    m = yaml.safe_load(CUSTOMER_COUNT)
    set_ext(m, status="draft")
    _dataset(doc, "customers").setdefault("metrics", []).append(m)
    # to 쪽 order_items.order_id 는 주문 하나에 여러 행이라 한 행 쪽이 아니다
    doc["relationships"].append({"name": "bad_link", "from": "customers", "to": "order_items",
                                 "from_columns": ["customer_id"], "to_columns": ["order_id"]})
    r = findings(doc, db)
    assert "customers.customer_count (draft): 2" in r["samples"]
    assert any("기본키가 아니라 N:1 연결로 쓸 수 없음" in p for p in r["problems"])


@pytest.mark.parametrize("change, expected", [
    (lambda d: _dataset(d, "customers")["fields"].remove(  # orders_to_customers 가 가리키는 필드 삭제
        next(f for f in _dataset(d, "customers")["fields"] if f["name"] == "customer_id")), "customers 에 없는 필드 customer_id"),
    (lambda d: _dataset(d, "orders")["fields"].append({"name": "order_count", "expression": {"sql": "order_id"}}), "필드·지표 이름 중복 order_count"),
    (lambda d: _dataset(d, "orders")["metrics"].append({"name": "scoped", "expression": {"sql": "COUNT(orders.order_id)"}}), "접두어 없이 쓴다"),
    (lambda d: next(f for f in _dataset(d, "customers")["fields"] if f["name"] == "customer_state").update(datatype="Money"), "Ossie 자료형이 아님"),
    (lambda d: d["relationships"].append({"name": "items_to_customers", "from": "order_items", "to": "customers",
                                          "from_columns": ["order_id"], "to_columns": ["customer_id"]}), "모호함"),
    (lambda d: set_ext(_metric(d, "revenue"), decision="nope"), "decisions 에 없는 결정 nope"),
    # 확장 칸 값의 모양. 오타 난 status 는 오류 없이 승인 전으로 읽혀 지표가 답변에서 빠진다
    (lambda d: set_ext(_metric(d, "revenue"), status="aproved"), "draft 나 approved 가 아님"),
    (lambda d: set_ext(d["relationships"][0], status="approve"), "draft 나 approved 가 아님"),
    (lambda d: set_ext(_metric(d, "revenue"), expected={"value": "12%"}), "expected.value 는 숫자"),
    (lambda d: set_ext(_metric(d, "revenue"), discovery=["단위는 주문"]), "discovery 는 q·a"),
    (lambda d: set_ext(d, revision="6"), "revision 은 정수"),
], ids=["missing_field", "duplicate_name", "prefixed_metric", "bad_datatype", "ambiguous_path", "unknown_decision",
        "bad_status", "bad_edge_status", "text_expected", "bad_discovery", "text_revision"])
def test_static_rules(doc, change, expected):
    change(doc)
    r = findings(doc)
    assert not r["ok"] and any(expected in p for p in r["problems"]), r["problems"]


def test_expected_values(doc, db):
    """담당자 예상값이 어긋나면 문제가 아니라 확인 요청(notes)이다. where 를 주면 그 범위로 견준다."""
    set_ext(_metric(doc, "revenue"), expected={"value": 150})
    r = findings(doc, db)
    assert r["ok"] and r["notes"] == ["revenue: 담당자 예상 150, 계산 200. 정의나 예상값을 다시 확인한다"]
    jan = ["orders.order_purchase_timestamp >= '2018-01-01'", "orders.order_purchase_timestamp < '2018-02-01'"]
    set_ext(_metric(doc, "revenue"), expected={"value": 180, "where": jan})
    assert findings(doc, db)["notes"] == []
    set_ext(_metric(doc, "revenue"), expected={"value": "12%"})  # 글자 값은 예외 없이 문제로 보고하고 대조는 건너뛴다
    r = findings(doc, db)
    assert not r["ok"] and r["notes"] == [] and any("expected.value 는 숫자" in p for p in r["problems"])


def test_label_overlap_is_a_note(doc, db):
    """같은 말이 두 지표에 붙으면 그 말로 물을 때 어느 지표인지 갈리지 않는다. 막지는 않고 알린다."""
    _metric(doc, "freight")["ai_context"]["synonyms"].append("매출")
    note = "이름·동의어 겹침 '매출': revenue, freight. 그 말로 물으면 어느 지표인지 정해지지 않는다. 한쪽에서 빼거나 말을 나눈다"
    assert findings(doc) == {"ok": True, "problems": [], "notes": [note], "samples": [], "pending": []}
    assert findings(doc, db)["notes"] == [note]


ORDER_LINES = ("SELECT oi.order_id, oi.order_item_id, oi.price, o.order_status "
               "FROM order_items AS oi LEFT JOIN orders AS o ON o.order_id = oi.order_id")


def _with_lines(doc, source=ORDER_LINES):
    """주문 상품 줄에 주문 상태를 붙인 계산용 데이터셋을 더한다."""
    doc["datasets"].append({"name": "order_lines", "source": source, "primary_key": ["order_id", "order_item_id"],
                            "fields": [{"name": n, "expression": {"sql": n}} for n in ("order_id", "order_item_id", "price", "order_status")]})
    return doc


@pytest.mark.parametrize("source, expected", [
    (ORDER_LINES.replace("LEFT JOIN", "JOIN"), "기준 표의 행을 바꿈(JOIN orders"),  # 주문 없는 상품 줄이 빠진다
    (ORDER_LINES + " WHERE o.order_status = 'delivered'", "기준 표의 행을 바꿈(WHERE)"),  # 조건은 지표 FILTER 로
    ("SELECT name AS order_id FROM sqlite_master", "정의 밖 테이블"),  # DB 없이도 잡는다
], ids=["inner_join", "where", "outside_table"])
def test_query_dataset_static(doc, source, expected):
    r = findings(_with_lines(doc, source))
    assert not r["ok"] and any(expected in p for p in r["problems"]), r["problems"]


def test_query_dataset_rows(doc, db):
    """LEFT JOIN 이어도 붙인 표가 N:1 이 아니면 행이 불어난다. 기본키를 넓게 잡으면 기본키 중복 검사로는 못 잡는다."""
    assert findings(_with_lines(copy.deepcopy(doc)), db)["ok"]
    fan = ("SELECT o.order_id, oi.order_item_id, oi.price, o.order_status "
           "FROM orders AS o LEFT JOIN order_items AS oi ON oi.order_id = o.order_id")  # 주문 o1 의 상품이 둘이라 5행
    r = findings(_with_lines(doc, fan), db)
    assert r["problems"] == ["order_lines: 행 5개가 기준 표 orders 의 4개와 다름. LEFT JOIN 으로 붙인 표가 N:1 이 아니다"]


def test_nonportable_extensions_read_like_custom_extensions(doc, db):
    """Ossie 0.3.0.dev0 형식(nonportable_extensions, data 는 객체)도 0.2.0.dev0 형식과 같은 값으로 읽는다."""
    old = findings(copy.deepcopy(doc), db)
    objs = [doc, *doc["relationships"], *doc.get("metrics", []), *(m for d in doc["datasets"] for m in d.get("metrics", []))]
    for obj in objs:
        if "custom_extensions" in obj:
            obj["nonportable_extensions"] = [{**x, "data": json.loads(x["data"])} for x in obj.pop("custom_extensions")]
    assert not any("custom_extensions" in o for o in objs)
    assert findings(doc, db) == old


def test_broken_extension_is_reported(doc, db):
    """확장 칸 JSON 이 깨져도 예외 없이 문제로 보고한다."""
    _metric(doc, "revenue")["custom_extensions"][0]["data"] = "{status: approved}"
    r = findings(doc, db)
    assert not r["ok"] and r["problems"]
