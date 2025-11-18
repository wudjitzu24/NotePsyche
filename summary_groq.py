import os
import datetime
import time
import random
from groq import Groq
import vosk
import wave
import json
from pydub import AudioSegment

# === KONFIGURACJA ===
NOTES_FOLDER = "notes_data"
SUMMARY_FOLDER = "summary_data"
os.makedirs(SUMMARY_FOLDER, exist_ok=True)

MODEL_PATH = "/home/przemek/note_app/vosk-model-small-pl-0.22"
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Nie znaleziono modelu Vosk w {MODEL_PATH}")
vosk_model = vosk.Model(MODEL_PATH)
print("Model Vosk załadowany poprawnie!")

MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
# Opcjonalny fallback model (mniejszy) jeśli masz go w środowisku
FALLBACK_MODEL = os.environ.get("GROQ_FALLBACK_MODEL")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise SystemExit("Brak GROQ_API_KEY w środowisku. Ustaw: export GROQ_API_KEY=...")
client = Groq(api_key=GROQ_API_KEY)

# === UTILITY ===
def convert_m4a_to_wav(m4a_path):
    wav_path = m4a_path.rsplit(".", 1)[0] + ".wav"
    audio = AudioSegment.from_file(m4a_path, format="m4a")
    audio.export(wav_path, format="wav")
    return wav_path

def transcribe_audio(audio_path):
    wf = wave.open(audio_path, "rb")
    rec = vosk.KaldiRecognizer(vosk_model, wf.getframerate())
    result_text = ""
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            result_text += " " + res.get("text", "")
    res = json.loads(rec.FinalResult())
    result_text += " " + res.get("text", "")
    wf.close()
    return result_text.strip()

def read_all_notes(folder):
    all_notes = ""
    if not os.path.isdir(folder):
        return all_notes

    for fname in sorted(os.listdir(folder)):
        fpath = os.path.join(folder, fname)
        if not os.path.isfile(fpath):
            continue

        if fname.lower().endswith(".txt"):
            with open(fpath, "r", encoding="utf-8") as fh:
                txt = fh.read().strip()
                if txt:
                    all_notes += f"\n---\n{fname} (txt):\n{txt}\n"
        elif fname.lower().endswith(".m4a"):
            try:
                wav_path = convert_m4a_to_wav(fpath)
                txt = transcribe_audio(wav_path)
                all_notes += f"\n---\n{fname} (audio):\n{txt}\n"
            except Exception as e:
                print(f"Błąd przy przetwarzaniu {fname}: {e}")
    return all_notes

def extract_choice_text(response):
    try:
        choice = response.choices[0]
    except Exception:
        return str(response)
    msg = getattr(choice, "message", None)
    if msg is None:
        try:
            msg = choice.get("message") if isinstance(choice, dict) else None
        except Exception:
            msg = None
    if isinstance(msg, dict):
        if "content" in msg:
            content = msg["content"]
            if isinstance(content, dict):
                return content.get("text") or (content.get("parts") and " ".join(content.get("parts"))) or str(content)
            return content
    else:
        text = getattr(msg, "content", None) or getattr(msg, "text", None)
        if text is not None:
            return text
    text = getattr(choice, "text", None) or getattr(choice, "message_content", None)
    if text:
        return text
    return str(response)

# === NOWE: dzielenie na kawałki + hierarchiczne podsumowanie ===
def chunk_text(text, max_chars=15000):
    """
    Dzieli text na kawałki nie większe niż max_chars (stara metoda prostego dzielenia po znakach).
    Możemy później ulepszyć do dzielenia po akapitach.
    """
    chunks = []
    start = 0
    L = len(text)
    while start < L:
        end = min(L, start + max_chars)
        # spróbuj pociąć do końca akapitu, jeśli to możliwe
        if end < L:
            next_newline = text.rfind("\n", start, end)
            if next_newline > start:
                end = next_newline
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]

