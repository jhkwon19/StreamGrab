# 아키텍처

이 문서는 StreamGrab 0.3.0의 실제 코드 구조를 설명합니다.

## 실행 진입점

```text
Windows StreamGrab.exe ── Tkinter GUI (`streamgrab.gui`)
                               │ worker subprocess (`--cli`)
                               ▼
Python console script ── `streamgrab.cli:main`
                               ▲
python -m streamgrab ── `streamgrab.__main__`
```

`streamgrab.__main__`은 CLI 모듈을 import하기 전에 외부 yt-dlp 설치를 활성화합니다.
`--ytdlp-status`, `--update-ytdlp`, 내부 self-test 같은 유지보수 명령도 이 단계에서
처리합니다. GUI는 다운로드와 변환을 별도 worker 프로세스로 실행하므로 네트워크나
FFmpeg 작업 중에도 응답합니다.

## 전체 실행 흐름

```text
URL
 ├─ YouTube 판별 성공
 │    └─ YouTubeBackend (yt-dlp 분석·다운로드)
 └─ 일반 URL
      ├─ ExtractionPipeline.extract_static
      │    ├─ 직접 미디어 URL
      │    ├─ Generic HTML + iframe
      │    └─ Mingky Site Extractor
      ├─ 실패: Generic yt-dlp backend
      └─ 다시 실패: BrowserNetworkExtractor
            ├─ 숨김 Edge/Chrome CDP
            └─ Cloudflare 감지 시 전용 표시 창

StreamInfo 후보
 ├─ direct ── urllib downloader
 └─ HLS/DASH ── FFmpeg downloader

저장 결과
 └─ 선택 코덱 검사 및 필요 시 FFmpeg 변환
```

일반 yt-dlp 백엔드는 형식 분석과 다운로드를 함께 수행하므로 `StreamInfo`와
Downloader 경로를 거치지 않습니다. 이 차이는 전문 플랫폼 코드를 범용 Extractor와
섞지 않기 위한 의도적인 경계입니다.

## 패키지 구조

```text
src/streamgrab/
├─ __main__.py          런타임 활성화와 CLI 진입
├─ cli.py               인자 처리와 상위 작업 흐름
├─ gui.py               Tkinter 화면과 worker 수명 주기
├─ gui_support.py       명령 구성, 진행률 파싱, 설정, 프로세스 종료
├─ config.py            명시적 TOML 설정 로딩과 검증
├─ models.py            StreamType, StreamInfo
├─ network.py           크기 제한 HTML/JSON 요청과 URL 검증
├─ filenames.py         안전한 파일명과 비덮어쓰기 경로
├─ transcode.py         ffprobe, 영상·오디오 변환과 진행률
├─ ytdlp_runtime.py     배포 앱 외부 yt-dlp 업데이트·활성화
├─ extractors/
│  ├─ pipeline.py       정적 단계 조정, 중복 제거와 정렬
│  ├─ generic.py        HTML·스크립트·iframe 후보 발견
│  ├─ mingky.py         Mingky 공개 API Site Extractor
│  └─ browser.py        Chromium CDP 네트워크 분석
├─ backends/
│  ├─ youtube.py        YouTube yt-dlp adapter
│  ├─ generic_ytdlp.py  일반 보호·임베드 페이지 fallback
│  └─ ytdlp_common.py   형식, 출력, 진행률, 로그 공통 정책
└─ downloaders/
   ├─ service.py        StreamType별 구현 선택
   ├─ direct.py         MP4/WebM HTTP 다운로드
   └─ hls.py            HLS/DASH FFmpeg와 HLS 호환 경로
```

## 공통 모델

Extractor와 Downloader 사이의 계약은 다음 값으로 제한됩니다.

```python
StreamInfo(
    url="https://cdn.example/video.m3u8",
    title="Video title",
    stream_type=StreamType.HLS,
    referer="https://example.com/watch/1",
    user_agent="...",
)
```

