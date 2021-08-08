@ECHO OFF

:: -----------------------------------------------------
:: launcher for python scripts using the SAGA Python API
:: Author: Volker Wichmann 
:: ------------------------------------------------------


REM directories to set:
SET PYTHONINSTALL=C:\Users\vw\AppData\Local\Programs\Python\Python39


REM check argument
IF %1.==. (
    ECHO.
    ECHO Please pass the python script to run as argument to this batch file
    EXIT /B 1
)

REM set directories
SET PATH=%PYTHONINSTALL%;%PATH%

REM run the script
%PYTHONINSTALL%\python.exe %*

