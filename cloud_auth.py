import http.server
import json
import secrets
import urllib.parse
import webbrowser

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import pyrebase
    PYREBASE_AVAILABLE = True
except ImportError:
    PYREBASE_AVAILABLE = False

try:
    from firebase_config import FIREBASE_CONFIG, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
except ImportError:
    FIREBASE_CONFIG = {
        "apiKey": "YOUR_API_KEY",
        "authDomain": "YOUR_PROJECT.firebaseapp.com",
        "databaseURL": "https://YOUR_PROJECT-default-rtdb.firebaseio.com",
        "projectId": "YOUR_PROJECT",
        "storageBucket": "YOUR_PROJECT.appspot.com",
        "appId": "YOUR_APP_ID",
    }
    GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"
    GOOGLE_CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
FIREBASE_SIGN_IN_WITH_IDP_ENDPOINT = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp"

OAUTH_CALLBACK_HOST = "localhost"
OAUTH_CALLBACK_PORT = 8551
OAUTH_CALLBACK_PATH = "/oauth2callback"
OAUTH_REDIRECT_URL = f"http://{OAUTH_CALLBACK_HOST}:{OAUTH_CALLBACK_PORT}{OAUTH_CALLBACK_PATH}"


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """One-shot handler that captures ?code=...&state=... from Google's
    redirect, then tells the browser tab it can close itself."""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != OAUTH_CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        self.server.oauth_result = {
            "code": params.get("code", [None])[0],
            "state": params.get("state", [None])[0],
            "error": params.get("error", [None])[0],
        }
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body style='font-family:sans-serif;text-align:center;padding-top:80px;'>"
            b"<h2>Signed in!</h2><p>You can close this window and return to Quiz Master.</p>"
            b"<script>window.close();</script></body></html>"
        )

    def log_message(self, format, *args):
        pass  # silence default per-request console logging


def run_google_oauth_flow(client_id, client_secret, timeout=120, login_hint=None):
    """Blocking. Runs the full Authorization Code flow against Google.
    Returns (id_token, access_token, error). Call this from a background
    thread, never from the UI thread, since it blocks until the user
    finishes (or times out) in their browser.

    login_hint: optional email address passed to Google so it skips the
    account picker and goes straight to that account (used for auto-fallback
    when a user tries email/password on a Google-linked account).
    """
    if not REQUESTS_AVAILABLE:
        return None, None, "The 'requests' package is required (pip install requests)."
    if not client_id or client_id.startswith("YOUR_"):
        return None, None, "Google OAuth isn't configured yet (edit firebase_config.py)."

    state = secrets.token_urlsafe(16)
    params = {
        "client_id": client_id,
        "redirect_uri": OAUTH_REDIRECT_URL,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    if login_hint:
        params["login_hint"] = login_hint
        params["prompt"] = "consent"  # forces re-consent so the hint actually takes effect
    auth_url = f"{GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

    try:
        httpd = http.server.HTTPServer((OAUTH_CALLBACK_HOST, OAUTH_CALLBACK_PORT), _OAuthCallbackHandler)
    except OSError as e:
        return None, None, f"Couldn't start local sign-in listener on port {OAUTH_CALLBACK_PORT}: {e}"

    httpd.oauth_result = None
    httpd.timeout = 1  # seconds per handle_request() poll

    webbrowser.open(auth_url)

    waited = 0
    while httpd.oauth_result is None and waited < timeout:
        httpd.handle_request()
        waited += 1
    httpd.server_close()

    result = httpd.oauth_result
    if result is None:
        return None, None, "Timed out waiting for Google sign-in. Please try again."
    if result.get("error"):
        return None, None, f"Google sign-in was cancelled or denied ({result['error']})."
    if result.get("state") != state:
        return None, None, "Sign-in response failed a security check. Please try again."
    code = result.get("code")
    if not code:
        return None, None, "Google did not return an authorization code."

    try:
        token_resp = requests.post(GOOGLE_TOKEN_ENDPOINT, data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": OAUTH_REDIRECT_URL,
            "grant_type": "authorization_code",
        }, timeout=15)
        token_resp.raise_for_status()
    except Exception as e:
        return None, None, f"Google token exchange failed: {e}"

    token_data = token_resp.json()
    return token_data.get("id_token"), token_data.get("access_token"), None


