# ADR 0003: 비용이 낮은 단계부터 실행하는 추출 파이프라인

- 상태: 승인, 0.3 구현 반영
- 날짜: 2026-08-18
- 최근 검토: 2026-11-07

## 배경

웹 영상은 직접 URL, HTML 태그, 스크립트 문자열, iframe, 사이트 API, 전문 플랫폼
extractor 또는 실제 브라우저 요청에 나타날 수 있다. 모든 사이트를 브라우저로
열거나 도메인 조건을 CLI에 계속 추가하면 느리고 유지하기 어렵다.

## 결정

- YouTube는 URL 분류 뒤 전문 yt-dlp backend로 직접 보낸다.
- 일반 URL은 direct 확장자, Generic HTML, 제한된 iframe 순서로 정적 분석한다.
- 도메인 고유 공개 API는 Site Extractor에 격리하고 Generic 결과가 없을 때 실행한다.
- 정적 분석이 실패하면 yt-dlp Generic backend를 사용한다.
- yt-dlp도 실패한 경우에만 Edge/Chrome CDP 네트워크 분석을 실행한다.
- Extractor 결과는 `StreamInfo`로 정규화하고 Downloader는 발견 단계를 알지 못한다.
- 현재 후보 정규화는 완전한 URL 중복 제거와 HLS/DASH/direct 정렬만 수행한다.
- Site Extractor 수가 늘어 명시적 분기가 불편해질 때 Protocol과 Registry를
  도입한다.

## 결과

표준 페이지는 빠르고 결정적인 정적 경로로 처리하고, 동적 브라우저의 비용과 공격
표면은 마지막 단계에 제한한다. 현재 Mingky Site Extractor는 pipeline에 명시적으로
연결되어 있다. 콘텐츠 그룹과 품질 variant는 아직 모델에 없으므로 URL만 보고
임의로 같은 영상으로 묶지 않는다.

정확한 현재 순서와 제한은 [스트림 분석 파이프라인](../extraction-pipeline.md)을
기준으로 한다.
