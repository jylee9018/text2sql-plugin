"""정의 파일 검사(t2s check): 형식·규칙 검사와 실제 DB 대조.

- 정적 검사: 연결이 가리키는 필드, 키가 아닌 연결, 이름 중복, Ossie 자료형·지표 범위, 없는 결정, 모호한 연결 경로,
  확장 칸 값의 모양(status·expected·discovery·revision), 계산용 데이터셋 조회문(모양, 기준 표 행을 바꾸는 JOIN·WHERE 등).
  지표 이름·동의어가 다른 지표와 겹치면 문제가 아니라 확인 요청(notes)으로 알린다.
- 민감 컬럼: 연락처·계좌번호·카드번호·주민번호처럼 보이는 필드는 문제로 낸다.
- 이전 판과 비교(changes): 이번에 승인된 지표의 승인 기록, 새 지표의 결정, 내용이 바뀌었을 때 revision 증가.
  예전부터 있던 항목에는 묻지 않는다(규칙이 생기기 전에 승인된 지표가 있다).
- DB 대조: 필드를 실제로 읽어 보고, 기본키·연결 키 중복을 세고, 계산용 데이터셋 행 수를 기준 표와 견주고,
  지표마다 값을 계산하고, 담당자 예상값(expected)과 견준다.
"""
from __future__ import annotations

import re

import sqlglot
from sqlalchemy.exc import SQLAlchemyError
from sqlglot import exp
from sqlglot.errors import SqlglotError

from .db import Database
from .engine import BUILD, EngineError, SemanticModel, source_table
from .guard import UnsafeSQL, prepare
from .ossie import READ, expr_sql, ext, status

DATATYPES = ("String", "Integer", "Decimal", "Float", "Boolean", "Date", "Time", "DateTime", "DateTimeTz", "Opaque")
STATUSES = ("draft", "approved")
_CHECK_ERRORS = (UnsafeSQL, SQLAlchemyError, EngineError, SqlglotError, KeyError, ValueError)  # ValueError: 확장 칸 JSON 깨짐 등
# 기준 표의 행을 빼거나 묶는 절. 계산용 데이터셋은 기준 표 1행이 1행이어야 원래 표의 조건·묶음과 값이 같다
_ROW_CHANGING = {"where": "WHERE", "group": "GROUP BY", "having": "HAVING", "distinct": "DISTINCT", "limit": "LIMIT", "qualify": "QUALIFY"}


# 정의에 필드로 넣지 않는 민감 컬럼. 이름이나 필드 식에 이 말이 보이면 문제로 낸다
_SENSITIVE = re.compile(
    r"phone|mobile|e_?mail|card_?(no|num|number)|account_?(no|num|number)|bank_?account|ssn|resident_?(no|num|number)|passport"
    r"|전화|휴대폰|연락처|이메일|카드번호|계좌|주민", re.I)


def _short(e: Exception) -> str:
    return str(e.__cause__ or e).splitlines()[0][:200]


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _expected_problem(want) -> str | None:
    """담당자 예상값(expected) 모양이 틀렸으면 그 이유. 틀린 값은 DB 대조에서 건너뛴다."""
    if not isinstance(want, dict) or not _number(want.get("value")):
        return "expected.value 는 숫자로 적는다(예: 0.12. '12%' 같은 글자는 안 된다)"
    if "tolerance" in want and not _number(want["tolerance"]):
        return "expected.tolerance 는 숫자로 적는다"
    where = want.get("where") or []
    if not isinstance(where, list) or not all(isinstance(w, str) for w in where):
        return "expected.where 는 조건 문장의 목록으로 적는다"
    return None


