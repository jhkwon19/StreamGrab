# 개발 기록

이 문서는 구현 결과와 검증 내용을 시간순으로 기록한다. 설계의 이유와 장기적인
영향은 `docs/decisions/`의 ADR에 별도로 남긴다.

## 2026-08-18 — Phase 1 프로젝트 기반

### 목표

- 설치 가능한 Python 패키지 구성
- `streamgrab --help` 실행
- 설정, 로깅, 테스트의 최소 기반 마련
- 이후 변경을 추적할 문서 구조 마련

### 구현

- `src` 레이아웃과 `pyproject.toml`을 추가했다.
- 표준 라이브러리 `argparse`로 CLI 진입점을 추가했다.
- 표준 라이브러리 `tomllib`으로 선택적 TOML 설정 파일을 읽는다.
- 설정 값의 형식과 범위를 검증하고 예상 오류를 `ConfigError`로 표현한다.
- 중복 핸들러를 만들지 않는 애플리케이션 로깅을 추가했다.
- CLI, 설정, 로깅의 단위 테스트를 추가했다.

### 의도적으로 제외한 범위

- URL 분석과 다운로드
- 자동으로 사용자 홈 디렉터리의 설정 파일 탐색
- FFmpeg 실행과 버전 검사
- 외부 런타임 라이브러리

이 항목들은 실제 사용 흐름과 함께 다음 단계부터 하나씩 구현한다.

### 검증

- Python 3.12.3 가상 환경에서 editable 설치를 확인했다.
- 전체 자동화 테스트 8개가 통과했다.
- 설치된 `streamgrab --help`와 `streamgrab --version` 실행을 확인했다.
- 개발 환경에서 FFmpeg 6.1.1이 감지되었지만 아직 프로그램에서 사용하지 않는다.

## 2026-08-18 — 첫 실제 페이지 분석과 HLS 저장

### 대상 구조

사용자가 제공한 공개 페이지의 정적 HTML을 읽기 전용으로 확인했다. 해당
플레이어는 `<video data-source>`에 HLS 마스터 재생목록을 지정하고 `hls.js`로
재생한다. 브라우저 JavaScript 실행이나 복사 방지 우회 없이 Generic Extractor로
처리할 수 있는 구조였다.

실제 미디어 파일은 내려받지 않았으며, 콘텐츠 권리와 서비스 이용 조건은
사용자가 확인해야 한다.

### 구현

- Extractor와 Downloader 사이의 공통 계약인 `StreamInfo`와 `StreamType`을 추가했다.
- 제한된 크기의 정적 HTML을 가져오는 기본 HTTP 클라이언트를 추가했다.
- `video`의 `src`와 `data-source`, `source`의 `src`를 분석한다.
- MP4, WebM, HLS, DASH 주소를 구분하고 상대 주소를 절대 주소로 변환한다.
- 직접 미디어 Downloader와 FFmpeg 기반 HLS Downloader를 추가했다.
- Referer와 User-Agent를 HLS 요청에 전달하되 셸은 사용하지 않는다.
- 파일명 정제와 기존 파일 자동 번호 부여 정책을 추가했다.
- `--list-formats`, `--format`, `--output` CLI 옵션을 추가했다.

### 검증

- 대상 페이지에서 HLS 스트림 1개가 탐지되는 것을 확인했다.
- FFmpeg로 만든 1초짜리 로컬 HLS fixture를 HTTP로 제공했다.
- StreamGrab으로 이를 MP4에 저장하고 `ffprobe`에서 1.044898초 미디어로 확인했다.
- 전체 자동화 테스트 15개가 통과했다.

### 다음 작업

HLS 마스터 재생목록을 직접 분석해 해상도와 대역폭별 품질을 표시하고 선택할 수
있어야 한다. 진행률과 중단 시 정리, HTTP 재시도도 함께 보강한다.

## 2026-08-18 — HTTP/2 전용 CDN 403 대응

### 증상과 원인

대상 페이지 분석은 성공했지만 FFmpeg가 HLS 재생목록 요청에서 HTTP 403을
반환했다. 동일 URL과 헤더를 비교한 결과 HTTP/2 요청은 200, HTTP/1.1 요청은
403이었다. FFmpeg 6.1 내장 HTTP 클라이언트가 HTTP/1.1을 사용하므로 Referer나
User-Agent만 바꿔서는 해결되지 않았다.

