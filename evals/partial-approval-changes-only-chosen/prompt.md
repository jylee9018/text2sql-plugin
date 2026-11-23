---
name: partial-approval-changes-only-chosen
tags: [define-metric, approval]
runs: 3
max_turns: 30
timeout_seconds: 900
disallowed_tools: [Agent]
---

평균 배송일수 지표(avg_delivery_days)는 정의를 검토했고 이대로 승인할게. 승인 상태로 바꿔 줘. 단, 결제와 주문을 잇는 연결(order_payments_to_orders)은 아직 승인하지 마.

데이터는 작업 폴더의 olist.db(`DATABASE_URL=sqlite:///olist.db`), 정의 파일은 작업 폴더의 sales.ossie.yaml(`SEMANTIC_MODEL=sales.ossie.yaml`)을 쓴다. 이 두 가지는 다시 묻지 않아도 된다.
