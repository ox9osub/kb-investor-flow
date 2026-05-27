# KB 투자자별 매매동향 실시간 대시보드

KB증권 투자자별 매매동향 페이지(KOSPI/KOSDAQ)를 1분 간격으로 수집해 정적 웹 대시보드로 시각화.

- **대시보드:** https://<USER>.github.io/<REPO>/
- **설계:** [docs/superpowers/specs/2026-05-27-kb-investor-flow-dashboard-design.md](docs/superpowers/specs/2026-05-27-kb-investor-flow-dashboard-design.md)
- **구현 계획:** [docs/superpowers/plans/2026-05-27-kb-investor-flow-dashboard.md](docs/superpowers/plans/2026-05-27-kb-investor-flow-dashboard.md)

## 구성
- `index.html`, `assets/` — 정적 대시보드
- `collect/` — 로컬 PC에서 동작하는 Python 수집기
- `data/` (별도 브랜치) — 수집된 일별 JSON
