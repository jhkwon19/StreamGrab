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
DASH·JavaScript 실행·브라우저 쿠키·DRM 콘텐츠는 지원하지 않습니다.

StreamGrab은 본인이 저장할 권한이 있거나 공개적으로 저장이 허용된 콘텐츠에만
사용해야 합니다. 서비스 이용약관과 저작권은 사용자가 확인해야 합니다.

## 테스트

```bash
pytest
```

프로젝트의 전체 방향은 [PROJECT.md](PROJECT.md), 현재 할 일은
[TODO.md](TODO.md), 진행 기록은 [docs/development.md](docs/development.md)를
참조하세요.

다양한 플레이어 구조와 여러 영상·품질을 처리하는 확장 원칙은
[스트림 분석 파이프라인](docs/extraction-pipeline.md)에 정리되어 있습니다.
