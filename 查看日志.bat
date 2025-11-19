@echo off
chcp 65001 >nul
echo ========================================
echo 查看应用日志文件
echo ========================================
echo.

if exist logs\app_*.log (
    echo 找到日志文件：
    dir /b logs\app_*.log
    echo.
    echo 显示最新的日志内容（最后50行）：
    echo ========================================
    echo.
    for %%f in (logs\app_*.log) do (
        echo 文件: %%f
        powershell -Command "Get-Content '%%f' -Tail 50 -Encoding UTF8"
        echo.
    )
) else (
    echo 未找到日志文件！
    echo 请先运行应用（python app.py）生成日志。
)

echo.
echo ========================================
pause

