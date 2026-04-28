print("RUNNING UPDATED VERSION")

from fastapi import FastAPI, UploadFile, File, Form
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaInMemoryUpload
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import os, json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://josephcox23.github.io"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SPREADSHEET_ID = "1JZAGEGxh5Sfr5NBdOu5BAmMEE8A9aGmAbqv_QDG_I5Y"
DRIVE_FOLDER_ID = "1jAOBOwOHtq04kJpKGIZr4QYid3hiS6Hp"

creds = Credentials.from_authorized_user_info(
    json.loads(os.environ["GOOGLE_TOKEN"])
)

sheets = build("sheets", "v4", credentials=creds)
drive = build("drive", "v3", credentials=creds)


@app.get("/config")
def config():
    j = sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Judges!A2:B"
    ).execute().get("values", [])

    b = sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range="Bands!A2:A"
    ).execute().get("values", [])

    return {
        "judges":[{"name":r[0],"caption":r[1] if len(r)>1 else ""} for r in j],
        "bands":[r[0] for r in b]
    }


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    judge: str = Form(...),
    caption: str = Form(...),
    band: str = Form(...)
):
    try:
        contents = await file.read()

        # 👇 Find or create band folder
        safe_band = band.replace("'", "\\'")
        query = f"name='{safe_band}' and mimeType='application/vnd.google-apps.folder' and '{DRIVE_FOLDER_ID}' in parents and trashed=false"
        
        results = drive.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        items = results.get("files", [])
        
        if items:
            folder_id = items[0]["id"]
        else:
            folder = drive.files().create(
                body={
                    "name": band,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [DRIVE_FOLDER_ID]
                },
                fields="id",
                supportsAllDrives=True
            ).execute()
            folder_id = folder["id"]
        
        # 👇 Upload INTO that folder
        file_metadata = {
            "name": file.filename,
            "parents": [folder_id]
        }

        media = MediaInMemoryUpload(contents, mimetype="audio/webm")

        uploaded = drive.files().create(
            body=file_metadata,
            media_body=media,
            supportsAllDrives=True,
            fields="id"
        ).execute()

        file_id = uploaded["id"]

        # 👇 Make file viewable
        drive.permissions().create(
            fileId=file_id,
            body={
                "type": "anyone",
                "role": "reader"
            }
        ).execute()

        file_link = f"https://drive.google.com/file/d/{file_id}/view"

        # 👇 Log to sheet
        sheets.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Submissions!A1",
            valueInputOption="USER_ENTERED",
            body={
                "values": [[
                    datetime.now().isoformat(),
                    judge,
                    caption,
                    band,
                    file.filename,
                    file_link
                ]]
            }
        ).execute()

        return {"status": "success"}

    except Exception as e:
        print("UPLOAD ERROR:", str(e))
        return {"status": "error", "error": str(e)}