_run_google_oauth_flow = run_google_oauth_flow

_FIREBASE_ERROR_MESSAGES = {
    "EMAIL_EXISTS": "An account with that email already exists. Try logging in instead.",
    "EMAIL_NOT_FOUND": "No account found with that email. Try signing up instead.",
    "INVALID_PASSWORD": "Incorrect password. Please try again.",
    "INVALID_LOGIN_CREDENTIALS": "Incorrect email or password. Please try again.",
    "USER_DISABLED": "This account has been disabled.",
    "WEAK_PASSWORD": "Password should be at least 6 characters.",
    "INVALID_EMAIL": "That doesn't look like a valid email address.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Please wait a moment and try again.",
}


def _friendly_firebase_error(exc):
    """Turn pyrebase/requests/HTTPError into a safe, readable message without leaking tokens or URLs."""
    raw = str(exc)
    for code, friendly in _FIREBASE_ERROR_MESSAGES.items():
        if code in raw:
            return friendly
    if "Permission denied" in raw or "401" in raw or "403" in raw:
        return "Permission denied or session expired. Please log in again."
    if "ConnectionError" in raw or "timeout" in raw.lower() or "MaxRetryError" in raw:
        return "Network connection issue. Working offline."
    return "Cloud service temporarily unavailable (running in offline mode)."


