@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Liber Canticorum - uruchamianie z wiersza polecen (to samo co "Liber Canticorum.bat" pietro wyzej).
rem   start.bat             - uruchom
rem   start.bat odtwarzacz  - doinstaluj wbudowany odtwarzacz YouTube
rem   start.bat skrot       - skrot na pulpicie i w menu Start (z ikona)
cd /d "%~dp0"
set "ARG="
if /i "%~1"=="odtwarzacz" set "ARG=--odtwarzacz"
if /i "%~1"=="skrot" set "ARG=--skrot"
where py >nul 2>&1 && ( py -3 uruchom.py --konsola %ARG% & exit /b )
python uruchom.py --konsola %ARG%
