---
name: approved-metric-exists-points-to-it
tags: [define-metric, existing-metric]
runs: 3
max_turns: 25
timeout_seconds: 600
disallowed_tools: [Agent]
---

주문 건수 지표를 새로 만들어 줘.

- 영업팀장이 매주 월별 주문 건수를 보고 프로모션을 더 할지 정한다. 취소·미처리 주문은 빼고 센다.
- 데이터는 작업 폴더의 olist.db(`DATABASE_URL=sqlite:///olist.db`), 정의 파일은 작업 폴더의 sales.ossie.yaml(`SEMANTIC_MODEL=sales.ossie.yaml`)을 쓴다. 이 두 가지는 다시 묻지 않아도 된다.