class CloudStore:
    """Thin wrapper around Firebase Realtime Database + Email/Password Auth.

    Each signed-in user gets their own private subtree at users/{uid}/... in
    the Realtime Database, so accounts never see each other's quizzes.

    Every method is best-effort: if the device is offline, or Firebase hasn't
    been configured yet, calls simply no-op (self.connected stays False) so
    the app keeps working entirely off the local cache.
    """

    def __init__(self, config_dict):
        self.config = config_dict
        self.connected = False
        self.id_token = None
        self.refresh_token = None
        self.uid = None
        self.email = None
        self.db = None
        self.auth = None
        self.last_error = None

    def _init_app(self):
        """Initialize the Firebase app/auth handle (without signing in)."""
        if self.auth is not None and self.db is not None:
            return True
        if not PYREBASE_AVAILABLE:
            self.last_error = "pyrebase4 not installed (pip install pyrebase4)"
            return False
        api_key = self.config.get("apiKey", "")
        if not api_key or api_key.startswith("YOUR_"):
            self.last_error = "Firebase not configured yet (edit firebase_config.py)"
            return False
        try:
            app = pyrebase.initialize_app(self.config)
            self.auth = app.auth()
            self.db = app.database()
            return True
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)
            return False

    def sign_up(self, email, password):
        """Create a brand-new account. Returns (success: bool, error: str|None)."""
        if not self._init_app():
            return False, self.last_error
        try:
            user = self.auth.create_user_with_email_and_password(email, password)
            self.id_token = user["idToken"]
            self.refresh_token = user.get("refreshToken")
            self.uid = user["localId"]
            self.email = email
            self.connected = True
            return True, None
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)
            self.connected = False
            return False, self.last_error

    def sign_in(self, email, password):
        """Log in to an existing account. Returns (success: bool, error: str|None)."""
        if not self._init_app():
            return False, self.last_error
        try:
            user = self.auth.sign_in_with_email_and_password(email, password)
            self.id_token = user["idToken"]
            self.refresh_token = user.get("refreshToken")
            self.uid = user["localId"]
            self.email = email
            self.connected = True
            return True, None
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)
            self.connected = False
            return False, self.last_error

    def send_password_reset(self, email):
        if not self._init_app():
            return False, self.last_error
        try:
            self.auth.send_password_reset_email(email)
            return True, None
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)
            return False, self.last_error

    def sign_in_with_google(self, id_token):
        """Exchanges a Google ID token (from run_google_oauth_flow) for a
        real Firebase session, via Firebase's accounts:signInWithIdp REST
        endpoint. Returns (success, error)."""
        if not self._init_app():
            return False, self.last_error
        if not REQUESTS_AVAILABLE:
            return False, "The 'requests' package is required (pip install requests)."
        api_key = self.config.get("apiKey", "")
        try:
            resp = requests.post(
                f"{FIREBASE_SIGN_IN_WITH_IDP_ENDPOINT}?key={api_key}",
                json={
                    "postBody": f"id_token={id_token}&providerId=google.com",
                    "requestUri": OAUTH_REDIRECT_URL,
                    "returnIdpCredential": True,
                    "returnSecureToken": True,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self.id_token = data["idToken"]
            self.refresh_token = data.get("refreshToken")
            self.uid = data["localId"]
            self.email = data.get("email")
            self.connected = True
            return True, None
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)
            self.connected = False
            return False, self.last_error

    def refresh_session(self, refresh_token, email=None):
        """Exchanges a saved refresh token for a fresh ID token, restoring a
        signed-in session without re-entering credentials. Returns (success, error)."""
        if not self._init_app():
            return False, self.last_error
        if not REQUESTS_AVAILABLE:
            return False, "The 'requests' package is required (pip install requests)."
        api_key = self.config.get("apiKey", "")
        try:
            resp = requests.post(
                f"https://securetoken.googleapis.com/v1/token?key={api_key}",
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self.id_token = data["id_token"]
            self.refresh_token = data.get("refresh_token", refresh_token)
            self.uid = data["user_id"]
            self.email = email
            self.connected = True
            return True, None
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)
            self.connected = False
            return False, self.last_error

    def sign_out(self):
        self.connected = False
        self.id_token = None
        self.refresh_token = None
        self.uid = None
        self.email = None

    def _user_path(self, *subpaths):
        parts = ["users", self.uid] + list(subpaths)
        return "/".join(str(p) for p in parts if p is not None)

    def fetch_all(self):
        """Returns (quizzes, drafts, subjects) or None on failure."""
        if not self.connected or not self.uid:
            return None
        try:
            quizzes_raw = self.db.child(self._user_path("quizzes")).get(self.id_token).val() or {}
            drafts_raw = self.db.child(self._user_path("drafts")).get(self.id_token).val() or {}
            subjects_raw = self.db.child(self._user_path("subjects")).get(self.id_token).val()
            quizzes = list(quizzes_raw.values()) if isinstance(quizzes_raw, dict) else []
            drafts = [dict(v, _key=k) for k, v in drafts_raw.items()] if isinstance(drafts_raw, dict) else []
            subjects = subjects_raw if isinstance(subjects_raw, list) else None
            return quizzes, drafts, subjects
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)
            return None

    def save_quiz(self, quiz):
        if not self.connected or not self.uid:
            return
        try:
            self.db.child(self._user_path("quizzes", quiz["id"])).set(quiz, self.id_token)
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)

    def delete_quiz(self, quiz_id):
        if not self.connected or not self.uid:
            return
        try:
            self.db.child(self._user_path("quizzes", quiz_id)).remove(self.id_token)
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)

    def save_draft(self, draft_payload, key):
        if not self.connected or not self.uid:
            return
        try:
            self.db.child(self._user_path("drafts", key)).set(draft_payload, self.id_token)
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)

    def delete_draft(self, key):
        if not self.connected or not self.uid:
            return
        try:
            self.db.child(self._user_path("drafts", key)).remove(self.id_token)
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)

    def save_subjects(self, subjects):
        if not self.connected or not self.uid:
            return
        try:
            self.db.child(self._user_path("subjects")).set(subjects, self.id_token)
        except Exception as e:
            self.last_error = _friendly_firebase_error(e)
