$ErrorActionPreference = "Stop"

$Python = "C:\Users\Abdul\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

& $Python "$Root\src\dress_watch.py" --config "$Root\config.json" @args
