---
type: regex
pattern: 'DATEDIFF\([^)]*order_estimated_delivery_date[^)]*order_delivered_customer_date|DATEDIFF\([^)]*order_delivered_customer_date[^)]*order_estimated_delivery_date|order_delivered_customer_date[^\n<>]{0,40}>=?[^\n]{0,40}order_estimated_delivery_date|order_estimated_delivery_date[^\n<>]{0,40}<=?[^\n]{0,40}order_delivered_customer_date'
match: contains
target:
  source: file
  path: sales.ossie.yaml
---