def _extension_problems(model: SemanticModel) -> list[str]:
    """확장 칸(TEXT2SQL) 값의 모양. 규격 검증기는 이 칸 안을 보지 않는다.
    status 오타는 오류 없이 승인 전으로 읽혀 지표가 답변에서 조용히 빠지므로 여기서 잡는다."""
    problems = []
    revision = ext(model.doc).get("revision")
    if revision is not None and (not isinstance(revision, int) or isinstance(revision, bool)):
        problems.append(f"모델 revision 은 정수로 적는다({revision!r})")
    for key, obj in [*model.metrics.items(), *((r["name"], r) for r in model.doc.get("relationships", []))]:
        x = ext(obj)
        if "status" in x and x["status"] not in STATUSES:
            problems.append(f"{key}: status {x['status']!r} 는 draft 나 approved 가 아님. 이대로면 승인 전으로 읽혀 답변에서 빠진다")
        if "expected" in x and (why := _expected_problem(x["expected"])):
            problems.append(f"{key}: {why}")
        approval = x.get("approval")
        if approval is not None and not (isinstance(approval, dict) and isinstance(approval.get("by"), str) and approval["by"].strip()
                                         and isinstance(approval.get("at"), str) and approval["at"].strip()):
            problems.append(f"{key}: approval 은 by(승인한 사람의 역할)·at(날짜 문자열)이 있는 객체로 적는다")
        discovery = x.get("discovery")
        if discovery is not None and not (isinstance(discovery, list) and all(isinstance(q, dict) and q.get("q") and q.get("a") for q in discovery)):
            problems.append(f"{key}: discovery 는 q·a 가 있는 항목의 목록으로 적는다")
    return problems


def _query_problems(model: SemanticModel) -> list[str]:
    """계산용 데이터셋(source 가 조회문)의 모양. 기준 표(FROM 의 표)에 LEFT JOIN 으로 N:1 만 이어야 행 수가 기준 표와 같다.
    INNER JOIN·WHERE 는 기준 표의 행을 빼서 지표가 조용히 작아진다. N:1 이 아닌 LEFT JOIN 으로 불어나는 행은 DB 대조가 잡는다."""
    problems = []
    for name, d in model.datasets.items():
        if source_table(d) is not None:
            continue
        try:
            tree = model._source_query(name, d["source"].strip())
        except EngineError as e:
            problems.append(f"{e} ({e.hint})" if e.hint else str(e))
            continue
        bad = [label for key, label in _ROW_CHANGING.items() if tree.args.get(key)]
        bad += [j.sql(BUILD) for j in tree.args.get("joins") or [] if j.side != "LEFT" or j.kind not in ("", "OUTER")]
        if bad:
            problems.append(f"{name}: source 조회문이 기준 표의 행을 바꿈({'; '.join(bad)}). 기준 표에 LEFT JOIN 으로 N:1 만 잇고, 거르는 조건은 지표의 FILTER 로 쓴다")
    return problems


def _label_notes(model: SemanticModel) -> list[str]:
    """지표 이름·동의어가 다른 지표와 겹치면 알린다. 그 말로 물으면 어느 지표인지 정해지지 않는다. 막지는 않는다."""
    owners: dict[str, list[str]] = {}
    for key, m in model.metrics.items():
        context = m.get("ai_context")
        labels = {m["name"], *((context.get("synonyms") or []) if isinstance(context, dict) else [])}
        for label in {str(s).strip().lower() for s in labels}:
            owners.setdefault(label, []).append(key)
    return [f"이름·동의어 겹침 '{label}': {', '.join(keys)}. 그 말로 물으면 어느 지표인지 정해지지 않는다. 한쪽에서 빼거나 말을 나눈다"
            for label, keys in sorted(owners.items()) if len(keys) > 1]


def _sensitive_problems(model: SemanticModel) -> list[str]:
    """연락처·계좌번호 같은 민감 컬럼은 필드로 넣지 않는다."""
    return [f"{d}.{n}: 민감 정보로 보이는 필드(연락처·계좌번호·카드번호·주민번호 등)는 정의에 넣지 않는다"
            for (d, n), f in model.fields.items() if _SENSITIVE.search(n) or _SENSITIVE.search(expr_sql(f))]


