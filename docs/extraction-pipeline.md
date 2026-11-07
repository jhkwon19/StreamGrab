# 스트림 분석 파이프라인

새 사이트를 지원할 때 도메인 이름보다 페이지 구조를 먼저 분류하기 위한 현재
구현 규칙입니다.

## 실제 우선순위

```text
1. YouTube URL인가?
   └─ 예: YouTube yt-dlp backend

2. 직접 미디어 확장자인가?
   └─ .mp4 / .webm / .m3u8 / .mpd → StreamInfo

3. 정적 페이지와 iframe 분석
   ├─ video/source의 src, data-source
   ├─ link rel=preload as=fetch|video
   ├─ HTML·script 안의 m3u8/mpd/mp4/webm 문자열
   └─ iframe/data-src, 깊이 2·전체 8페이지 제한

4. 지원되는 Site Extractor
   └─ 현재: Mingky movie API → embed page → Generic Extractor

5. yt-dlp Generic backend
   ├─ curl-cffi impersonation
   └─ yt-dlp가 지원하는 iframe·플랫폼 extractor

6. Edge/Chrome CDP 네트워크 분석
   ├─ 숨김 브라우저
   └─ Cloudflare 확인 감지 시 표시 브라우저
```

각 단계가 사용할 수 있는 결과를 반환하면 뒤 단계는 실행하지 않습니다. 단, 정적
단계 안에서는 방문한 페이지들의 후보를 모두 모은 뒤 중복 제거와 정렬을 합니다.

## 구조별 지원 현황

| 구조 | 처리 방식 | 상태 |
|---|---|---|
| 직접 MP4/WebM | URL path 확장자 | 지원 |
| 직접 HLS/DASH | URL path 확장자 | 지원 |
| `video`/`source` | 표준 HTML 파서 | 지원 |
| `data-source` | 표준 HTML 파서 | 지원 |
| preload 미디어 | `link`의 rel/as 검사 | 지원 |
| script/JSON 문자열 | 실행 없이 미디어 확장자 URL 정규식 | 지원 |
| iframe | 제한된 BFS 정적 요청 | 지원 |
| Mingky movie API | 도메인·path가 일치할 때 Site Extractor | 지원 |
| YouTube | yt-dlp 전문 backend | 지원 |
| yt-dlp가 아는 embed | Generic backend가 위임 | 지원 |
| SPA/blob/동적 API | 브라우저 Network 이벤트 URL·MIME | 지원 |
| cross-origin iframe | CDP auto-attach한 OOPIF Network 이벤트 | 지원 |
| Cloudflare 확인 | 사용자가 전용 창에서 완료 | 지원 |
| HLS master 품질 목록 | 자체 variant 분석 | 미지원 |
| 로그인 쿠키 입력 | 명시적 cookie API | 미지원 |
| DRM | 해제 또는 우회 | 범위 밖 |

## Generic Extractor 규칙

HTML은 Python `HTMLParser`로 읽고 JavaScript를 실행하지 않습니다. 상대 주소는
응답의 최종 URL을 기준으로 절대 주소로 바꿉니다. 다음 조건을 만족하지 않는
후보는 버립니다.

- scheme이 `http` 또는 `https`
- hostname 존재
- URL 사용자 정보 없음
- path가 `.m3u8`, `.mpd`, `.mp4`, `.webm` 중 하나로 끝남

스크립트 문자열 분석도 확장자가 명시된 URL만 수집합니다. MIME만으로 알 수 있는
확장자 없는 미디어 요청은 브라우저 단계가 담당합니다.

## Site Extractor 기준

Site Extractor는 표준 HTML로 표현되지 않는 안정된 공개 API나 도메인 규칙이 있을
때만 추가합니다. 현재 `MingkyExtractor`는 다음 순서로 동작합니다.

1. `mingky숫자.com/movie/{id}` 형식 확인
2. 같은 origin의 `/api/movies/{id}` JSON 요청
3. `embed_url` 플레이어 HTML 요청
4. Generic Extractor로 미디어 후보 추출
5. API 제목을 각 `StreamInfo`에 적용

사이트별 코드가 Downloader나 CLI의 형식 분기를 직접 추가해서는 안 됩니다. Site
Extractor가 더 늘어나 단순한 명시 분기가 불편해질 때 Protocol과 Registry를
도입합니다.

## yt-dlp backend 경계

YouTube는 처음부터 전용 backend로 분기합니다. 일반 URL은 정적 파이프라인이
`NetworkError` 또는 `StreamNotFoundError`로 끝났을 때만 yt-dlp Generic backend로
넘깁니다. 이 backend는 yt-dlp native format ID를 유지하며 분석과 전송을 함께
담당합니다.

yt-dlp에서도 실패하면 마지막으로 브라우저 분석을 시작합니다. 따라서 yt-dlp가
정상 형식을 반환한 페이지에서 불필요하게 실제 브라우저가 열리지 않습니다.

## 브라우저 후보 판별

CDP의 `Network.requestWillBeSent`와 `Network.responseReceived`에서 다음 정보를
사용합니다.

- URL path 확장자
- HLS MIME (`mpegurl`)
- DASH MIME (`dash+xml`)
- `video/*` MIME
- Media resource의 octet-stream 응답

후보 점수는 HLS 300, DASH 250, direct 100을 기준으로 하며 URL path에 master,
index, playlist, manifest가 있으면 가점을 줍니다. 요청의 Referer와 브라우저
User-Agent도 `StreamInfo`에 보존합니다.

Cloudflare의 `403`과 `cf-mitigated: challenge` 또는 challenge 제목이 확인되고
후보가 없으면 숨김 브라우저를 종료한 뒤 같은 전용 프로필로 표시 브라우저를
엽니다. 사용자가 확인을 완료하면 같은 네트워크 관찰을 계속합니다.

## 후보 정규화와 선택

현재 정규화는 의도적으로 단순합니다.

- 완전한 URL 문자열이 같은 후보만 중복으로 간주
- signed query는 제거하지 않음
- 제목, 형식, Referer, User-Agent만 보존
- HLS → DASH → direct 순서로 정렬
- 일반 CLI의 기본 선택은 첫 후보, `-f N`은 1부터 시작하는 번호

서로 다른 영상과 동일 영상의 품질 variant를 판단할 근거는 아직 모델에 없습니다.
URL이 다르다는 이유만으로 콘텐츠를 합치거나 나누지 않습니다.

## 확장 절차

1. 실패한 구조를 민감정보 없이 최소 fixture로 만든다.
2. 기존 Generic Extractor로 표현 가능한지 확인한다.
3. 여러 사이트에 재사용되면 Generic 규칙을 확장한다.
4. 특정 공개 API에만 의미가 있으면 Site Extractor로 분리한다.
5. 유지보수되는 전문 extractor가 있으면 backend 위임을 우선한다.
6. 실제 JavaScript와 네트워크가 필수일 때만 브라우저 단계를 확장한다.
7. 성공, 후보 없음, 중복, 네트워크 오류, 수명 주기 회귀 테스트를 추가한다.
8. 사용자 영향은 CHANGELOG, 설계 이유는 ADR에 기록한다.

## 실패와 안전성

- 후보 없음과 네트워크 실패는 별도 예외로 유지합니다.
- iframe 요청 수와 응답 크기를 제한합니다.
- HTML의 JavaScript를 Python에서 평가하지 않습니다.
- Cookie, Authorization, signed query를 로그에 노출하지 않습니다.
- 사용자 확인 창은 보안 검증을 자동으로 풀지 않습니다.
- 인증 우회, CAPTCHA 자동화, DRM 해제는 구현하지 않습니다.
