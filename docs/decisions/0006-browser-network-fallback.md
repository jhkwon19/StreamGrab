# ADR 0006: 최종 단계에서 Chromium 네트워크 요청 관찰

- 상태: 승인
- 날짜: 2026-11-07

## 배경

정적 HTML과 yt-dlp가 모두 처리하지 못해도 사용자의 브라우저에서는 JavaScript가
실행된 뒤 영상 요청이 발생하는 페이지가 있다. blob URL과 확장자 없는 API 응답은
원래 네트워크 요청을 보지 않으면 실제 미디어 URL을 알 수 없다.

## 결정

- 설치된 Edge, Chrome 또는 Chromium을 CDP remote debugging으로 실행한다.
- StreamGrab 전용 프로필을 사용하고 일반 사용자 브라우저 프로필은 열지 않는다.
- headless 분석을 먼저 수행하고 Cloudflare challenge가 명시적으로 감지된 경우에만
  표시 창에서 사용자가 확인하도록 한다.
- page와 cross-origin iframe target의 Network 이벤트를 관찰한다.
- URL 확장자, MIME과 resource type으로 HLS, DASH, direct 후보를 만든다.
- Referer와 브라우저 User-Agent를 후보에 보존해 다운로드 요청에 전달한다.
- 작업 후 CDP `Browser.close`를 호출하고 launcher 수명 주기도 정리한다.
- Edge가 launcher를 실제 프로세스로 교체할 수 있으므로 최초 프로세스 종료만으로
  실패를 판정하지 않고 디버깅 포트 제한 시간까지 기다린다.

## 결과

사이트별 DOM selector를 계속 추가하지 않고 동적 플레이어를 처리할 수 있다. 대신
설치된 브라우저, 사이트의 사용자 확인과 네트워크 타이밍에 의존한다. 브라우저는
분석 전용이며 CAPTCHA를 자동 클릭하거나 로그인·DRM을 우회하지 않는다. 전용
프로필을 유지해 Cloudflare 상태를 재사용하지만 사용자가 해당 폴더를 삭제하면
초기화된다.
