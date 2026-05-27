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
[Local PC] daemon.py (상시 실행) → 매 분 정각 거래시간 체크
                                    ↓ (08:50–15:40 KST 평일)
                       KB 페이지 fetch → 파싱 → JSON append → git push (data 브랜치)
                                                                    ↓ push 직후 purge.jsdelivr.net 호출
[GitHub] data 브랜치 → cdn.jsdelivr.net/gh/<USER>/<REPO>@data (CORS + 5초 내 fresh)
[GitHub] main 브랜치 → GitHub Pages → 정적 사이트 → fetch jsdelivr → ECharts 갱신
```

## 로컬 셋업 (수집기)

상세 안내: [collect/README.md](collect/README.md). 요약:

1. Python 3.10+ 설치, `pip install -r collect/requirements.txt`
2. data 브랜치를 sibling 디렉토리에 worktree:
   `git worktree add ../kb-investor-flow-data data`
3. 1회 검증: `cd collect && python collect.py --dry-run`
4. 상시 데몬 실행: `python collect/daemon.py` — 콘솔 1개 열어두면 24/7 동작.
   거래시간(평일 08:50–15:40 KST) 동안만 실제 수집, 그 외엔 sleep.
   Ctrl+C로 종료.

## 로컬 사이트 미리보기

```powershell
python -m http.server 8000
# http://localhost:8000/
```
