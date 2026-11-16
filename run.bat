@echo off
title CINEPLEX - Movie Ticket Booking System
cd /d "%~dp0"
start "" "http://127.0.0.1:5000"
"C:\Users\sumit\AppData\Local\Programs\Python\Python314\python.exe" app.py
pause
