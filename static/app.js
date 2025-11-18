document.addEventListener("DOMContentLoaded", () => {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const statusDiv = document.getElementById('status');
    const analysisFrame = document.getElementById('analysisFrame');
    const previewAudio = document.getElementById('preview');
    const analyzeDriveBtn = document.getElementById('analyzeDriveBtn');

    let mediaRecorder;
    let audioChunks = [];

    // Nagrywanie
    startBtn.addEventListener('click', async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
            mediaRecorder.onstart = () => {
                statusDiv.textContent = "Nagrywanie w toku...";
                startBtn.disabled = true;
                stopBtn.disabled = false;
                previewAudio.style.display = "none";
            };
            mediaRecorder.onstop = async () => {
                statusDiv.textContent = "Nagrywanie zakończone.";
                stopBtn.disabled = true;
                startBtn.disabled = false;

                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                previewAudio.src = URL.createObjectURL(audioBlob);
                previewAudio.style.display = "block";

                const formData = new FormData();
                formData.append('file', audioBlob, 'nagranie.webm');

                try {
                    statusDiv.textContent = "Wysyłanie nagrania...";
                    const res = await fetch('/upload_audio', { method: 'POST', body: formData });
                    const result = await res.json();
                    statusDiv.textContent = `✅ Plik wysłany: ${result.saved}`;
                } catch (err) {
                    statusDiv.textContent = `❌ Błąd wysyłki: ${err}`;
                }
            };

            mediaRecorder.start();
        } catch (err) {
            statusDiv.textContent = `❌ Brak dostępu do mikrofonu: ${err}`;
        }
    });

    stopBtn.addEventListener('click', () => {
        if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
    });

    // Analiza wszystkich notatek dynamicznie
    analyzeBtn.addEventListener('click', async () => {
        analysisFrame.textContent = "Analizuję wszystkie notatki...";
        try {
            const res = await fetch('/list_analyses_content'); // endpoint, który zwraca analizę
            if (!res.ok) throw new Error(`Status ${res.status}`);
            const data = await res.json();
            const text = data.latest_analysis || "Brak analiz do wyświetlenia";
            analysisFrame.textContent = text;
        } catch (err) {
            analysisFrame.textContent = `❌ Błąd ładowania analiz: ${err}`;
        }
    });
});