def changes(doc: dict, before: dict | None) -> dict:
    """이전 판(before, 보통 git HEAD)과 견줘 이번 고침에만 묻는 규칙. before 가 없으면 아무것도 묻지 않는다.

    - 이번에 approved 가 된 지표: approval(by·at) 기록이 있어야 한다. 사용자가 고른 것만 승인했다는 흔적이다.
    - 새로 생긴 지표: decision 이 있어야 한다. 어떤 결정에 쓰는지 정해지지 않은 지표는 만들지 않는다.
    - 내용이 바뀌었으면 모델 revision 이 올라가야 한다.
    """
    if not isinstance(before, dict):
        return {"problems": [], "notes": []}
    try:
        now, old = SemanticModel(doc), SemanticModel(before)
    except (KeyError, TypeError, AttributeError, ValueError, SqlglotError):
        return {"problems": [], "notes": []}  # 형식 오류는 findings 가 낸다
    problems, notes = [], []
    for key, m in now.metrics.items():
        if key not in old.metrics:
            if not ext(m).get("decision"):
                problems.append(f"{key}: 새 지표에 decision 이 없다. 이 지표로 누가 무엇을 결정하는지 정해 모델 decisions 에 적고 그 id 를 쓴다")
        if status(m) == "approved" and (key not in old.metrics or status(old.metrics[key]) != "approved") and not ext(m).get("approval"):
            problems.append(f"{key}: 승인 기록 없이 approved 가 됐다. 사용자가 승인을 고른 경우에만 approval: {{by: <역할>, at: \"<날짜>\"}} 와 함께 바꾼다")
    for r in now.doc.get("relationships", []):
        prev = next((x for x in old.doc.get("relationships", []) if x["name"] == r["name"]), None)
        if status(r) == "approved" and (prev is None or status(prev) != "approved") and not ext(r).get("approval"):
            problems.append(f"{r['name']}: 승인 기록 없이 approved 가 됐다. 사용자가 승인을 고른 경우에만 approval: {{by: <역할>, at: \"<날짜>\"}} 와 함께 바꾼다")

    def without_revision(d: dict) -> dict:
        d = {k: v for k, v in d.items()}
        for key in ("nonportable_extensions", "custom_extensions"):
            if key in d:
                d[key] = [{**x, "data": {k: v for k, v in (ext({key: [x]}) or {}).items() if k != "revision"}}
                          if x.get("vendor_name") == "TEXT2SQL" else x for x in d[key]]
        return d
    if without_revision(doc) != without_revision(before) and (now.revision or 0) <= (old.revision or 0):
        notes.append(f"정의 내용이 바뀌었는데 모델 revision 이 그대로다({now.revision}). 고칠 때마다 1 올린다")
    return {"problems": problems, "notes": notes}


def _static_problems(model: SemanticModel) -> list[str]:
    """DB 를 보지 않고 정의만으로 잡는 문제: 연결이 가리키는 필드, 키가 아닌 연결, 이름 중복, Ossie 지표 범위, 모호한 경로."""
    problems = []
    for r in model.doc.get("relationships", []):
        for side, cols in (("from", "from_columns"), ("to", "to_columns")):
            if r[side] not in model.datasets:
                problems.append(f"{r['name']}: 없는 데이터셋 {r[side]}")
                continue
            missing = [c for c in r[cols] if (r[side], c) not in model.fields]
            if missing:
                problems.append(f"{r['name']}: {r[side]} 에 없는 필드 {', '.join(missing)}")
        if len(r["from_columns"]) != len(r["to_columns"]):
            problems.append(f"{r['name']}: from_columns 와 to_columns 개수가 다름")
    problems += [
        f"{r['name']}: to_columns 가 {r['to']} 의 기본키가 아니라 N:1 연결로 쓸 수 없음"
        for r in model.bad_edges if r["to"] in model.datasets
    ]
    typed = [*model.fields.items(), *model.metrics.items()]
    problems += [
        f"{key}: datatype {obj['datatype']} 는 Ossie 자료형이 아님({', '.join(DATATYPES)})"
        for key, obj in typed if "datatype" in obj and obj["datatype"] not in DATATYPES
    ]
    for d in model.doc["datasets"]:
        names = [f["name"] for f in d.get("fields", [])] + [m["name"] for m in d.get("metrics", [])]
        problems += [f"{d['name']}: 필드·지표 이름 중복 {n}" for n in sorted({n for n in names if names.count(n) > 1})]
        for m in d.get("metrics", []):
            if any(c.table for c in sqlglot.parse_one(expr_sql(m), read=READ).find_all(exp.Column)):
                problems.append(f"{d['name']}.{m['name']}: 데이터셋 지표는 자기 필드를 접두어 없이 쓴다(Ossie 규칙)")
    names = [m["name"] for m in model.doc.get("metrics", [])]
    problems += [f"모델 지표 이름 중복 {n}" for n in sorted({n for n in names if names.count(n) > 1})]
    decisions = {d.get("id") for d in ext(model.doc).get("decisions") or []}
    problems += [
        f"{key}: 모델의 decisions 에 없는 결정 {ext(m)['decision']}"
        for key, m in model.metrics.items() if ext(m).get("decision") and ext(m)["decision"] not in decisions
    ]
    edges = model.all_edges()  # 초안 연결도 센다. 승인되는 순간 모호해질 길을 승인 전에 잡는다
    for a in model.datasets:
        for b in model.datasets:
            if a != b and len(paths := model._paths(a, b, edges=edges)) > 1:
                problems.append(f"{a} 에서 {b} 로 가는 연결이 {len(paths)}개라 모호함")
    return problems + _extension_problems(model) + _query_problems(model) + _sensitive_problems(model)


