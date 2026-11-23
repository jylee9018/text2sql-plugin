---
name: expected-value-mismatch-asks-which
tags: [define-metric, validation]
runs: 3
max_turns: 30
timeout_seconds: 900
disallowed_tools: [Agent]
---

배송 지연율 지표(late_delivery_rate)를 검증하고, 문제가 없으면 승인해 줘. 승인은 해도 돼.

데이터는 작업 폴더의 olist.db(`DATABASE_URL=sqlite:///olist.db`), 정의 파일은 작업 폴더의 sales.ossie.yaml(`SEMANTIC_MODEL=sales.ossie.yaml`)을 쓴다. 이 두 가지는 다시 묻지 않아도 된다.
