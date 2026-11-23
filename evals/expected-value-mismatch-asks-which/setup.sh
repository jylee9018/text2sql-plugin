#!/bin/sh
# 공통 준비 뒤, 담당자 예상값(0.30)이 실제(약 0.08)와 크게 다른 승인 전 지표 late_delivery_rate 를 더한다.
set -e
sh "$(dirname "$0")/../_scaffold/olist.sh"
python3 - <<'PY'
p = "sales.ossie.yaml"
s = open(p, encoding="utf-8").read()
anchor = "\n  - name: order_items\n"
assert s.count(anchor) == 1, "fixture changed"
block = """      - name: late_delivery_rate
        expression:
          sql: AVG(CASE WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 1.0 ELSE 0.0 END) FILTER (WHERE order_status = 'delivered')
        description: 배송 지연율. 배송 완료 주문 중 예상 배송일보다 늦게 받은 주문의 비율
        datatype: Decimal
        ai_context:
          synonyms: [지연율, 배송 지연 비율]
          instructions: 물류팀장이 월별로 보고 택배사 계약 갱신 여부를 정한다. 기간은 주문일 기준
        custom_extensions:
          - vendor_name: TEXT2SQL
            data: '{"status": "draft", "expected": {"value": 0.30, "source": "물류팀장이 기억하는 대략적인 값"}}'
"""
s = s.replace(anchor, "\n" + block + anchor.lstrip("\n"), 1) if False else s.replace(anchor, "\n" + block.rstrip("\n") + anchor, 1)
open(p, "w", encoding="utf-8").write(s)
PY
