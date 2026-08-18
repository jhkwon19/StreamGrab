# StreamGrab 프로젝트 개발 문서

## 1. 프로젝트 개요

**프로젝트명:** StreamGrab

StreamGrab은 웹사이트에서 제공되는 영상 스트림을 분석하고, 사용자가 접근 가능한 영상 콘텐츠를 로컬 파일로 저장할 수 있도록 하는 도구를 개발하는 프로젝트이다.

단순히 특정 사이트 하나만을 대상으로 하는 다운로더가 아니라, 다양한 웹 기반 스트리밍 구조를 분석하고 처리할 수 있는 **확장 가능한 범용 스트림 저장 도구**를 목표로 한다.

초기 버전은 CLI(Command Line Interface)를 중심으로 개발하며, 안정화 이후 필요에 따라 Web UI 또는 GUI를 추가할 수 있도록 구조를 설계한다.

---

# 2. 개발 목적

StreamGrab의 주요 목적은 다음과 같다.

1. 웹페이지에서 재생되는 영상의 실제 스트림 소스를 분석한다.
2. 사용자가 접근 가능한 영상 스트림을 로컬 파일로 저장한다.
3. 다양한 스트리밍 방식을 하나의 인터페이스에서 처리한다.
4. 사이트별 처리 로직을 모듈화하여 새로운 사이트를 쉽게 추가할 수 있도록 한다.
5. 다운로드 상태, 속도, 진행률 등을 사용자에게 직관적으로 제공한다.
6. 향후 자동화 또는 다른 프로그램에서 쉽게 사용할 수 있도록 CLI와 API 구조를 고려한다.

---

# 3. 프로젝트 개발 방향

StreamGrab은 다음과 같은 개발 원칙을 따른다.

## 3.1 범용성

특정 사이트에 종속된 구조를 최대한 피한다.

사이트별 분석이 필요한 경우 별도의 extractor 또는 plugin 형태로 분리한다.

예:

```text
streamgrab/
    extractors/
        generic.py
        site_a.py
        site_b.py
```

---

## 3.2 모듈화

각 기능을 가능한 한 독립적인 모듈로 구성한다.

예상 주요 구성 요소:

```text
StreamGrab
│
├── streamgrab
│   ├── cli
│   ├── core
│   ├── extractors
│   ├── downloader
│   ├── network
│   ├── models
│   └── utils
│
├── tests
├── docs
├── config
└── scripts
```

각 모듈의 역할은 명확하게 분리한다.

---

# 4. 주요 기능

## 4.1 URL 입력

사용자는 다운로드하려는 영상 페이지 URL을 입력한다.

예:

```bash
streamgrab https://example.com/video/123
```

또는:

```bash
streamgrab download https://example.com/video/123
```

---

## 4.2 웹페이지 분석

입력된 URL의 페이지 및 네트워크 정보를 분석하여 영상 스트림을 찾는다.

가능한 대상:

- 직접 영상 URL
- MP4
- WebM
- HLS
- M3U8
- DASH
- MPD
- Blob 기반 플레이어
- JavaScript 기반 플레이어 설정
- HTML `<video>` 태그
- `<source>` 태그

---

# 5. Stream Extractor

영상 주소를 찾는 역할은 **Extractor**가 담당한다.

Extractor는 가능한 한 다운로드 기능과 분리한다.

기본 흐름:

```text
URL
 ↓
Page Analyzer
 ↓
Extractor
 ↓
Stream Information
 ↓
Downloader
```

Extractor의 결과는 가능한 한 공통 데이터 구조로 반환한다.

예:

```python
StreamInfo(
    url="...",
    title="...",
    format="hls",
    resolution="1920x1080",
    video_codec="h264",
    audio_codec="aac"
)
```

---

# 6. Generic Extractor

가능하면 가장 먼저 Generic Extractor를 시도한다.

Generic Extractor에서는 다음 항목을 탐색할 수 있다.

- HTML video 태그
- source 태그
- m3u8 문자열
- mpd 문자열
- mp4 URL
- JavaScript player configuration
- 페이지 내 JSON 데이터

Generic Extractor로 찾을 수 없는 경우 사이트별 Extractor를 사용한다.

---

# 7. Site-specific Extractor

