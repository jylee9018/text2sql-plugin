---
name: approve-with-open-question-asks-first
tags: [define-metric, approval]
runs: 3
max_turns: 25
timeout_seconds: 600
disallowed_tools: [Agent]
---

평균 배송일수 지표(avg_delivery_days)를 승인해 줘. 이제 답변에 쓰고 싶어.

데이터는 작업 폴더의 olist.db(`DATABASE_URL=sqlite:///olist.db`), 정의 파일은 작업 폴더의 sales.ossie.yaml(`SEMANTIC_MODEL=sales.ossie.yaml`)을 쓴다. 이 두 가지는 다시 묻지 않아도 된다.
