print("RUNNING UPDATED VERSION")

from fastapi import FastAPI, UploadFile, File, Form
from googleapiclient.discovery import build
from google.oauth2 import service_account
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

# Load credentials from Render env variable
creds = service_account.Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_CREDS"]),
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
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

        # 👇 Upload directly into YOUR folder (no folder creation logic)
        file_metadata = {
            "name": file.filename,
            "parents": [DRIVE_FOLDER_ID]
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