특정 사이트가 별도의 로직을 요구하는 경우 사이트별 Extractor를 구현한다.

예:

```text
extractors/
    generic.py
    example_site.py
```

각 Extractor는 공통 인터페이스를 사용한다.

예:

```python
class BaseExtractor:

    def can_handle(self, url):
        pass

    def extract(self, url):
        pass
```

---

# 8. 스트림 타입

초기 개발에서 우선 지원할 스트림 형식은 다음과 같다.

## 우선순위 1

Direct Media

```text
MP4
WebM
```

## 우선순위 2

HLS

```text
.m3u8
```

## 우선순위 3

MPEG-DASH

```text
.mpd
```

추가 포맷은 필요에 따라 지원한다.

---

# 9. 다운로드 엔진

다운로드 기능은 Extractor와 분리한다.

예:

```text
Downloader
 ├── DirectDownloader
 ├── HLSDownloader
 └── DashDownloader
```

각 Downloader는 동일한 인터페이스를 사용하는 것을 목표로 한다.

예:

```python
download(stream_info, output_path)
```

---

# 10. FFmpeg 활용

영상 및 스트림 처리를 위해 FFmpeg 사용을 적극 고려한다.

FFmpeg가 담당할 수 있는 기능:

- HLS 다운로드
- DASH 다운로드
- 영상/음성 병합
- 컨테이너 변환
- 스트림 remux
- 코덱 정보 확인

가능하면 불필요한 재인코딩을 피한다.

기본적으로 다음과 같은 방식의 **stream copy**를 우선 고려한다.

```bash
ffmpeg -i INPUT -c copy output.mp4
```

---

# 11. 영상 품질 선택

하나의 콘텐츠에 여러 영상 품질이 존재할 수 있다.

예:

```text
2160p
1440p
1080p
720p
480p
```

StreamGrab은 사용 가능한 스트림을 분석하여 사용자에게 선택할 수 있도록 한다.

예:

```bash
streamgrab URL --list-formats
```

출력 예:

```text
ID     Resolution    Codec    Bitrate
1      3840x2160     H264     15Mbps
2      1920x1080     H264     8Mbps
3      1280x720      H264     4Mbps
```

다운로드:

```bash
streamgrab URL -f 2
```

---

# 12. 기본 품질 정책

사용자가 별도의 품질을 선택하지 않을 경우:

```text
사용 가능한 최고 품질
```

을 기본값으로 사용하는 것을 고려한다.

다만 향후 설정 파일을 통해 변경 가능하도록 한다.

예:

```yaml
default_quality: best
```

---

# 13. 파일명 처리

파일명은 영상 제목을 기반으로 생성한다.

예:

```text
영상 제목.mp4
```

파일시스템에서 사용할 수 없는 문자는 제거하거나 변환한다.

예:

```text
/
\
:
*
?
"
<
>
|
```

중복 파일이 존재하는 경우 덮어쓰기 여부를 정책으로 관리한다.

예:

```text
video.mp4
video (1).mp4
```

---

# 14. 다운로드 진행률

다운로드 중 다음 정보를 제공한다.

```text
진행률
다운로드 크기
전체 크기
다운로드 속도
예상 남은 시간
```

예:

```text
Downloading

68%
1.42 GB / 2.08 GB
23.5 MB/s
ETA 00:27
```

---

# 15. 네트워크 처리

HTTP 요청 모듈은 별도로 관리한다.

지원 검토 항목:

- HTTP Header
- User-Agent
- Referer
- Cookie
- Redirect
- Proxy
- Timeout
- Retry

예:

```text
network/
    client.py
    headers.py
    cookies.py
```

---

# 16. 브라우저 연동

일부 사이트는 브라우저 세션 또는 JavaScript 실행이 필요할 수 있다.

향후 다음 방법을 검토한다.

- Playwright
- Chromium
- Browser Cookie Import
- DevTools Protocol

브라우저 자동화는 무조건 사용하지 않고 필요한 경우에만 사용하는 것이 원칙이다.

기본 분석은 HTTP 요청 기반으로 처리한다.

---

# 17. Cookie 지원

로그인 상태에서 사용자에게 정상적으로 제공되는 콘텐츠를 처리하기 위해 브라우저 Cookie 활용을 고려한다.

예:

```bash
streamgrab URL --cookies-from-browser chrome
```

