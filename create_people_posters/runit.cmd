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

.\venv\Scripts\python .\prep_people_dirs.py
REM pause

REM Now selenium flow twice as second time will get any stragglers
REM D:
REM cd D:\bullmoose20\pyprogs\sel_remove_bg
.\venv\Scripts\python .\sel_remove_bg.py
.\venv\Scripts\python .\sel_remove_bg.py
pause

REM Now run pad flow(well actually PAD flow was replaced but this is what creates the posters now as PAD flow within ps1 is disabled as of aug 25,2025)
REM D:
REM cd D:\Defaults-Image-Creation\create_people_posters
"C:\Program Files\PowerShell\7\pwsh.exe" -ExecutionPolicy Bypass -File ".\create_people_poster.ps1"
REM pause

.\venv\Scripts\python sync_people_images.py --dest_root "D:/bullmoose20/Kometa-People-Images"
REM pause

.\venv\Scripts\python update_people_repos.py --repo-root "D:/bullmoose20/Kometa-People-Images" --branch master
REM pause

echo Debugging: Starting python auto_readme.py -s transparent
D:
cd D:\bullmoose20\Kometa-People-Images
python auto_readme.py -s transparent
pause

echo Debugging: Starting robocopy of transparent *.md
robocopy D:\bullmoose20\Kometa-People-Images\transparent\ D:\bullmoose20\people\transparent\ *.md /E /COPY:DAT /DCOPY:T /XO

echo Debugging: Ending robocopy of transparent

echo Debugging: ALL DONE!!!!

pause