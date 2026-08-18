# 아키텍처

## 현재 범위

StreamGrab은 CLI를 진입점으로 하는 Python 애플리케이션이다. 현재는 정적 HTML
분석과 직접 미디어 및 HLS 저장이 연결된 첫 수직 기능 단위를 제공한다.

```text
CLI
 ├─ Config (TOML 로딩과 검증)
 ├─ Network (제한된 크기의 HTML 요청)
 ├─ Generic Extractor
 │    └─ StreamInfo
 └─ Downloader
      ├─ Direct (MP4, WebM)
      └─ HLS (FFmpeg stream copy)
```

## 모듈 경계

- `cli`: 사용자 입력을 해석하고 작업 흐름을 연결한다.
- `config`: 외부 설정을 내부의 검증된 값으로 변환한다.
- `logging`: 애플리케이션 로그의 레벨과 출력 형식을 관리한다.
- `exceptions`: 사용자에게 설명할 수 있는 예상 오류의 공통 계층이다.
- `network`: 스크립트를 실행하지 않고 제한된 크기의 HTML을 가져온다.
- `extractors`: 표준 미디어 속성에서 스트림 후보를 찾는다.
- `downloaders`: 스트림 형식에 맞는 구현으로 파일을 저장한다.
- `filenames`: 운영체제에 안전하고 기존 파일을 덮어쓰지 않는 경로를 만든다.

Extractor는 파일을 저장하지 않고, Downloader는 웹페이지를 분석하지 않는다는
경계를 유지한다.

다양한 페이지 구조의 분석 순서, 여러 영상·품질 그룹화, Site Extractor 추가
기준은 [스트림 분석 파이프라인](extraction-pipeline.md)에 정의한다.

## 의존성 원칙

표준 라이브러리로 충분한 동안 런타임 의존성을 추가하지 않는다. 새 의존성은
구현할 기능, 대안, 유지 비용을 검토한 뒤 추가하고 중요한 선택은 ADR로 남긴다.

## 현재 제한

- JavaScript를 실행하거나 브라우저 네트워크 요청을 가로채지 않는다.
- 쿠키, 로그인 세션, 프록시는 아직 지원하지 않는다.
- HLS 품질 선택은 아직 재생목록 내부가 아닌 HTML에서 발견된 스트림 단위이다.
- FFmpeg HTTP 요청이 403이고 CDN이 HTTP/2를 요구하면, 평문 TS-HLS에 한해
  curl로 세그먼트를 전송한 뒤 FFmpeg로 로컬 병합한다.
- DASH를 식별할 수 있지만 Downloader는 아직 없다.
- DRM 해제와 접근 권한 우회는 프로젝트 범위에 포함하지 않는다.
