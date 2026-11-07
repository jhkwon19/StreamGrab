# StreamGrab

StreamGrab은 웹페이지에서 사용자가 접근할 수 있는 영상 스트림을 찾아 저장하고,
필요하면 TV 호환 코덱으로 변환하는 Windows 데스크톱 앱 겸 Python CLI입니다.
현재 버전은 `0.3.0`입니다.

DRM 해제, 로그인 우회, CAPTCHA 자동 우회 기능은 제공하지 않습니다. 본인이 저장할
권한이 있거나 공개적으로 저장이 허용된 콘텐츠에만 사용해야 하며, 서비스 약관과
저작권은 사용자가 확인해야 합니다.

## 주요 기능

- MP4·WebM 직접 미디어 저장
- FFmpeg를 이용한 HLS(`.m3u8`) 및 DASH(`.mpd`) 저장
- HTML 미디어 태그, preload, 스크립트 문자열과 iframe 정적 분석
- YouTube 및 일반 보호 페이지의 yt-dlp 백엔드
- 정적 분석과 yt-dlp가 실패할 때 Edge/Chrome 네트워크 요청 분석
- Cloudflare 사용자 확인이 필요할 때 전용 브라우저 창으로 이어서 분석
- Mingky 계열 `/movie/{id}` 페이지의 공개 API·임베드 플레이어 분석
- H.264/H.265 영상과 AAC/MP3/AC-3 오디오 선택 및 변환
- 기존 영상 파일의 일괄 코덱 변환
- 배포 앱의 yt-dlp 자동 업데이트

## Windows 데스크톱 앱

배포 폴더의 `StreamGrab.exe`를 실행합니다. **다운로드** 탭에서는 영상 주소, 저장
폴더, 영상·오디오 코덱을 선택할 수 있습니다. **코덱 변환** 탭에서는 기존 파일을
여러 개 추가해 원본을 유지한 채 변환 사본을 만듭니다. 마지막으로 선택한 폴더와
코덱은 `%LOCALAPPDATA%\StreamGrab\settings.json`에 저장됩니다.

기본 영상 코덱은 호환성이 높은 H.264이고 기본 오디오는 AAC입니다. 원본 코덱을
유지하려면 영상 코덱에서 `원본 유지`를 선택합니다. TV에서 소리가 나지 않는 경우
MP3 또는 AC-3를 선택할 수 있습니다.

HLS·DASH 저장, 영상·음성 병합 또는 코덱 변환에 FFmpeg가 필요합니다. Windows
앱은 FFmpeg가 없을 때 사용자 확인을 받은 뒤 WinGet으로 설치하고 작업을 다시
시도합니다.

### 브라우저 확인 창

일반 HTTP 분석으로 접근할 수 없는 페이지는 설치된 Edge 또는 Chrome을 마지막
분석 단계에서 사용합니다. 먼저 숨김 브라우저로 시도하고, Cloudflare 사용자
확인이 감지되면 전용 창이 나타납니다. 확인이 끝나면 영상 요청을 감지하고 창을
자동으로 닫습니다. 창이 닫힌 뒤 GUI가 다운로드 진행률로 바뀌면 정상 동작입니다.

전용 프로필은 일반 브라우저 프로필과 분리되어 있으며 다음 위치에 유지됩니다.

```text
%LOCALAPPDATA%\StreamGrab\browser-profile
```

확인 상태를 초기화하려면 StreamGrab 작업이 없는 상태에서 이 폴더를 삭제할 수
있습니다. 로그인 정보가 필요한 사이트의 기존 사용자 프로필이나 쿠키를 자동으로
가져오지는 않습니다.

## CLI 설치와 실행

Python 3.11 이상이 필요합니다.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Windows PowerShell에서는 `.venv\Scripts\Activate.ps1`로 가상 환경을 활성화합니다.

