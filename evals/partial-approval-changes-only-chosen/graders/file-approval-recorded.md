---
type: regex
pattern: 'name: avg_delivery_days(?:(?!\n\s*- name:)[\s\S])*?approval'
match: contains
target:
  source: file
  path: sales.ossie.yaml
---
