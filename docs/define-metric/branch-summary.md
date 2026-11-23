# `improve/define-metric` 브랜치 작업 요약

- 기준: `main` 커밋 `e250ebb`
- 범위: 작업 커밋 8개와 문서 정리 커밋, 2026-11-21 ~ 2026-11-24
- 관련 문서: [작업 정리 (글)](work-summary.md), [고도화 계획안](improvement-plan.md)

## 한눈에 보기

지표 정의 에이전트(`define-metric`)로 만든 지표가 **정의 → 미리 계산 → 승인**까지 끊기지 않고 이어지게 했다. 각 변경의 효과는 시험(evals)으로 확인했다.

| 작업 | 무엇을 했나 | 결과 |
|---|---|---|
| 1. 시험 환경과 현재 점수 | 시험 10개 추가(총 16개), `main` 점수 측정 | 문제 2개를 점수로 확인 |
| 2. 승인 요청 연결 | 스킬 설명에 승인·검토 용도 추가 | 스킬 호출 3/12 → 12/12 |
| 3. 정의를 읽는 곳 정리 | `t2s`에 `--definition <파일>` 추가 | 미리 계산 0/3 → 4/4 |
| 4. 규칙 검사 이동 | `t2s check`에 규칙 5개 추가 | 시험 점수 유지, 단위 테스트 125개 통과 |
| 5. 설명서 정리 | 작성 형식 세부를 참고 문서로 분리 | `SKILL.md` 147 → 119줄, 점수 유지 |

## 1. 무엇이 바뀌었나: 정의를 읽는 곳

### 바꾸기 전 (`main`)

에이전트는 지표를 **로컬 정의 파일**에 적었다. 그런데 미리 계산과 답변은 **Graph 서버**의 정의를 읽었다. 그래서 방금 만든 지표가 보이지 않았다.

```mermaid
flowchart LR
    U([사용자]) --> DM[define-metric]
    DM -- "지표를 적음" --> L[(로컬 정의 파일)]
    DM -- "t2s context / values /<br/>compile --allow-draft" --> G[(Graph 서버<br/>게시된 정의)]
    G -. "새 지표 없음" .-x P[미리 계산 실패]
    L -. "승인해도" .-x A[ask 답변에 안 쓰임]
    G --> A2[ask 답변]

    style P fill:#fde2e2,stroke:#c0392b
    style A fill:#fde2e2,stroke:#c0392b
```

### 바꾼 뒤 (이 브랜치)

지표를 정의하는 동안에는 `t2s ... --definition <파일>`로 **로컬 정의 파일만** 읽는다. 승인은 "게시 준비 완료"를 뜻한다. Graph에 게시된 뒤에 질문 답변(ask)에 쓰인다.

```mermaid
flowchart LR
    U([사용자]) --> DM[define-metric]
    DM -- "지표를 적음" --> L[(로컬 정의 파일)]
    DM -- "t2s ... --definition 파일" --> L
    L --> P[미리 계산<br/>source: local]
    L -- "승인 = 게시 준비 완료" --> PUB[[정의 저장소 → Graph 게시<br/>사람이 진행]]
    PUB --> G[(Graph 서버<br/>게시된 정의)]
    G --> A[ask 답변]

    style P fill:#e2f5e9,stroke:#27ae60
    style PUB fill:#fff6db,stroke:#d4a017
```

**전제**: 로컬 정의 파일(정의 저장소)이 원본이고, Graph는 그 파일을 게시한 것이다. Graph에만 있는 지표가 생기는 운영 방식이라면 이 전제가 깨지므로, 지표를 찾는 단계에 Graph 확인을 추가해야 한다.

## 2. 지표 정의 흐름과 이번에 바뀐 곳

