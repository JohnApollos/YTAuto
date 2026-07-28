import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

class QuotaExhaustedError(Exception):
    pass

class YouTubeAPIClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self.credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token"
        )
        self.youtube = build("youtube", "v3", credentials=self.credentials)

    def upload_video(self, video_path: str, title: str, description: str, tags: list = None) -> str:
        """
        Uploads a video to YouTube. 
        Returns the YouTube Video ID on success.
        Raises QuotaExhaustedError if the daily quota is exceeded.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": "22" # People & Blogs by default
            },
            "status": {
                "privacyStatus": "private", # Default to private for safety
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        
        request = self.youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        try:
            print(f"[YouTubeAPIClient] Uploading {video_path}...")
            response = request.execute()
            video_id = response.get("id")
            print(f"[YouTubeAPIClient] Upload successful. Video ID: {video_id}")
            return video_id
        except HttpError as e:
            if e.status_code in [403, 429] and "quota" in str(e).lower():
                raise QuotaExhaustedError("YouTube API daily quota exhausted.") from e
            raise
