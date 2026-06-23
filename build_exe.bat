@echo off
echo Dang tien hanh dong goi widget.exe...
echo.
rem Su dung thu muc Temp cua he thong de chua cac file rac tam thoi
pyinstaller --noconfirm --workpath "%TEMP%\widget_build" --distpath . dist\widget.spec
echo.
echo ====================================================
echo Thanh cong! File widget.exe da duoc cap nhat truc tiep o day.
echo Cac thu muc rac da duoc chuyen sang muc Temp va se khong lam ban thu muc cua ban nua.
echo ====================================================
pause
