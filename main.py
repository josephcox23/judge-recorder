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
    allow_origins=["https://josephcox23.github.io"],  # your GitHub site
    allow_credentials=False,  # 👈 IMPORTANT CHANGE
    allow_methods=["*"],
    allow_headers=["*"],
)

SPREADSHEET_ID = "1JZAGEGxh5Sfr5NBdOu5BAmMEE8A9aGmAbqv_QDG_I5Y"
DRIVE_FOLDER_ID = "1jAOBOwOHtq04kJpKGIZr4QYid3hiS6Hp"

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
async def upload(file: UploadFile = File(...), judge: str = Form(...), caption: str = Form(...), band: str = Form(...)):
    try:
        contents = await file.read()

        safe_band = band.replace("'", "\\'")
        q = f"name='{safe_band}' and mimeType='application/vnd.google-apps.folder' and '{DRIVE_FOLDER_ID}' in parents and trashed=false"
        items = drive.files().list(q=q).execute().get("files", [])

        if items:
            folder_id = items[0]["id"]
        else:
            folder = drive.files().create(body={
                "name": band,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [DRIVE_FOLDER_ID]
            }).execute()
            folder_id = folder["id"]

        file_meta = {"name": file.filename, "parents":[folder_id]}

        media = MediaInMemoryUpload(contents, mimetype="audio/webm")

        uploaded = drive.files().create(body=file_meta, media_body=media).execute()

        link = f"https://drive.google.com/file/d/{uploaded['id']}/view"

        row = [[
            datetime.now().isoformat(),
            judge,
            caption,
            band,
            file.filename,
            link
        ]]

        sheets.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Submissions!A1",
            valueInputOption="USER_ENTERED",
            body={"values": row}
        ).execute()

        return {"status":"success"}

    except Exception as e:
        return {"status":"error","error":str(e)}
