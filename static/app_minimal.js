console.log('=== app_minimal.js LOADED ===');

document.addEventListener("DOMContentLoaded", function() {
    console.log('=== DOMContentLoaded fired ===');
    
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
    const statusDiv = document.getElementById('status');
    
    console.log('Elements found:', {
        loginRegisterBtn: !!loginRegisterBtn,
        authModal: !!authModal,
        authSubmitBtn: !!authSubmitBtn
    });
    
    let isRegistering = false;
    let authToken = localStorage.getItem('authToken');
    let loggedInUsername = localStorage.getItem('loggedInUsername');
    
    function updateAuthUI() {
        if (authToken && loggedInUsername) {
            authStatus.textContent = `Zalogowany: ${loggedInUsername}`;
            loginRegisterBtn.style.display = 'none';
            logoutBtn.style.display = 'inline-block';
        } else {
            authStatus.textContent = 'Zaloguj się, aby nagrywać';
            loginRegisterBtn.style.display = 'inline-block';
            logoutBtn.style.display = 'none';
        }
    }
    
    updateAuthUI();
    console.log('Auth UI updated');
    
    // Login/Register button
    loginRegisterBtn.addEventListener('click', function() {
        console.log('LOGIN BUTTON CLICKED');
        isRegistering = false;
        authError.textContent = '';
        authUsername.value = '';
        authPassword.value = '';
        authModal.classList.add('show');
    });
    
    // Close modal
    authModalClose.addEventListener('click', function() {
        console.log('CLOSE BUTTON CLICKED');
        authModal.classList.remove('show');
    });
    
    // Modal background click
    authModal.addEventListener('click', function(e) {
        if (e.target === authModal) {
            authModal.classList.remove('show');
        }
    });
    
    // Toggle button (login/register)
    authToggleBtn.addEventListener('click', function(e) {
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
    
    // Submit button
    authSubmitBtn.addEventListener('click', function() {
        console.log('SUBMIT BUTTON CLICKED');
        const username = authUsername.value.trim();
        const password = authPassword.value.trim();
        
        console.log('Form values:', { username, password });
        
        if (!username || !password) {
            authError.textContent = 'Enter username and password';
            return;
        }
        
        const endpoint = isRegistering ? '/register' : '/login';
        const params = new URLSearchParams();
        params.append('username', username);
        params.append('password', password);
        
        console.log('Making request to:', endpoint);
        
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
                        // If JSON parsing fails, show generic error
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
            statusDiv.textContent = isRegistering ? 'Successfully registered and logged in!' : 'Successfully logged in!';
        })
        .catch(err => {
            console.error('Error:', err);
            authError.textContent = err.message;
        });
    });
    
    // Logout button
    logoutBtn.addEventListener('click', function() {
        console.log('LOGOUT BUTTON CLICKED');
        authToken = null;
        loggedInUsername = null;
        localStorage.removeItem('authToken');
        localStorage.removeItem('loggedInUsername');
        updateAuthUI();
        statusDiv.textContent = 'Logged out';
    });
    
    // Navigation buttons
    const lastAnalysisBtn = document.getElementById('lastAnalysisBtn');
    const listAnalysesBtn = document.getElementById('listAnalysesBtn');
    
    lastAnalysisBtn.addEventListener('click', function() {
        window.location.href = '/last_analysis';
    });
    
    listAnalysesBtn.addEventListener('click', function() {
        window.location.href = '/list_analyses';
    });
});
