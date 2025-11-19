#!/usr/bin/env python3
"""Integration test: register/login and upload a generated WAV file.

Usage:
  python3 scripts/integration_test.py --url http://localhost:8000 --username testuser --password secret --register

The script will:
 - optionally register the user (if --register)
 - login and obtain a Bearer token
 - generate a short silent WAV and upload it to /upload_audio with the token
"""
import argparse
import io
import wave
import requests
import random
import string
import sys
import time


def make_silent_wav(duration_s=1, framerate=16000):
    buf = io.BytesIO()
    nframes = int(duration_s * framerate)
    nchannels = 1
    sampwidth = 2
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(nchannels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(framerate)
        wf.writeframes(b'\x00' * nframes * nchannels * sampwidth)
    buf.seek(0)
    return buf


def random_suffix(n=6):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))


def register(url, username, password):
    resp = requests.post(f"{url}/register", data={"username": username, "password": password})
    return resp


def login(url, username, password):
    resp = requests.post(f"{url}/login", data={"username": username, "password": password})
    return resp


def upload(url, token, wav_buf, filename="test.wav"):
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, wav_buf, "audio/wav")}
    # include summary param as form field
    data = {"summary": "true"}
    resp = requests.post(f"{url}/upload_audio", headers=headers, files=files, data=data)
    return resp


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='http://localhost:8000')
    p.add_argument('--username', default=None)
    p.add_argument('--password', default=None)
    p.add_argument('--register', action='store_true')
    p.add_argument('--duration', type=float, default=1.0)
    args = p.parse_args()

    url = args.url.rstrip('/')
    username = args.username or f"test_{random_suffix()}"
    password = args.password or 'testpass'

    print(f"Using server: {url}")
    print(f"User: {username}")

    if args.register:
        print("Registering user...")
        r = register(url, username, password)
        print(r.status_code, r.text)
        if r.status_code >= 400 and r.status_code != 400:
            print("Register request failed; aborting")
            sys.exit(1)
        # if user exists (400), we continue to login

    print("Logging in...")
    r = login(url, username, password)
    print(r.status_code, r.text)
    if r.status_code != 200:
        print("Login failed")
        sys.exit(1)
    token = r.json().get('access_token')
    if not token:
        print('No access_token in login response')
        sys.exit(1)

    print('Generating WAV...')
    wav = make_silent_wav(duration_s=args.duration)

    print('Uploading WAV...')
    r = upload(url, token, wav, filename=f"itest_{int(time.time())}.wav")
    print('Upload response:', r.status_code, r.text)


if __name__ == '__main__':
    main()
