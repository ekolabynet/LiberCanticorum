@echo off
rem Liber Canticorum - uruchamianie w Windows (przy pierwszym starcie pobiera biblioteki).
rem Po pierwszym uruchomieniu w tym folderze pojawi sie skrot "Liber Canticorum" z ikona.
cd /d "%~dp0program"
where pyw >nul 2>&1 && ( start "" pyw -3 uruchom.py %* & exit /b 0 )
where pythonw >nul 2>&1 && ( start "" pythonw uruchom.py %* & exit /b 0 )
where py >nul 2>&1 && ( py -3 uruchom.py %* & exit /b 0 )
echo.
echo Do uruchomienia potrzebny jest Python 3.10 lub nowszy (bezplatny).
echo Zainstaluj go ze strony python.org i zaznacz opcje "Add python.exe to PATH".
echo.
start https://www.python.org/downloads/
pause
