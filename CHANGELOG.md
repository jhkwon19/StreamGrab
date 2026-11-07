# 변경 이력

StreamGrab의 사용자에게 영향을 주는 변경 사항을 버전별로 기록합니다.

## 0.3.0 — 2026-11-07

### 추가

- Tkinter 기반 Windows 앱의 **다운로드** 및 **코덱 변환** 탭
- 다운로드 코덱 선택: H.264, H.265, 원본 유지
- 오디오 코덱 선택: AAC, MP3, AC-3 및 마지막 설정 기억
- 기존 파일을 보존하는 다중 파일 변환과 `--convert`
- 배포 앱 외부의 yt-dlp 자동 업데이트, SHA-256 검증, 자가 점검과 최근 버전 폴백
- 정적 분석 실패 뒤 Edge/Chrome 네트워크 요청을 관찰하는 CDP fallback
- Cloudflare 확인이 필요할 때 전용 브라우저 창으로 이어서 분석하는 흐름
- 스크립트 미디어 URL, preload와 깊이 제한 iframe 정적 분석
- Mingky 계열 `/movie/{id}` 페이지의 공개 API Site Extractor
- 직접 MP4/WebM의 Content-Length 기반 다운로드 진행률
- FFmpeg 기반 DASH 저장

### 개선

- HLS, DASH, direct 후보 중복 제거와 HLS 우선 정렬
- 브라우저에서 감지한 Referer와 User-Agent를 실제 다운로드에 전달
- 전용 브라우저 프로필을 `%LOCALAPPDATA%\StreamGrab\browser-profile`에 유지
- Cloudflare 분석 종료 후 CDP로 브라우저 전체를 닫고 런처 hand-off를 허용
- FFmpeg 9가 `.bin`, `.dat` 같은 HLS 조각을 거부할 때 호환 옵션으로 재시도
- HTTP/2 전용 단순 TS-HLS를 curl-cffi로 전송하고 FFmpeg로 병합
- GUI 취소 시 worker와 FFmpeg 자식 프로세스 트리 종료
- GUI 상태에 다운로드, 후처리, 변환, 브라우저 확인 단계를 구분해 표시
- 빌드 결과를 `dist\StreamGrab\` 배포 폴더로 구성
- yt-dlp 2026.10.26, curl-cffi 0.17.0, brotli 1.2.1, certifi
  2026.10.23을 기본 의존성으로 갱신

### 수정

- 영상 제목의 이모지 때문에 cp949 출력에서 다운로드가 중단되는 문제
- 직접 다운로드 중 GUI가 “브라우저 확인 대기 중”에 머물러 보이는 문제
- Edge가 런처 프로세스를 교체할 때 브라우저 종료로 오인하는 문제
- 다음 실행과 충돌하던 StreamGrab 전용 Edge 고립 프로세스
- YouTube fragment 전환 중 진행률이 뒤로 움직이는 문제
- 영상·음성 병합 안내가 여러 번 출력되는 문제

### 검증

- 자동화 테스트 84개 통과
- AVsee Cloudflare 페이지의 direct 영상 요청을 연속 실행에서 검출하고 전용 Edge
  프로세스가 남지 않는 것을 확인

## 0.2.0 — 2026-08-18

### 추가

- yt-dlp 기반 YouTube URL 감지, 형식 조회, 다운로드 및 MP4 병합
- PATH와 NVM에서 Node.js 22 이상 탐색
- 정적 HTML 분석 실패 시 yt-dlp Generic fallback
- curl-cffi impersonation과 외부 iframe 전문 extractor 연계

### 개선

- 영상과 음성의 전체 바이트를 합친 단일 진행률
- playlist 자동 다운로드와 기존 파일 덮어쓰기 방지
- 서명된 미디어 URL query 로그 마스킹

당시의 상세 내용과 제한은 [v0.2.0 릴리스 노트](docs/releases/0.2.0.md)를
참조합니다.

## 0.1.0 — 2026-08-18

- Python CLI와 TOML 설정 기반
- 표준 HTML `video`, `source`, `data-source` 분석
- MP4/WebM 직접 다운로드와 FFmpeg 기반 HLS 저장
- HTTP/2 전용 단순 TS-HLS fallback과 세그먼트 진행률
