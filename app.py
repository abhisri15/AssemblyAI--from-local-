from flask import Flask, render_template, send_file, request, url_for, redirect
import assemblyai as aai
import requests
import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import google.auth
import io
from datetime import datetime

app = Flask(__name__)

# Replace with your AssemblyAI API key
aai.settings.api_key = "817cc900f5ec4b44be6559a62905a600"

# Set the path to your service account key JSON file
SERVICE_ACCOUNT_KEY_PATH = "videoscribe-408208-6b26f8619ce9.json"

# Set the GOOGLE_APPLICATION_CREDENTIALS environment variable
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SERVICE_ACCOUNT_KEY_PATH

# Google Drive API credentials
creds, _ = google.auth.default()
drive_service = build("drive", "v3", credentials=creds)

MEDIA_FILE_URL = ""
MEDIA_FILE_PATH = ""

# Transcribe the media file
config = aai.TranscriptionConfig(speaker_labels=True, sentiment_analysis=True, summarization=True,
                                 summary_model=aai.SummarizationModel.informative, summary_type=aai.SummarizationType.bullets)
transcriber = aai.Transcriber(config=config)
transcript = None

def format_timestamp(milliseconds):
    seconds = milliseconds / 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

def upload_to_google_drive(file_path):
    try:
        file_metadata = {"name": "uploaded_video.mp4"}
        media = MediaFileUpload(file_path, mimetype="video/mp4")
        file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        return file.get("id")
    except HttpError as error:
        print(f"Google Drive API error: {error}")
        return None

def get_google_drive_link(file_id):
    try:
        permission = drive_service.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    except HttpError as error:
        print(f"Google Drive API error: {error}")
        return None

def transcribe_video(file_link):
    transcript = transcriber.transcribe(file_link)
    return transcript

@app.route('/')
def index():
    result_data = []
    summary = None

    if transcript and transcript.utterances:
        for utterance, sentiment_result in zip(transcript.utterances, transcript.sentiment_analysis):
            result_data.append({
                'speaker': utterance.speaker,
                'start': format_timestamp(utterance.start),
                'end': format_timestamp(utterance.end),
                'transcription': utterance.text,
                'sentiment': sentiment_result.sentiment,
                'confidence': sentiment_result.confidence
            })

        summary = str(transcript.summary) if transcript.summary else None

    # Render the template with the results
    return render_template('index.html', result_data=result_data, summary=summary, media_file=MEDIA_FILE_PATH)

# ... (existing code)

@app.route('/upload', methods=['POST'])
def upload_file():
    uploaded_file = request.files['videoFile']

    if uploaded_file.filename != '':
        # Create a directory to store uploaded files if it doesn't exist
        upload_directory = "uploads"  # Update this to your desired directory name
        os.makedirs(upload_directory, exist_ok=True)

        # Save the uploaded file to the specified directory
        temp_file_path = os.path.join(upload_directory, "uploaded_video.mp4")
        uploaded_file.save(temp_file_path)

        # Update MEDIA_FILE_PATH with the new uploaded file
        global MEDIA_FILE_PATH
        MEDIA_FILE_PATH = temp_file_path

        # Upload the file to Google Drive
        drive_file_id = upload_to_google_drive(temp_file_path)

        # Get a shareable link for the uploaded file
        global MEDIA_FILE_URL
        MEDIA_FILE_URL = get_google_drive_link(drive_file_id)

        # Perform transcription using AssemblyAI with the file link
        global transcript
        transcript = transcribe_video(MEDIA_FILE_URL)

    # Redirect to the home page after uploading
    return redirect(url_for('index'))

@app.route('/media')
def media():
    return send_file(MEDIA_FILE_PATH)

if __name__ == '__main__':
    app.run(debug=True)
