# 지표 정의 시험: 작업 2 결과 (승인 요청 연결)

- 측정일: 2026-11-23
- 변경: `skills/define-metric/SKILL.md`의 설명(description)에 두 가지를 추가했다. 승인 전 지표를 검토·승인할 때도 이 기능을 쓴다는 것, 그리고 "~ 지표 승인해줘", "이 지표 이제 답변에 쓰고 싶어" 같은 사용 예다.
- 비교 기준: [현재 점수 (`main` 기준)](eval-baseline.md)
- 관련 문서: [고도화 계획안](improvement-plan.md)의 작업 2

## 요약

- **승인·검증 요청에서 `define-metric`이 쓰인 횟수가 12번 중 3번에서 12번 중 12번으로 늘었다.** 동작(미정 사항 질문, 고른 것만 승인, 예상값 차이 지적)도 모두 그대로 맞았다.
- **설명을 넓혀서 생길 수 있는 부작용은 보이지 않았다.** "답변에 쓰고 싶어"가 들어간 데이터 질문은 여전히 ask로 갔고, 기존 스킬 연결 시험 4개도 모두 통과했다.
- 통과하지 못한 시험 2개는 이번 변경과 관계없다. 미리 계산 실패(작업 3에서 고칠 대상)와, `main` 기준에서도 3번 중 1번 실패했던 민감 컬럼 이유 설명 판정이다.

## 고칠 대상: 승인·검증 시험 (3회씩)

| 시험 | 스킬 호출 (`main` → 작업 2) | 점수 |
|---|---|---|
| `approve-with-open-question-asks-first` | 0/3 → **3/3** | 1.00 |
| `partial-approval-changes-only-chosen` | 0/3 → **3/3** | 1.00 |
| `expected-value-mismatch-asks-which` | 1/3 → **3/3** | 1.00 |
| `approve-draft-reviews-then-confirms` | 2/3 → **3/3** | 1.00 |
| 합계 | 3/12 → **12/12** | |

이 측정은 플러그인을 켠 실행만 돌렸다. 스킬 호출 항목도 점수에 포함된다.

## 지킬 대상과 보강 후보 (1회씩)

| 시험 | 결과 | 비고 |
|---|---|---|
| `data-question-with-use-phrase-routes-to-ask` | 통과 | ask로 가고 define-metric은 호출되지 않음 |
| `data-question-routes-to-ask` | 통과 | |
| `explain-request-routes-to-explain-sql` | 통과 | |
| `new-metric-routes-to-define-metric` | 통과 | |
| `schema-question-routes-to-explore-schema` | 통과 | |
| `ratio-of-approved-metrics-uses-expr` | 통과 | |
| `ambiguous-metric-asks-rules` | 통과 | |
| `no-decision-asks-why-first` | 통과 | |
| `approved-metric-exists-points-to-it` | 통과 | |
| `synonym-overlap-asks-owner` | 통과 | |
| `sensitive-column-not-added` | 0.80 | 연락처 컬럼은 넣지 않았다. 이유 설명이 부족하다는 판정 1건. `main` 기준에서도 3번 중 1번 같은 판정이 나왔다 |
| `define-preview-end-to-end` | 0.80 | 미리 계산 실패. 작업 3에서 고칠 대상 |

## 비용

$8.12 (전체 16개 1회 $4.55, 승인·검증 4개 3회 $3.58)

## 남은 확인

민감 컬럼 시험의 "이유 설명" 판정이 실행마다 흔들린다(`main` 2/3, 작업 2 0/1). 채점 기준이 너무 엄격한지, 실제로 설명이 빠지는지 작업 5 전에 확인한다.
