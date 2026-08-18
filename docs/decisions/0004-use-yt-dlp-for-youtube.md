# ADR 0004: YouTube 지원에 yt-dlp 어댑터 사용

- 상태: 승인
- 날짜: 2026-08-18

## 배경

YouTube는 실제 미디어 URL을 정적 HTML에 노출하지 않으며 서명, JavaScript
challenge, PO token 정책과 영상·음성 분리 형식이 계속 변한다. 이를 StreamGrab의
사이트별 정규식으로 복제하면 안정성과 유지보수성이 낮다.

## 결정

- YouTube URL은 Generic Extractor보다 먼저 식별해 `yt-dlp` 백엔드로 전달한다.
- PyPI의 `yt-dlp[default]`를 런타임 의존성으로 사용한다.
- 형식 분석과 전송은 yt-dlp에 맡기고 출력 경로, 오류, 단일 진행률과 로그 보안은
  StreamGrab 어댑터가 담당한다.
- 기본 형식은 MP4 영상과 M4A 오디오의 최고 품질 조합을 우선한다.
- playlist는 의도하지 않은 대량 다운로드를 막기 위해 기본적으로 비활성화한다.
- 서명된 미디어 URL의 query는 DEBUG 로그에서도 제거한다.
- 안정판에서 재현된 Google Video 403 수정이 포함된 yt-dlp 개발판을 임시 최소
  버전으로 사용하며, 다음 안정판이 나오면 안정판 최소 버전으로 교체한다.

## 결과

YouTube 변경 대응을 전문 프로젝트에 위임할 수 있지만 yt-dlp 업데이트가 중요한
운영 의존성이 된다. 전체 JavaScript 형식 지원에는 Deno 2.3+ 또는 Node.js 22+
같은 외부 런타임이 필요할 수 있다. PO token, 로그인 cookie, 비공개·연령 제한
콘텐츠는 별도 설계 없이 우회하지 않는다.
