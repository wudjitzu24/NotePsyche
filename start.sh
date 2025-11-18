#!/bin/bash
# Uruchomienie serwera
uvicorn main:app --reload &
# Uruchomienie ngrok
ngrok http 8000