```bash
streamgrab --help
streamgrab --version
streamgrab 'https://example.com/watch/1' --list-formats
streamgrab 'https://example.com/watch/1' -o ./downloads
```

일반 페이지의 `-f` 값은 `--list-formats`에 표시된 1부터 시작하는 스트림
번호입니다. YouTube와 yt-dlp fallback 경로에서는 `137+140` 같은 yt-dlp native
format ID를 사용합니다.

```bash
streamgrab 'https://www.youtube.com/watch?v=VIDEO_ID' --list-formats
streamgrab 'https://www.youtube.com/watch?v=VIDEO_ID' -f '137+140' -o ./downloads
```

영상과 오디오 코덱을 지정할 수 있습니다.

```bash
streamgrab URL --codec h264 --audio aac
streamgrab URL --codec h265 --audio ac3
streamgrab URL --codec original
```

기존 파일은 원본을 유지한 채 변환합니다. `--convert`에는 `original`을 사용할 수
없습니다.

```bash
streamgrab --convert video1.mkv video2.webm --codec h264 --audio mp3
streamgrab --convert video.mkv --codec h265 -o ./converted
```

출력 경로가 디렉터리이면 안전하게 정제한 제목을 파일명으로 사용합니다. 같은
파일이 있으면 `(1)`, `(2)`를 붙이며 기존 파일을 덮어쓰지 않습니다.

## 설정 파일

설정 파일은 자동 탐색하지 않으며 `--config`로 명시해야 합니다.

```bash
streamgrab URL --config streamgrab.toml
```

현재 다운로드 흐름에 적용되는 설정은 다음 두 가지입니다.

```toml
output_directory = "downloads"

[network]
timeout = 30
```

파서는 이전 설정과의 호환을 위해 `default_quality`와 `retry.count`도 읽지만 현재
다운로드 선택과 재시도에는 사용하지 않습니다.

## yt-dlp 업데이트

Windows 배포 앱에는 빌드 시점의 yt-dlp가 비상용으로 포함됩니다. 앱은 하루 한 번
PyPI의 최신 정식 버전을 확인해 실행 파일 옆 `yt-dlp\`에 설치합니다. wheel의
SHA-256을 검증하고 별도 프로세스의 import 점검이 성공한 뒤에만 새 버전으로
전환하며 최근 두 설치를 보관합니다. 해당 위치에 쓸 수 없으면
`%LOCALAPPDATA%\StreamGrab\yt-dlp\`를 사용합니다.

```text
StreamGrab\
├─ StreamGrab.exe
└─ yt-dlp\
   ├─ current.txt
   ├─ state.json
   └─ 2026.10.26\
```

GUI 상태 표시줄의 **업데이트 확인** 버튼으로 즉시 확인할 수 있습니다. 내부 유지
보수 명령은 다음과 같습니다.

```bash
python -m streamgrab --ytdlp-status
python -m streamgrab --update-ytdlp --force
```

YouTube의 JavaScript challenge 전체 지원에는 Deno 2.3 이상 또는 Node.js 22
이상이 필요할 수 있습니다. StreamGrab은 PATH를 먼저 확인하고 Windows NVM 설치가
있으면 지원되는 최신 Node.js를 선택합니다.

## Windows 실행 파일 빌드

Windows Python 3.11 이상과 Python Launcher가 설치된 환경에서 실행합니다.

```bat
build_windows.bat
```

결과는 `dist\StreamGrab\StreamGrab.exe`에 생성됩니다. 자동 업데이트 폴더를 함께
유지하려면 `dist\StreamGrab` 폴더째 복사해 사용합니다.

## 테스트와 문서

```bash
pytest
```

- [현재 제품 사양](PROJECT.md)
- [문서 안내](docs/README.md)
- [아키텍처](docs/architecture.md)
- [스트림 분석 파이프라인](docs/extraction-pipeline.md)
- [개발과 검증](docs/development.md)
- [작업 목록](TODO.md)
- [변경 이력](CHANGELOG.md)
