# 변경 이력

StreamGrab의 사용자에게 영향을 주는 변경 사항을 버전별로 기록한다.

## 미출시 — 2026-09-06

### 추가

- URL과 저장 경로만 입력하는 컴팩트한 Windows 데스크톱 UI
- 진행률, 작업 취소, 저장 폴더 열기와 한글 오류 안내
- FFmpeg 미설치 감지, WinGet 자동 설치 및 원래 다운로드 자동 재시도
- PyInstaller 기반 `StreamGrab.exe` 빌드 스크립트

### 개선

- Windows 콘솔 출력 인코딩을 자동 감지해 한글 경로와 오류가 깨지지 않도록 수정
- 중단 후 남은 직접 미디어 및 HLS 임시 파일을 다음 실행에서 안전하게 교체
- HTTP/2 전용 HLS 전송을 Windows curl 대신 curl-cffi로 처리
- WinGet 설치 직후 PATH 갱신 없이도 FFmpeg 설치 위치를 자동 탐색

### 검증

- GUI 지원 로직과 WinGet FFmpeg 탐색 회귀 테스트 추가
- 전체 자동화 테스트 39개 통과

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