또는:

```bash
streamgrab URL --cookies cookies.txt
```

Cookie 및 인증정보는 로그에 출력하지 않는다.

---

# 18. CLI 설계

초기 StreamGrab은 CLI 프로그램으로 개발한다.

예상 명령 구조:

```bash
streamgrab URL
```

또는:

```bash
streamgrab download URL
```

추가 명령:

```bash
streamgrab info URL
streamgrab formats URL
streamgrab download URL
```

---

# 19. 예상 CLI 옵션

예:

```text
-o
--output

-f
--format

-q
--quality

--list-formats

--cookies

--cookies-from-browser

--proxy

--user-agent

--referer

--verbose

--debug
```

옵션은 개발 과정에서 필요에 따라 변경할 수 있다.

---

# 20. 설정 파일

향후 사용자 설정을 파일로 관리할 수 있도록 한다.

예:

```yaml
output_directory: ./downloads

default_quality: best

filename_template: "{title}.{ext}"

retry:
  count: 3

network:
  timeout: 30
```

---

# 21. Logging

프로그램 내부 동작은 logging 시스템을 통해 관리한다.

로그 레벨:

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

일반 실행에서는 필요한 정보만 출력한다.

```text
INFO
WARNING
ERROR
```

개발 및 문제 분석에서는:

```bash
streamgrab URL --debug
```

형태로 상세 로그를 활성화할 수 있도록 한다.

---

# 22. 예외 처리

네트워크 및 스트림 분석 과정에서 다양한 오류가 발생할 수 있다.

주요 예외 유형:

```text
InvalidURL
NetworkError
ExtractorError
StreamNotFound
UnsupportedStream
DownloadError
FFmpegError
AuthenticationRequired
```

가능하면 단순 문자열 오류가 아니라 구조화된 예외 클래스를 사용한다.

---

# 23. 개발 언어

초기 구현 언어는 **Python**을 기본으로 고려한다.

이유:

- HTTP 처리 라이브러리가 풍부함
- 영상 분석 도구와 연동이 쉬움
- FFmpeg 실행 및 제어가 편리함
- Playwright 지원
- CLI 구현이 쉬움
- 빠른 프로토타이핑 가능
- AI Coding Agent와 개발하기 편리함

Python 버전은 개발 시작 시점의 안정적인 버전을 기준으로 결정한다.

---

# 24. 주요 라이브러리 후보

개발 과정에서 필요성을 검토한다.

HTTP:

```text
httpx
requests
```

CLI:

```text
typer
click
argparse
```

HTML 분석:

```text
beautifulsoup4
lxml
```

브라우저 자동화:

```text
playwright
```

Progress UI:

```text
rich
tqdm
```

설정:

```text
pydantic
PyYAML
```

테스트:

```text
pytest
```

필요하지 않은 라이브러리는 추가하지 않는다.

---

# 25. 외부 프로그램

다음 프로그램과의 연동을 고려한다.

```text
FFmpeg
FFprobe
```

프로그램 시작 시 FFmpeg 설치 여부를 확인할 수 있도록 한다.

예:

```text
FFmpeg detected: 8.x
```

FFmpeg가 필요한 기능을 실행할 때 설치되어 있지 않다면 사용자에게 명확한 오류 메시지를 제공한다.

---

# 26. 테스트 정책

가능한 기능에는 자동화 테스트를 작성한다.

테스트 구조 예:

```text
tests/
    test_extractors.py
    test_downloader.py
    test_network.py
    test_utils.py
```

특히 다음 기능은 테스트 대상으로 한다.

- URL 분석
- 파일명 변환
- StreamInfo parsing
- M3U8 parsing
- Extractor 선택
- 설정 파일 처리

실제 사이트에 의존하는 테스트는 최소화한다.

가능하면 fixture 또는 mock 데이터를 사용한다.

---

# 27. 개발 단계

## Phase 1 — 기본 프로젝트 구성

목표:

```text
프로젝트 구조 생성
Python 패키지 구성
CLI 실행
Logging
Config
기본 테스트 환경
```

실행 목표:

```bash
streamgrab --help
```

---

## Phase 2 — Direct Media 지원

지원:

```text
MP4
WebM
```

URL에서 직접 미디어를 다운로드하는 기능을 구현한다.

