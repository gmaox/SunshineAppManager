@echo off
chcp 65001 >nul
echo 正在使用 PyInstaller 打包 QuickStreamAppAdd ...
py -m PyInstaller --clean QuickStreamAppAdd.spec
if %ERRORLEVEL% equ 0 (
    echo.
    echo 打包完成。输出目录: dist\QuickStreamAppAdd.exe
) else (
    echo 打包失败，请检查是否已安装: pip install pyinstaller
)
pause
