# 작업 규칙

사각 Software Engineer (AI Agent) 기술 과제 저장소이다. 프로젝트 둘이 각각 독립된 uv 프로젝트로 구성된다.

| 디렉토리          | 과제     | AI 도구                                                                           |
| ----------------- | -------- | --------------------------------------------------------------------------------- |
| look-and-say/     | 알고리즘 | 풀이 접근과 판단은 직접 한다. 도구는 테스트 세팅, 파이썬 문법, 문서 정리에만 쓴다 |
| health-assistant/ | 구현     | 사용한다. 범위와 프롬프트는 health-assistant/docs/ai-usage.md에 있다              |

### 커밋 규칙

- 제목: `type: 요약` (feat, fix, refactor, docs, test, config, chore)
- 본문은 필요할 때만 한두 줄
- Co-Authored-By 같은 AI 표기, 마크다운 문법, 이모지는 쓰지 않는다.
- `.githooks/commit-msg`가 커밋 시 형식을 검사한다. 클론 후 `git config core.hooksPath .githooks`
