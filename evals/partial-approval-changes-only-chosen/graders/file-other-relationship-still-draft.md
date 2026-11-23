---
type: regex
pattern: 'name: order_items_to_sellers(?:(?!\n\s*- name:)[\s\S])*?status"?:\s*"?draft'
match: contains
target:
  source: file
  path: sales.ossie.yaml
---
