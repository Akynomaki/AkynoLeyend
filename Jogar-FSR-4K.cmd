@echo off
setlocal
call "%~dp0Jogar.cmd" --output-resolution 4k --resolution 50 --upscaling fsr-temporal --sharpness 0 --framegen 0 --pacing on --fps-counter on --handheld off --cache-mode streaming %*
exit /b %errorlevel%