def summarize_chunk(text_chunk, model=MODEL, max_tokens=800):
    """
    Wywołanie pojedynczego podsumowania z retry i backoffem.
    Zwraca tekst podsumowania lub rzuca wyjątek po przekroczeniu prób.
    """
    prompt = (
        "Przeczytaj poniższe notatki i stwórz krótkie (2-4 akapity) podsumowanie oraz 5 kluczowych obserwacji:\n\n"
        f"{text_chunk}\n\n"
        "Wynik podaj w czytelnym, wypunktowanym formacie."
    )

    max_attempts = 5
    base_sleep = 5  # sekundy
    for attempt in range(1, max_attempts+1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            return extract_choice_text(resp)
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = "rate limit" in err_str or "429" in err_str or "tokens" in err_str and "limit" in err_str
            # dłuższe czekanie przy 429
            if is_rate_limit:
                sleep_time = 60 * attempt + random.uniform(0, 10)  # rosnąco: 60s, 120s, 180s...
                print(f"[WARN] Wykryto limit (429). Próba {attempt}/{max_attempts}. Czekam {int(sleep_time)}s przed retry.")
            else:
                # wykładniczy backoff z jitter
                sleep_time = base_sleep * (2 ** (attempt - 1)) + random.uniform(0, 3)
                print(f"[WARN] Błąd wywołania Groq (próba {attempt}/{max_attempts}): {e}. Czekam {int(sleep_time)}s.")
            time.sleep(sleep_time)

            # Jeżeli mamy fallback model i to nie była ostatnia próba, spróbuj zmniejszyć model
            if FALLBACK_MODEL and attempt >= 3:
                print(f"[INFO] Próba użycia fallback modelu: {FALLBACK_MODEL}")
                model = FALLBACK_MODEL

    raise RuntimeError("Nie udało się wygenerować podsumowania po kilku próbach.")

def summarize_hierarchical(full_text, chunk_chars=15000, max_tokens_chunk=800, final_max_tokens=900):
    """
    Dla długich notatek: dzieli, podsumowuje każdy kawałek, łączy krótkie podsumowania i generuje finalne podsumowanie.
    """
    chunks = chunk_text(full_text, max_chars=chunk_chars)
    print(f"[INFO] Podzielono na {len(chunks)} chunk(ów).")
    if len(chunks) == 1:
        return summarize_chunk(chunks[0], max_tokens=max_tokens_chunk)

    # 1) Podsumuj każdy chunk osobno
    chunk_summaries = []
    for i, c in enumerate(chunks, start=1):
        print(f"[INFO] Podsumowuję chunk {i}/{len(chunks)} (ok. {len(c)} znaków)...")
        s = summarize_chunk(c, max_tokens=max_tokens_chunk)
        chunk_summaries.append(f"Chunk {i} podsumowanie:\n{s}")

    # 2) Połącz krótkie podsumowania i zrób finalne podsumowanie
    combined = "\n\n".join(chunk_summaries)
    final_prompt_preamble = (
        "Masz poniżej zebrane krótkie podsumowania części notatek. Stwórz z nich jedno spójne, krótkie podsumowanie i 5 najważniejszych obserwacji/akcji.\n\n"
    )
    final_text = final_prompt_preamble + combined
    print("[INFO] Tworzę finalne podsumowanie z podsumowań częściowych...")
    final_summary = summarize_chunk(final_text, max_tokens=final_max_tokens)
    return final_summary

def cleanup_notes(folder):
    for fname in os.listdir(folder):
        fpath = os.path.join(folder, fname)
        if os.path.isfile(fpath):
            os.remove(fpath)
    print(f"✅ Folder {folder} wyczyszczony.")

# === MAIN ===
def main():
    # 1️⃣ Pobierz notatki z Google Drive
    print("Pobieram pliki z Google Drive...")
    from gdrive_fetch import fetch_notes_from_drive
    fetch_notes_from_drive()  # <- zamiast gdrive_fetch.main()

    # 2️⃣ Wczytaj notatki + audio i transkrypcje
    notes = read_all_notes(NOTES_FOLDER)
    if not notes:
        print("Brak notatek do przetworzenia.")
        return

    # 3️⃣ Wysyłamy do Groq (hierarchiczne)
    print("Wysyłam dane do modelu:", MODEL)
    try:
        result = summarize_hierarchical(notes, chunk_chars=15000, max_tokens_chunk=800, final_max_tokens=900)
    except Exception as e:
        print(f"[ERROR] Nie udało się wygenerować podsumowania: {e}")
        return

    # 4️⃣ Zapis podsumowania z timestampem
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    summary_file = os.path.join(SUMMARY_FOLDER, f"summary_{timestamp}.txt")
    with open(summary_file, "w", encoding="utf-8") as fh:
        fh.write(result)

    print(f"✅ Gotowe — podsumowanie zapisane w {summary_file}")
    print("\n=== PODSUMOWANIE (preview) ===\n")
    print(result[:2000])

    # 5️⃣ Czyścimy folder z notatkami
    cleanup_notes(NOTES_FOLDER)

if __name__ == "__main__":
    main()
