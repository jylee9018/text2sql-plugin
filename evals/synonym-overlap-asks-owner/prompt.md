---
name: synonym-overlap-asks-owner
tags: [define-metric, naming]
runs: 3
max_turns: 30
timeout_seconds: 900
disallowed_tools: [Agent]
---

배송 완료 주문 수 지표를 정의 파일에 승인 전 상태로 추가해 줘. 동의어는 "주문 건수"로 해 줘.

- 물류팀장이 매달 월별 배송 완료 주문 수를 보고 택배사 물량 계약을 정한다.
- 세는 대상은 주문(orders) 한 건. 주문 상태가 delivered 인 주문만 센다. 기간은 주문일(order_purchase_timestamp)로 자른다.
- 담당자가 아는 값은 없다.
- 데이터는 작업 폴더의 olist.db(`DATABASE_URL=sqlite:///olist.db`), 정의 파일은 작업 폴더의 sales.ossie.yaml(`SEMANTIC_MODEL=sales.ossie.yaml`)을 쓴다. 이 두 가지는 다시 묻지 않아도 된다.