### 구현

- FFmpeg 입력 단계가 403인 경우에만 HTTP/2 호환 경로로 전환한다.
- curl로 재생목록과 TS 세그먼트를 순서대로 전송한다.
- 다운로드한 TS를 FFmpeg stream copy로 MP4에 병합한다.
- 암호화, 마스터 목록, fMP4 및 byte-range는 현재 호환 경로에서 거부한다.
- 외부 명령은 모두 셸 없이 인자 배열로 실행한다.

### 검증

- CDN 재생목록에서 HTTP/2 200과 HTTP/1.1 403을 재현했다.
- 로컬 HLS fixture에 HTTP/2 호환 경로를 직접 적용해 MP4 생성을 확인했다.
- 생성 파일은 `ffprobe`에서 1.044898초 MP4로 확인되었다.
- 전체 자동화 테스트 19개가 통과했다.

## 2026-08-18 — HLS 전체 진행률 표시

HTTP/2 호환 다운로드에서 curl이 세그먼트마다 별도의 100% 진행 막대를 출력하던
문제를 수정했다. curl의 개별 진행 출력을 숨기고, StreamGrab이 전체 세그먼트
개수를 기준으로 한 줄의 진행 막대를 0%부터 100%까지 갱신한다. 세그먼트는 연결
재사용과 화면 갱신 빈도의 균형을 위해 10개 단위로 요청한다.

## 2026-08-18 — 다양한 사이트 구조를 위한 분석 원칙

새 사이트마다 CLI나 Downloader에 예외 조건을 추가하지 않도록 단계별 Extractor
파이프라인을 문서화했다. 직접 URL, 표준 HTML, JSON, iframe, Site Extractor,
브라우저 분석 순으로 비용과 특수성이 증가하도록 구성한다.

한 페이지의 여러 영상과 한 영상의 여러 품질은 서로 다른 문제로 정의했다. 현재는
모든 URL 후보를 ID로 선택할 수 있지만 콘텐츠 그룹과 품질 관계는 표현하지 못한다.
HLS 마스터 분석과 함께 그룹 모델을 추가하고, 근거가 부족한 후보를 임의로 합치지
않는 정책을 적용한다.

두 번째 독립 Extractor가 실제로 필요해질 때 공통 Protocol과 Registry를 도입한다.
이는 확장 경계를 분명히 하면서 현재 코드에 사용되지 않는 추상화를 만들지 않기
위한 결정이다.

## 2026-08-18 — YouTube 전문 백엔드

### 배경

YouTube 페이지는 정적 HTML Generic Extractor로 처리할 수 없고 서명과 JavaScript
challenge가 자주 변경된다. 자체 추출기를 복제하지 않고 `yt-dlp[default]`를
전문 백엔드로 연결했다.

### 구현

- YouTube, youtu.be, youtube-nocookie URL을 안전하게 식별한다.
- `--list-formats`에서 native format ID, 해상도, 코덱과 예상 크기를 표시한다.
- 기본 최고 품질 또는 사용자가 지정한 `-f` 조합을 다운로드한다.
- 영상과 오디오가 분리된 경우 FFmpeg로 MP4에 병합한다.
- 두 전송의 알려진 전체 바이트를 합산해 하나의 진행률로 표시한다.
- playlist 자동 다운로드를 비활성화하고 기존 파일을 덮어쓰지 않는다.
- yt-dlp 진단 로그에서 서명 query를 제거한다.

### 검증

- 제공된 YouTube URL에서 메타데이터, 오디오 및 최대 1080p 형식을 확인했다.
- 실제 영상 파일은 다운로드하지 않았다.
- 당시 전체 자동화 테스트 27개가 통과했다. 이후 진행률 회귀 테스트를 추가해
  현재는 29개가 통과한다.

### 환경 제한

현재 개발 환경의 Node.js 20은 최신 yt-dlp가 요구하는 Node.js 22 이상에 미치지
않는다. 이 URL은 제한 모드에서도 형식 조회가 가능했지만 전체 JavaScript
challenge 지원을 위해 Deno 2.3+ 또는 Node.js 22+ 설치를 권장한다.

## 2026-08-18 — YouTube 403 및 NVM 런타임 탐색

