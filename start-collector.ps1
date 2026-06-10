# KB 투자자별 매매동향 수집 데몬 시작 스크립트
#
# NOTIFY_ACTORS(슬랙 알림 트리거 주체)를 "금융투자,외국인"으로 지정해 daemon.py를 띄운다.
#   - 금융투자 = 지수 견인 자기매매, 외국인 = 수급 큰손 (notify.py 기본 트리거와 동일).
#   - 트리거 주체를 바꾸려면 아래 NOTIFY_ACTORS 값만 수정 (쉼표구분, 금융투자는 항상 포함됨).
#
# 사용법:
#   콘솔에서  .\start-collector.ps1
#   (실행 정책 막히면)  powershell -ExecutionPolicy Bypass -File .\start-collector.ps1
#
# 종료: Ctrl+C. 슬랙 토큰 미설정 시 알림은 stdout으로만 출력된다(README 슬랙 설정 참고).

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$env:NOTIFY_ACTORS = "금융투자,외국인"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$daemon = Join-Path $PSScriptRoot "collect\daemon.py"

if (-not (Test-Path $python)) {
    Write-Error "venv 파이썬이 없습니다: $python  (README '초기 셋업'의 venv 생성 단계를 먼저 실행하세요)"
    exit 1
}

Write-Host "NOTIFY_ACTORS = $env:NOTIFY_ACTORS"
Write-Host "starting daemon: $daemon"
Write-Host ("-" * 60)

& $python $daemon

