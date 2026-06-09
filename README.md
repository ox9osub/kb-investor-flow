# KB 투자자별 매매동향 실시간 대시보드

KB증권 [투자자별 매매동향 페이지](https://m.kbsec.com/go.able?linkcd=s050400010000&gubun=0)의
KOSPI/KOSDAQ 데이터를 한국 정규 장중(평일 08:50–15:40 KST) 1분 간격으로 로컬 PC에서 수집해,
GitHub Pages의 정적 사이트에서 ECharts로 시계열·스냅샷 차트로 시각화합니다.

- **라이브 대시보드:** https://ox9osub.github.io/kb-investor-flow/
- **설계 문서:** [docs/superpowers/specs/2026-05-27-kb-investor-flow-dashboard-design.md](docs/superpowers/specs/2026-05-27-kb-investor-flow-dashboard-design.md)
- **구현 계획:** [docs/superpowers/plans/2026-05-27-kb-investor-flow-dashboard.md](docs/superpowers/plans/2026-05-27-kb-investor-flow-dashboard.md)

## 구성

- `index.html`, `assets/` — 정적 대시보드 (GitHub Pages가 main 브랜치에서 서빙)
- `collect/` — Python 수집기 (로컬 PC의 콘솔에서 `daemon.py` 상시 실행)
- `data/` (별도 브랜치 `data` — orphan) — 일별 JSON, 매분 푸시

## 데이터 흐름

```
[Local PC] daemon.py (콘솔 상시 실행) → 매 분 정각 거래시간 체크
                                          ↓ (평일 08:50–15:40 KST 만)
                       KB 페이지 fetch → 파싱 → JSON append → git push (data 브랜치)
[GitHub] data 브랜치 → raw.githubusercontent.com/<USER>/<REPO>/data (CORS OK, ?t= 캐시버스터로 즉시 fresh)
[GitHub] main 브랜치 → GitHub Pages → 정적 사이트 → fetch raw + ?t= → ECharts 갱신

  ※ jsdelivr는 쿼리스트링을 캐시 키에서 무시해 ?t= 캐시버스터가 안 먹히고, 엣지가
    s-maxage(12h) 동안 옛 사본을 내려줘 1분 신선도가 깨졌음. raw로 전환해 해결.
```

## 초기 셋업 (새 PC / 처음 클론 시)

```powershell
# 1. 리포 클론
git clone https://github.com/ox9osub/kb-investor-flow.git
cd kb-investor-flow

# 2. Python venv 생성 + 의존성 설치
python -m venv .venv
.\.venv\Scripts\pip install -r collect\requirements.txt

# 3. data 브랜치를 sibling 디렉토리에 worktree로 체크아웃
git worktree add ..\kb-investor-flow-data data

# 4. 1회 dry-run으로 동작 확인 (네트워크는 호출, 파일/git은 안 건드림)
.\.venv\Scripts\python.exe collect\collect.py --dry-run
```

`.venv\`는 `.gitignore`에 포함되어 commit되지 않습니다. PC마다 새로 만드세요.

## 운영 (수집기 가동)

콘솔(PowerShell 또는 cmd) 창 1개를 열고 다음을 실행하면 데몬이 24/7 상주합니다:

```powershell
cd C:\Users\suble\Desktop\work\project\kb-investor-flow
.\.venv\Scripts\python.exe collect\daemon.py
```

**동작 방식 (`collect/daemon.py`):**
- 매 분 `:01`초에 깨어남 (KB 페이지가 새 분으로 갱신될 1초 여유; 매 루프 재정렬 → 드리프트 없음)
- 평일 **08:50–15:40 KST** 구간이면 → `collect_once()` 호출 (fetch + parse + push + jsdelivr purge)
- 그 외 시간(주말·공휴일·장 외 시간) → 조용히 sleep, 매시 정각만 `idle` 로그
- 예외 발생해도 데몬 자체는 죽지 않음 — 다음 분에 자가 회복
- 종료: `Ctrl+C`

콘솔 창은 그냥 띄워 두기만 하면 됨. 다른 작업 해도 백그라운드에서 매 분 갱신.
PC 재부팅 시에는 창을 다시 띄워야 합니다.

## 슬랙 알림 — 투자주체 추세 상태 변화 (`collect/notify.py`)

각 투자주체의 누적순매수 기울기를 매분 8개 라벨(`지속매수/지속매도/매수전환/매도전환/
매수둔화/매도둔화/혼조/중립`)로 분류하고, **트리거 주체의 라벨이 바뀌면** 슬랙으로 보냅니다.
`collect_once()`가 수집 직후 자동 호출하므로 데몬을 띄워 두면 알림도 같이 동작합니다.

- **트리거 기본값 = 금융투자 + 외국인** (하루 ~36–69회). 금융투자=지수 견인 자기매매,
  외국인=수급 큰손. 매 알림에 11개 주체 전체 상태를 진영별로 함께 싣습니다. 금융투자는
  항상 포함. 더 넓히거나(기관·개인 등) 좁히려면 `NOTIFY_ACTORS` 환경변수(쉼표구분)로 지정.
- 메시지 형식: **변화 주체는 줄별로**(`아이콘 주체 기존→변화 (속도)`) → **핵심 한 줄**
  (외국인·개인·기관·금융투자·연기금 중 안 바뀐 것, 아이콘만) → 시각·시장 → 대시보드 링크.
  소형주체(보험·사모·은행 등)는 표시 제외(`BOARD` 상수). 아이콘: 🔥지속매수 💦지속매도
  ❤️매수전환 💙매도전환 🔸매수둔화 🔹매도둔화 💤혼조 ◽중립.
- 분류 로직은 `collect/trend.py`(pandas 분석용)와 동일하며 `notify.py`는 수집기 venv에서
  돌도록 순수 파이썬으로 재구현. 일치 검증: `python collect/notify.py <date> --selftest`.

**슬랙 설정** — 두 방법 중 하나. **환경변수가 `.slack.json`보다 우선**합니다.
미설정 시 알림은 stdout으로만 출력(드라이런). 봇은 대상 채널에 `/invite` 돼 있어야 합니다.

방법 ① 로컬 설정파일 `collect/.slack.json` (gitignore됨, 다른 PC엔 수동 복사 필요):

```json
{ "token": "xoxb-…", "channel": "C0B99209CKB" }
```

방법 ② 환경변수 (PowerShell):

```powershell
# 봇토큰 방식 — 이번 콘솔 세션에만 적용 (창 닫으면 사라짐)
$env:SLACK_BOT_TOKEN = "xoxb-…"
$env:SLACK_CHANNEL   = "C0B99209CKB"

# 영구 저장 — 사용자 환경변수에 기록, 새로 여는 콘솔부터 적용
setx SLACK_BOT_TOKEN "xoxb-…"
setx SLACK_CHANNEL   "C0B99209CKB"

# 웹훅 방식 (봇토큰 대신)
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/…"

# 트리거 주체 지정 (기본=금융투자,외국인 / 금융투자는 항상 포함, 쉼표구분)
$env:NOTIFY_ACTORS = "금융투자,외국인,기관,개인"
```

> 데몬을 띄운 콘솔에서 환경변수를 쓰려면, **그 콘솔에서** `$env:…` 설정 후
> `daemon.py`를 실행하거나(세션 한정), `setx`로 영구 저장 뒤 콘솔을 새로 열어야 합니다.
> `SLACK_CHANNEL` 미지정 시 기본 채널 `C0B99209CKB`이 사용됩니다.

```powershell
# 특정일 현재 상태 보드 / 전환 이벤트 로그 (분석용, trend.py)
.\.venv-pandas\Scripts\python.exe collect\trend.py 2026-06-01
.\.venv-pandas\Scripts\python.exe collect\trend.py 2026-06-01 --transitions
# 알림 1회 수동 점검 (슬랙 미설정 시 stdout)
.\.venv\Scripts\python.exe collect\notify.py 2026-06-01 --test
```

> `trend.py`는 pandas/pyarrow가 필요합니다(분석용 별도 venv). `notify.py`는 수집기 venv로 동작.

## 디버깅용 1회 실행

`daemon.py`를 안 띄우고 한 사이클만 수동 실행하고 싶을 때:

```powershell
# 파싱 결과만 stdout, 파일/git 손대지 않음 (가장 안전)
.\.venv\Scripts\python.exe collect\collect.py --dry-run

# 파일은 저장하되 git push는 안 함
.\.venv\Scripts\python.exe collect\collect.py --no-push

# 평소 한 사이클 그대로 (데몬이 매분 하는 것과 동일)
.\.venv\Scripts\python.exe collect\collect.py
```

## 테스트

```powershell
cd collect
..\.venv\Scripts\python.exe -m pytest tests/ -v
```

13개 테스트 (parse 7 + storage 6) 통과 기준.

## 로컬 사이트 미리보기

배포 전 차트 확인:

```powershell
python -m http.server 8000
# http://localhost:8000/
```

`assets/app.js`가 GitHub의 jsdelivr URL을 fetch하므로 로컬에서도 실데이터로 동작.
