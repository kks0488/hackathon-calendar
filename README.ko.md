<p align="center">
  <img src="assets/banner-ko.png" alt="hackathon-calendar: 해커톤 마감일을 쓰던 캘린더에서 바로 확인" width="100%">
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> · <b>한국어</b>
</p>

<h2 align="center">해커톤 마감일을, 쓰던 캘린더에서 바로 확인하세요.</h2>

<p align="center">
  애플 캘린더·구글 캘린더 등 iCalendar 앱에 주소 하나로 구독합니다.<br>
  GitHub Actions가 매일 목록을 갱신합니다. NAS(WebDAV) 동기화는 선택입니다.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/kks0488/hackathon-calendar?color=f778ba" alt="라이선스: MIT"></a>
  <a href="https://github.com/kks0488/hackathon-calendar/stargazers"><img src="https://img.shields.io/github/stars/kks0488/hackathon-calendar?style=flat&color=e3b341" alt="stars"></a>
  <img src="https://img.shields.io/github/languages/top/kks0488/hackathon-calendar?color=3fb950" alt="top language">
  <a href="https://github.com/kks0488/hackathon-calendar/commits/main"><img src="https://img.shields.io/github/last-commit/kks0488/hackathon-calendar?color=79c0ff" alt="last commit"></a>
</p>

<table>
<tr>
<td width="50%" valign="top">

### 한 번만 구독
캘린더는 GitHub에서 제공하는 평범한 `.ics` 파일입니다. 주소를 한 번 추가하면 캘린더 앱이 알아서 갱신합니다.

</td>
<td width="50%" valign="top">

### 알림이 붙은 마감일
해커톤마다 상금·주최·테마·링크가 담긴 마감 일정과 마감 3일 전·1일 전 알림이 있습니다.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 매일 자동 갱신
GitHub Actions가 Devpost·MLH에서 온라인 참가가 가능한 해커톤을 매일 수집합니다. LabLab.ai는 공개 목록에서 행사 정보를 읽을 수 있을 때 포함합니다.

</td>
<td width="50%" valign="top">

### 선택: NAS 동기화
`sync-calendar.sh`가 파일을 WebDAV로 NAS에 올리고 GitHub에 커밋합니다. 자격증명은 본인만 읽을 수 있는 별도 파일에 둡니다.

</td>
</tr>
</table>

## 구독하기

```text
https://raw.githubusercontent.com/kks0488/hackathon-calendar/main/hackathon-calendar.ics
```

**애플 캘린더(아이폰):** 설정 › 캘린더 › 계정 › 계정 추가 › 기타 › 구독 캘린더 추가에 주소를 붙여 넣습니다(iOS 버전마다 경로가 조금 다릅니다). 맥에서는 파일 › 새로운 캘린더 구독.

**구글 캘린더:** calendar.google.com에서 *다른 캘린더* 옆 **+** › **URL로 추가**에 주소를 붙여 넣습니다.

## 데모

<p align="center">
  <img src="assets/demo.svg" alt="터미널: 공개 피드의 일정 11개를 세고, 해커톤 목록을 보고, 동기화 스크립트를 실행" width="100%">
</p>

<sub>초기 피드로 실행한 예시로, 현재 일정 수와 날짜는 달라졌습니다. 선택 사항인 동기화 출력은 NAS·GitHub 업로드가 성공했을 때의 모습입니다.</sub>

## 캘린더에 든 것

온라인 참가가 가능하고 마감일이 오늘 이후(UTC 기준)인 진행 중·예정 해커톤을 모읍니다. 최신 목록과 갱신 시각, 출전 후보 프로젝트는 [HACKATHONS.md](HACKATHONS.md)에 있고, 수집 데이터는 [data/hackathons.json](data/hackathons.json)에 있습니다.

Devpost에서 시각을 공개하지 않은 마감은 종일 일정으로 표시합니다. MLH는 행사 종료 시각을 마감으로 사용합니다. 참가 자격과 정확한 제출 시각은 각 행사 링크에서 확인하세요.

## 내 캘린더로 쓰기

