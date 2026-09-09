@echo off
cd /d "%~dp0"
if exist "E:\anconda\envs\point_clicker\python.exe" (
    "E:\anconda\envs\point_clicker\python.exe" main.py
) else (
    echo [错误] 未找到环境 E:\anconda\envs\point_clicker，请先创建 conda 环境。
    pause
)