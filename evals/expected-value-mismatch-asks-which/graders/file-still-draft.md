---
type: regex
pattern: 'name: late_delivery_rate(?:(?!\n\s*- name:)[\s\S])*?status"?:\s*"?draft'
match: contains
target:
  source: file
  path: sales.ossie.yaml
---
