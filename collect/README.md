# collect

KB 투자자별 매매동향 수집기. Windows Task Scheduler에서 1분마다 트리거되어 데이터를
data 브랜치 worktree에 푸시.

## 설치

```powershell
pip install -r requirements.txt
```

## 사용

```powershell
# 파싱 결과만 출력 (네트워크는 호출, 파일/git은 안 건드림)
python collect.py --dry-run

# 파일 저장하되 git push는 안 함 (로컬 검증용)
python collect.py --no-push

# 정식 실행 (Task Scheduler가 호출하는 형태)
python collect.py
```

## 테스트

```powershell
cd tests
pytest -v
```
