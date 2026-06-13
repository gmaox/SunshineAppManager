@echo off
setlocal enabledelayedexpansion

set FILES=

for %%f in (*.py) do (
    set FILES=!FILES! "%%f"
)

pylupdate5 -noobsolete %FILES% -ts app_en_US.ts

pause