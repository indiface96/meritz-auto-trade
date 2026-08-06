@echo off
cd /d d:\메리츠자동매매
set PY32=C:\Users\KDM_HOME\AppData\Local\Programs\Python\Python314-32\python.exe
powershell -Command "Start-Process '%PY32%' -ArgumentList 'd:\메리츠자동매매\main.py' -Verb RunAs"
