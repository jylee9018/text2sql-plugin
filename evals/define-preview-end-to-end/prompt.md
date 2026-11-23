---
name: define-preview-end-to-end
tags: [define-metric, end-to-end]
runs: 3
max_turns: 30
timeout_seconds: 900
disallowed_tools: [Agent]
---

월별 배송 지연율 지표를 만들어 줘. 정의 파일에 승인 전 상태로 추가하고, 월별로 미리 계산한 결과를 보여 줘. 승인은 결과를 보고 내가 따로 할게.

- 물류팀장이 매달 월별 지연율을 보고 택배사 계약을 갱신할지 정한다. 지금은 고객 문의를 손으로 세서 일주일쯤 걸린다. 비슷한 지표는 없다.
- 세는 대상은 주문(orders) 한 건. 배송이 끝난(delivered) 주문만 넣는다.
- 지연 기준: 고객 수령일(order_delivered_customer_date)이 예상 배송일(order_estimated_delivery_date)보다 늦으면 지연이다. 같은 날은 지연이 아니다.
- 기간은 주문일(order_purchase_timestamp)로 자른다. 담당자가 아는 값은 없다.
- 데이터는 작업 폴더의 olist.db(`DATABASE_URL=sqlite:///olist.db`), 정의 파일은 작업 폴더의 sales.ossie.yaml(`SEMANTIC_MODEL=sales.ossie.yaml`)을 쓴다. 이 두 가지는 다시 묻지 않아도 된다.
