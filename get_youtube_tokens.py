import sys
import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes needed for YouTube uploads
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]

def main():
    print("====================================================")
    print(" YouTube OAuth Token Generator")
    print("====================================================\n")

    client_id = input("Enter your OAuth Client ID: ").strip()
    client_secret = input("Enter your OAuth Client Secret: ").strip()

    if not client_id or not client_secret:
        print("Error: Both Client ID and Client Secret are required.")
        sys.exit(1)

    # Construct the client configuration dict dynamically
    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/"]
        }
    }

    # Start the local server flow to authenticate
    print("\nStarting authorization flow...")
    print("A browser window should open. If it doesn't, copy the link printed in the terminal.")
    
    try:
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        # Using a fixed port to match our redirect URI
        credentials = flow.run_local_server(
            port=8080,
            prompt="consent",
            authorization_prompt_message=""
        )

        print("\n====================================================")
        print(" OAUTH TOKENS GENERATED SUCCESSFULLY!")
        print("====================================================\n")
        print(f"OAuth Access Token:\n{credentials.token}\n")
        print(f"OAuth Refresh Token:\n{credentials.refresh_token}\n")
        print("----------------------------------------------------")
        print("You can copy these tokens and paste them directly")
        print("into 'Section C: Rights & OAuth Credentials' on the dashboard.")
        print("====================================================")

    except Exception as e:
        print(f"\nError running OAuth flow: {e}")
        print("Please ensure your Google Cloud Console project is configured with:")
        print("  - Desktop app type credentials")
        print("  - Authorized redirect URIs: http://localhost:8080/")

if __name__ == "__main__":
    main()
