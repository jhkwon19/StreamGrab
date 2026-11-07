# ADR 0005: 보호·임베드 페이지에 yt-dlp Generic fallback 사용

- 상태: 승인
- 날짜: 2026-08-18
- 최근 검토: 2026-11-07

## 배경

일반 웹페이지 중에는 기본 HTTP 클라이언트를 차단하거나 실제 영상 대신 외부
플레이어 iframe만 제공하는 경우가 있다. StreamGrab이 모든 플랫폼의 서명과
플레이어 규칙을 직접 유지할 필요는 없다.

## 결정

- 직접 URL과 정적 Generic HTML 분석을 첫 번째 경로로 유지한다.
- 네트워크 차단 또는 미디어 미발견 때 yt-dlp Generic backend를 한 번 실행한다.
- yt-dlp의 `generic:impersonate`와 curl-cffi를 Generic 추출에만 사용한다.
- iframe의 알려진 플랫폼은 yt-dlp 전문 extractor에 위임한다.
- playlist 자동 다운로드, 기존 파일 덮어쓰기와 signed query 로그 출력을 막는다.
- yt-dlp도 처리하지 못한 페이지는 ADR 0006의 브라우저 네트워크 fallback으로
  넘긴다.

## 결과

도메인 하드코딩 없이 많은 보호·임베드 구조를 처리할 수 있다. 사이트가 실제
사용자 확인을 요구하면 impersonation만으로 해결하지 않고 전용 브라우저 흐름을
사용한다. CAPTCHA, 로그인, DRM 또는 접근 권한 우회는 이 backend의 책임이 아니다.
