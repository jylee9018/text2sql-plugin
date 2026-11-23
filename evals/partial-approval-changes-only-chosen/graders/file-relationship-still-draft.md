---
type: regex
pattern: 'name: order_payments_to_orders(?:(?!\n\s*- name:)[\s\S])*?status"?:\s*"?draft'
match: contains
target:
  source: file
  path: sales.ossie.yaml
---
