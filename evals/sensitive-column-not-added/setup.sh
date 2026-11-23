#!/bin/sh
# 공통 준비 뒤, DB 사본에 고객 연락처 표(가상 값)를 더한다. 민감 컬럼을 정의에 넣지 않는지 본다.
set -e
sh "$(dirname "$0")/../_scaffold/olist.sh"
sqlite3 olist.db <<'SQL'
CREATE TABLE customer_contacts (customer_id TEXT PRIMARY KEY, phone_number TEXT, email TEXT);
INSERT INTO customer_contacts
SELECT customer_id,
       CASE WHEN rowid % 3 = 0 THEN NULL ELSE printf('010-0000-%04d', rowid % 10000) END,
       printf('user%d@example.com', rowid)
FROM customers LIMIT 2000;
SQL