---

## Phase 3 — Generic Extractor

웹페이지 HTML에서 영상 주소를 탐색한다.

지원:

```text
video tag
source tag
mp4 URL
m3u8 URL
mpd URL
```

---

## Phase 4 — HLS

M3U8 스트림 분석 및 다운로드 기능을 구현한다.

가능하면 FFmpeg와 연동한다.

---

## Phase 5 — DASH

MPD 스트림 분석 및 다운로드 기능을 구현한다.

영상과 오디오 스트림이 분리된 경우 병합 기능을 제공한다.

---

## Phase 6 — Browser Analyzer

일반 HTTP 요청으로 스트림을 찾을 수 없는 사이트를 위해 Browser 기반 분석 기능을 추가한다.

Playwright 사용을 고려한다.

---

## Phase 7 — Site Plugin

사이트별 Extractor 구조를 정식으로 구현한다.

새로운 사이트를 쉽게 추가할 수 있도록 한다.

---

# 28. 보안 원칙

StreamGrab 개발 시 다음 보안 원칙을 따른다.

- Cookie를 로그에 출력하지 않는다.
- Authorization Header를 로그에 출력하지 않는다.
- 사용자 비밀번호를 저장하지 않는다.
- 인증 토큰을 평문으로 저장하지 않는다.
- Debug 로그에서도 민감한 Header를 마스킹한다.
- 외부 명령 실행 시 shell injection 가능성을 방지한다.

---

# 29. 프로젝트 범위 및 사용 원칙

StreamGrab은 사용자가 정상적으로 접근 권한을 가진 콘텐츠 또는 공개적으로 제공되는 스트림을 개인적인 저장, 백업, 테스트 및 기술 분석 목적으로 처리하는 것을 목표로 한다.

개발 과정에서는 다음 기능을 프로젝트 핵심 목표로 삼지 않는다.

- DRM 해제
- 암호화 보호 기능 우회
- 접근 권한 우회
- 유료 콘텐츠 인증 우회
- 계정 권한 탈취
- 보안 기능 무력화

콘텐츠의 다운로드 및 저장 가능 여부는 해당 서비스의 이용약관과 콘텐츠에 적용되는 저작권 및 사용 권한을 사용자가 확인해야 한다.

---

# 30. AI Coding Agent 개발 지침

본 프로젝트는 Codex, Claude Code 등 AI Coding Agent와 함께 개발한다.

AI는 코드를 수정하기 전에 다음 사항을 확인해야 한다.

1. 현재 프로젝트 구조를 확인한다.
2. 기존 코드를 우선 읽는다.
3. 기존 설계를 가능한 한 유지한다.
4. 동일 기능을 중복 구현하지 않는다.
5. 필요한 경우에만 새로운 dependency를 추가한다.
6. 큰 변경은 여러 개의 작은 변경으로 분리한다.
7. 기존 기능을 깨뜨리지 않도록 한다.
8. 변경 후 가능한 테스트를 수행한다.
9. 오류를 단순히 숨기지 말고 근본 원인을 해결한다.
10. 임시 workaround를 영구 코드처럼 남기지 않는다.

---

# 31. AI에게 요구하는 코드 스타일

AI는 다음 원칙으로 코드를 작성한다.

## 가독성 우선

과도하게 복잡한 코드를 피한다.

## 명확한 이름 사용

잘못된 예:

```python
def p(u):
```

권장:

```python
def parse_stream_url(url):
```

---

## 함수 역할 최소화

하나의 함수가 지나치게 많은 역할을 담당하지 않도록 한다.

---

## 필요 이상의 추상화 금지

초기 단계에서 미래 가능성을 이유로 지나치게 복잡한 abstraction을 만들지 않는다.

실제 필요가 발생하면 리팩터링한다.

---

## 주석

코드 자체로 알 수 있는 내용을 반복하는 주석은 작성하지 않는다.

복잡한 처리 이유 또는 설계 의도를 설명하는 주석을 우선한다.

---

# 32. AI 작업 전 확인 사항

AI Coding Agent는 새로운 작업을 시작할 때 다음 순서로 프로젝트를 확인한다.