`referer`와 `user_agent`는 브라우저에서 성공한 요청 조건을 실제 다운로드에
전달합니다. 현재 모델에는 해상도, 비트레이트, 콘텐츠 그룹 또는 발견 근거가
없습니다.

## 정적 분석 경계

`ExtractionPipeline.extract_static`은 다음 제한을 둡니다.

- 직접 `.mp4`, `.webm`, `.m3u8`, `.mpd` URL은 페이지 요청 없이 반환
- HTML 응답 최대 10 MiB, JSON 응답 최대 2 MiB
- iframe 깊이 최대 2, 전체 정적 페이지 최대 8
- 발견 URL은 HTTP/HTTPS와 hostname을 요구
- URL에 사용자 이름이나 비밀번호가 있으면 거부
- 같은 완전한 URL은 처음 발견한 후보만 유지
- HLS, DASH, direct 순서로 후보 정렬

Mingky Site Extractor는 Generic 단계에서 후보를 찾지 못했고 입력 URL이 지원되는
`mingky숫자.com/movie/{id}`일 때만 실행합니다.

## 브라우저 분석

`BrowserNetworkExtractor`는 설치된 Edge, Chrome 또는 Chromium을 찾고 임의의 로컬
디버깅 포트에서 CDP에 연결합니다. OOPIF를 포함한 page/iframe target에 Network
도메인을 활성화하고 URL 확장자, 응답 MIME, Media resource type으로 HLS, DASH,
direct 후보를 판별합니다. 알려진 플레이어 버튼과 `<video>`의 재생도 시도합니다.

프로필은 Windows에서 `%LOCALAPPDATA%\StreamGrab\browser-profile`, 그 외 환경에서
`~/.cache/streamgrab/browser-profile`을 사용합니다. 일반 사용자 프로필을 열지
않습니다. 분석 후 브라우저 websocket의 `Browser.close`를 호출하고 launcher
프로세스도 정리합니다. Edge가 실제 브라우저로 hand-off하면서 최초 launcher가
종료되는 것은 실패로 간주하지 않고 디버깅 포트 제한 시간까지 기다립니다.

## 저장과 변환

- direct: 1 MiB 단위로 `.part`에 기록하고 완료 뒤 원자적으로 최종 이름으로 이동
- HLS/DASH: FFmpeg에 Referer와 User-Agent를 전달해 MP4 stream copy
- HLS 비표준 조각: FFmpeg 오류 문구를 확인해 허용 확장자 옵션으로 한 번 재시도
- HTTP/2 HLS: FFmpeg가 403일 때 curl-cffi로 단순 TS 조각을 받아 FFmpeg remux
- 변환: ffprobe로 첫 영상·오디오 스트림을 확인하고 필요한 트랙만 변환
- H.265 MP4는 `hvc1`, 영상 출력은 `yuv420p`, 오디오는 최대 stereo를 기본으로 함

HTTP/2 HLS 호환 경로는 master playlist, 암호화, fMP4 map, byte-range를 지원하지
않으며 추측해서 처리하지 않습니다.

## 배포와 업데이트

`build_windows.bat`는 Windows Python 환경에서 의존성을 갱신하고 PyInstaller
`--onefile --windowed` 빌드를 생성합니다. yt-dlp는 EXE 안의 버전을 폴백으로
유지하면서 별도 폴더의 더 최신 버전만 활성화합니다. 업데이트는 wheel SHA-256,
경로 안전성, 새 프로세스 import self-test를 통과해야 합니다.

## 보안과 수명 주기

- 로그인, CAPTCHA, DRM을 자동으로 우회하지 않음
- URL query를 yt-dlp 진단 로그에서 제거
- playlist와 기존 파일 덮어쓰기 비활성화
- GUI 취소 시 Windows `taskkill /T`로 worker와 자식 FFmpeg 종료
- 변환 중단 시 `.converting.*` 임시 파일 정리
- 브라우저·네트워크·외부 프로세스에는 제한 시간을 적용
