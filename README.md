# StreamGrab

StreamGrab은 웹페이지에서 사용자가 접근할 수 있는 영상 스트림을 찾아 로컬에
저장하는 범용 CLI 도구를 목표로 합니다. 현재는 프로젝트 기반을 구축한 초기
개발 단계입니다.

## 개발 환경 준비

Python 3.11 이상이 필요합니다.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Windows PowerShell에서는 가상 환경 활성화 명령으로
`.venv\Scripts\Activate.ps1`을 사용합니다.

## 실행

```bash
streamgrab --help
streamgrab --version
```

## Windows 데스크톱 앱

주소 입력, 저장 폴더 선택, 진행률 표시와 다운로드 취소를 지원하는 컴팩트한
데스크톱 UI를 실행할 수 있습니다. HLS 영상에 FFmpeg가 필요하지만 설치되어 있지
않다면 사용자 확인 후 WinGet으로 자동 설치하고 원래 다운로드를 다시 시작합니다.

```powershell
streamgrab-gui
```

독립 실행 파일이 필요하면 Windows Python 3.11 이상을 설치한 뒤
`build_windows.bat`를 실행하세요. UNC 형식의 WSL 공유 경로도 스크립트가 임시
드라이브로 연결하며, 빌드가 끝나면 `dist\StreamGrab.exe`가 생성됩니다.

페이지에서 지원 스트림 확인:

```bash
streamgrab 'https://example.com/video' --list-formats
```

첫 번째 스트림 저장:

```bash
streamgrab 'https://example.com/video'
streamgrab 'https://example.com/video' -f 1 -o ./downloads
```

현재 버전은 정적 HTML의 `<video src>`, `<video data-source>`, `<source src>`를
분석합니다. MP4/WebM 직접 미디어와 FFmpeg를 이용한 HLS 저장을 지원하며,
DASH·브라우저 쿠키·DRM 콘텐츠는 지원하지 않습니다. 정적 분석이 네트워크 차단
또는 미디어 미발견으로 끝나면 yt-dlp Generic Extractor로 한 번 전환해 iframe
플레이어와 Cloudflare 보호 페이지를 분석합니다. 공식 impersonation 전송만
사용하며 CAPTCHA나 로그인을 우회하지 않습니다.

보호된 일반 페이지도 같은 명령을 사용합니다. HTTP/2 전용 HLS CDN은 외부 curl
실행 파일 대신 패키지에 포함된 curl-cffi 전송 엔진을 사용합니다. 이 경로의 `-f`에는
`--list-formats`에서 표시한 native format ID를 입력합니다.

```bash
streamgrab 'https://example.com/protected-video' --list-formats
streamgrab 'https://example.com/protected-video' -f '4731' -o ./downloads
```

## YouTube

YouTube는 유지보수되는 `yt-dlp` 백엔드로 처리합니다.

```bash
streamgrab 'https://www.youtube.com/watch?v=VIDEO_ID' --list-formats
streamgrab 'https://www.youtube.com/watch?v=VIDEO_ID' -o ./downloads
streamgrab 'https://www.youtube.com/watch?v=VIDEO_ID' -f '137+140' -o ./downloads
```

기본값은 가능한 최고 품질의 MP4 영상과 M4A 오디오를 우선 선택하고 FFmpeg로
병합합니다. 최신 YouTube JavaScript challenge의 전체 형식을 사용하려면 Deno
2.3 이상(권장) 또는 Node.js 22 이상이 필요합니다. 런타임이 없더라도 yt-dlp가
제공하는 제한된 형식으로 동작을 시도합니다.

StreamGrab은 PATH의 런타임을 먼저 확인하고, NVM을 사용한다면 설치된 Node.js
22 이상 중 가장 최신 버전을 자동으로 선택합니다.

2026년 8월 안정판 `2026.7.4`에는 일부 YouTube 미디어 전송이 403으로 끝나는
문제가 있어, 이를 해결한 `2026.8.18.122307.dev0` 이상을 최소 버전으로 사용합니다.
Cloudflare impersonation용 `curl-cffi`도 함께 설치합니다. 기존 개발 환경은 다음
명령으로 의존성을 갱신할 수 있습니다.

```bash
pip install --upgrade --pre -e '.[dev]'
```

StreamGrab은 본인이 저장할 권한이 있거나 공개적으로 저장이 허용된 콘텐츠에만
사용해야 합니다. 서비스 이용약관과 저작권은 사용자가 확인해야 합니다.

## 테스트

```bash
pytest
```

프로젝트의 전체 방향은 [PROJECT.md](PROJECT.md), 현재 할 일은
[TODO.md](TODO.md), 진행 기록은 [docs/development.md](docs/development.md)를
참조하세요.

버전별 변경 사항은 [CHANGELOG.md](CHANGELOG.md)와
[v0.2.0 릴리스 노트](docs/releases/0.2.0.md)에 정리되어 있습니다.

다양한 플레이어 구조와 여러 영상·품질을 처리하는 확장 원칙은
[스트림 분석 파이프라인](docs/extraction-pipeline.md)에 정리되어 있습니다.