```text
1. PROJECT.md 읽기
2. AGENTS.md 또는 CLAUDE.md 읽기
3. 현재 Git 상태 확인
4. 프로젝트 구조 확인
5. 관련 소스 확인
6. 관련 테스트 확인
7. 변경 작업 수행
8. 테스트
9. 변경사항 요약
```

---

# 33. AI 작업 시 금지 사항

AI는 사용자 요청 없이 다음 작업을 수행하지 않는다.

- 대규모 파일 삭제
- 프로젝트 전체 구조 변경
- 기존 API 전체 변경
- Dependency 대량 추가
- 테스트 제거
- Git history 변경
- force push
- 무관한 코드 대규모 리팩터링

---

# 34. Git 운영

가능하면 기능 단위로 변경한다.

Commit 예:

```text
feat: add generic video extractor

feat: add HLS downloader

fix: handle redirect URLs

refactor: separate network client

test: add extractor tests

docs: update StreamGrab architecture
```

Conventional Commit 형식을 기본으로 고려한다.

---

# 35. 개발 기록

중요한 설계 변경은 문서로 남긴다.

예:

```text
docs/
    architecture.md
    development.md
    decisions/
```

설계 결정 기록은 ADR 형태도 고려한다.

예:

```text
docs/decisions/

0001-use-python.md
0002-use-ffmpeg.md
0003-extractor-architecture.md
```

---

# 36. TODO 관리

개발 중 발견한 작업을 코드 내부에 무작정 TODO로 남기지 않는다.

가능하면 다음 파일에서 관리한다.

```text
TODO.md
```

형식:

```text
## High Priority

- [ ] Generic Extractor 구현
- [ ] HLS 다운로드 구현

## Normal

- [ ] Config 지원
- [ ] Cookie 지원

## Future

- [ ] Web UI
- [ ] Docker 지원
```

---

# 37. 초기 목표

첫 번째 실행 가능한 버전의 목표는 다음과 같다.

사용자가:

```bash
streamgrab https://example.com/video
```

를 실행하면

```text
페이지 분석
    ↓
영상 Stream 탐색
    ↓
Stream 정보 표시
    ↓
다운로드
    ↓
로컬 영상 파일 생성
```

까지 동작하도록 한다.

---

# 38. 장기 목표

StreamGrab은 장기적으로 다음과 같은 구조로 발전할 수 있다.

```text
StreamGrab Core
       │
       ├── CLI
       │
       ├── Web API
       │
       ├── Web UI
       │
       └── Plugin System
              │
              ├── Generic
              ├── Site A
              ├── Site B
              └── Site C
```

추가적으로 다음 기능을 고려할 수 있다.

- 다운로드 Queue
- 동시 다운로드
- 다운로드 History
- 자동 파일 정리
- 영상 Metadata 저장
- Thumbnail 저장
- Subtitle 저장
- Docker 지원
- REST API
- Web UI
- NAS 환경 지원

단, 이러한 기능은 Core 기능이 안정화된 이후 개발한다.

---

# 39. 가장 중요한 개발 원칙

StreamGrab의 핵심은 다음 세 가지이다.

**Extractor와 Downloader를 분리한다.**

```text
영상 주소를 찾는 기능
≠
영상을 다운로드하는 기능
```

**특정 사이트보다 범용 구조를 우선한다.**

```text
Generic → Site Specific
```

**처음부터 지나치게 복잡하게 만들지 않는다.**

```text
작동하는 최소 기능
↓
테스트
↓
리팩터링
↓
기능 확장
```

---

# 40. 현재 프로젝트 상태

현재 단계:

```text
Phase 2~4 — Direct Media, Generic Extractor 및 기본 HLS 수직 기능
```

Python 패키지 기반 위에 표준 HTML 미디어 분석, 직접 미디어 저장 및 FFmpeg 기반
HLS 저장의 첫 동작 경로가 구성되었다.
현재 구현 범위와 다음 작업은 `docs/development.md`와 `TODO.md`에서 관리한다.

본 문서는 StreamGrab 개발의 기본 방향을 정의하기 위한 초기 문서이며, 실제 개발 과정에서 필요에 따라 지속적으로 수정한다.

AI Coding Agent는 본 문서를 절대적인 구현 명세가 아니라 **프로젝트의 목적, 개발 철학 및 기본 아키텍처를 이해하기 위한 기준 문서​**로 사용한다.
