#!/bin/sh
# 공통 준비 뒤, avg_delivery_days 의 미정 사항을 지운다(미정 사항 없는 승인 전 지표).
set -e
sh "$(dirname "$0")/../_scaffold/olist.sh"
python3 - <<'PY'
p = "sales.ossie.yaml"
s = open(p, encoding="utf-8").read()
old = "instructions: 기간은 주문일 기준. 시작 시점을 주문일로 볼지 결제 승인일로 볼지 아직 정하지 않았다"
assert old in s, "fixture changed"
s = s.replace(old, "instructions: 기간은 주문일 기준. 물류팀장이 월별 배송 소요일을 보고 택배사 계약 갱신 여부를 정한다")
open(p, "w", encoding="utf-8").write(s)
PY
