# StreamGrab 작업 목록

완료 여부는 코드와 테스트로 검증하며, 세부 진행 내용은
`docs/development.md`에 기록한다.

## 현재 — Phase 1

- [x] Python 패키지와 CLI 진입점 구성
- [x] 기본 로깅 구성
- [x] TOML 설정 모델과 검증 구성
- [x] pytest 테스트 환경 구성
- [ ] CI에서 테스트 자동 실행

## 다음 — Phase 2: Direct Media

- [x] `StreamInfo` 공통 데이터 모델 정의
- [x] 기본 URL과 HTTP 응답 검증
- [x] MP4/WebM 직접 다운로드 구현
- [x] 안전한 파일명과 중복 파일 정책 구현
- [x] HTTP/2 HLS 호환 경로의 단일 전체 진행률 구현
- [ ] 직접 미디어 및 FFmpeg 기본 경로의 바이트 기반 진행률 구현

## Phase 3~4 기초

- [x] 표준 HTML 미디어 태그 Generic Extractor 구현
- [x] FFmpeg 기반 기본 HLS 저장 구현
- [x] HTTP/2 전용 CDN용 단순 TS-HLS 호환 경로 구현
- [ ] HLS 마스터 재생목록 품질 목록 분석
- [ ] HLS 암호화 및 DRM 감지 후 명확한 오류 제공
- [ ] HTTP 재시도와 응답 헤더 검증 강화
- [ ] 다운로드 중단 시 임시 파일 정리 정책 통일

## Extractor 확장

- [ ] JSON-LD 및 페이지 내 JSON 미디어 후보 분석
- [ ] 알려진 JavaScript 플레이어 설정의 안전한 정적 분석
- [ ] 제한된 깊이의 iframe 재귀 분석
- [ ] 콘텐츠 그룹과 품질 variant를 표현하는 모델 추가
- [ ] 여러 영상과 여러 품질을 구분하는 CLI 출력
- [ ] 두 번째 독립 Extractor 추가 시 Protocol과 Registry 도입
- [ ] Extractor별 발견 근거와 진단 로그 추가
- [ ] 익명화된 구조별 HTML/manifest fixture 모음 구축

## 이후

- [ ] DASH 다운로드 구현
- [ ] 브라우저 기반 분석 검토
- [ ] 사이트별 플러그인 구조 구현

## 장기 검토

- [ ] Web UI 또는 GUI
- [ ] Docker 지원
- [ ] 다운로드 큐와 기록