def findings(doc: dict, db: Database | None = None) -> dict:
    """검사 결과 {ok, problems, notes, samples, pending}. db 가 없으면 정적 검사만 한다. 형식 오류면 samples 는 None."""
    try:
        model = SemanticModel(doc)
        problems = _static_problems(model)
        labels = _label_notes(model)
    except (KeyError, TypeError, AttributeError, ValueError, SqlglotError) as e:
        return {"ok": False, "problems": [f"형식 오류: 필수 칸이 없거나 모양이 다름 ({e!r})"], "notes": [], "samples": None, "pending": []}
    if db is None:
        return {"ok": not problems, "problems": problems, "notes": labels, "samples": [], "pending": []}

    def run(sql: str, build: bool = True) -> list:
        sql = sqlglot.transpile(sql, read=BUILD, write=db.dialect)[0] if build else sql
        return db.execute(prepare(sql, db.dialect, set(db.tables), 5, schema=db.schema))["rows"]

    def duplicates(dataset: str, keys: list[str]) -> int:
        cols = ", ".join(model._field(dataset, k).sql(BUILD) for k in keys)
        return run(f"SELECT COUNT(*) FROM (SELECT {cols} FROM {model._table(dataset)} GROUP BY {cols} HAVING COUNT(*) > 1) AS d")[0][0]

    samples = []
    for name, d in model.datasets.items():
        fields = [n for ds, n in model.fields if ds == name]
        try:
            run(f"SELECT {', '.join(f'{model._field(name, n).sql(BUILD)} AS {n}' for n in fields) or '1'} FROM {model._table(name)}")
            n = duplicates(name, d["primary_key"]) if d.get("primary_key") else 0
            if source_table(d) is None:  # 계산용 데이터셋: 행 수가 기준 표(FROM 의 표)와 같아야 한다
                base = model._source_query(name, d["source"].strip()).find(exp.From).this.copy()
                base.set("alias", None)
                got, want = (run(f"SELECT COUNT(*) FROM {t}")[0][0] for t in (model._table(name), base.sql(BUILD)))
                if got != want:
                    problems.append(f"{name}: 행 {got}개가 기준 표 {base.sql(BUILD)} 의 {want}개와 다름. LEFT JOIN 으로 붙인 표가 N:1 이 아니다")
        except _CHECK_ERRORS as e:
            problems.append(f"{name}: 필드를 읽을 수 없음 ({_short(e)})")
            continue
        if n:
            problems.append(f"{name}: primary_key {d['primary_key']} 값이 {n}개 중복됨")
    for r in (r for rs in model.edges.values() for r in rs):
        try:
            n = duplicates(r["to"], r["to_columns"])
        except _CHECK_ERRORS as e:
            problems.append(f"{r['name']}: 확인 실패 ({_short(e)})")
            continue
        if n:
            problems.append(f"{r['name']}: {r['to']}.{', '.join(r['to_columns'])} 값이 {n}개 중복돼 한 행 쪽이 아님. 이 연결로 조인하면 값이 부풂")
    pending = []
    for key, m in model.metrics.items():
        label = status(m)
        try:
            try:
                sql = model.compile([key], limit=None, dialect=db.dialect, allow_draft=True)
            except EngineError as e:
                # 승인 전 지표가 승인 전 연결을 기다리는 것은 정의 오류가 아니라 승인 대기다. 문제로 두면 새 연결이 필요한 새 지표가 늘 검사에 걸린다.
                # 값은 승인 전 연결까지 쓰는 미리 보기로 계산해 보여 준다(승인 전에 결과를 보고 고치려고)
                if e.code != "relationship_not_approved" or status(m) == "approved":
                    raise
                pending.append(f"{key}: 승인 대기. {_short(e)}. 연결이 승인돼야 답변에 쓰인다")
                sql, label = model.compile([key], limit=None, dialect=db.dialect, allow_draft=True, draft_joins=True), f"{label}, 미리 보기"
            rows = run(sql, build=False)
            samples.append(f"{key} ({label}): {rows[0][0] if rows else '없음'}")
        except _CHECK_ERRORS as e:
            problems.append(f"{key}: 계산할 수 없음 ({_short(e)})")
    notes = labels + _expected_notes(model, db.dialect, run)
    return {"ok": not problems, "problems": problems, "notes": notes, "samples": samples, "pending": pending}


