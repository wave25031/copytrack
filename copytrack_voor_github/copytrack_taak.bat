@echo off
REM Dit bestand is voor Taakplanner (automatisch, zonder iemand achter de pc).
REM Voor handmatig dubbelklikken: gebruik copytrack_draaien.bat (die blijft open
REM staan zodat je de uitkomst kan lezen -- dit bestand doet dat expres NIET,
REM anders blijft Taakplanner voor altijd op een toetsdruk wachten die nooit komt).
cd /d C:\trading-bot\copytrack
python track_positions.py