```mermaid
flowchart TD
    R["요청<br/>예: '배송 지연율 지표 만들어 줘'<br/>예: '이 지표 승인해 줘'"] --> S0{"define-metric<br/>호출"}
    S0 --> S1["1. 이미 있는지 찾기<br/>t2s context --definition"]
    S1 -->|같은 승인 지표 있음| E1[그 지표를 알려 주고 끝]
    S1 -->|승인 지표끼리 비율| E2[t2s compile --expr 안내]
    S1 -->|승인 전 지표 있음| S7
    S1 -->|없음| S2["2. 누가 무엇을 결정하나 묻기"]
    S2 --> S3["3. 계산 규칙 묻기<br/>t2s values / schema --definition"]
    S3 --> S4["4. 정의 파일에 승인 전 상태로 적기<br/>references/definition-format.md 를 읽고 형식대로"]
    S4 --> CHK{{"t2s check<br/>(훅이 편집 직후 실행)"}}
    CHK -->|문제 있음| S4
    CHK --> S5["5. 미리 계산<br/>t2s compile --allow-draft --definition"]
    S5 --> S7["7. 승인 여부 묻기<br/>고른 것만 approved + approval 기록"]
    S7 --> E3["게시 안내<br/>게시 전 값은 '게시 전 정의'로 표시"]

    classDef changed fill:#e8f0fe,stroke:#1a73e8,stroke-width:2px
    class S0,S1,S3,S4,S5,S7,E3,CHK changed
```

파란 테두리가 이번에 바뀐 곳이다.

| 바뀐 곳 | 작업 | 내용 |
|---|---|---|
| define-metric 호출 | 2 | "~ 지표 승인해 줘" 같은 요청도 이 스킬로 온다 |
| 1·3·5단계 명령 | 3 | 모든 `t2s` 명령에 `--definition <정의 파일>` |
| 4단계 작성 형식 | 5 | 형식 세부는 참고 문서(`references/definition-format.md`)로 옮기고, 본문에는 꼭 지킬 규칙만 둔다 |
| 편집 직후 검사 | 4 | 민감 컬럼, 승인 기록, 새 지표의 결정, `revision` |
| 7단계 승인 | 3·4 | 승인 기록(역할·날짜)을 함께 적고, 승인은 "게시 준비 완료"로 안내 |

## 3. `t2s check`에 추가한 규칙 (작업 4)

예전부터 있던 지표에 경고가 쏟아지지 않도록, 일부 규칙은 git 마지막 커밋과 비교해 **이번에 바뀐 것**에만 적용한다.

```mermaid
flowchart LR
    F[(정의 파일)] --> ALL["파일 전체 검사"]
    F --> GIT{"git 저장소에<br/>있는가?"}
    GIT -->|예| DIFF["마지막 커밋과 비교<br/>compared_with: git HEAD"]
    GIT -->|아니오| SKIP["비교 생략<br/>compared_with: null"]

    ALL --> A1["민감 컬럼<br/>(연락처·계좌번호 등, 식 안 포함)"]
    ALL --> A2["승인 기록 형식<br/>(by 역할, at 날짜)"]
    DIFF --> D1["이번에 승인된 항목에<br/>승인 기록이 있는가"]
    DIFF --> D2["새 지표에<br/>decision 이 있는가"]
    DIFF --> D3["내용이 바뀌었으면<br/>revision 이 올랐는가"]

    A1 & A2 & D1 & D2 --> PR[problems<br/>고쳐야 함]
    D3 --> NT[notes<br/>확인 요청]

    style PR fill:#fde2e2,stroke:#c0392b
    style NT fill:#fff6db,stroke:#d4a017
```

## 4. 시험 체계 (작업 1)

시험 16개를 두 묶음으로 나눠 쓴다.

```mermaid
flowchart TB
    subgraph FIX["고칠 대상: 작업 2·3의 효과를 3회씩 측정"]
        F1[미정 사항이 남은 승인 요청]
        F2[미정 사항 없는 승인 요청]
        F3[지표만 승인하고 연결은 보류]
        F4[예상값과 계산값이 다름]
        F5[정의 → 미리 계산 → 게시 안내]
    end
    subgraph KEEP["지킬 대상: 작업마다 1회씩 확인"]
        K1[승인 지표끼리 비율 요청]
        K2[연락처 컬럼 요청]
        K3[계산 기준이 모호한 요청]
        K4[스킬 연결 5개]
    end
    subgraph WEAK["보강 후보: 플러그인 없이도 통과"]
        W1[결정을 먼저 묻기]
        W2[같은 지표가 이미 있음]
        W3[동의어 겹침]
    end
```

- 시험 준비: 시나리오마다 작업 폴더에 `olist.db`와 시험용 정의 파일을 복사하고, 정의 파일을 git에 한 번 커밋한다(`evals/_scaffold/`).
- 채점: LLM 판정과 함께 결정적 채점을 둔다. 정의 파일의 최종 상태는 정규식으로, 도구 호출은 호출 기록으로 본다.
- Graph 서버는 쓰지 않는다. 지표 정의가 Graph 없이 되는지가 이번 작업의 전제이기 때문이다.