def uncovered(model: SemanticModel, db: Database) -> dict:
    """DB 에 있지만 정의가 덮지 않은 범위: 정의에 없는 테이블, 정의된 테이블에서 어느 필드 식도 읽지 않는 컬럼."""
    used: dict[str, set[str]] = {}
    for (d, _), f in model.fields.items():
        table = source_table(model.datasets[d])
        if not table:  # 조회문 source 의 필드는 조회문의 결과 컬럼을 읽는다. 테이블 컬럼은 이름으로 가리킨 데이터셋이 덮는다
            continue
        cols = used.setdefault(table.rpartition(".")[2], set())
        cols |= {c.name.lower() for c in sqlglot.parse_one(expr_sql(f), read=READ).find_all(exp.Column)}
    columns = {}
    for t, cols in sorted(used.items()):
        if t in db.tables:
            rest = [c["name"] for c in db._insp.get_columns(db.tables[t], schema=db.schema) if c["name"].lower() not in cols]
            if rest:
                columns[t] = rest
    return {"tables": sorted(n for k, n in db.tables.items() if k not in used), "columns": columns}


def _expected_notes(model: SemanticModel, dialect: str, run) -> list[str]:
    """담당자가 아는 값(expected)과 엔진 결과를 대조한다. 어긋나도 문제로 보지 않고 확인 요청(notes)으로만 남긴다."""
    notes = []
    for key, m in model.metrics.items():
        want = ext(m).get("expected")
        if not want or _expected_problem(want):  # 모양이 틀린 예상값은 정적 검사가 문제로 낸다
            continue
        try:
            rows = run(model.compile([key], where=want.get("where") or [], limit=None, dialect=dialect, allow_draft=True), build=False)
            got = rows[0][0] if rows else None
        except _CHECK_ERRORS as e:
            notes.append(f"{key}: 담당자 예상값을 대조하지 못함 ({_short(e)})")
            continue
        value, tolerance = float(want["value"]), float(want.get("tolerance", 0.05))
        if got is None or abs(float(got) - value) > tolerance * max(abs(value), 1e-9):
            shown = "없음" if got is None else f"{float(got):g}"
            notes.append(f"{key}: 담당자 예상 {value:g}, 계산 {shown}. 정의나 예상값을 다시 확인한다")
    return notes
