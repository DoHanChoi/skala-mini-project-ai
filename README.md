# SKALA AI 서비스 Mini-project

운영 장애 진단 에이전트의 기존 기능을 개선하는 **주제 1** 프로젝트입니다.

## 현재 상태

- 첫 커밋은 제공된 `all_total_vue_student` 예제 소스를 기준 버전으로 보존합니다.
- 개선 기능은 논의 단계이며, 요구사항과 설계를 문서화한 뒤 개발합니다.
- 현재 검토 중인 A안은 수치·시스템명·출처 검증과 근거 표시를 통한 진단 답변의 신뢰성 개선입니다. 세부 범위는 아직 확정되지 않았습니다.
- 기준 버전은 키워드 규칙으로 대응 매뉴얼을 선택하며, 벡터 DB나 하이브리드 검색은 구현되어 있지 않습니다.

## 구성 및 실행

FastAPI 백엔드, LangGraph 처리 흐름, MCP 모니터링·매뉴얼 조회, Vue 채팅 화면, SQLite 대화 저장으로 구성됩니다. 모니터링 데이터는 샘플 데이터입니다.

실행 방법과 아키텍처는 [기존 프로젝트 매뉴얼](doc/README.md)을 참고하세요.

```bash
# 최초 한 번: 가상환경 생성 및 의존성 설치
bash sh/setup_venv.sh

# 환경설정 파일 생성 후 본인 환경에 맞게 편집
cp .env.example .env

# 로컬 모델 준비
bash sh/setup_ollama.sh

# 백엔드 실행
bash sh/run_agent_ollma.sh
```

별도 터미널에서 `bash sh/run_frontend.sh`를 실행하고 `http://localhost:8600`에 접속합니다.

기준 버전의 에이전트 실행 스크립트는 시작할 때 `session.db`를 삭제합니다. 대화 유지 동작을 평가할 때 이 동작을 고려해야 합니다.

## 참고 자료

- [Ollama 사용 예시](doc/manual_ollma.md)
- [OpenAI API 사용 예시](doc/manual_openai.md)
- [회귀 테스트 질문](doc/regression_test_queries.md)

실제 API 키가 있는 `.env`, 가상환경, 대화 DB, 캐시와 로그는 Git 추적에서 제외합니다. 설정 예시인 `.env.example`은 포함합니다.