## 5. 시험 결과 변화

| 시험 | `main` (3회) | 작업 2 | 작업 3 | 작업 4 | 작업 5 (3회) |
|---|---|---|---|---|---|
| 승인·검증 4개: 스킬 호출 | 3/12 | **12/12** | 4/4 | 4/4 | 12/12 |
| 정의 → 미리 계산: 결과 제시 | 0/3 | 0/1 | **4/4** | 1/1 | 3/3 |
| 일부 승인: 승인 기록 남김 | — | — | — | **6/6** | 3/3 |
| 나머지 지킬 대상·보강 후보 | 통과 | 통과 | 통과 | 통과 | 통과 (채점 오판 1건) |
| 모든 항목을 통과한 회차 | — | — | — | — | 정리 전 47/48 → 정리 후 46/48 |

`—`는 아직 해당 채점이 없던 시점이다. 작업 2~4는 고칠 대상만 3회, 나머지는 1회 측정했다. 작업 5는 설명서 정리 전후를 모두 3회씩 쟀다. 정리 후 실패 2건은 채점 쪽 문제였다(판정 오판 1건, 정규식이 좁았던 1건). 자세한 수치는 작업별 결과 문서에 있다.

## 6. 커밋과 작업의 대응

```mermaid
gitGraph
    commit id: "e250ebb (main)"
    branch improve/define-metric
    commit id: "bf7e29b 개발 환경 안내"
    commit id: "7088067 모호한 기준 시험"
    commit id: "90bf204 작업 1: 시험·현재 점수"
    commit id: "983382a 작업 2: 승인 요청 연결"
    commit id: "210364c 작업 3: --definition"
    commit id: "3677998 작업 4: check 규칙"
    commit id: "472b11b 민감 컬럼 파생 필드"
    commit id: "d442873 작업 5: 설명서 정리"
```

| 커밋 | 날짜 | 작업 | 주요 파일 |
|---|---|---|---|
| `bf7e29b` | 11-21 | 준비 | `DEVELOPMENT.md`, `scripts/dev.sh` |
| `7088067` | 11-22 | 준비 | `evals/ambiguous-metric-asks-rules/` |
| `90bf204` | 11-23 | 1 | `evals/` 시험 10개, `docs/define-metric/` |
| `983382a` | 11-23 | 2 | `skills/define-metric/SKILL.md` (설명) |
| `210364c` | 11-24 | 3 | `t2s/cli.py`, `tests/test_cli.py`, `SKILL.md` |
| `3677998` | 11-24 | 4 | `t2s/definition.py`, `t2s/cli.py`, `tests/`, `evals/_scaffold/` |
| `472b11b` | 11-24 | 4 보완 | `SKILL.md`, 민감 컬럼 시험 채점 |
| `d442873` | 11-24 | 5 | `SKILL.md`, `references/definition-format.md`, `docs/define-metric/` |

이 문서를 고치기만 한 문서 정리 커밋은 위 도식과 표에서 뺐다.

변경 규모: 파일 107개, 2,188줄 추가, 58줄 삭제. 대부분은 시험 시나리오와 문서다. 코드·설명서·참고 문서·테스트는 7개 파일, 418줄 추가, 58줄 삭제다.

## 7. 남은 일

- **보강 후보 시험 3개**: 더 어려운 상황으로 바꿀지, 뺄지 정한다.
- **LLM 채점 흔들림**: 긴 답변에서 기준을 충족한 내용을 놓친 오판이 2건 있었다(작업 3, 작업 5). 채점 모델(`--judge-model`)이나 기준 문장을 손본다.
- **정규식 채점의 폭**: 정의 파일의 식을 정규식으로 보는 채점이 같은 뜻의 다른 표기(여러 줄 식, `CAST` 감싸기)를 두 번 놓쳤다. 여유 있게 쓴다.
- **승인 기록 검사의 실제 동작**: 에이전트가 매번 기록을 적어서, 검사가 문제를 잡는 장면은 시험에서 나오지 않았다. 단위 테스트로만 확인했다.

## 작업별 결과 문서

- [현재 점수 (`main` 기준)](eval-baseline.md)
- [작업 2 결과](eval-task2.md)
- [작업 3 결과](eval-task3.md)
- [작업 4 결과](eval-task4.md)
- [작업 5 결과](eval-task5.md)
- [시험 목록](eval-cases.md)
