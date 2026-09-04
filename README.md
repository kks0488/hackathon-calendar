# Hackathon Calendar

해커톤 일정 자동 구독 캘린더

## 캘린더 구독 URL

```
https://raw.githubusercontent.com/kks0488/hackathon-calendar/main/hackathon-calendar.ics
```

### Apple Calendar 구독
1. 설정 > 캘린더 > 계정 > 캘린더 구독 추가
2. 위 URL 붙여넣기
3. 자동 새로고침: 매일

### Google Calendar 구독
1. calendar.google.com > 다른 캘린더 + > URL로 추가
2. 위 URL 붙여넣기

## NAS WebDAV 동기화

`sync-calendar.sh`의 URL과 실행 설정은 Git에서 제외된 프로젝트 `.env`에,
WebDAV 사용자명과 비밀번호는 `/home/kkaemo/.config/synology/credentials.env`에
둡니다. 자격증명 파일은 현재 사용자 소유의 일반 파일이며 권한이 600이어야
합니다. DSM 운영 계정 대신 캘린더 경로에만 접근 가능한 별도 WebDAV 계정을
사용합니다.

## 현재 트래킹 중인 해커톤

| 해커톤 | 기간 | 상금 |
|--------|------|------|
| Vercel AI Gateway | ~Sept 5 | $2,500+ |
| Microsoft AI Dev Days | ~Mar 15 | $10,000 |
| LabLab AI Trading | Mar 9~22 | $50,000 |
| MLH Cloud Week | Mar 13~19 | Free |
| MLH APIs Week | Apr 10~16 | Free |
| Anthropic Claude | ~May 4 | Credits |
| MLH GenAI Week | May 8~14 | Free |
| DevNetwork AI+ML | May 11~28 | TBD |
