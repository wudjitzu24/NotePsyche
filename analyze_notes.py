import os
import datetime
from main import analyze_single_summary

NOTES_FOLDER = "notes_data"
SUMMARY_FOLDER = "summaries"  # folder na gotowe analizy

def analyze_all_notes():
    os.makedirs(SUMMARY_FOLDER, exist_ok=True)
    
    # lista wszystkich plików .txt w notes_data
    all_files = sorted([f for f in os.listdir(NOTES_FOLDER) if f.endswith(".txt")])
    
    if not all_files:
        print("Brak plików w notes_data do analizy")
        return
    
    combined_results = []
    
    for fname in all_files:
        file_path = os.path.join(NOTES_FOLDER, fname)
        print(f"Analizuję: {fname}")
        try:
            analysis = analyze_single_summary(file_path)
            combined_results.append(f"--- {fname} ---\n{analysis}\n")
        except Exception as e:
            print(f"[Błąd] Nie udało się przeanalizować {fname}: {e}")
    
    # scal wszystkie wyniki w jeden plik
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = os.path.join(SUMMARY_FOLDER, f"combined_analysis_{timestamp}.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(combined_results))
    
    print(f"✅ Analiza zakończona. Zapisano w: {output_file}")

if __name__ == "__main__":
    analyze_all_notes()
