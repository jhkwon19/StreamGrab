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
- [x] 컴팩트한 Windows 데스크톱 UI와 단일 EXE 빌드
- [x] GUI에서 FFmpeg 자동 설치 후 다운로드 재시도

## 플랫폼 백엔드

- [x] yt-dlp 기반 YouTube URL 감지와 다운로드
- [x] YouTube 형식 목록과 native format ID 선택
- [x] YouTube 영상·음성 전체 바이트 진행률 통합
- [x] YouTube fragment 진행률 역행 및 병합 안내 중복 방지
- [x] yt-dlp 로그의 서명 query 마스킹
- [x] PATH 및 NVM에서 지원되는 Node.js 22+ 자동 탐색
- [x] 정적 분석 실패 시 yt-dlp Generic Extractor fallback
- [x] curl-cffi 기반 Cloudflare impersonation 지원
- [ ] Deno/Node 런타임 진단 명령 추가
- [ ] Generic fallback에서 여러 embedded video 선택 정책 설계
- [ ] YouTube 로그인·연령 제한용 명시적 cookie 옵션 검토
- [ ] YouTube playlist는 별도 명령과 확인 절차로 설계
- [ ] YouTube 자막 저장 기능 설계 시 기존 transcript API 경험 검토

## 장기 검토

- [ ] Web UI
- [ ] Docker 지원
- [ ] 다운로드 큐와 기록
