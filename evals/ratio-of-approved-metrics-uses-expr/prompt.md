---
name: ratio-of-approved-metrics-uses-expr
tags: [define-metric, derived-metric]
runs: 3
max_turns: 25
timeout_seconds: 600
disallowed_tools: [Agent]
---

주문당 평균 매출 지표를 만들어 줘.

- 마케팅팀장이 매달 고객 주별로 이 값을 보고, 주별 쿠폰 금액을 정한다. 매출은 지금 쓰는 매출 기준 그대로, 주문 수도 지금 쓰는 주문 수 기준 그대로 쓴다.
- 데이터는 작업 폴더의 olist.db(`DATABASE_URL=sqlite:///olist.db`), 정의 파일은 작업 폴더의 sales.ossie.yaml(`SEMANTIC_MODEL=sales.ossie.yaml`)을 쓴다. 이 두 가지는 다시 묻지 않아도 된다.
