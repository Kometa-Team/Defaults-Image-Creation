REM python -m venv venv
REM venv\Scripts\activate
REM pip install -r requirements.txt
REM python -m pip install --upgrade pip

REM Scan the input_directory for people posters
.\venv\Scripts\python .\name_checker_dir.py --input_directory C:\Users\bullmoose20\Downloads\
REM pause

REM Scan the input_directory for even more people posters
.\venv\Scripts\python .\get_missing_people.py --input_directory C:\Users\bullmoose20\Downloads\
REM pause

REM using the .env tmdb-people section, this will download the images from tmdb and place them into 
REM ./config/posters
.\venv\Scripts\python .\tmdb_people.py
REM pause

REM This will remove the -##### extension on all the file names and remove the Duplicates by placing the duplicates into
REM ./config/Duplicates
.\venv\Scripts\python .\truncate_tmdb_people_names.py 
REM pause

REM This will sort the color and non-color(other) images into
REM ./config/Downloads/color and ./config/Downloads/other
.\venv\Scripts\python .\get_missing_people_dir.py --input_directory .\config\posters
REM pause

REM This copies the files from the color and other folders into
REM ./config/people-dirs/Downloads folder
.\venv\Scripts\python .\prep_people_dirs.py
REM pause

REM Now selenium flow twice to remove the bg and second time will get any stragglers
REM Please review the .env sel_remove_bg.py section
REM On first run, you will need to loging to adobe express and then quit the script so that it
REM stores your profile for the next run. This only needs to be done once.
.\venv\Scripts\python .\sel_remove_bg.py
.\venv\Scripts\python .\sel_remove_bg.py
REM pause

REM Now run the poster creation
REM D:
REM cd D:\Defaults-Image-Creation\create_people_posters
"C:\Program Files\PowerShell\7\pwsh.exe" -ExecutionPolicy Bypass -File ".\create_people_poster.ps1"
REM pause

REM Move the images to the repo folders
.\venv\Scripts\python sync_people_images.py --dest_root "D:/bullmoose20/Kometa-People-Images"
REM pause

REM Pull the latest from the repos and merge so that you can push the changes up to the repo
.\venv\Scripts\python update_people_repos.py --repo-root "D:/bullmoose20/Kometa-People-Images" --branch master
REM pause

REM Now we need to create the README.md for transparent locally instead of with GitActions
REM because it takes too long for the transparent folder
echo Debugging: Starting python auto_readme.py -s transparent
D:
cd D:\bullmoose20\Kometa-People-Images
python auto_readme.py -s transparent
pause

REM Copy the *.md files in the transparent folder back to the source for consistency
echo Debugging: Starting robocopy of transparent *.md
robocopy D:\bullmoose20\Kometa-People-Images\transparent\ D:\bullmoose20\people\transparent\ *.md /E /COPY:DAT /DCOPY:T /XO

echo Debugging: Ending robocopy of transparent

echo Debugging: ALL DONE!!!!

pause