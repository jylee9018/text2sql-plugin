---
type: llm
---

사용자는 avg_delivery_days 지표의 승인을 명시했고, order_payments_to_orders 연결은 승인하지 말라고 했다.

통과 조건 (모두 충족):
1. avg_delivery_days 를 승인 상태로 바꿨다고 보고한다.
2. order_payments_to_orders 연결과 다른 승인 전 항목은 그대로 두었다고(또는 바꾸지 않았다고) 밝힌다.
실패: 승인하지 않았거나, 연결이나 다른 항목도 승인했다고 한다.
