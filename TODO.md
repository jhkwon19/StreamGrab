# StreamGrab 작업 목록

현재 코드에 남아 있는 작업만 기록합니다. 완료된 구현의 설명은
`CHANGELOG.md`와 `docs/development.md`에서 확인합니다.

## 우선순위 높음

- [ ] CI에서 Python 3.11 이상 테스트 자동 실행
- [ ] HLS 마스터 재생목록의 variant 해상도·대역폭 분석과 품질 선택
- [ ] 여러 영상과 같은 영상의 여러 품질을 구분하는 후보 모델
- [ ] 일반 후보 목록에 해상도·코덱·발견 출처 표시
- [ ] 네트워크 재시도 정책을 실제 `retry.count` 설정과 연결
- [ ] 사용하지 않는 `default_quality` 설정을 구현하거나 제거

## 다운로드 안정성

- [x] 직접 미디어 바이트 진행률
- [x] HLS 비표준 세그먼트 확장자 재시도
- [x] 취소 시 GUI 작업 프로세스 트리와 변환 임시 파일 정리
- [ ] 모든 다운로드 경로의 `.part` 정리 정책 통일
- [ ] Content-Length가 없는 직접 미디어의 전송량·속도 표시
- [ ] HTTP 응답 MIME 및 최종 파일 유효성 검증 강화
- [ ] HLS 암호화와 DRM을 구분하는 오류 메시지

## Extractor와 브라우저

- [x] 정적 HTML·스크립트·preload 분석
- [x] 깊이 제한 iframe 탐색
- [x] Mingky 공개 API Site Extractor
- [x] Edge/Chrome CDP 네트워크 fallback
- [x] Cloudflare 사용자 확인과 전용 프로필 재사용
- [x] Edge 런처 hand-off와 고립 프로세스 회귀 수정
- [ ] Site Extractor가 더 늘어날 때 공통 Protocol과 Registry 도입
- [ ] 익명화한 HTML·manifest·CDP 이벤트 fixture 확대
- [ ] 명시적인 쿠키 파일 또는 사용자 승인 기반 브라우저 쿠키 입력 설계
- [ ] 브라우저 분석 타임아웃과 단계별 진단 메시지 개선

## 플랫폼과 유지보수

- [x] YouTube 및 일반 페이지 yt-dlp 백엔드
- [x] 배포 앱의 검증된 yt-dlp 자동 업데이트와 폴백
- [x] PATH/NVM Node.js 런타임 탐색
- [ ] Deno/Node 런타임 상태 진단 화면
- [ ] 여러 embedded video를 반환하는 yt-dlp 결과의 선택 정책
- [ ] 로그인·연령 제한 콘텐츠용 명시적 cookie 옵션 검토
- [ ] playlist 다운로드는 별도 명령과 확인 절차로 설계

## 사용자 경험

- [x] 다운로드·코덱 변환 Windows GUI
- [x] 영상·오디오 코덱 선택과 마지막 설정 기억
- [x] FFmpeg WinGet 설치 후 작업 재시도
- [x] 직접 다운로드와 변환 진행률 표시
- [ ] 실패 보고서 내보내기 또는 민감정보를 제거한 진단 로그
- [ ] 다운로드 큐와 완료 기록
- [ ] 접근성 및 고해상도 DPI 점검

## 장기 검토

- [ ] Web UI
- [ ] Docker/서버 모드의 필요성 검토
- [ ] 공개 Python API를 제공할 경우 안정된 인터페이스 정의
