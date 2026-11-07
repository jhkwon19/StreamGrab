# ADR 0004: YouTube 지원에 yt-dlp adapter 사용

- 상태: 승인, 안정판 의존성으로 운영
- 날짜: 2026-08-18
- 최근 검토: 2026-11-07

## 배경

YouTube는 서명, JavaScript challenge, PO token과 영상·음성 분리 정책이 계속
변한다. 이를 StreamGrab 정규식과 Site Extractor로 복제하면 안정성과 유지보수성이
낮다.

## 결정

- YouTube URL은 Generic Extractor보다 먼저 식별해 yt-dlp backend로 전달한다.
- 형식 분석과 전송은 yt-dlp에 맡기고 출력 경로, 오류, 진행률, 코덱 선호와 로그
  보안은 StreamGrab adapter가 담당한다.
- 기본 선택은 요청한 영상 코덱을 우선하고 MP4 영상과 M4A 오디오의 최고 품질
  조합으로 fallback한다.
- playlist 자동 다운로드와 기존 파일 덮어쓰기를 비활성화한다.
- 서명된 미디어 URL query는 DEBUG 로그에서도 제거한다.
- 배포 EXE는 내장 yt-dlp를 폴백으로 두고, 검증된 최신 정식 버전을 외부 폴더에서
  활성화할 수 있게 한다.

## 결과

YouTube 변경 대응을 전문 프로젝트에 위임하는 대신 yt-dlp 업데이트가 중요한 운영
의존성이 된다. 현재 패키지 최소 버전은 `2026.10.26`이며 Windows 배포 앱은 하루
한 번 최신 정식 버전을 확인한다. 전체 JavaScript challenge 지원에는 Deno 2.3+
또는 Node.js 22+가 필요할 수 있다. 로그인, 연령 제한, 비공개 영상과 PO token은
별도 승인·쿠키 설계 없이 우회하지 않는다.