YouTube 영상 정보 조회 후 실제 미디어 요청이 HTTP 403으로 실패하는 사례를
재현했다. yt-dlp 로그에서 Node.js 20.19.6이 지원되지 않아 JavaScript challenge를
처리하지 못한 것이 원인이었다.

기존 Node 기본 alias를 변경하지 않고 NVM에 Node.js 22.21.1을 추가했다.
StreamGrab은 활성 PATH뿐 아니라 사용자 NVM 설치 디렉터리에서 Node.js 22 이상의
가장 최신 버전을 찾아 yt-dlp에 명시적으로 전달한다. 문제 영상에서 `399+251`
1080p 조합의 형식 접근 검사를 통과했으며 실제 전체 영상은 내려받지 않았다.

### 추가 403 원인

Node.js 문제를 해결한 뒤에도 전체 전송에서 403이 발생했다. yt-dlp의 10 KiB
테스트와 직접 1바이트 Range 요청은 성공했지만, extractor가 지정한 기본 10 MiB
청크의 전체 전송은 실패했다. 청크를 1 MiB와 64 KiB로 낮춰도 약 7 MiB 부근에서
다시 실패했으므로 청크 크기는 근본 해결책이 아니었다.

공식 yt-dlp 오늘자 개발판 `2026.8.18.122307.dev0`으로 같은 URL을 다시 검사하자
클라이언트 선택이 변경되었고 다운로드가 정상 완료되었다. StreamGrab 명령으로
1080p 영상과 한국어 M4A 음성을 전부 받은 뒤 MP4 병합까지 검증했다. 따라서 해당
버전을 임시 최소 의존성으로 지정하고, 불필요한 `http_chunk_size` 설정은 제거했다.

실전 검증 중 yt-dlp의 fragment 진행 이벤트에서 누적 바이트가 일시적으로 작아져
전체 퍼센트가 뒤로 움직이는 현상도 발견했다. 마지막 표시값을 하한으로 유지해
진행률이 0%에서 100%까지 단조 증가하도록 수정하고, 여러 후처리 이벤트에서 병합
안내가 중복되지 않게 했다.

### 참고 저장소 검토

`jhkwon19/youtube-transcriber-api`의 `main` 브랜치도 검토했다. 이 저장소는
`youtube_transcript_api`를 이용한 자막 조회·번역 REST API이며 yt-dlp, FFmpeg,
format 선택 또는 영상 다운로드 구현은 포함하지 않는다. 따라서 영상 다운로드
코드는 가져오지 않았고, 향후 자막 저장 기능을 설계할 때 별도 참고 대상으로
남긴다.

## 2026-08-18 — Cloudflare 보호 페이지와 Bunny CDN fallback

`kr88.sogirl.so` 사례는 Python 기본 HTTP 요청과 브라우저 User-Agent를 넣은 curl
요청을 모두 HTTP 403으로 거부했다. 응답의 `cf-mitigated: challenge`로 보아 단순
헤더 차단이 아니라 Cloudflare 브라우저 검증이었다.

공식 yt-dlp Generic Extractor도 같은 원인을 진단했으며 curl-cffi impersonation과
`generic:impersonate` 사용을 안내했다. `yt-dlp[default,curl-cffi]`를 설치하고 공식
경로로 재분석하자 외부 iframe이 Bunny CDN 플레이어임을 식별하고 1280x720
HLS 형식 ID `4731`을 발견했다.

### 구현

- 기존 정적 Generic Extractor를 빠르고 단순한 첫 번째 경로로 유지한다.
- 페이지 요청이 실패하거나 정적 미디어를 발견하지 못하면 yt-dlp Generic
  fallback을 한 번 실행한다.
- impersonation은 모든 요청에 강제하지 않고 Generic 페이지 추출 단계에만 쓴다.
- fallback도 playlist 자동 다운로드, 덮어쓰기, signed query 로그 출력을 막는다.
- YouTube와 Generic fallback이 런타임 탐색, 출력 경로 및 단일 진행률 코드를
  공유하도록 공통 모듈로 분리했다.

### 검증

- 실제 StreamGrab `--list-formats`로 형식 ID `4731`, 1280x720, H.264/AAC를 확인했다.
- yt-dlp `--test`로 1,768개 HLS 조각 중 첫 조각 전송이 가능한지 확인했다.
- 전체 파일은 수백 MiB 이상으로 예상되어 자동 검증에서는 내려받지 않았다.
- 자동화 테스트 33개가 통과한다.
