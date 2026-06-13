@echo off
chcp 65001 >nul
echo 正在使用 PyInstaller 打包 QuickStreamAppAdd ...
C:/Users/86150/AppData/Local/Programs/Python/Python38/python.exe -m PyInstaller main.py -w -i ".\icon.ico" -n SunshineAppManager --clean --noconfirm --add-data "i18n;i18n"
if %ERRORLEVEL% equ 0 (
    echo.
    echo 打包完成。输出目录: dist\QuickStreamAppAdd.exe
) else (
    echo 打包失败，请检查是否已安装: pip install pyinstaller
    pause
)
