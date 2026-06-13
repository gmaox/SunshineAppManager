@echo off

"C:\Users\86150\AppData\Local\Programs\Python\Python38\Lib\site-packages\qt5_applications\Qt\bin\lrelease.exe" app_en_US.ts -qm app_en_US.qm

if %errorlevel% neq 0 (
    echo QM生成失败
    pause
    exit /b 1
)

echo QM生成成功：app_en_US.qm
pause