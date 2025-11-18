#!/usr/bin/env python3
# main.py - FastAPI backend dla NotePsyche z LangGraph Session Manager

import hashlib
import os, io, json, datetime, wave, shutil
from typing import Optional
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydub import AudioSegment
import vosk
from groq import Groq
from dotenv import load_dotenv
from session_manager import SessionManager

load_dotenv()

# === KONFIGURACJA ===
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOTES_FOLDER = os.path.join(BASE_DIR, "notes_data")
SUMMARY_FOLDER = os.path.join(BASE_DIR, "summary_data")
os.makedirs(NOTES_FOLDER, exist_ok=True)
os.makedirs(SUMMARY_FOLDER, exist_ok=True)

# ensure processed.json exists (we may reset it for new sessions)
PROCESSED_PATH = os.path.join(BASE_DIR, "processed.json")
if not os.path.exists(PROCESSED_PATH):
    with open(PROCESSED_PATH, "w", encoding="utf-8") as f:
        json.dump({}, f)

CHECKPOINT_DIR = os.path.join(BASE_DIR, "checkpoints")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

# Session manager (uses langgraph if available)
SESSION_ID = os.environ.get("SESSION_ID", "default")
session_manager = SessionManager(checkpoints_dir=CHECKPOINT_DIR)

def _cleanup_user_files(clean_dirs, processed_path):
    """Remove files inside the given directories and reset processed.json.

    This deletes only the contents of the configured folders, not the folders themselves.
    """
    for d in clean_dirs:
        try:
            if not os.path.exists(d):
                continue
            for entry in os.listdir(d):
                entry_path = os.path.join(d, entry)
                try:
                    if os.path.islink(entry_path) or os.path.isfile(entry_path):
                        os.remove(entry_path)
                    elif os.path.isdir(entry_path):
                        shutil.rmtree(entry_path)
                except Exception as e:
                    print(f"Warning: could not remove {entry_path}: {e}")
        except Exception as e:
            print(f"Warning: could not cleanup directory {d}: {e}")

    # reset processed.json
    try:
        with open(processed_path, "w", encoding="utf-8") as f:
            json.dump({}, f)
    except Exception as e:
        print(f"Warning: could not reset processed file {processed_path}: {e}")

# create session and perform cleanup when a new session is created
created = session_manager.create_session(SESSION_ID)
if created:
    _cleanup_user_files([
        NOTES_FOLDER,
        SUMMARY_FOLDER,
        os.path.join(BASE_DIR, "drive_notes")
    ], PROCESSED_PATH)

VOSK_MODEL_PATH = os.environ.get("VOSK_MODEL_PATH", os.path.join(BASE_DIR, "vosk-model-small-pl-0.22"))
if not os.path.exists(VOSK_MODEL_PATH):
    raise SystemExit(f"Nie znaleziono modelu Vosk w {VOSK_MODEL_PATH}")

vosk_model = vosk.Model(VOSK_MODEL_PATH)

MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise SystemExit("Brak GROQ_API_KEY w środowisku")

client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="NotePsyche - Audio notes + summaries")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# === POMOCNICZE FUNKCJE ===
def load_checkpoint(session_id: str = SESSION_ID):
    try:
        cp = session_manager.get_checkpoint(session_id)
        if not cp:
            return {"processed_files": []}
        return cp
    except Exception:
        return {"processed_files": []}


def save_checkpoint(data: dict, session_id: str = SESSION_ID):
    try:
        session_manager.save_checkpoint(session_id, data)
    except Exception:
        # best-effort
        pass


def sha256_of_bytes(b: bytes):
    return hashlib.sha256(b).hexdigest()


def load_processed():
    try:
        with open(PROCESSED_PATH, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}


def save_processed(d):
    with open(PROCESSED_PATH, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)


def convert_to_wav_bytes(data: bytes) -> bytes:
    seg = AudioSegment.from_file(io.BytesIO(data))
    seg = seg.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    out = io.BytesIO()
    seg.export(out, format="wav")
    return out.getvalue()


def transcribe_wav_bytes(wav_bytes: bytes) -> str:
    wf = wave.open(io.BytesIO(wav_bytes), "rb")
    rec = vosk.KaldiRecognizer(vosk_model, wf.getframerate())
    rec.SetWords(False)
    text = []
    while True:
        data = wf.readframes(4000)
        if not data: break
        if rec.AcceptWaveform(data):
            try: text.append(json.loads(rec.Result()).get("text", ""))
            except: pass
    try: text.append(json.loads(rec.FinalResult()).get("text", ""))
    except: pass
    wf.close()
    return " ".join(t for t in text if t).strip()


