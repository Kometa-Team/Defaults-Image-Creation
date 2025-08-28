REM python -m venv venv
REM venv\Scripts\activate
REM pip install -r requirements.txt
REM python -m pip install --upgrade pip

.\venv\Scripts\python .\name_checker_dir.py --input_directory C:\Users\bullmoose20\Downloads\
REM pause
.\venv\Scripts\python .\get_missing_people.py --input_directory C:\Users\bullmoose20\Downloads\
REM pause

.\venv\Scripts\python .\tmdb-people.py
REM pause
.\venv\Scripts\python .\truncate_tmdb_people_names.py 
REM pause
.\venv\Scripts\python .\get_missing_people_dir.py --input_directory .\config\posters
REM pause
del .\config\posters\*.* /Q
move .\config\Downloads\color\*.* D:\bullmoose20\people\Downloads\
del .\config\Downloads\color\*.* /Q
move .\config\Downloads\other\*.* D:\bullmoose20\people\Downloads\
del .\config\Downloads\other\*.* /Q
REM pause

REM Now selenium flow twice as second time will get any stragglers
REM D:
REM cd D:\bullmoose20\pyprogs\sel_remove_bg
.\venv\Scripts\python .\sel_remove_bg.py
.\venv\Scripts\python .\sel_remove_bg.py
REM pause

REM Now run pad flow(well actually PAD flow was replaced but this is what creates the posters now as PAD flow within ps1 is disabled as of aug 25,2025)
D:
cd D:\Defaults-Image-Creation\create_people_posters
REM "C:\Program Files\PowerShell\7\pwsh.exe" -ExecutionPolicy Bypass -File ".\create_people_poster.ps1" d:\ "remove backgrounds chrome-en windows-en"
"C:\Program Files\PowerShell\7\pwsh.exe" -ExecutionPolicy Bypass -File ".\create_people_poster.ps1" x:\
pause

D:
cd D:\bullmoose20\people
robocopy D:\bullmoose20\people\bw\ D:\bullmoose20\Kometa-People-Images\bw\ /E /COPY:DAT /DCOPY:T /XO
robocopy D:\bullmoose20\people\diiivoy\ D:\bullmoose20\Kometa-People-Images\diiivoy\ /E /COPY:DAT /DCOPY:T /XO
robocopy D:\bullmoose20\people\diiivoycolor\ D:\bullmoose20\Kometa-People-Images\diiivoycolor\ /E /COPY:DAT /DCOPY:T /XO
robocopy D:\bullmoose20\people\original\ D:\bullmoose20\Kometa-People-Images\original\ /E /COPY:DAT /DCOPY:T /XO
robocopy D:\bullmoose20\people\signature\ D:\bullmoose20\Kometa-People-Images\signature\ /E /COPY:DAT /DCOPY:T /XO
robocopy D:\bullmoose20\people\rainier\ D:\bullmoose20\Kometa-People-Images\rainier\ /E /COPY:DAT /DCOPY:T /XO
robocopy D:\bullmoose20\people\transparent\ D:\bullmoose20\Kometa-People-Images\transparent\ /E /COPY:DAT /DCOPY:T /XO

D:
cd D:\bullmoose20\pyprogs\get_people_posters
call .\@people_git_readme_merge.cmd

echo Debugging: Starting python auto_readme.py -s transparent
D:
cd D:\bullmoose20\Kometa-People-Images
REM python auto_readme.py
REM python auto_readme.py -s bw
REM python auto_readme.py -s diivoy
REM python auto_readme.py -s diivoycolor
REM python auto_readme.py -s rainier
REM python auto_readme.py -s signature
python auto_readme.py -s transparent

echo Debugging: Starting robocopy of transparent

robocopy D:\bullmoose20\Kometa-People-Images\transparent\ D:\bullmoose20\people\transparent\ *.md /E /COPY:DAT /DCOPY:T /XO

echo Debugging: Ending robocopy of transparent

echo Debugging: ALL DONE!!!!

pause