---
type: regex
pattern: 'phone_number|email|customer_contacts'
match: not_contains
target:
  source: file
  path: sales.ossie.yaml
---
