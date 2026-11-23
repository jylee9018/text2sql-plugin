---
type: llm
---

정의 파일에는 승인된 지표 `revenue`(매출)와 `order_count`(주문 수)가 있다. 주문당 평균 매출은 이 둘의 비율이라 새 지표가 필요 없고, `t2s compile revenue order_count --expr "revenue / order_count"` 처럼 기존 지표로 계산할 수 있다.

통과: 응답이 새 지표를 만들지 않고, 기존 revenue 와 order_count 를 나눠 계산하는 방법(t2s compile --expr 또는 같은 뜻의 안내)을 알려 준다.
실패: 주문당 평균 매출을 새 지표로 정의 파일에 추가했다고 하거나, 추가할 새 지표 정의를 제시한다.
