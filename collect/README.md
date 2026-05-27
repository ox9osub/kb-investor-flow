# collect

KB 투자자별 매매동향 수집기. 상시 데몬(`daemon.py`)이 콘솔 창에서 24/7 실행되며,
평일 08:50–15:40 KST 동안 매 분 정각에 KB 페이지를 fetch → 파싱 → data 브랜치 worktree에 push.

## 설치

```powershell
pip install -r requirements.txt
```

## 사용

### 상시 데몬 (정상 운영 방식)

콘솔 창을 열고 다음을 실행. Ctrl+C로 종료.
```powershell
cd C:\Users\suble\Desktop\work\project\kb-investor-flow\collect
python daemon.py
```

- 매 분 정각에 거래시간 여부 체크
- 거래시간 내: `collect_once()` 호출 → fetch + parse + write + push + jsdelivr purge
- 거래시간 외: 매시 정각에만 idle 로그
- 예외 발생해도 데몬 자체는 죽지 않음 (다음 분에 재시도)

### 1회성 실행 (디버깅용)

```powershell
# 파싱 결과만 stdout, 파일/git 손대지 않음
python collect.py --dry-run

# 파일은 저장하되 push는 안 함
python collect.py --no-push

# 평소 한 사이클 (push 포함)
python collect.py
```

## 테스트

```powershell
cd tests
python -m pytest -v
```
