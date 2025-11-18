import os
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

FOLDER_ID = "1A6_69CaxPr_reZRsIgoHv9C6CS9ll7Nv"  # Twój folder w Google Drive
LOCAL_FOLDER = "drive_notes"  # lokalny folder do zapisu plików

def fetch_notes_from_drive():
    os.makedirs(LOCAL_FOLDER, exist_ok=True)

    # Autoryzacja – w tym trybie otwiera się przeglądarka
    gauth = GoogleAuth()
    gauth.CommandLineAuth()  # 🔑 to działa ręcznie i zapisuje token w credentials.json
    drive = GoogleDrive(gauth)

    file_list = drive.ListFile({
        'q': f"'{FOLDER_ID}' in parents and trashed=false",
        'supportsAllDrives': True,
        'includeItemsFromAllDrives': True
    }).GetList()

    if not file_list:
        print("Brak plików w folderze!")
        return 0

    downloaded = 0
    for file in file_list:
        file_title = file['title']
        mime_type = file['mimeType']
        local_path = os.path.join(LOCAL_FOLDER, file_title)

        try:
            if mime_type == 'application/vnd.google-apps.document':
                # konwersja Google Docs do pliku .txt
                file.GetContentFile(local_path + ".txt", mimetype='text/plain')
            else:
                file.GetContentFile(local_path)
            downloaded += 1
            print(f"Pobrano: {file_title}")
        except Exception as e:
            print(f"Błąd przy pobieraniu {file_title}: {e}")

    print(f"✅ Pobrano łącznie {downloaded} plików.")
    return downloaded

# Uruchomienie skryptu ręcznie
if __name__ == "__main__":
    fetch_notes_from_drive()
