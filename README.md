# 텔레그램 소통방 채팅 순위 봇

그룹별 채팅을 한국시간 기준으로 집계해 **오늘 순위**와 **주간 순위**를 보여주는 봇입니다.

## 명령어

- `.채팅순위` — 오늘·이번 주 TOP 10
- `.나` — 내 일간·주간 채팅 수와 세로형 상금표
- `.도움말` — 사용법

## 주간 순위 상금

- 1위: 10만원
- 2위: 5만원
- 3위: 3만원
- 4위: 2만원

`.채팅순위`와 `.나`에는 1~4위 상금이 세로로 표시됩니다. 상금과 안내 문구는 웹 관리자에서 언제든 바꿀 수 있습니다.

일간 집계는 매일 00:00, 주간 집계는 매주 월요일 00:00을 기준으로 자동 분리됩니다. 기록을 실제로 삭제하는 초기화 방식이 아니므로 봇을 재시작해도 현재 순위가 유지됩니다.

## 기본 도배 방지

- 봇·익명 관리자 메시지 제외
- 관리자 메시지 제외 (`EXCLUDE_ADMINS=true`)
- 명령어, 이모티콘만 있는 메시지, 5글자 미만 메시지 제외
- `ㅋㅋㅋ`, `ㅇㅇㅇ`처럼 초성·자음만 있는 메시지 제외
- 같은 회원이 3초 안에 연속 작성한 메시지 제외
- 60초 안에 같은 내용을 반복하면 제외

숫자는 `.env`에서 바꿀 수 있습니다.

## 웹 관리자

배포 주소에 접속하면 관리자 로그인 창이 뜹니다. 로그인 후 소통방을 선택해 다음 항목을 수정할 수 있습니다.

- 이벤트 제목
- 일간·주간 순위 제목
- 1~4위 상금
- 순위 하단 안내문
- `.도움말` 안내 문구
- 표시할 TOP 인원
- `.채팅순위` 답변 전체 형식
- `.나` 답변 전체 형식
- `.도움말` 답변 전체 형식
- 순위 한 줄과 상금표 형식(상금은 1~4위가 세로로 표시)

저장한 내용은 재배포나 코드 수정 없이 다음 명령어부터 즉시 반영됩니다. 봇을 그룹에 추가한 뒤 그룹에서 아무 채팅이나 한 번 보내면 해당 소통방이 관리자 화면에 자동 등록됩니다.

### 답변 전체 편집과 치환값

웹 관리자의 **봇 답변 전체 편집**에서 문구, 이모지, 줄바꿈과 표시 순서를 모두 바꿀 수 있습니다. `{WEEKLY_RANKING}`처럼 중괄호로 표시된 값은 실제 데이터로 자동 변경됩니다. 화면에 있는 치환값 버튼을 누르면 현재 커서 위치에 자동 삽입됩니다.

주요 치환값:

| 답변 | 사용할 수 있는 값 |
|---|---|
| `.채팅순위` | `{EVENT_TITLE}`, `{DAY_DATE}`, `{DAILY_RANKING}`, `{WEEK_DATE}`, `{WEEKLY_RANKING}`, `{PRIZE_LINE}`, `{FOOTER}` |
| 순위 한 줄 | `{MEDAL}`, `{POSITION}`, `{NAME}`, `{NAME_BOLD}`, `{COUNT}` |
| `.나` | `{NAME}`, `{DAILY_COUNT}`, `{DAILY_RANK}`, `{DAILY_GAP}`, `{WEEKLY_COUNT}`, `{WEEKLY_RANK}`, `{WEEKLY_GAP}`, `{PRIZE}`, `{PRIZE_TABLE}`, `{PRIZE_LINE}`, `{DAY_DATE}`, `{WEEK_DATE}` |
| `.도움말` | `{EVENT_TITLE}`, `{HELP_MESSAGE}` |

치환값은 필요 없으면 지워도 되고 원하는 위치로 옮겨도 됩니다. `**강조할 글씨**`처럼 입력하면 텔레그램에서 굵게 표시됩니다. 관리자 입력은 안전하게 처리되므로 HTML 태그를 직접 입력할 필요는 없습니다.

## 1. BotFather 설정

1. `@BotFather`에서 봇을 만들고 토큰을 발급받습니다.
2. `/setprivacy` → 해당 봇 선택 → **Disable**로 설정합니다.
3. 봇을 소통방에 추가합니다. 관리자 메시지도 제외하려면 봇을 관리자에 두는 것을 권장합니다.

Privacy Mode를 끄지 않으면 봇이 일반 채팅을 받지 못해 집계가 되지 않습니다.

## 2. 로컬 실행

Python 3.11 이상을 권장합니다.

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env
```

`.env`의 `BOT_TOKEN`을 실제 토큰으로 바꾸고 `ADMIN_PASSWORD`를 8자 이상의 강한 비밀번호로 변경한 뒤 실행합니다.

```bash
python -m chat_rank_bot
```

브라우저에서 `http://localhost:8000`으로 접속하면 관리자 화면이 열립니다.

## 3. Railway 배포

1. 이 프로젝트를 GitHub 저장소에 업로드합니다.
2. Railway에서 저장소를 연결해 새 서비스를 만듭니다.
3. Variables에 `BOT_TOKEN`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`를 추가합니다.
4. Railway에서 PostgreSQL 서비스를 추가하고 봇 서비스에 연결합니다.
5. 배포한 뒤 Railway에서 Public Domain을 생성합니다.
6. 생성된 주소로 접속해 관리자 화면에 로그인합니다.

PostgreSQL을 연결하면 Railway가 제공하는 `DATABASE_URL`을 자동 사용합니다. PostgreSQL 없이 SQLite로도 실행되지만, Railway 재배포 시 기록 보존을 위해 PostgreSQL 사용을 권장합니다.

## 환경변수

| 이름 | 기본값 | 설명 |
|---|---:|---|
| `BOT_TOKEN` | 필수 | BotFather 토큰 |
| `ADMIN_USERNAME` | `admin` | 웹 관리자 아이디 |
| `ADMIN_PASSWORD` | 필수 | 웹 관리자 비밀번호, 최소 8자 |
| `PORT` | `8000` | 웹 서버 포트, Railway는 자동 설정 |
| `DATABASE_URL` | `sqlite:///data/chat_rank.db` | PostgreSQL 또는 SQLite 주소 |
| `TIMEZONE` | `Asia/Seoul` | 집계 시간대 |
| `MIN_TEXT_LENGTH` | `5` | 최소 글자 수 |
| `MIN_MESSAGE_INTERVAL_SECONDS` | `3` | 연속 채팅 제외 시간 |
| `DUPLICATE_WINDOW_SECONDS` | `60` | 같은 내용 반복 제외 시간 |
| `EXCLUDE_ADMINS` | `true` | 관리자 메시지 제외 |
| `ADMIN_CACHE_SECONDS` | `600` | 관리자 목록 캐시 시간 |

## 참고

채팅창에 `.채팅순위`, `.나`를 입력하면 작동합니다. 영문 명령어 `.ranking`, `.me`도 함께 지원합니다.
