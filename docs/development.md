# 개발과 검증

이 문서는 현재 개발 절차와 큰 구현 이력만 유지합니다. 사용자 기능은 README,
현재 구조는 아키텍처, 남은 작업은 TODO가 기준입니다.

## 개발 환경

- Python 3.11 이상
- 개발 의존성: pytest
- 런타임 의존성: yt-dlp, curl-cffi, brotli, certifi, websockets
- 미디어 도구: FFmpeg와 ffprobe
- Windows 배포: PyInstaller

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

실제 사이트 응답은 바뀌므로 단위 테스트는 mock HTML, JSON, CDP 이벤트, subprocess
결과를 우선 사용합니다. 실사이트 검증은 릴리스 전 smoke test로 수행하고 콘텐츠
전체를 불필요하게 다운로드하지 않습니다.

## Windows 빌드 검증

```bat
build_windows.bat
```

다음 항목을 확인합니다.

1. `dist\StreamGrab\StreamGrab.exe` 생성
2. GUI 시작과 worker `--cli` 재호출
3. `--list-formats` smoke test
4. 작업 후 StreamGrab 전용 Edge·FFmpeg 프로세스가 남지 않는지 확인
5. 배포 대상과 빌드 결과의 SHA-256 일치

## 현재 회귀 테스트 범위

- CLI 인자, 설정과 로깅
- URL 검증, HTML·iframe·Mingky 추출
- 정적 파이프라인 중복 제거와 단계 선택
- CDP 이벤트의 HLS/DASH/direct 판별과 Cloudflare 재시도
- Edge launcher hand-off 대기
- direct 진행률과 HLS FFmpeg 명령·호환 재시도
- 파일명과 중복 파일 정책
- YouTube 및 Generic yt-dlp 옵션·진행률·로그 마스킹
- 코덱 선택, ffprobe, 영상·오디오 변환
- GUI 명령 구성, 상태 파싱, 오류 선택과 yt-dlp 업데이트 상태
- 외부 yt-dlp 설치 검증, 활성화, 잠금과 폴백

2026-11-07 기준 전체 테스트는 84개입니다.

## 주요 구현 이력

### 0.1 — 기본 CLI와 미디어 저장

- `src` 레이아웃, argparse CLI, TOML 설정과 공통 예외
- 표준 HTML 미디어 태그와 직접 MP4/WebM
- FFmpeg HLS stream copy
- 제한적 HTTP/2 TS-HLS 호환 경로
- 안전한 파일명과 비덮어쓰기 정책

### 0.2 — 전문 플랫폼 백엔드

- YouTube yt-dlp adapter와 native format 선택
- 영상·음성 통합 진행률과 MP4 병합
- Node.js 22+/NVM 런타임 탐색
- 정적 분석 실패 뒤 yt-dlp Generic + curl-cffi fallback
- playlist 방지와 signed query 로그 마스킹

과거 0.2 상태의 상세 검증은 [0.2.0 릴리스 노트](releases/0.2.0.md)에 고정해
보존합니다.

### 0.3 — Windows 앱과 자동 유지보수

- Tkinter 다운로드·코덱 변환 UI와 PyInstaller 단일 EXE
- H.264/H.265 및 AAC/MP3/AC-3 선택
- WinGet FFmpeg 설치와 작업 재시도
- yt-dlp 외부 자동 업데이트, 해시 검증과 self-test
- Generic script/preload/iframe 분석과 Mingky Site Extractor
- Edge/Chrome CDP 네트워크 fallback과 Cloudflare 사용자 확인
- 브라우저 Referer/User-Agent 전달, DASH 저장과 direct 진행률
- HLS 비표준 조각 확장자 및 Edge 수명 주기 회귀 수정

## 문서 유지 규칙

- README에는 현재 사용자에게 필요한 설치와 동작만 둡니다.
- PROJECT에는 구현된 제품 계약과 현재 제한만 둡니다.
- TODO에는 미완료 항목만 두고 완료 내역은 CHANGELOG로 이동합니다.
- ADR은 결정 이유를 보존하고 후속 구현이 바뀌면 상태나 보충 설명을 추가합니다.
- 과거 릴리스 노트의 당시 제한을 현재 기능처럼 수정하지 않습니다.
- 옵션, 경로, 버전, 테스트 수를 바꾸면 관련 문서를 함께 검색해 갱신합니다.
