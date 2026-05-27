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
                                                                    ↓ push 직후 purge.jsdelivr.net 호출
[GitHub] data 브랜치 → cdn.jsdelivr.net/gh/<USER>/<REPO>@data (CORS + 5초 내 fresh)
[GitHub] main 브랜치 → GitHub Pages → 정적 사이트 → fetch jsdelivr → ECharts 갱신
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
- 매 분 정각(`:00`초)에 깨어남
- 평일 **08:50–15:40 KST** 구간이면 → `collect_once()` 호출 (fetch + parse + push + jsdelivr purge)
- 그 외 시간(주말·공휴일·장 외 시간) → 조용히 sleep, 매시 정각만 `idle` 로그
- 예외 발생해도 데몬 자체는 죽지 않음 — 다음 분에 자가 회복
- 종료: `Ctrl+C`

콘솔 창은 그냥 띄워 두기만 하면 됨. 다른 작업 해도 백그라운드에서 매 분 갱신.
PC 재부팅 시에는 창을 다시 띄워야 합니다.

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
