# ADR 0002: HLS와 DASH 저장에 FFmpeg 사용

- 상태: 승인, 0.3 구현 반영
- 날짜: 2026-08-18
- 최근 검토: 2026-11-07

## 배경

HLS와 DASH는 manifest, 세그먼트, 영상·음성 트랙, 컨테이너 처리까지 직접 구현할
경우 범위가 크다. StreamGrab은 프로토콜 구현보다 스트림 발견과 안전한 사용자
흐름에 집중한다.

## 결정

- HLS와 DASH 입력 및 MP4 stream copy는 FFmpeg에 맡긴다.
- 외부 명령은 셸 없이 인자 배열로 실행한다.
- Extractor가 수집한 Referer와 User-Agent를 FFmpeg 입력에 전달한다.
- 기본 저장은 `-map 0 -c copy`로 재인코딩을 피한다.
- 기존 출력 파일은 덮어쓰지 않는다.
- FFmpeg가 비표준 HLS 조각 확장자를 거부하면 관련 오류일 때만 확장자 호환 옵션으로
  한 번 재시도한다.
- FFmpeg HTTP/1.1 요청만 403으로 거부되는 경우 단순 비암호화 MPEG-TS HLS에 한해
  curl-cffi로 조각을 전송하고 FFmpeg로 로컬 remux한다.

## 결과

검증된 미디어 도구로 HLS master와 DASH 트랙 처리를 위임할 수 있지만 FFmpeg가
필수 외부 의존성이 된다. Windows GUI는 FFmpeg가 없을 때 사용자 확인 후 WinGet
설치를 제공한다.

HTTP/2 호환 경로는 master playlist, 암호화, fMP4 초기화 조각과 byte-range를
지원하지 않는다. 이 경우 범용 FFmpeg 경로가 실패하면 명확한 오류를 반환하며 DRM
해제나 추측성 복호화는 하지 않는다.