def summarize_text_with_groq(text: str) -> str:
    prompt = (
        "Wyobraź sobie, że jesteś psychologiem i analizujesz nagranie osoby, która mówi o swoich myślach i emocjach.\n"
        "Twoim zadaniem jest:\n"
        "- W delikatny i empatyczny sposób wskaż najważniejsze tematy i wzorce, które pojawiają się w nagraniu..\n"
        "- Podziel się refleksją na temat emocji, nastroju i możliwych wyzwań psychologicznych, które mogą wpływać na samopoczucie rozmówcy..\n"
        "- Zadaj pytania refleksyjne, które pomogą osobie głębiej zrozumieć swoje myśli, uczucia i potrzeby.\n"
        "- Skoncentruj się na wspieraniu, zrozumieniu i budowaniu poczucia bezpieczeństwa, aby osoba czuła się wysłuchana i doceniona.\n"
        "- Formułuj wnioski w przyjaznym, ciepłym tonie, tak jakbyś rozmawiał z pacjentem twarzą w twarz, unikaj sztywnej, akademickiej formy..\n\n"
        f"Nagranie: {text}\n\n"
        "Proszę, odpowiedz w sposób jasny, ciepły i empatyczny, który zachęca do refleksji i samoświadomości, tak jakbyś prowadził rozmowę, która naprawdę pomaga osobie lepiej zrozumieć siebie.."
    )
    resp = client.chat.completions.create(model=MODEL, messages=[{"role":"user","content":prompt}], temperature=0.3, max_tokens=1200)
    try:
        choice = resp.choices[0]
        msg = getattr(choice, "message", None)
        if isinstance(msg, dict):
            content = msg.get("content")
            return content.get("text") if isinstance(content, dict) else str(resp)
        return getattr(msg, "content", None) or getattr(choice, "text", None) or str(resp)
    except Exception:
        return str(resp)


def analyze_single_summary(summary_path: str) -> str:
    with open(summary_path, "r", encoding="utf-8") as f:
        text = f.read()

    prompt = (
        "Jesteś psychologiem. Przeczytaj poniższe notatki podsumowujące "
        "rozmowę pacjenta. Przygotuj analizę w formie zrozumiałych punktów, "
        "zwracając się do pacjenta, tak jakbyś omawiał jego doświadczenia i emocje. "
        "Udziel wskazówek, refleksji i możliwych pytań do dalszej pracy nad sobą.\n\n"
        f"{text}\n\n"
        "Wynik podaj w formie listy punktowanej, przyjaznym tonem."
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25,
            max_tokens=800
        )

        choice = resp.choices[0]
        msg = getattr(choice, "message", None)
        if isinstance(msg, dict):
            content = msg.get("content")
            analysis_text = content.get("text") if isinstance(content, dict) else str(resp)
        else:
            analysis_text = getattr(msg, "content", None) or getattr(choice, "text", None) or str(resp)

    except Exception as e:
        analysis_text = f"[Błąd przy generowaniu analizy: {e}]"

    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    summary_name = os.path.splitext(os.path.basename(summary_path))[0]
    analysis_name = f"analysis_{stamp}_{summary_name}.txt"
    analysis_folder = os.path.dirname(summary_path)
    analysis_path = os.path.join(analysis_folder, analysis_name)

    try:
        with open(analysis_path, "w", encoding="utf-8") as af:
            af.write(analysis_text)
    except Exception as e:
        print(f"Błąd zapisu analizy do pliku: {e}")

    return analysis_text


def process_uploaded_audio(saved_path: str, orig_name: str, compute_summary: bool = True):
    try:
        wav_bytes = convert_to_wav_bytes(open(saved_path, "rb").read())
    except Exception as e:
        print("Konwersja do WAV nie powiodla sie:", e)
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = os.path.splitext(orig_name)[0].replace(" ", "_")
    wav_name = f"{timestamp}_{safe_name}.wav"
    wav_path = os.path.join(NOTES_FOLDER, wav_name)
    with open(wav_path, "wb") as wf: wf.write(wav_bytes)

    try:
        text = transcribe_wav_bytes(wav_bytes)
    except Exception as e:
        print(f"Błąd transkrypcji: {e}")
        text = ""

    transcript_name = f"{safe_name}_{timestamp}.txt"
    transcript_path = os.path.join(NOTES_FOLDER, transcript_name)
    with open(transcript_path, "w", encoding="utf-8") as tf: tf.write(text)

    processed = load_processed()
    try:
        processed[sha256_of_bytes(open(saved_path, "rb").read())] = {
            "orig": orig_name,
            "wav": wav_name,
            "transcript": transcript_name,
            "processed_at": datetime.datetime.now().isoformat()
        }
        save_processed(processed)
        try:
            # update session checkpoint with list of processed file hashes
            save_checkpoint({
                "processed_files": list(processed.keys()),
                "last_processed": datetime.datetime.now().isoformat()
            })
        except Exception:
            pass
    except Exception as e:
        print(f"Błąd zapisu processed: {e}")

    summary_file = None
    if compute_summary:
        try:
            summary_text = summarize_text_with_groq(text if text else "[brak transkrypcji]")
        except Exception as e:
            summary_text = f"[Błąd przy generowaniu summary: {e}]"
        summary_file = os.path.join(SUMMARY_FOLDER, f"summary_{timestamp}_{safe_name}.txt")
        try:
            with open(summary_file, "w", encoding="utf-8") as sf: sf.write(summary_text)
        except Exception as e:
            print(f"Błąd zapisu summary: {e}")

    if summary_file:
        try:
            analysis_text = analyze_single_summary(summary_file)
            analysis_path = os.path.join(SUMMARY_FOLDER, f"analysis_{timestamp}_{safe_name}.txt")
            with open(analysis_path, "w", encoding="utf-8") as af: af.write(analysis_text)
        except Exception as e:
            print(f"[Błąd przy generowaniu analizy: {e}]")