1. 저장소를 포크하고 GitHub Actions를 활성화합니다. 매일 **21:17 UTC(다음 날 한국 시각 06:17)**에 갱신하며, **Actions → Update hackathon calendar → Run workflow**로 직접 실행할 수도 있습니다. API 키나 별도로 등록할 비밀값은 없습니다.
2. 위와 같은 방법으로 내 포크의 raw 주소를 구독합니다.
3. 선택: NAS 동기화

```bash
cp .env.example .env          # NAS_WEBDAV_URL 설정
mkdir -p ~/.config/synology
printf 'NAS_WEBDAV_USER=...\nNAS_WEBDAV_PASSWORD=...\n' > ~/.config/synology/credentials.env
chmod 600 ~/.config/synology/credentials.env
./sync-calendar.sh
```

내 컴퓨터에서 갱신하려면 Python 3.11 이상으로 실행합니다. 추가 라이브러리는 필요 없습니다.

```bash
python3 scripts/fetch_hackathons.py
python3 scripts/build_calendar.py
python3 -B -m unittest discover -s tests -v
```

<details>
<summary><b>기술 세부 사항</b></summary>

- `sync-calendar.sh`는 저장소 폴더의 `.env`(Git 제외)를 읽고, 이어서 자격증명 파일(기본값 `~/.config/synology/credentials.env`, 또는 `SYNOLOGY_CREDENTIAL_FILE`)을 읽습니다.
- 자격증명 파일이 없거나, 심링크이거나, 현재 사용자 소유가 아니거나, 그룹·다른 사용자가 읽을 수 있으면 실행을 거부합니다.
- 1단계는 `curl -T`로 `.ics`를 올리고 HTTP 상태를 보여 줍니다(201·204면 성공). 2단계는 폴더가 git 저장소면 파일을 커밋하고 푸시합니다.
- NAS 관리자 계정이 아니라 캘린더 폴더에만 접근할 수 있는 별도 WebDAV 계정을 쓰세요.
- `bash`, `curl`, `git`, GNU `stat`(리눅스)이 필요합니다. macOS에는 `stat -c`가 없습니다.
- 수집기는 Devpost 공개 JSON을 끝 페이지까지 읽고, MLH 2027·2026 시즌 페이지를 확인합니다. LabLab.ai는 선택 출처입니다. 한 출처가 실패하거나 목록을 읽을 수 없으면 경고를 남기고 나머지는 계속 수집합니다.
- 생성기는 출전 후보 프로젝트 부분을 보존하면서 `hackathon-calendar.ics`, `HACKATHONS.md`, `data/hackathons.json`을 만듭니다. 워크플로는 파일이 바뀐 경우에만 커밋하고 푸시합니다.
- 시각이 있는 마감은 피드에 UTC, 목록에 한국 시각으로 표시합니다. 날짜만 있는 일정은 `VALUE=DATE`를 씁니다. 행사마다 고정 식별자와 마감 알림 두 개가 있으며, 캘린더 이름은 기존 `Hackathon Tracker`를 유지합니다.

</details>

## 동작 방식

```mermaid
flowchart LR
  A[GitHub Actions<br>매일 또는 수동 실행] --> B[공개 해커톤 출처]
  B --> C[data/hackathons.json]
  C --> D[hackathon-calendar.ics<br>HACKATHONS.md]
  D -->|변경 파일 커밋| E[GitHub raw 주소]
  E --> F[애플·구글 캘린더]
  D -. 선택: sync-calendar.sh .-> G[(NAS / WebDAV)]
```

## 자주 묻는 질문

**목록이 계속 갱신되나요?**
네. GitHub Actions가 매일 21:17 UTC에 실행되도록 설정되어 있고, 직접 실행할 수도 있습니다. 최근 갱신 시각은 [HACKATHONS.md](HACKATHONS.md), 출처별 경고는 워크플로 실행 로그에서 확인할 수 있습니다.

**NAS가 꼭 있어야 하나요?**
아니요. 구독은 GitHub raw 주소만으로 됩니다. NAS 업로드는 선택입니다.

**캘린더는 얼마나 자주 새로고침되나요?**
앱마다 다릅니다. 애플 캘린더는 주기를 고를 수 있고, 구글 캘린더는 자체 주기로 구독 캘린더를 갱신합니다.

## 라이선스

[MIT](LICENSE)
