@echo off
echo Otwieranie podgladu calego tla wyspy w Houdini Geometry Viewer (gplay)...
echo Plik: cache\lesson03_context_material.bgeo.sc (8000 x 8000m, 2048 x 2048 komorek)
start "" "D:\yacs\tools\houdini-22.0.466\bin\gplay.exe" "%~dp0cache\lesson03_context_material.bgeo.sc"
