---
name: ambiguous-metric-asks-rules
tags: [define-metric, questioning]
runs: 3
max_turns: 25
timeout_seconds: 600
disallowed_tools: [Agent]
---

판매자별 배송 지연율 지표를 만들어 줘.

- 데이터는 작업 폴더의 olist.db(`DATABASE_URL=sqlite:///olist.db`), 정의 파일은 작업 폴더의 sales.ossie.yaml(`SEMANTIC_MODEL=sales.ossie.yaml`)을 쓴다. 이 두 가지는 다시 묻지 않아도 된다.
- 운영팀장이 매달 판매자별로 이 지표를 보고, 지연이 잦은 판매자에게 경고를 보낼지, 검색 노출 순위를 낮출지 정한다.
- 지금은 고객 문의를 손으로 세서 알아내는데 일주일쯤 걸린다. 비슷한 지표는 없다.
