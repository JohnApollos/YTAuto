# First install the OAuth helper: pip install google-auth-oauthlib
from google_auth_oauthlib.flow import InstalledAppFlow

# Request permission to upload videos to your YouTube channel
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def get_tokens():
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret.json', scopes=SCOPES
    )
    # This will open a browser window to authorize your channel account
    credentials = flow.run_local_server(port=0)
    print("\n--- COPY THESE VALUES INTO THE WEB GUI ---")
    print("Access Token:  ", credentials.token)
    print("Refresh Token: ", credentials.refresh_token)

if __name__ == '__main__':
    get_tokens()