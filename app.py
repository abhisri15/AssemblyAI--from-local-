from flask import Flask, render_template, send_file, request
import assemblyai as aai
import requests
import os
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import google.auth
import io

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

# URL of the audio file to transcribe
MEDIA_FILE_URL = "https://drive.google.com/uc?export=download&id=13jYN1wN_MBUu3a7XKTCna1CpGjr4Nbbv"
# File path for the media file to play
MEDIA_FILE_PATH = "/tmp/20230607_me_canadian_wildfires.mp3"

# Ensure the directory exists
os.makedirs(os.path.dirname(MEDIA_FILE_PATH), exist_ok=True)

# Download the file if it doesn't exist
if not os.path.exists(MEDIA_FILE_PATH):
    print("Downloading the media file...")
    response = requests.get(MEDIA_FILE_URL)
    with open(MEDIA_FILE_PATH, 'wb') as f:
        f.write(response.content)
    print("Download complete.")

# Transcribe the media file
config = aai.TranscriptionConfig(speaker_labels=True, sentiment_analysis=True, summarization=True,
                                 summary_model=aai.SummarizationModel.informative, summary_type=aai.SummarizationType.bullets)
transcriber = aai.Transcriber(config=config)
transcript = transcriber.transcribe(MEDIA_FILE_URL)

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

    summary = str(transcript.summary) if transcript and transcript.summary else None

    return render_template('index.html', result_data=result_data, summary=summary, media_file=MEDIA_FILE_PATH)

@app.route('/upload', methods=['POST'])
def upload_file():
    uploaded_file = request.files['videoFile']

    if uploaded_file.filename != '':
        # Save the uploaded file to a temporary location
        temp_file_path = "uploaded_video.mp4"  # Update this path
        uploaded_file.save(temp_file_path)

        # Upload the file to Google Drive
        drive_file_id = upload_to_google_drive(temp_file_path)

        # Get a shareable link for the uploaded file
        file_link = get_google_drive_link(drive_file_id)

        # Perform transcription using AssemblyAI with the file link
        transcript = transcribe_video(file_link)

        # Initialize variables for result_data and summary
        result_data = []
        summary = None

        # Process the transcript if available
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
        return render_template('index.html', result_data=result_data, summary=summary, media_file=file_link)

    return "File upload failed."

@app.route('/media')
def media():
    return send_file(MEDIA_FILE_PATH)

if __name__ == '__main__':
    app.run(debug=True)
