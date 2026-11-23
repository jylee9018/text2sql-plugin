#!/bin/sh
# 시험 준비의 마지막 단계: 작업 폴더의 정의 파일을 git 에 한 번 커밋한다.
# t2s check 가 이 판과 견줘 이번에 바뀐 것(승인 기록, 새 지표의 결정, revision)을 본다.
# 시나리오별로 정의 파일을 고치는 준비가 모두 끝난 뒤에 부른다.
set -e
git init -q
git -c user.name=eval -c user.email=eval@example.invalid add sales.ossie.yaml
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "시험 시작 시점의 정의"
