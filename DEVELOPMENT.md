# 개발 안내

플러그인을 고치고 시험하는 사람을 위한 문서입니다. 플러그인 사용법은 [README](README.md)를 봅니다.

## 구성

| 위치 | 내용 | 확인 방법 |
|---|---|---|
| `skills/*/SKILL.md` | 에이전트가 따르는 절차(지시문) | 직접 실행, `claude plugin eval .` |
| `agents/` | 서브에이전트(sql-reviewer) | 직접 실행 |
| `hooks/` | 도구 실행 전후에 자동으로 도는 스크립트 | `uv run pytest tests/test_hooks.py` |
| `t2s/` | 스킬이 부르는 명령줄 도구(검사·실행·지표 엔진). LLM 을 쓰지 않는다 | `uv run pytest` |
| `evals/` | 에이전트 동작 평가 시나리오 | `claude plugin eval .` |
| `tests/fixtures/` | 테스트 정답이 맞춰진 시험용 정의와 데이터. **고치지 않는다** | |

반드시 지켜야 하는 규칙(승인 조건, SQL 검사)은 스킬이 아니라 `t2s` 코드와 테스트에 둡니다. 스킬은 지시문이라 매번 똑같이 지켜진다는 보장이 없습니다.

## 준비 (한 번)

1. [uv](https://docs.astral.sh/uv/getting-started/installation/)를 설치합니다.
2. Olist SQLite 파일을 `data/olist.db`에 둡니다. 다른 곳에 있으면 링크를 걸어도 됩니다. `data/`는 git에서 제외됩니다.
   ```bash
   mkdir -p data && ln -s /path/to/olist.db data/olist.db
   ```
   PostgreSQL 등 다른 DB를 쓰려면 `data/olist.db` 대신 `DATABASE_URL`을 설정합니다.
3. 설치된 text2sql 플러그인을 꺼 둡니다. 켜 두면 설치본(캐시 복사본)과 레포 버전이 함께 로드되어, 고친 내용이 아니라 옛 버전이 돌 수 있습니다.
   ```bash
   claude plugin disable text2sql
   ```
   개발을 마치면 `claude plugin enable text2sql`로 다시 켭니다.

## 실행

```bash
sh scripts/dev.sh
```

레포의 플러그인을 설치 없이 불러와(`claude --plugin-dir`) Claude Code를 엽니다. 스킬을 고친 뒤 다시 실행하면 바로 반영됩니다.

- 정의 파일은 `.dev/sales.ossie.yaml` 사본을 씁니다. 처음 실행할 때 `tests/fixtures/olist/`에서 복사됩니다. `define-metric`처럼 정의 파일을 고치는 스킬을 마음껏 시험해도 원본과 테스트에 영향이 없습니다.
- 사본을 처음 상태로 되돌리려면 `.dev/sales.ossie.yaml`을 지우고 다시 실행합니다.
- `DATABASE_URL`, `SEMANTIC_MODEL`을 미리 설정하면 그 값을 씁니다.

## 테스트와 평가

```bash
uv run pytest            # t2s 코드, 훅, 패키지 구성
claude plugin eval .     # evals/ 시나리오로 에이전트 동작 평가
claude plugin validate . # 매니페스트와 폴더 구조 검사
```

## 배포

1. 버전을 세 곳에서 함께 올립니다: `.claude-plugin/plugin.json`, `plugin.json`(Codex용), `pyproject.toml`
2. `python3 scripts/build_plugin.py`로 claude.ai 업로드 파일(`dist/text2sql.plugin`)을 만듭니다.
3. 사용자는 `claude plugin update text2sql`로 갱신합니다.
