#!/bin/sh
# 개발용 실행: 이 레포의 플러그인을 설치 없이 불러와 Claude Code 를 연다. 자세한 내용은 DEVELOPMENT.md.
#
#   sh scripts/dev.sh
#
# - DB: DATABASE_URL 이 있으면 그 값, 없으면 data/olist.db (data/ 는 git 에서 제외)
# - 정의 파일: SEMANTIC_MODEL 이 있으면 그 값, 없으면 .dev/sales.ossie.yaml
#   .dev/ 의 사본은 처음 실행할 때 tests/fixtures/olist/ 에서 복사한다. 원본은 테스트 정답이라 고치지 않는다.
#   사본을 처음 상태로 되돌리려면 .dev/sales.ossie.yaml 을 지우고 다시 실행한다.
# - 설치된 text2sql 플러그인과 섞이지 않게 먼저 `claude plugin disable text2sql` 을 해 둔다.
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK="$ROOT/.dev"

if [ -z "$DATABASE_URL" ]; then
  DB="$ROOT/data/olist.db"
  if [ ! -f "$DB" ]; then
    echo "DB 가 없다: $DB" >&2
    echo "Olist SQLite 파일을 data/olist.db 에 두거나(링크도 된다), DATABASE_URL 을 설정한 뒤 다시 실행한다." >&2
    exit 1
  fi
  export DATABASE_URL="sqlite:///$DB"
fi

if [ -z "$SEMANTIC_MODEL" ]; then
  mkdir -p "$WORK"
  [ -f "$WORK/sales.ossie.yaml" ] || cp "$ROOT/tests/fixtures/olist/sales.ossie.yaml" "$WORK/"
  export SEMANTIC_MODEL="$WORK/sales.ossie.yaml"
fi

# t2s 를 처음 설치할 때 conda·venv 의 파이썬 대신 uv 가 관리하는 파이썬을 쓴다(conda 파이썬은 sqlite 모듈이 깨져 있는 경우가 있다)
export UV_PYTHON_PREFERENCE=only-managed
unset VIRTUAL_ENV

# .dev/ 에서 연다. 레포 최상위에서 열면 스킬이 정의 파일 후보로 원본(tests/fixtures/)도 찾는다
mkdir -p "$WORK"
cd "$WORK" || exit 1
exec claude --plugin-dir "$ROOT" "$@"
