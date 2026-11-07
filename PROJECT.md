# StreamGrab 제품 사양

이 문서는 계획 초안이 아니라 현재 구현의 범위와 유지해야 할 제품 계약을
정리합니다. 세부 모듈 관계는 [아키텍처 문서](docs/architecture.md), 남은 작업은
[TODO](TODO.md)를 참조합니다.

## 목적

StreamGrab은 사용자가 정상적으로 접근할 수 있는 웹 영상의 실제 미디어 요청을
찾아 로컬 파일로 저장하고, 재생 장치에 맞는 코덱으로 정리하는 도구입니다. 특정
사이트의 HTML에만 의존하지 않도록 가벼운 범용 분석에서 전문 백엔드와 실제
브라우저 분석으로 단계적으로 확장합니다.

## 현재 제품 형태

- Python 3.11 이상의 `src` 레이아웃 패키지
- `argparse` 기반 `streamgrab` CLI
- Tkinter 기반 Windows 데스크톱 앱
- PyInstaller 단일 EXE 배포
- FFmpeg/ffprobe 외부 도구 연동
- yt-dlp, curl-cffi, websockets 런타임 의존성

## 지원 기능

| 영역 | 현재 동작 |
|---|---|
| 직접 미디어 | MP4·WebM URL 저장, Content-Length 기반 진행률 |
| HLS | FFmpeg stream copy, 비표준 조각 확장자 재시도, 제한적 HTTP/2 호환 경로 |
| DASH | FFmpeg 입력과 MP4 stream copy |
| 정적 페이지 | video/source/data-source, preload, 스크립트 미디어 URL, iframe |
| 사이트 규칙 | Mingky `/movie/{id}` API와 임베드 플레이어 |
| 플랫폼 | YouTube와 일반 페이지의 yt-dlp 백엔드 |
| 동적 페이지 | Edge/Chrome CDP 네트워크 요청에서 URL·MIME 감지 |
| 보호 페이지 | curl-cffi impersonation, 필요 시 Cloudflare 사용자 확인 창 |
| 변환 | H.264/H.265 영상, AAC/MP3/AC-3 오디오, 원본 보존 변환 |
| Windows UX | 진행률, 취소, 폴더 열기, FFmpeg 설치, 설정 기억, yt-dlp 업데이트 |

## 핵심 제품 계약

### 분석과 저장의 분리

Extractor는 `StreamInfo`만 반환하고 파일을 저장하지 않습니다. Downloader는
`StreamInfo`를 받아 저장하며 페이지 HTML이나 사이트 API를 해석하지 않습니다.
yt-dlp처럼 분석과 전송을 함께 맡는 전문 도구는 `backends`에 격리합니다.

### 안전한 기본값

- URL은 HTTP/HTTPS만 허용하고 사용자 정보가 포함된 URL은 거부합니다.
- 정적 HTML은 10 MiB, 사이트 JSON은 2 MiB로 제한합니다.
- iframe 정적 탐색은 깊이 2, 최대 8페이지로 제한합니다.
- 페이지 스크립트는 문자열만 검사하고 실행하지 않습니다.
- playlist 자동 다운로드와 기존 파일 덮어쓰기를 기본 금지합니다.
- 서명된 미디어 URL의 query를 진단 로그에 남기지 않습니다.
- 외부 명령은 셸 문자열이 아닌 인자 배열로 실행합니다.

### 출력 정책

- 일반 페이지의 기본 선택은 정렬된 첫 번째 후보입니다.
- 후보 우선순위는 HLS, DASH, direct 순서입니다.
- 파일명은 제목에서 운영체제 금지 문자를 정리하고 최대 길이를 제한합니다.
- 같은 이름이 있으면 번호를 붙여 보존합니다.
- 다운로드 후 기본 H.264/AAC 정책에 맞지 않으면 FFmpeg로 변환합니다.
- `original`을 선택하면 다운로드 결과를 재인코딩하지 않습니다.

### 브라우저 정책

브라우저 분석은 정적 분석과 yt-dlp가 모두 실패했을 때만 실행합니다. StreamGrab
전용 프로필을 사용해 사용자의 일반 Edge/Chrome 프로필과 분리하며, 작업이 끝나면
CDP `Browser.close`와 프로세스 정리를 수행합니다. Cloudflare 확인은 사용자가 직접
완료해야 하고 로그인·CAPTCHA·DRM은 자동으로 우회하지 않습니다.

## 비목표

- DRM 또는 암호화 보호 해제
- 유료·비공개 콘텐츠의 인증 우회
- 계정 자격 증명 수집이나 기존 브라우저 쿠키 무단 사용
- 사이트의 rate limit 또는 접근 제어 무력화
- 사용자가 요청하지 않은 playlist·다중 영상 일괄 저장

## 현재 제한

- 일반 `StreamInfo`는 해상도·비트레이트·콘텐츠 그룹을 표현하지 않습니다.
- 정적 HLS 마스터 variant를 자체적으로 펼쳐 품질별로 표시하지 않습니다.
- HTTP/2 HLS 호환 경로는 비암호화 MPEG-TS 미디어 목록만 처리합니다.
- 브라우저 fallback은 설치된 Chromium 계열 브라우저와 사이트 동작에 의존합니다.
- 명시적인 쿠키 파일, 프록시, 기존 브라우저 프로필 가져오기는 없습니다.
- TOML의 `default_quality`와 `retry.count`는 파싱되지만 현재 실행 흐름에 적용되지
  않습니다.

## 변경 원칙

새 사이트 문제가 발생하면 먼저 범용 구조인지 확인합니다. 여러 사이트에서 재사용
가능하면 Generic Extractor를 확장하고, 특정 도메인의 공개 API 규칙일 때만 Site
Extractor를 추가합니다. 변동이 크고 검증된 전문 구현이 있으면 yt-dlp 백엔드에
위임합니다. 모든 변경은 실제 네트워크에 의존하지 않는 fixture·mock 회귀 테스트를
우선 추가하고 사용자 영향은 `CHANGELOG.md`에 기록합니다.
