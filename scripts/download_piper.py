"""
Automated Piper TTS Binary & Voice Models Downloader for Windows
Downloads piper.exe and ONNX neural voice models into models/piper/
"""

import os
import sys
import zipfile
import urllib.request
from pathlib import Path

PIPER_ZIP_URL = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"

VOICE_FILES = [
    # Neutral Narrator
    ("https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/en_US-lessac-high.onnx", "en_US-lessac-high.onnx"),
    ("https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/en_US-lessac-high.onnx.json", "en_US-lessac-high.onnx.json"),
    # Motivational Male
    ("https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx", "en_US-ryan-high.onnx"),
    ("https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx.json", "en_US-ryan-high.onnx.json"),
    # Warm Female
    ("https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx", "en_US-amy-medium.onnx"),
    ("https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json", "en_US-amy-medium.onnx.json"),
]

def download_file(url: str, dest_path: Path):
    if dest_path.exists() and dest_path.stat().st_size > 0:
        print(f"[SKIP] {dest_path.name} already exists.")
        return
    print(f"[DOWNLOADING] {dest_path.name} from {url}...")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp, open(dest_path, 'wb') as out_file:
        chunk = resp.read(1024 * 1024)
        while chunk:
            out_file.write(chunk)
            chunk = resp.read(1024 * 1024)
    print(f"[DONE] {dest_path.name}")

def setup_piper():
    target_dir = Path("models/piper")
    target_dir.mkdir(parents=True, exist_ok=True)

    piper_exe = target_dir / "piper.exe"
    if not piper_exe.exists():
        zip_path = target_dir / "piper_windows_amd64.zip"
        download_file(PIPER_ZIP_URL, zip_path)
        print("[EXTRACTING] piper_windows_amd64.zip...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        # Handle if extracted into a subfolder "piper/"
        nested_piper = target_dir / "piper" / "piper.exe"
        if nested_piper.exists():
            for item in (target_dir / "piper").glob("*"):
                dest = target_dir / item.name
                if not dest.exists():
                    item.rename(dest)
        if zip_path.exists():
            os.remove(zip_path)
        print("[DONE] piper.exe binary extracted cleanly!")

    for url, filename in VOICE_FILES:
        download_file(url, target_dir / filename)

    print("\n[OK] Piper Neural Voice Setup Completed Successfully!")
    print(f"Location: {target_dir.resolve()}")

if __name__ == "__main__":
    setup_piper()
