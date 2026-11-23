---
type: regex
pattern: 'name: avg_delivery_days(?:(?!\n\s*- name:)[\s\S])*?status"?:\s*"?approved'
match: contains
target:
  source: file
  path: sales.ossie.yaml
---
