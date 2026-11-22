---
type: llm
---

지표는 매달 본다. 응답이 월을 어느 날짜로 자를지 사용자에게 묻는다. 후보: 주문일(order_purchase_timestamp), 고객 수령일(order_delivered_customer_date), 예상 배송일(order_estimated_delivery_date) 등.

통과: 기간을 자를 기준 날짜를 질문으로 묻는다.
실패: 묻지 않거나, 기준 날짜를 스스로 정해 확정된 것처럼 적는다.