# === ENDPOINTY ===
@app.get("/", response_class=HTMLResponse)
async def index():
    path = os.path.join(BASE_DIR, "static", "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return f.read()
    return HTMLResponse("<h1>NotePsyche</h1><p>Brak pliku static/index.html</p>")


@app.post("/upload_audio")
async def upload_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...), summary: Optional[bool] = True):
    data = await file.read()
    if not data: raise HTTPException(status_code=400, detail="Brak danych audio")
    saved_path = os.path.join(NOTES_FOLDER, f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
    with open(saved_path, "wb") as f: f.write(data)
    background_tasks.add_task(process_uploaded_audio, saved_path, file.filename, summary)
    return {"status": "ok", "saved": file.filename}


@app.get("/list_analyses", response_class=HTMLResponse)
async def list_analyses():
    files = sorted([f for f in os.listdir(SUMMARY_FOLDER) if f.startswith("analysis_") and f.endswith(".txt")],
                   key=lambda f: os.path.getmtime(os.path.join(SUMMARY_FOLDER, f)))
    html_files = "".join(f"<li class='file'>{f}</li>" for f in files)
    return f"""
    <html><body>
    <h2>Lista analiz</h2>
    <ul>{html_files}</ul>
    <button onclick="window.location.href='/'">Powrót do głównej strony</button>
    </body></html>
    """

@app.get("/list_analyses_content")
async def list_analyses_content():
    files = sorted(
        [f for f in os.listdir(SUMMARY_FOLDER) if f.startswith("analysis_") and f.endswith(".txt")],
        key=lambda f: os.path.getmtime(os.path.join(SUMMARY_FOLDER, f))
    )
    if not files:
        return {"latest_analysis": "Brak analiz"}
    latest_file = files[-1]
    with open(os.path.join(SUMMARY_FOLDER, latest_file), "r", encoding="utf-8") as f:
        latest_analysis = f.read()
    return {"latest_analysis": latest_analysis}


@app.get("/last_analysis", response_class=HTMLResponse)
async def last_analysis():
    files = sorted(
        [f for f in os.listdir(SUMMARY_FOLDER) if f.startswith("analysis_") and f.endswith(".txt")],
        key=lambda f: os.path.getmtime(os.path.join(SUMMARY_FOLDER, f))
    )
    if not files:
        content = "Brak analiz"
    else:
        latest_file = files[-1]
        with open(os.path.join(SUMMARY_FOLDER, latest_file), "r", encoding="utf-8") as f:
            content = f.read()

    # Simple HTML page with a back button
    safe_html = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""
    <html><head><meta charset='utf-8'><title>Ostatnia analiza</title></head>
    <body>
    <button onclick="window.location.href='/'">Powrót do strony głównej</button>
    <pre style='white-space:pre-wrap; border:1px solid #ccc; padding:1em; margin-top:1em;'>{safe_html}</pre>
    </body></html>
    """


@app.get("/check_summary")
async def check_summary():
    """Check if a recent summary file exists (created in last 60 seconds)."""
    try:
        files = [f for f in os.listdir(SUMMARY_FOLDER) if f.startswith("summary_") and f.endswith(".txt")]
        if not files:
            return {"has_summary": False}
        
        # Get the most recently modified summary file
        latest_file = max(files, key=lambda f: os.path.getmtime(os.path.join(SUMMARY_FOLDER, f)))
        latest_time = os.path.getmtime(os.path.join(SUMMARY_FOLDER, latest_file))
        current_time = datetime.datetime.now().timestamp()
        
        # Consider a summary "recent" if created within the last 60 seconds
        is_recent = (current_time - latest_time) < 60
        return {"has_summary": is_recent, "file": latest_file}
    except Exception:
        return {"has_summary": False}
