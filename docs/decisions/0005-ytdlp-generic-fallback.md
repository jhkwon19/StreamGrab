# ADR 0005: 보호·임베드 페이지에 yt-dlp Generic fallback 사용

- 상태: 승인
- 날짜: 2026-08-18

## 배경

일반 웹페이지 중에는 Cloudflare 브라우저 검증으로 기본 HTTP 클라이언트를 막거나,
실제 영상 대신 외부 플레이어 iframe만 넣는 경우가 있다. 모든 페이지를 브라우저로
실행하면 의존성과 공격 표면이 커지고 빠른 정적 분석의 장점을 잃는다.

## 결정

- 표준 HTML 정적 분석을 첫 번째 경로로 유지한다.
- 네트워크 차단 또는 미디어 미발견 때 yt-dlp Generic Extractor를 fallback으로 쓴다.
- Cloudflare가 요구할 경우 공식 curl-cffi impersonation 기능을 사용한다.
- impersonation은 Generic 추출에만 제한하며 CAPTCHA, 로그인, DRM은 우회하지 않는다.
- iframe에서 발견된 플랫폼은 yt-dlp의 해당 전문 extractor에 위임한다.
- playlist 자동 다운로드와 기존 파일 덮어쓰기는 계속 금지한다.

## 결과

사이트 도메인을 하드코딩하지 않고 Cloudflare → iframe → Bunny CDN 같은 구조를
처리할 수 있다. 반면 curl-cffi가 추가 의존성이 되며 사이트 정책이 바뀌거나 실제
사용자 검증이 요구되면 명시적인 cookie 또는 브라우저 설계가 별도로 필요하다.
