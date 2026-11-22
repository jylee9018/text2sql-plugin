#!/bin/sh
# eval 준비: 에이전트 작업 폴더(현재 폴더)에 DB 와 정의 파일 사본을 두고, t2s 환경을 미리 만든다.
# eval 은 HOME 을 임시 폴더로 바꾸고 그 밖의 파일 읽기를 막는다. 그래서 uv 가 관리하는 파이썬을 임시 HOME 에 복사하고,
# 그 파이썬으로 t2s 환경을 만든다. 패키지는 이 컴퓨터의 uv 캐시에서 가져와 빠르다.
set -e
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
REAL_HOME=$(eval echo "~$(id -un)")

DB=${EVAL_DB:-$ROOT/data/olist.db}
[ -f "$DB" ] || { echo "DB 가 없다: $DB (DEVELOPMENT.md 의 준비 참고)" >&2; exit 1; }
cp -L "$DB" olist.db
cp "$ROOT/tests/fixtures/olist/sales.ossie.yaml" sales.ossie.yaml

unset VIRTUAL_ENV
export UV_CACHE_DIR="$REAL_HOME/.cache/uv"
export UV_PYTHON_PREFERENCE=only-managed
PY=$(UV_PYTHON_INSTALL_DIR="$REAL_HOME/.local/share/uv/python" uv python find ">=3.10" 2>/dev/null) \
  || { echo "uv 가 관리하는 파이썬이 없다. 'uv python install 3.12' 를 한 번 실행한다" >&2; exit 1; }
PYDIR=$(CDPATH= cd -- "$(dirname -- "$PY")/.." && pwd -P)
export UV_PYTHON_INSTALL_DIR="$HOME/.local/share/uv/python"
mkdir -p "$UV_PYTHON_INSTALL_DIR"
cp -R "$PYDIR" "$UV_PYTHON_INSTALL_DIR/"
sh "$ROOT/scripts/t2s" setup >&2
