# Run FilamentMonitor
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
& "$ScriptDir\.venv\Scripts\streamlit.exe" run "$ScriptDir\app.py" --server.port 8501
