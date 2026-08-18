# 변경 이력

StreamGrab의 사용자에게 영향을 주는 변경 사항을 버전별로 기록한다.

## 0.2.0 — 2026-08-18

### 추가

- yt-dlp 기반 YouTube URL 감지, 형식 조회, 다운로드 및 MP4 병합
- PATH와 NVM에서 지원되는 Node.js 22 이상 자동 탐색
- 정적 HTML 분석 실패 시 yt-dlp Generic fallback
- curl-cffi impersonation을 이용한 Cloudflare 보호 페이지 분석
- iframe에서 발견된 Bunny CDN 같은 전문 플레이어 extractor 연계

### 개선

- 영상과 음성의 전체 바이트를 합친 단일 진행률 표시
- fragment 전환 중에도 퍼센트가 뒤로 움직이지 않는 진행률
- playlist 자동 다운로드와 기존 파일 덮어쓰기 방지
- signed media URL query 로그 마스킹
- YouTube와 Generic fallback의 공통 yt-dlp 지원 코드 분리

### 검증

- YouTube 1080p 영상과 한국어 음성 다운로드 및 MP4 병합
- Cloudflare → iframe → Bunny CDN 형식 조회 및 HLS 첫 조각 전송
- 자동화 테스트 33개 통과

자세한 내용은 [v0.2.0 릴리스 노트](docs/releases/0.2.0.md)를 참조한다.

## 0.1.0 — 2026-08-18

- Python CLI와 TOML 설정 기반 구축
- 표준 HTML `video`, `source`, `data-source` 분석
- MP4/WebM 직접 다운로드와 FFmpeg 기반 HLS 저장
- HTTP/2 전용 TS-HLS fallback과 전체 세그먼트 진행률
