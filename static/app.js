console.log('=== app.js LOADED ===');

document.addEventListener("DOMContentLoaded", function() {
    console.log('=== DOMContentLoaded fired ===');
    
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const lastAnalysisBtn = document.getElementById('lastAnalysisBtn');
    const listAnalysesBtn = document.getElementById('listAnalysesBtn');
    const statusDiv = document.getElementById('status');
    const analysisFrame = document.getElementById('analysisFrame');
    const previewAudio = document.getElementById('preview');
    
    // Auth UI elements
    const loginRegisterBtn = document.getElementById('loginRegisterBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const authModal = document.getElementById('authModal');
    const authModalClose = document.getElementById('authModalClose');
    const authUsername = document.getElementById('authUsername');
    const authPassword = document.getElementById('authPassword');
    const authSubmitBtn = document.getElementById('authSubmitBtn');
    const authToggleBtn = document.getElementById('authToggleBtn');
    const authError = document.getElementById('authError');
    const authStatus = document.getElementById('authStatus');
    
    console.log('All elements found');
    
    let mediaRecorder;
    let audioChunks = [];
    let isRegistering = false;
    let authToken = localStorage.getItem('authToken');
    let loggedInUsername = localStorage.getItem('loggedInUsername');
    
    // Initialize: check if already logged in
    function updateAuthUI() {
        if (authToken && loggedInUsername) {
            authStatus.textContent = `Zalogowany: ${loggedInUsername}`;
            loginRegisterBtn.style.display = 'none';
            logoutBtn.style.display = 'inline-block';
            startBtn.disabled = false;
        } else {
            authStatus.textContent = 'Zaloguj się, aby nagrywać';
            loginRegisterBtn.style.display = 'inline-block';
            logoutBtn.style.display = 'none';
            startBtn.disabled = true;
        }
    }
    
    updateAuthUI();
    console.log('Auth UI updated');
    
    // Auth modal handlers
    loginRegisterBtn.addEventListener('click', () => {
        console.log('LOGIN BUTTON CLICKED');
        isRegistering = false;
        authError.textContent = '';
        authUsername.value = '';
        authPassword.value = '';
        authModal.classList.add('show');
    });
    
    authModalClose.addEventListener('click', () => {
        authModal.classList.remove('show');
    });
    
    authModal.addEventListener('click', (e) => {
        if (e.target === authModal) {
            authModal.classList.remove('show');
        }
    });
    
    authToggleBtn.addEventListener('click', (e) => {
        e.preventDefault();
        console.log('TOGGLE BUTTON CLICKED');
        isRegistering = !isRegistering;
        authError.textContent = '';
        
        if (isRegistering) {
            authSubmitBtn.textContent = 'Zarejestruj się';
            authToggleBtn.textContent = 'Masz konto? Zaloguj się';
        } else {
            authSubmitBtn.textContent = 'Zaloguj się';
            authToggleBtn.textContent = 'Nie masz konta? Zarejestruj się';
        }
    });
    
    authSubmitBtn.addEventListener('click', () => {
        console.log('SUBMIT BUTTON CLICKED');
        const username = authUsername.value.trim();
        const password = authPassword.value.trim();
        
        if (!username || !password) {
            authError.textContent = 'Podaj nazwę użytkownika i hasło';
            return;
        }
        
        const endpoint = isRegistering ? '/register' : '/login';
        const params = new URLSearchParams();
        params.append('username', username);
        params.append('password', password);
        
        console.log(`Making request to: ${endpoint}`);
        
        fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: params.toString()
        })
        .then(res => {
            console.log('Response status:', res.status);
            if (!res.ok) {
                return res.text().then(text => {
                    console.error('Error response text:', text);
                    try {
                        const err = JSON.parse(text);
                        throw new Error(err.detail || 'Error: ' + res.status);
                    } catch (e) {
                        if (res.status === 400) {
                            throw new Error(isRegistering ? 'User already exists or invalid credentials' : 'Invalid username or password');
                        }
                        throw new Error('Server error: ' + res.status);
                    }
                });
            }
            return res.json();
        })
        .then(data => {
            console.log('Success! Token:', data.access_token ? 'received' : 'missing');
            authToken = data.access_token;
            loggedInUsername = username;
            localStorage.setItem('authToken', authToken);
            localStorage.setItem('loggedInUsername', username);
            authModal.classList.remove('show');
            updateAuthUI();
            statusDiv.textContent = isRegistering ? '✅ Successfully registered and logged in!' : '✅ Successfully logged in!';
        })
        .catch(err => {
            console.error('Error:', err);
            authError.textContent = err.message;
        });
    });
    
    logoutBtn.addEventListener('click', () => {
        console.log('LOGOUT BUTTON CLICKED');
        authToken = null;
        loggedInUsername = null;
        localStorage.removeItem('authToken');
        localStorage.removeItem('loggedInUsername');
        // Uncheck all analysis checkboxes
        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => checkbox.checked = false);
        // Refresh the page
        window.location.reload();
    });
    
    // Initially disable the analyze button
    analyzeBtn.disabled = true;
    
    // Nagrywanie
    startBtn.addEventListener('click', async () => {
        if (!authToken) {
            statusDiv.textContent = "❌ Zaloguj się, aby nagrywać";
            return;
        }
        
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
            mediaRecorder.onstart = () => {
                statusDiv.textContent = "�� Nagrywanie w toku...";
                startBtn.disabled = true;
                stopBtn.disabled = false;
                previewAudio.style.display = "none";
            };
            mediaRecorder.onstop = async () => {
                statusDiv.textContent = "⏸️ Nagrywanie zakończone.";
                stopBtn.disabled = true;
                startBtn.disabled = false;

                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                previewAudio.src = URL.createObjectURL(audioBlob);
                previewAudio.style.display = "block";

                const formData = new FormData();
                formData.append('file', audioBlob, 'nagranie.webm');

                try {
                    statusDiv.textContent = "📤 Wysyłanie nagrania...";
                    const res = await fetch('/upload_audio', {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'Authorization': `Bearer ${authToken}`
                        }
                    });

                    if (!res.ok) {
                        statusDiv.textContent = `❌ Błąd wysyłki: ${res.status}`;
                        if (res.status === 401) {
                            authToken = null;
                            localStorage.removeItem('authToken');
                            localStorage.removeItem('loggedInUsername');
                            updateAuthUI();
                        }
                        return;
                    }

                    const result = await res.json();
                    statusDiv.textContent = `✅ Plik wysłany: ${result.saved}`;
                    
                    // Poll for summary creation (check every 2 seconds, up to 30 seconds)
                    let attempts = 0;
                    const pollInterval = setInterval(async () => {
                        attempts++;
                        try {
                            const checkRes = await fetch('/check_summary');
                            const checkData = await checkRes.json();
                            if (checkData.has_summary) {
                                clearInterval(pollInterval);
                                analyzeBtn.disabled = false;
                                statusDiv.textContent = `✅ Plik wysłany: ${result.saved}. Podsumowanie gotowe!`;
                            }
                        } catch (err) {
                            // Ignore polling errors
                        }
                        
                        // Stop polling after 30 seconds
                        if (attempts >= 15) {
                            clearInterval(pollInterval);
                        }
                    }, 2000);
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
        analysisFrame.textContent = "📊 Analizuję wszystkie notatki...";
        try {
            const res = await fetch('/list_analyses_content');
            if (!res.ok) throw new Error(`Status ${res.status}`);
            const data = await res.json();
            const text = data.latest_analysis || "Brak analiz do wyświetlenia";
            analysisFrame.textContent = text;
        } catch (err) {
            analysisFrame.textContent = `❌ Błąd ładowania analiz: ${err}`;
        }
    });
    
    // Navigation buttons
    lastAnalysisBtn.addEventListener('click', () => {
        console.log('LAST ANALYSIS BUTTON CLICKED');
        window.location.href = '/last_analysis';
    });
    
    listAnalysesBtn.addEventListener('click', () => {
        console.log('LIST ANALYSES BUTTON CLICKED');
        window.location.href = '/list_analyses';
    });
    
    console.log('=== All event listeners attached ===');
});
