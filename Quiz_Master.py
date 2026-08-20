"""
Quiz Master — Flet Edition
============================
A mobile-compatible rewrite of the original PyQt6 desktop app using Flet.
Same "Academic Clarity" design system, same screens and flows, but built
with Flet controls so it runs natively on iOS/Android/web/desktop from one
codebase.

Run:
    pip install flet
    flet run Quiz_Master.py          # desktop preview
    flet run --web Quiz_Master.py         # browser preview
    flet build apk / ipa                   # package for mobile

Written against Flet's current control API (Page.show_dialog / pop_dialog,
RadioGroup, PopupMenuButton(content=...), ft.dropdown.Option, etc).
"""

import copy
import json
import pathlib
import random
import threading
import time

import flet as ft

# Local cache file, stored right next to this script (works the same on
# every OS/Flet version — no dependency on Flet's storage controls).
CACHE_FILE = pathlib.Path(__file__).resolve().parent / "quiz_master_cache.json"

try:
    import pyrebase
    PYREBASE_AVAILABLE = True
except ImportError:
    PYREBASE_AVAILABLE = False

# ══════════════════════════════════════════════════════════════════════════
# Academic Clarity Design System Tokens
# ══════════════════════════════════════════════════════════════════════════

BG_APP = "#f8f9ff"
BG_SURFACE = "#ffffff"
SURFACE_LOW = "#eff4ff"
SURFACE_MID = "#e5eeff"
SURFACE_HIGH = "#dce9ff"
PRIMARY = "#00685f"
PRIMARY_CONTAINER = "#008378"
PRIMARY_LIGHT = "#e6f5f3"
SECONDARY = "#4648d4"
SECONDARY_LIGHT = "#eef0ff"
TERTIARY = "#a35532"
TERTIARY_LIGHT = "#fff0eb"
TEXT_ON_SURFACE = "#0b1c30"
TEXT_MUTED = "#6d7a77"
TEXT_VARIANT = "#2d3a4b"
BORDER_COLOR = "#e2e8f0"
SUCCESS = "#00875a"
SUCCESS_CONTAINER = "#e6f8ef"
ERROR = "#ba1a1a"
ERROR_CONTAINER = "#ffdad6"

FONT_FAMILY = "Segoe UI"
LETTERS = ["A", "B", "C", "D", "E", "F"]

CARD_SHADOW = ft.BoxShadow(
    blur_radius=12, offset=ft.Offset(0, 3), color="#00000014"
)


def card(content, padding=16, radius=16, bgcolor=BG_SURFACE,
         border_color=BORDER_COLOR, shadow=True):
    """A bordered, softly-shadowed surface container — the workhorse of the UI."""
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=radius,
        bgcolor=bgcolor,
        border=ft.Border.all(1, border_color) if border_color else None,
        shadow=CARD_SHADOW if shadow else None,
    )


def field_label(text):
    return ft.Text(text, size=13, weight=ft.FontWeight.BOLD, color=TEXT_ON_SURFACE)


def pill(text, fg, bg, size=10):
    return ft.Container(
        content=ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=fg),
        bgcolor=bg, border_radius=6, padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def kebab_menu(items):
    """items: list of (label, on_click) tuples -> a small circular '⋮' popup menu."""
    return ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Text("⋮", size=16, weight=ft.FontWeight.W_900, color=TEXT_ON_SURFACE),
            width=28, height=28, bgcolor=SURFACE_LOW, border_radius=8,
            alignment=ft.Alignment.CENTER,
        ),
        items=[ft.PopupMenuItem(content=ft.Text(label, size=12, weight=ft.FontWeight.BOLD), on_click=cb)
               for label, cb in items],
    )


def hex_to_light_bg(hex_color, blend=0.85):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    lr = int(r + (255 - r) * blend)
    lg = int(g + (255 - g) * blend)
    lb = int(b + (255 - b) * blend)
    return f"#{lr:02x}{lg:02x}{lb:02x}"


def slugify(text):
    """Turn a title into a stable, Firebase-safe key ('World History Quiz' -> 'world_history_quiz')."""
    cleaned = "".join(c if c.isalnum() else "_" for c in text.strip().lower())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "item"


# ══════════════════════════════════════════════════════════════════════════
# Firebase (Realtime Database + Anonymous Auth) — shared cloud sync
# ══════════════════════════════════════════════════════════════════════════
# 1. Create a project at https://console.firebase.google.com (free tier is fine)
# 2. Build > Realtime Database > Create database (start in locked mode)
# 3. Build > Authentication > Sign-in method > enable "Anonymous"
# 4. Project settings > General > Your apps > Add app > Web  -> copy the config below
# 5. Realtime Database > Rules, set:
#    { "rules": { ".read": "auth != null", ".write": "auth != null" } }
# The apiKey below is a public project identifier, not a secret — it's safe to
# ship in the app. The security rules above are what actually protect the data.

FIREBASE_CONFIG = {
    "apiKey": "AIzaSyCp4-T3q_IdXLvNwuZs145KO8FnOLaR4rE",
    "authDomain": "quiz-master-dadf5.firebaseapp.com",
    "databaseURL": "https://quiz-master-dadf5-default-rtdb.firebaseio.com",
    "projectId": "quiz-master-dadf5",
    "storageBucket": "quiz-master-dadf5.firebasestorage.app",
    "appId": "1:15147716655:web:4c4f39120aedbfb370f6da",
}


class CloudStore:
    """Thin wrapper around Firebase Realtime Database + Anonymous Auth.

    Every method is best-effort: if the device is offline, or Firebase hasn't
    been configured yet, calls simply no-op (self.connected stays False) so
    the app keeps working entirely off the local cache.
    """

    def __init__(self, config):
        self.config = config
        self.connected = False
        self.id_token = None
        self.db = None
        self.last_error = None

    def connect(self):
        if not PYREBASE_AVAILABLE:
            self.last_error = "pyrebase4 not installed (pip install pyrebase4)"
            return
        api_key = self.config.get("apiKey", "")
        if not api_key or api_key.startswith("YOUR_"):
            self.last_error = "Firebase not configured yet (edit FIREBASE_CONFIG)"
            return
        try:
            app = pyrebase.initialize_app(self.config)
            user = app.auth().sign_in_anonymous()
            self.id_token = user["idToken"]
            self.db = app.database()
            self.connected = True
        except Exception as e:
            self.last_error = str(e)
            self.connected = False

    def fetch_all(self):
        """Returns (quizzes, drafts, subjects) or None on failure."""
        if not self.connected:
            return None
        try:
            quizzes_raw = self.db.child("quizzes").get(self.id_token).val() or {}
            drafts_raw = self.db.child("drafts").get(self.id_token).val() or {}
            subjects_raw = self.db.child("subjects").get(self.id_token).val()
            quizzes = list(quizzes_raw.values()) if isinstance(quizzes_raw, dict) else []
            drafts = [dict(v, _key=k) for k, v in drafts_raw.items()] if isinstance(drafts_raw, dict) else []
            subjects = subjects_raw if isinstance(subjects_raw, list) else None
            return quizzes, drafts, subjects
        except Exception as e:
            self.last_error = str(e)
            return None

    def save_quiz(self, quiz):
        if not self.connected:
            return
        try:
            self.db.child("quizzes").child(quiz["id"]).set(quiz, self.id_token)
        except Exception as e:
            self.last_error = str(e)

    def delete_quiz(self, quiz_id):
        if not self.connected:
            return
        try:
            self.db.child("quizzes").child(quiz_id).remove(self.id_token)
        except Exception as e:
            self.last_error = str(e)

    def save_draft(self, draft_payload, key):
        if not self.connected:
            return
        try:
            self.db.child("drafts").child(key).set(draft_payload, self.id_token)
        except Exception as e:
            self.last_error = str(e)

    def delete_draft(self, key):
        if not self.connected:
            return
        try:
            self.db.child("drafts").child(key).remove(self.id_token)
        except Exception as e:
            self.last_error = str(e)

    def save_subjects(self, subjects):
        if not self.connected:
            return
        try:
            self.db.child("subjects").set(subjects, self.id_token)
        except Exception as e:
            self.last_error = str(e)


# ══════════════════════════════════════════════════════════════════════════
# Sample Data 
# ══════════════════════════════════════════════════════════════════════════
SAMPLE_QUIZZES = [
    {
        "id": "BIO101", "code": "BIO101", "title": "Cellular Biology Midterm",
        "subject": "Biology", "category": "Science",
        "description": "Covers cellular respiration, photosynthesis, organelle structures, and membrane transport fundamentals.",
        "difficulty": "Intermediate", "time_mins": 15, "edited": "Edited 2h ago",
        "badge_color": PRIMARY, "badge_bg": PRIMARY_LIGHT, "icon": "🔬", "students_taken": 142,
        "questions": [
            {"question": "What is the primary function of mitochondria in a eukaryotic cell?",
             "options": ["Protein synthesis and modification", "Cellular respiration and ATP energy production",
                         "Photosynthesis and glucose storage", "Lipid synthesis and packaging"],
             "correct_index": 1, "explanation": "Mitochondria are known as the powerhouse of the cell, generating most ATP energy."},
            {"question": "Which organelle is primarily responsible for protein synthesis?",
             "options": ["Ribosome", "Lysosome", "Golgi Apparatus", "Vacuole"],
             "correct_index": 0, "explanation": "Ribosomes translate mRNA sequences into polypeptide chains."},
            {"question": "What is the process by which plants convert sunlight into biochemical energy?",
             "options": ["Fermentation", "Glycolysis", "Photosynthesis", "Oxidative Phosphorylation"],
             "correct_index": 2, "explanation": "Photosynthesis captures light energy to produce glucose."},
            {"question": "Which process moves water molecules across a semi-permeable membrane?",
             "options": ["Active Transport", "Endocytosis", "Osmosis", "Phagocytosis"],
             "correct_index": 2, "explanation": "Osmosis is the passive diffusion of water across a semi-permeable membrane."},
            {"question": "Which macromolecule constitutes the primary bilayer of cell membranes?",
             "options": ["Phospholipids", "Polysaccharides", "Triglycerides", "Nucleic Acids"],
             "correct_index": 0, "explanation": "Phospholipids form the foundational phospholipid bilayer of biological membranes."},
        ],
    },
    {
        "id": "MATH101", "code": "MATH101", "title": "Calculus Fundamentals 101",
        "subject": "Mathematics", "category": "Mathematics",
        "description": "Essential limits, derivatives, chain rules, and basic integral calculus applications.",
        "difficulty": "Beginner", "time_mins": 10, "edited": "Edited 1d ago",
        "badge_color": SECONDARY, "badge_bg": SECONDARY_LIGHT, "icon": "📐", "students_taken": 98,
        "questions": [
            {"question": "What is the derivative of f(x) = x³ - 4x + 7 with respect to x?",
             "options": ["3x² - 4", "3x² + 4", "x² - 4", "3x³ - 4x"],
             "correct_index": 0, "explanation": "Using the power rule: d/dx(x³) = 3x² and d/dx(-4x) = -4."},
            {"question": "What is the limit of (sin x) / x as x approaches 0?",
             "options": ["0", "1", "Infinity", "Undefined"],
             "correct_index": 1, "explanation": "The fundamental trigonometric limit is 1."},
            {"question": "What geometric property does the first derivative of a function represent at a point?",
             "options": ["Area under the curve", "Slope of the tangent line", "Curvature of the graph", "Length of the arc"],
             "correct_index": 1, "explanation": "The first derivative represents the instantaneous slope of the tangent line."},
        ],
    },
    {
        "id": "HIST101", "code": "HIST101", "title": "The Industrial Revolution: Key Events",
        "subject": "History", "category": "History",
        "description": "Explore the technological breakthroughs, social transformations, and economic shifts of the 18th-19th centuries.",
        "difficulty": "Beginner", "time_mins": 10, "edited": "Edited 3d ago",
        "badge_color": TERTIARY, "badge_bg": TERTIARY_LIGHT, "icon": "🏛️", "students_taken": 64,
        "questions": [
            {"question": "In which country did the Industrial Revolution initially begin in the mid-18th century?",
             "options": ["France", "Great Britain", "Germany", "United States"],
             "correct_index": 1, "explanation": "Britain had abundant coal, capital, and trade networks."},
            {"question": "Which invention by James Watt greatly accelerated industrial mechanization?",
             "options": ["Cotton Gin", "Improved Steam Engine", "Spinning Jenny", "Telegraph"],
             "correct_index": 1, "explanation": "James Watt's steam engine provided reliable mechanized power."},
        ],
    },
    {
        "id": "CS202", "code": "CS202", "title": "Data Structures: Trees & Graphs",
        "subject": "Computer Science", "category": "Computer Science",
        "description": "Master traversal algorithms, binary search trees, graph representations, and algorithmic time complexity.",
        "difficulty": "Advanced", "time_mins": 25, "edited": "Edited 5d ago",
        "badge_color": PRIMARY, "badge_bg": PRIMARY_LIGHT, "icon": "💻", "students_taken": 115,
        "questions": [
            {"question": "What is the average time complexity for searching in a balanced Binary Search Tree (BST)?",
             "options": ["O(1)", "O(log n)", "O(n)", "O(n log n)"],
             "correct_index": 1, "explanation": "A balanced BST halves the search space at each level, taking O(log n) time."},
            {"question": "Which graph traversal algorithm uses a First-In-First-Out (FIFO) queue?",
             "options": ["Depth-First Search (DFS)", "Breadth-First Search (BFS)", "Dijkstra's with Stack", "Topological Sort with Recursion"],
             "correct_index": 1, "explanation": "BFS explores vertices level by level using a FIFO queue."},
        ],
    },
]

SAMPLE_DRAFTS = [
    {
        "title": "World History Quiz", "subject": "History",
        "description": "Key revolutions and geopolitical treaties of the early modern era.",
        "difficulty": "Medium", "time_mins": 15, "icon": "📄",
        "questions": [
            {"question": "Which historic treaty concluded the Thirty Years' War in 1648?",
             "options": ["Peace of Westphalia", "Treaty of Versailles", "Treaty of Utrecht", "Congress of Vienna"],
             "correct_index": 0, "explanation": "The Peace of Westphalia established the concept of state sovereignty."},
            {"question": "In what year did the French Revolution officially begin with the storming of the Bastille?",
             "options": ["1776", "1789", "1804", "1815"],
             "correct_index": 1, "explanation": "The storming of the Bastille took place on July 14, 1789."},
        ],
    },
    {
        "title": "Physics Lab Safety", "subject": "Science",
        "description": "Essential laboratory safety protocols and emergency guidelines.",
        "difficulty": "Easy", "time_mins": 10, "icon": "📄",
        "questions": [
            {"question": "What is the very first action you should take in case of a chemical spill in the laboratory?",
             "options": ["Immediately notify the instructor", "Try to clean it up with paper towels", "Leave the building", "Pour water on it"],
             "correct_index": 0, "explanation": "Always notify the instructor immediately before taking action."},
        ],
    },
]


# ══════════════════════════════════════════════════════════════════════════
# Main App
# ══════════════════════════════════════════════════════════════════════════
class ProfQuizzerApp:
    def __init__(self, page: ft.Page):
        self.page = page
        page.title = "Quiz Master"
        page.bgcolor = BG_APP
        page.padding = 0
        page.spacing = 0
        page.theme = ft.Theme(font_family=FONT_FAMILY)
        page.window.width = 420
        page.window.height = 860
        page.window.min_width = 340

        # ---- Data (bundled defaults, overridden by local cache / cloud below) ----
        self.quizzes = copy.deepcopy(SAMPLE_QUIZZES)
        self.drafts = copy.deepcopy(SAMPLE_DRAFTS)
        self.subjects = ["Science", "Biology", "Mathematics", "History",
                          "Computer Science", "Literature", "General Knowledge"]

        # ---- Local cache (plain JSON file next to the script) — lets the app
        # work offline and remember your data between launches, before Firebase
        # even connects. Deliberately not using ft.SharedPreferences here: its
        # API differs across Flet versions (sync vs async), so a plain file is
        # more predictable and works the same everywhere.
        self._load_local_cache()

        # ---- Cloud sync (Firebase) — shared data between you and your friends ----
        self.cloud = CloudStore(FIREBASE_CONFIG)
        self.current_route = "dashboard"

        # ---- Session state ----
        self.current_quiz = None
        self.quiz_question_idx = 0
        self.user_answers = []
        self.quiz_seconds_left = 0
        self.quiz_total_seconds = 0
        self.timer_running = False

        # ---- Quiz creation/editing state ----
        self.editing_quiz_id = None
        self.new_quiz_data = self._blank_quiz_data()
        self.current_difficulty = "Medium"
        self.color_choice = PRIMARY
        self.dash_search_text = ""
        self.current_lib_cat = "All Subjects"
        self.lib_search_text = ""
        self.editing_question_idx = None
        self.correct_option_idx = "0"

        # ---- Chrome: body + bottom nav ----
        self.active_nav = 0
        self.body = ft.Container(expand=True)
        self.bottom_nav = self._build_bottom_nav()

        page.add(
            ft.Column([self.body, self.bottom_nav], expand=True, spacing=0)
        )

        self.goto_dashboard()

        # Connect to Firebase and sync in the background so app startup is
        # never blocked waiting on the network.
        threading.Thread(target=self._connect_and_sync, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────
    # Persistence: local cache + cloud sync
    # ──────────────────────────────────────────────────────────────────
    def _load_local_cache(self):
        try:
            if CACHE_FILE.exists():
                data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
                if data.get("quizzes"):
                    self.quizzes = data["quizzes"]
                if data.get("drafts"):
                    self.drafts = data["drafts"]
                if data.get("subjects"):
                    self.subjects = data["subjects"]
        except Exception as e:
            print("Local cache unavailable, using bundled samples:", e)

    def _save_local_cache(self):
        try:
            CACHE_FILE.write_text(
                json.dumps({
                    "quizzes": self.quizzes,
                    "drafts": self.drafts,
                    "subjects": self.subjects,
                }, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            print("Could not write local cache:", e)

    def _connect_and_sync(self):
        self.cloud.connect()
        if not self.cloud.connected:
            print("Cloud sync unavailable:", self.cloud.last_error)
            return
        result = self.cloud.fetch_all()
        if not result:
            return
        quizzes, drafts, subjects = result
        if quizzes:
            self.quizzes = quizzes
        if drafts:
            self.drafts = drafts
        if subjects:
            self.subjects = subjects
        self._save_local_cache()
        self._on_cloud_synced()

    def _on_cloud_synced(self):
        try:
            self.toast("☁ Synced with the cloud")
        except Exception:
            pass
        if self.current_route == "dashboard":
            self._set_body(self.build_dashboard(), active_nav=0)
        elif self.current_route == "library":
            self._set_body(self.build_library(), active_nav=1)

    # ──────────────────────────────────────────────────────────────────
    # Small helpers
    # ──────────────────────────────────────────────────────────────────
    def _blank_quiz_data(self):
        return {
            "title": "", "subject": "Science", "description": "",
            "time_mins": 15, "difficulty": "Medium", "cover_color": PRIMARY,
            "questions": [],
        }

    def toast(self, message, bgcolor=PRIMARY):
        self.page.overlay.append(
            ft.SnackBar(content=ft.Text(message, color="white"), bgcolor=bgcolor, open=True)
        )
        self.page.update()

    def dialog_info(self, title, message):
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=lambda e: self.page.pop_dialog())],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def dialog_confirm(self, title, message, on_yes):
        def _yes(e):
            self.page.pop_dialog()
            on_yes()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=ft.Text(message),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton("Yes", on_click=_yes,
                                style=ft.ButtonStyle(bgcolor=PRIMARY, color="white")),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def dialog_text_input(self, title, hint, on_submit):
        tf = ft.TextField(hint_text=hint, autofocus=True)

        def _submit(e):
            val = (tf.value or "").strip()
            self.page.pop_dialog()
            if val:
                on_submit(val)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title, weight=ft.FontWeight.BOLD),
            content=tf,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton("Add", on_click=_submit,
                                style=ft.ButtonStyle(bgcolor=PRIMARY, color="white")),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def avatar(self, text="P", size=34, color=PRIMARY):
        return ft.CircleAvatar(
            content=ft.Text(text, color="white", weight=ft.FontWeight.BOLD, size=size * 0.4),
            bgcolor=color, radius=size / 2,
        )

    def circular_progress(self, pct=80, size=170):
        return ft.Stack(
            [
                ft.ProgressRing(value=pct / 100, width=size, height=size,
                                 stroke_width=12, color=PRIMARY, bgcolor=SURFACE_HIGH),
                ft.Container(
                    content=ft.Text(f"{int(pct)}%", size=26, weight=ft.FontWeight.BOLD, color=TEXT_ON_SURFACE),
                    width=size, height=size, alignment=ft.Alignment.CENTER,
                ),
            ],
            width=size, height=size,
        )

    # ──────────────────────────────────────────────────────────────────
    # Header + Bottom Nav
    # ──────────────────────────────────────────────────────────────────
    
    def build_header(self, title, subtitle=None, show_back=False, on_back=None):
        left_controls = []

        if show_back:
            left_controls.append(
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                    icon_size=18,
                    icon_color=PRIMARY,
                    on_click=on_back,
                )
            )

        title_column = ft.Column(
            [
                ft.Text(title, size=20, weight=ft.FontWeight.BOLD, color=PRIMARY),
                *( [ft.Text(subtitle, size=12, color=TEXT_MUTED)] if subtitle else [] )
            ],
            spacing=2,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        left_controls.append(title_column)

        right_controls = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.NOTIFICATIONS_OUTLINED,
                    icon_color=PRIMARY,
                    icon_size=22,
                    on_click=lambda e: self.toast("No new notifications"),
                ),
                ft.Container(
                    content=ft.CircleAvatar(
                        content=ft.Text("PQ", size=12, weight=ft.FontWeight.BOLD, color="white"),
                        bgcolor=PRIMARY,
                        radius=16,
                    ),
                    on_click=lambda e: self.toast("Profile clicked"),
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            content=ft.Row(
                [
                    ft.Row(left_controls, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(expand=True),
                    right_controls,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=20, vertical=12),
            bgcolor=BG_SURFACE,
        )

    def _build_bottom_nav(self):
        self.nav_home_btn = self._nav_button("🏠", "Home", 0, self.goto_dashboard)
        self.nav_lib_btn = self._nav_button("📚", "Library", 1, self.goto_library)
        self.nav_prof_btn = self._nav_button("👤", "Profile", 2, self._show_profile)
        row = ft.Row(
            [self.nav_home_btn, self.nav_lib_btn, self.nav_prof_btn],
            spacing=12,
        )
        return ft.Container(
            content=row, height=68, padding=ft.Padding.symmetric(horizontal=16, vertical=6),
            bgcolor=BG_SURFACE, border=ft.Border.only(top=ft.BorderSide(1, BORDER_COLOR)),
        )

    def _nav_button(self, icon, label, idx, on_click):
        active = self.active_nav == idx
        return ft.Container(
            content=ft.Row(
                [ft.Text(icon, size=14), ft.Text(label, size=13,
                                                  weight=ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL,
                                                  color="white" if active else TEXT_MUTED)],
                alignment=ft.MainAxisAlignment.CENTER, spacing=6,
            ),
            bgcolor=PRIMARY if active else "transparent",
            border_radius=14, height=44, expand=True, alignment=ft.Alignment.CENTER,
            on_click=lambda e: on_click(), ink=True,
            data=idx,
        )

    def _refresh_bottom_nav(self):
        for idx, btn in [(0, self.nav_home_btn), (1, self.nav_lib_btn), (2, self.nav_prof_btn)]:
            active = self.active_nav == idx
            btn.bgcolor = PRIMARY if active else "transparent"
            row = btn.content
            row.controls[0].color = "white" if active else TEXT_MUTED
            row.controls[1].color = "white" if active else TEXT_MUTED
            row.controls[1].weight = ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL
        self.bottom_nav.update()

    def _show_profile(self):
        self.dialog_info(
            "Profile",
            f"Quiz Master Instructor Account\nRole: Academic Professor\n"
            f"Active Quizzes: {len(self.quizzes)}\n"
            f"Total Students: {sum(q.get('students_taken', 0) for q in self.quizzes)}",
        )

    def _set_body(self, control, show_nav=True, active_nav=None):
        self.body.content = control
        self.bottom_nav.visible = show_nav
        if active_nav is not None:
            self.active_nav = active_nav
        self.page.update()

    # ══════════════════════════════════════════════════════════════════
    # SCREEN 1: Dashboard
    # ══════════════════════════════════════════════════════════════════
    def _filtered_dash_quizzes(self):
        t = self.dash_search_text.lower()
        return [q for q in self.quizzes if t in q["title"].lower() or t in q["subject"].lower()]

    def _stat_card(self, icon, value, label, color):
        return card(
            ft.Column([
                ft.Row([ft.Text(icon, size=22), ft.Container(expand=True),
                        ft.Text(value, size=24, weight=ft.FontWeight.W_800, color=color)]),
                ft.Text(label, size=10, weight=ft.FontWeight.W_800, color='black'),
            ], spacing=6),
            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        )

    def build_dashboard(self):
        header = self.build_header("Quiz Master")

        search_field = ft.TextField(
            hint_text="🔍  Search quizzes by title or topic...", value=self.dash_search_text,
            height=46, border_radius=14, border_color=BORDER_COLOR, bgcolor=BG_SURFACE,
            content_padding=ft.Padding.only(left=14), text_size=13, text_style=ft.TextStyle(color="black"),
            on_change=self._on_dash_search,
        )
        search_row = ft.Row(
            [
                ft.Container(content=search_field, expand=True),
                ft.Container(
                    content=ft.Text("⚙", size=18, color=PRIMARY), width=46, height=46,
                    bgcolor=SURFACE_LOW, border=ft.Border.all(1, BORDER_COLOR), border_radius=14,
                    alignment=ft.Alignment.CENTER, on_click=lambda e: self.goto_library(), ink=True,
                ),
            ],
            spacing=8,
        )

        stats_row = ft.Row(
            [
                self._stat_card("📄", str(len(self.quizzes)), "TOTAL QUIZZES", PRIMARY),
                self._stat_card("👥", str(sum(q.get("students_taken", 0) for q in self.quizzes)),
                                 "STUDENTS TAKEN", TERTIARY),
            ],
            spacing=14,
        )
        stats_row.controls[0].expand = True
        stats_row.controls[1].expand = True

        active_header = ft.Row([
            ft.Text("Active Quizzes", size=17, weight=ft.FontWeight.W_800, color="black"),
            ft.Container(expand=True),
            ft.TextButton("View All", on_click=lambda e: self.goto_library(),
                          style=ft.ButtonStyle(color=PRIMARY)),
        ])

        self.quiz_cards_container = ft.Column(self._get_quiz_card_controls(), spacing=12)

        drafts_header = ft.Text("Recent Drafts", size=17, color="black", weight=ft.FontWeight.W_800)
        drafts_row = ft.Row(
            [self._draft_card(d) for d in self.drafts] + [self._add_draft_card()],
            spacing=10, scroll=ft.ScrollMode.AUTO,
        )

        fab = ft.Container(
            content=ft.Icon(ft.Icons.ADD, color="white", size=28),
            width=54, height=54, bgcolor=PRIMARY, border_radius=27,
            alignment=ft.Alignment.CENTER, shadow=CARD_SHADOW, ink=True,
            on_click=lambda e: self.goto_create_setup(),
        )

        content = ft.ListView(
            controls=[
                search_row, stats_row, active_header, self.quiz_cards_container,
                drafts_header, ft.Container(content=drafts_row, height=125),
                ft.Container(height=60),
            ],
            spacing=18, padding=ft.Padding.symmetric(horizontal=20, vertical=16), expand=True,
        )

        return ft.Stack(
    [
        ft.Column([header, content], expand=True, spacing=0),
        ft.Container(
            content=fab,
            right=20,  # Positioned 20px from right
            bottom=20,  # Positioned 20px from bottom
        ),
    ],
    expand=True,
)

    def _get_quiz_card_controls(self):
        filtered = self._filtered_dash_quizzes()
        if filtered:
            return [self._dashboard_quiz_card(q) for q in filtered]
        return [ft.Text("No active quizzes match your search.", color='TEXT_MUTED', size=13)]

    def _on_dash_search(self, e):
        self.dash_search_text = e.control.value or ""
        self.quiz_cards_container.controls = self._get_quiz_card_controls()
        self.quiz_cards_container.update()

    def _dashboard_quiz_card(self, q):
        top_row = ft.Row([
            pill(q["subject"].upper(), q.get("badge_color", PRIMARY), q.get("badge_bg", PRIMARY_LIGHT)),
            ft.Text(f"{len(q['questions'])} Questions", size=11, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
            ft.Container(expand=True),
            kebab_menu([
                ("✏️  Edit Quiz", lambda e, qz=q: self.open_quiz_editor(qz)),
                ("🗑️  Delete Quiz", lambda e, qz=q: self._confirm_delete_quiz(qz)),
            ]),
        ])
        bottom_row = ft.Row([
            ft.Text(f"🕐 {q.get('edited', 'Recently')}  ·  ⏱ {q.get('time_mins', 15)}m",
                    size=11, weight=ft.FontWeight.W_500, color=TEXT_MUTED),
            ft.Container(expand=True),
            ft.Container(
                content=ft.Text("▶ Take Quiz", size=11, weight=ft.FontWeight.BOLD, color="white"),
                bgcolor=PRIMARY, border_radius=8, padding=ft.Padding.symmetric(horizontal=12, vertical=5),
                on_click=lambda e, qz=q: self.open_quiz_intro(qz), ink=True,
            ),
        ])
        return card(ft.Column([
            top_row,
            ft.Text(q["title"], size=15, weight=ft.FontWeight.W_800, color=TEXT_ON_SURFACE),
            bottom_row,
        ], spacing=8), padding=ft.Padding.symmetric(horizontal=16, vertical=12))

    def _draft_card(self, d):
        q_len = len(d.get("questions", []))
        return ft.Container(
            width=145, height=115, bgcolor=BG_SURFACE, border_radius=14,
            border=ft.Border.all(1, BORDER_COLOR), padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            content=ft.Column([
                ft.Row([
                    ft.Text(d.get("icon", "📄"), size=18),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Text("✕", size=10, weight=ft.FontWeight.BOLD, color=TEXT_MUTED),
                        on_click=lambda e, dd=d: self._delete_draft(dd), ink=True,
                    ),
                ]),
                ft.Text(d.get("title", "Draft"), size=11, weight=ft.FontWeight.W_800,
                        color=TEXT_ON_SURFACE, max_lines=2),
                ft.Text(f"{q_len} Questions added" if q_len else "Empty draft",
                        size=9, color=TEXT_MUTED, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=ft.Text("Resume →", size=10, weight=ft.FontWeight.BOLD, color=PRIMARY),
                    bgcolor=PRIMARY_LIGHT, border_radius=6, height=22, alignment=ft.Alignment.CENTER,
                    on_click=lambda e, dd=d: self.open_draft_in_maker(dd), ink=True,
                ),
            ], spacing=2),
        )

    def _add_draft_card(self):
        return ft.Container(
            width=100, height=115, bgcolor=SURFACE_LOW, border_radius=14,
            border=ft.Border.all(2, BORDER_COLOR),
            content=ft.Column(
                [ft.Text("+", size=20, color=PRIMARY, weight=ft.FontWeight.BOLD),
                 ft.Text("New Quiz", size=12, color=PRIMARY, weight=ft.FontWeight.BOLD)],
                alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=lambda e: self.goto_create_setup(), ink=True,
        )

    def _delete_draft(self, draft):
        def do_delete():
            self.drafts = [d for d in self.drafts if d is not draft]
            self._save_local_cache()
            key = draft.get("_key") or slugify(draft.get("title", "draft"))
            threading.Thread(target=self.cloud.delete_draft, args=(key,), daemon=True).start()
            self._set_body(self.build_dashboard())
        self.dialog_confirm("Delete Draft", f"Remove draft '{draft.get('title', 'Untitled')}'?", do_delete)

    def open_draft_in_maker(self, draft):
        self.editing_quiz_id = None
        self.new_quiz_data = {
            "title": draft.get("title", ""), "subject": draft.get("subject", "General Knowledge"),
            "description": draft.get("description", ""), "time_mins": draft.get("time_mins", 15),
            "difficulty": draft.get("difficulty", "Medium"), "cover_color": PRIMARY,
            "questions": [dict(q) for q in draft.get("questions", [])],
        }
        self.current_difficulty = self.new_quiz_data["difficulty"]
        self.color_choice = PRIMARY
        if self.new_quiz_data["questions"]:
            self.goto_add_questions()
        else:
            self.goto_create_setup(reset=False)

    def _confirm_delete_quiz(self, quiz):
        def do_delete():
            self.quizzes = [q for q in self.quizzes if q["id"] != quiz["id"]]
            self._save_local_cache()
            threading.Thread(target=self.cloud.delete_quiz, args=(quiz["id"],), daemon=True).start()
            self._set_body(self.build_dashboard())
            self.toast(f"'{quiz['title']}' has been deleted.", bgcolor=ERROR)
        self.dialog_confirm("Delete Quiz", f"Are you sure you want to delete '{quiz['title']}'?\nThis cannot be undone.", do_delete)

    # ══════════════════════════════════════════════════════════════════
    # SCREEN 2: Library
    # ══════════════════════════════════════════════════════════════════
    def build_library(self):
        header = self.build_header("Quiz Library", subtitle="All Quizzes & Subjects",
                                    show_back=True, on_back=self.goto_dashboard)

        self.code_input = ft.TextField(
            hint_text="Enter Quiz Code (e.g. BIO101, MATH101)", height=44,
            border_radius=12, bgcolor=SURFACE_LOW, border_color=BORDER_COLOR,
            content_padding=ft.Padding.only(left=12), text_size=13, text_style=ft.TextStyle(color="black"),
        )
        join_card = card(ft.Column([
            ft.Text("Join Live Session", size=15, weight=ft.FontWeight.W_800),
            ft.Row([
                ft.Container(content=self.code_input, expand=True),
                ft.Container(
                    content=ft.Text("Join", size=13, weight=ft.FontWeight.BOLD, color="white"),
                    width=70, height=44, bgcolor=PRIMARY, border_radius=12,
                    alignment=ft.Alignment.CENTER, on_click=self._handle_join_quiz, ink=True,
                ),
            ], spacing=8),
        ], spacing=8))

        chips = self._library_chip_row()
        search_field = ft.TextField(
            hint_text="🔍  Search topics, subjects...", value=self.lib_search_text,
            height=42, border_radius=12, border_color=BORDER_COLOR, bgcolor=BG_SURFACE,
            content_padding=ft.Padding.only(left=12), text_size=13, text_style=ft.TextStyle(color="black"),
            on_change=self._on_lib_search,
        )

        self.lib_cards_container = ft.Column(
          self._get_library_card_controls(), spacing=12
        )

        fab = ft.Container(
            content=ft.Icon(ft.Icons.ADD, color="white", size=28),
            width=54, height=54, bgcolor=PRIMARY, border_radius=27,
            alignment=ft.Alignment.CENTER, shadow=CARD_SHADOW, ink=True,
            on_click=lambda e: self.goto_create_setup(),
        )

        content = ft.ListView(
            controls=[join_card, chips, search_field, self.lib_cards_container, ft.Container(height=60)],
            spacing=16, padding=ft.Padding.symmetric(horizontal=20, vertical=16), expand=True,
        )

        return ft.Stack(
    [
        ft.Column([header, content], expand=True, spacing=0),
        ft.Container(
            content=fab,
            right=20,
            bottom=20,
        ),
    ],
    expand=True,
)

    def _library_chip_row(self):
        cats = ["All Subjects"] + sorted(set(self.subjects))
        chips = []
        for cat in cats:
            active = cat == self.current_lib_cat
            chips.append(
                ft.Container(
                    content=ft.Text(cat, size=11, weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_600,
                                     color="white" if active else TEXT_VARIANT),
                    bgcolor=PRIMARY if active else BG_SURFACE,
                    border=None if active else ft.Border.all(1, BORDER_COLOR),
                    border_radius=14, padding=ft.Padding.symmetric(horizontal=14, vertical=6),
                    on_click=lambda e, c=cat: self._filter_library_by_cat(c), ink=True,
                )
            )
        chips.append(
            ft.Container(
                content=ft.Text("+ New Subject", size=11, weight=ft.FontWeight.BOLD, color=PRIMARY),
                bgcolor=PRIMARY_LIGHT, border=ft.Border.all(1, PRIMARY), border_radius=14,
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                on_click=lambda e: self._prompt_add_custom_subject(), ink=True,
            )
        )
        return ft.Row(chips, spacing=8, scroll=ft.ScrollMode.AUTO)

    def _filter_library_by_cat(self, cat):
        self.current_lib_cat = cat
        self._set_body(self.build_library(), active_nav=1)

    def _on_lib_search(self, e):
        self.lib_search_text = e.control.value or ""
        self.lib_cards_container.controls = self._get_library_card_controls()
        self.lib_cards_container.update()

    def _prompt_add_custom_subject(self):
        def added(subj):
            if subj not in self.subjects:
                self.subjects.append(subj)
                self._save_local_cache()
                threading.Thread(target=self.cloud.save_subjects, args=(list(self.subjects),), daemon=True).start()
            self.toast(f"Subject '{subj}' is now available!")
            self._set_body(self.build_library(), active_nav=1)
        self.dialog_text_input("Add New Subject", "Enter custom subject name", added)

    def _get_library_card_controls(self):
      results = []
      for q in self.quizzes:
        if (
            self.current_lib_cat != "All Subjects"
            and q["subject"].lower() != self.current_lib_cat.lower()
        ):
          continue
        if (
            self.lib_search_text
            and self.lib_search_text.lower() not in q["title"].lower()
            and self.lib_search_text.lower() not in q["subject"].lower()
        ):
          continue
        results.append(self._library_quiz_card(q))

      if not results:
        return [
            ft.Text(
                "No quizzes match this filter.", color=TEXT_MUTED, size=13
            )
        ]
      return results

    def _library_quiz_card(self, q):
        top_row = ft.Row([
            pill(q["subject"].upper(), q.get("badge_color", PRIMARY), q.get("badge_bg", PRIMARY_LIGHT)),
            ft.Container(expand=True),
            ft.Text(f"Code: {q.get('code', q['id'])}", size=10, weight=ft.FontWeight.BOLD, color=TEXT_MUTED),
            kebab_menu([
                ("✏️  Edit Quiz", lambda e, qz=q: self.open_quiz_editor(qz)),
                ("🗑️  Delete Quiz", lambda e, qz=q: self._confirm_delete_quiz(qz)),
            ]),
        ])
        meta_row = ft.Row([
            ft.Text(f"⏱ {q.get('time_mins', 15)} Mins", size=11, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
            ft.Text(f"📊 {q.get('difficulty', 'Intermediate')}", size=11, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
            ft.Container(expand=True),
            ft.Container(
                content=ft.Text("Start Quiz →", size=11, weight=ft.FontWeight.BOLD, color="white"),
                bgcolor=PRIMARY, border_radius=8, padding=ft.Padding.symmetric(horizontal=14, vertical=5),
                on_click=lambda e, qz=q: self.open_quiz_intro(qz), ink=True,
            ),
        ])
        return card(ft.Column([
            top_row,
            ft.Text(q["title"], size=15, weight=ft.FontWeight.W_800, color=TEXT_ON_SURFACE),
            ft.Text(q.get("description", ""), size=12, color=TEXT_VARIANT),
            meta_row,
        ], spacing=8), padding=ft.Padding.symmetric(horizontal=16, vertical=14))

    def _handle_join_quiz(self, e):
        code = (self.code_input.value or "").strip().upper()
        if not code:
            self.dialog_info("Quiz Code", "Please enter a valid quiz code.")
            return
        match = next((q for q in self.quizzes if q["code"].upper() == code or q["id"].upper() == code), None)
        if match:
            self.open_quiz_intro(match)
        else:
            self.dialog_info("Not Found", f"No quiz found with code '{code}'. Try BIO101, MATH101, HIST101, or CS202.")

    # ══════════════════════════════════════════════════════════════════
    # SCREEN 3: Create/Edit Quiz
    # ══════════════════════════════════════════════════════════════════
    def goto_create_setup(self, reset=True):
        self.editing_quiz_id = None
        if reset:
            self.new_quiz_data = self._blank_quiz_data()
            self.current_difficulty = "Medium"
            self.color_choice = PRIMARY
        self._set_body(self.build_create_setup(), show_nav=False)

    def open_quiz_editor(self, quiz):
        self.editing_quiz_id = quiz["id"]
        self.new_quiz_data = {
            "id": quiz["id"], "title": quiz["title"], "subject": quiz["subject"],
            "description": quiz.get("description", ""), "time_mins": quiz.get("time_mins", 15),
            "difficulty": quiz.get("difficulty", "Medium"), "cover_color": quiz.get("badge_color", PRIMARY),
            "questions": [dict(item) for item in quiz["questions"]],
        }
        self.current_difficulty = self.new_quiz_data["difficulty"]
        self.color_choice = self.new_quiz_data["cover_color"]
        self._set_body(self.build_create_setup(), show_nav=False)

    def build_create_setup(self):
        header = self.build_header("Setup Quiz", subtitle="Step 1 of 3: Quiz Basics",
                                    show_back=True, on_back=self.goto_dashboard)
        progress = ft.ProgressBar(value=0.33, height=4, color=PRIMARY, bgcolor=SURFACE_LOW)

        # Added color="black"
        self.input_new_title = ft.TextField(
            value=self.new_quiz_data.get("title", ""), hint_text="e.g. Introduction to Organic Chemistry",
            height=44, border_radius=12, border_color=BORDER_COLOR, content_padding=ft.Padding.only(left=12),
            color="black",
        )

        # Added color="black"
        self.combo_subject = ft.Dropdown(
            value=self.new_quiz_data.get("subject", "Science"),
            options=[ft.dropdown.Option(s) for s in self.subjects],
            height=44, border_radius=12, border_color=BORDER_COLOR,
            color="black",
        )
        add_custom_btn = ft.TextButton(
            "+ Type Custom Subject", on_click=lambda e: self._prompt_add_subject_inline(),
            style=ft.ButtonStyle(color=PRIMARY),
        )

        # Added color="black"
        self.input_new_desc = ft.TextField(
            value=self.new_quiz_data.get("description", ""),
            hint_text="Briefly describe what this quiz covers and instructions for students...",
            multiline=True, min_lines=3, max_lines=4, border_radius=12, border_color=BORDER_COLOR,
            color="black",
        )

        basics_card = card(ft.Column([
            ft.Text("Quiz Basics", size=16, weight=ft.FontWeight.W_800, color=PRIMARY),
            field_label("Quiz Title"), self.input_new_title,
            ft.Row([field_label("Subject Category"), ft.Container(expand=True), add_custom_btn]),
            self.combo_subject,
            field_label("Description (Optional)"), self.input_new_desc,
        ], spacing=8))

        # Cover color swatches
        colors = [PRIMARY, SECONDARY, TERTIARY, "#8e44ad"]
        self.color_swatches = []
        swatch_row = []
        for c in colors:
            selected = c == self.color_choice
            sw = ft.Container(
                width=40, height=40, bgcolor=c, border_radius=20,
                border=ft.Border.all(2, "white" if not selected else TEXT_ON_SURFACE),
                content=ft.Text("✓", color="white", weight=ft.FontWeight.BOLD) if selected else None,
                alignment=ft.Alignment.CENTER,
                on_click=lambda e, col=c: self._select_cover_color(col), ink=True,
                data=c,
            )
            self.color_swatches.append(sw)
            swatch_row.append(sw)

        # Difficulty toggle
        self.diff_buttons = {}
        diff_row = []
        for d in ["Easy", "Medium", "Hard"]:
            active = d == self.current_difficulty
            btn = ft.Container(
                content=ft.Text(d, size=13, weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_600,
                                 color="white" if active else TEXT_ON_SURFACE),
                bgcolor=PRIMARY if active else SURFACE_LOW,
                border=None if active else ft.Border.all(1, BORDER_COLOR),
                border_radius=10, height=38, expand=True, alignment=ft.Alignment.CENTER,
                on_click=lambda e, lvl=d: self._select_difficulty(lvl), ink=True,
            )
            self.diff_buttons[d] = btn
            diff_row.append(btn)

        # Added color="black"
        self.input_new_time = ft.TextField(
            value=str(self.new_quiz_data.get("time_mins", 15)), height=44,
            border_radius=12, border_color=BORDER_COLOR, content_padding=ft.Padding.only(left=12),
            keyboard_type=ft.KeyboardType.NUMBER,
            color="black",
        )

        settings_card = card(ft.Column([
            ft.Text("Visuals & Rules", size=16, weight=ft.FontWeight.W_800, color=PRIMARY),
            field_label("Cover Color Theme"), ft.Row(swatch_row, spacing=10),
            field_label("Difficulty Level"), ft.Row(diff_row, spacing=8),
            field_label("Time Limit (Minutes)"), self.input_new_time,
        ], spacing=8))

        next_btn = ft.Container(
            content=ft.Text("Continue to Questions →", size=15, weight=ft.FontWeight.BOLD, color="white"),
            bgcolor=PRIMARY, border_radius=14, height=50, alignment=ft.Alignment.CENTER,
            on_click=lambda e: self._validate_and_goto_add_questions(), ink=True,
        )

        content = ft.ListView(
            controls=[basics_card, settings_card, next_btn],
            spacing=16, padding=ft.Padding.symmetric(horizontal=20, vertical=16), expand=True,
        )
        return ft.Column([header, progress, content], expand=True, spacing=0)

    def _prompt_add_subject_inline(self):
        def added(subj):
            if subj not in self.subjects:
                self.subjects.append(subj)
                self._save_local_cache()
                threading.Thread(target=self.cloud.save_subjects, args=(list(self.subjects),), daemon=True).start()
            self.combo_subject.options = [ft.dropdown.Option(s) for s in self.subjects]
            self.combo_subject.value = subj
            self.combo_subject.update()
        self.dialog_text_input("Add New Subject", "Enter custom subject name", added)

    def _select_cover_color(self, color):
        self.color_choice = color
        for sw in self.color_swatches:
            selected = sw.data == color
            sw.border = ft.Border.all(2, "white" if not selected else TEXT_ON_SURFACE)
            sw.content = ft.Text("✓", color="white", weight=ft.FontWeight.BOLD) if selected else None
            sw.update()

    def _select_difficulty(self, diff):
        self.current_difficulty = diff
        for d, btn in self.diff_buttons.items():
            active = d == diff
            btn.bgcolor = PRIMARY if active else SURFACE_LOW
            btn.border = None if active else ft.Border.all(1, BORDER_COLOR)
            btn.content.value = d
            btn.content.color = "white" if active else TEXT_ON_SURFACE
            btn.content.weight = ft.FontWeight.BOLD if active else ft.FontWeight.W_600
            btn.update()

    def _validate_and_goto_add_questions(self):
        title = (self.input_new_title.value or "").strip()
        if not title:
            self.dialog_info("Title Required", "Please enter a quiz title before proceeding.")
            return
        subject_text = (self.combo_subject.value or "").strip() or "General Knowledge"
        if subject_text not in self.subjects:
            self.subjects.append(subject_text)
        try:
            time_m = int((self.input_new_time.value or "15").strip())
        except ValueError:
            time_m = 15

        self.new_quiz_data["title"] = title
        self.new_quiz_data["subject"] = subject_text
        self.new_quiz_data["description"] = (self.input_new_desc.value or "").strip()
        self.new_quiz_data["time_mins"] = max(1, time_m)
        self.new_quiz_data["difficulty"] = self.current_difficulty
        self.new_quiz_data["cover_color"] = self.color_choice
        self.new_quiz_data.setdefault("questions", [])

        self.goto_add_questions()

    # ══════════════════════════════════════════════════════════════════
    # SCREEN 4: Add / Edit Questions
    # ══════════════════════════════════════════════════════════════════
    def goto_add_questions(self):
        self.editing_question_idx = None
        self._set_body(self.build_add_questions(), show_nav=False)

    def build_add_questions(self):
        header = self.build_header("Manage Questions", subtitle="Step 2 of 3: Add & Edit Questions",
                                    show_back=True, on_back=self.goto_create_setup_from_step2)
        progress = ft.ProgressBar(value=0.66, height=4, color=PRIMARY, bgcolor=SURFACE_LOW)

        q_count = len(self.new_quiz_data.get("questions", []))
        self.existing_q_header = ft.Text(f"Questions in this Quiz ({q_count}):", size=15,
                                          weight=ft.FontWeight.W_800, color=PRIMARY)
        self.existing_q_list = ft.Column(self._build_existing_question_rows(), spacing=8)

        self.q_form_header = ft.Text(
            f"Editing Question #{self.editing_question_idx + 1}" if self.editing_question_idx is not None
            else "+ Add New Question", size=15, weight=ft.FontWeight.W_800, color=PRIMARY,
        )

        # Added color="black"
        self.input_question_text = ft.TextField(
            hint_text="Type question prompt here...", multiline=True, min_lines=3, max_lines=4,
            border_radius=12, border_color=BORDER_COLOR, color="black",
        )
        q_card = card(ft.Column([field_label("Question Prompt"), self.input_question_text], spacing=8))

        self.opt_inputs = []
        self.opt_tags = []
        self.opt_rows = []
        radios_col = []
        for i in range(4):
            radio = ft.Radio(value=str(i))
            tag = ft.Container(
                content=ft.Text(f" {LETTERS[i]} ", size=12, weight=ft.FontWeight.W_800, color=PRIMARY),
                bgcolor=SURFACE_LOW, border_radius=6, padding=ft.Padding.symmetric(horizontal=6, vertical=4),
            )
            # Added color="black"
            opt_edit = ft.TextField(hint_text=f"Option {LETTERS[i]} text...", height=40,
                                     border_radius=10, border_color=BORDER_COLOR,
                                     content_padding=ft.Padding.only(left=12), expand=True, color="black")
            self.opt_inputs.append(opt_edit)
            self.opt_tags.append(tag)
            row = ft.Container(
                content=ft.Row([radio, tag, opt_edit], spacing=8),
                border_radius=10, border=ft.Border.all(1.5, "transparent"), padding=ft.Padding.symmetric(horizontal=4),
            )
            self.opt_rows.append(row)
            radios_col.append(row)

        self.radio_group = ft.RadioGroup(
            content=ft.Column(radios_col, spacing=6), value=self.correct_option_idx,
            on_change=self._on_correct_radio_change,
        )
        opt_card = card(ft.Column([
            field_label("Options (select the radio button for the correct answer)"),
            self.radio_group,
        ], spacing=10))

        add_more_btn = ft.Container(
            content=ft.Text("+ Save & Add Question to Quiz", size=13, weight=ft.FontWeight.BOLD, color=PRIMARY),
            bgcolor=SURFACE_LOW, border=ft.Border.all(2, PRIMARY), border_radius=12,
            height=46, alignment=ft.Alignment.CENTER, on_click=lambda e: self._save_question_and_add_another(), ink=True,
        )
        review_btn = ft.Container(
            content=ft.Text("Review & Save Quiz →", size=15, weight=ft.FontWeight.BOLD, color="white"),
            bgcolor=PRIMARY, border_radius=14, height=50, alignment=ft.Alignment.CENTER,
            on_click=lambda e: self._save_question_and_review(), ink=True,
        )

        content = ft.ListView(
            controls=[
                self.existing_q_header, self.existing_q_list,
                ft.Container(height=1, bgcolor=BORDER_COLOR),
                self.q_form_header, q_card, opt_card, add_more_btn, review_btn,
            ],
            spacing=14, padding=ft.Padding.symmetric(horizontal=20, vertical=16), expand=True,
        )
        return ft.Column([header, progress, content], expand=True, spacing=0)

    def goto_create_setup_from_step2(self):
        self._set_body(self.build_create_setup(), show_nav=False)

    def _on_correct_radio_change(self, e):
        self.correct_option_idx = e.control.value
        self._refresh_option_row_styles()

    def _refresh_option_row_styles(self):
        theme_color = self.new_quiz_data.get("cover_color", PRIMARY)
        light_bg = hex_to_light_bg(theme_color)
        checked_idx = int(self.correct_option_idx)
        for i, (row, tag, inp) in enumerate(zip(self.opt_rows, self.opt_tags, self.opt_inputs)):
            is_checked = i == checked_idx
            if is_checked:
                row.bgcolor = light_bg
                row.border = ft.Border.all(1.5, theme_color)
                tag.bgcolor = theme_color
                tag.content.color = "white"
                inp.border_color = theme_color
                inp.border_width = 2
            else:
                row.bgcolor = None
                row.border = ft.Border.all(1.5, "transparent")
                tag.bgcolor = SURFACE_LOW
                tag.content.color = TEXT_MUTED
                inp.border_color = BORDER_COLOR
                inp.border_width = 1
            row.update()
            tag.update()
            inp.update()

    def _build_existing_question_rows(self):
        questions = self.new_quiz_data.get("questions", [])
        if not questions:
            return [ft.Text("No questions added yet. Use the form below to add questions.",
                             size=12, italic=True, color=TEXT_MUTED)]
        rows = []
        for idx, q in enumerate(questions):
            rows.append(
                ft.Container(
                    bgcolor=BG_SURFACE, border=ft.Border.all(1, BORDER_COLOR), border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    content=ft.Row([
                        ft.Text(f"Q{idx + 1}: {q['question']}", size=12, color=TEXT_ON_SURFACE, expand=True),
                        kebab_menu([
                            ("✏️  Edit Question", lambda e, i=idx: self._load_question_for_editing(i)),
                            ("🗑️  Delete Question", lambda e, i=idx: self._delete_question_from_new_quiz(i)),
                        ]),
                    ]),
                )
            )
        return rows

    def _refresh_existing_questions(self):
        q_count = len(self.new_quiz_data.get("questions", []))
        self.existing_q_header.value = f"Questions in this Quiz ({q_count}):"
        self.existing_q_list.controls = self._build_existing_question_rows()
        self.existing_q_header.update()
        self.existing_q_list.update()

    def _load_question_for_editing(self, q_idx):
        questions = self.new_quiz_data.get("questions", [])
        if not (0 <= q_idx < len(questions)):
            return
        target = questions[q_idx]
        self.input_question_text.value = target["question"]
        for i, opt in enumerate(self.opt_inputs):
            opt.value = target["options"][i] if i < len(target["options"]) else ""
        corr = target.get("correct_index", 0)
        self.correct_option_idx = str(corr if corr < len(self.opt_inputs) else 0)
        self.radio_group.value = self.correct_option_idx
        self.new_quiz_data["questions"].pop(q_idx)
        self.editing_question_idx = q_idx
        self.q_form_header.value = f"Editing Question #{q_idx + 1}"
        self._refresh_existing_questions()
        self.input_question_text.update()
        for opt in self.opt_inputs:
            opt.update()
        self.radio_group.update()
        self._refresh_option_row_styles()
        self.q_form_header.update()

    def _delete_question_from_new_quiz(self, q_idx):
        if 0 <= q_idx < len(self.new_quiz_data.get("questions", [])):
            self.new_quiz_data["questions"].pop(q_idx)
            self._refresh_existing_questions()

    def _reset_add_question_form(self):
        self.editing_question_idx = None
        self.q_form_header.value = "+ Add New Question"
        self.input_question_text.value = ""
        for opt in self.opt_inputs:
            opt.value = ""
        self.correct_option_idx = "0"
        self.radio_group.value = "0"
        self.q_form_header.update()
        self.input_question_text.update()
        for opt in self.opt_inputs:
            opt.update()
        self.radio_group.update()
        self._refresh_option_row_styles()

    def _extract_current_question(self):
        q_text = (self.input_question_text.value or "").strip()
        if not q_text:
            return None, "Please enter question text."
        options = [inp.value.strip() for inp in self.opt_inputs if (inp.value or "").strip()]
        if len(options) < 2:
            return None, "Please provide at least 2 options for the question."
        correct_idx = int(self.correct_option_idx)
        if correct_idx >= len(options) or correct_idx < 0:
            correct_idx = 0
        return {
            "question": q_text, "options": options, "correct_index": correct_idx,
            "explanation": f"Correct answer is {options[correct_idx]}.",
        }, ""

    def _save_question_and_add_another(self):
        q_obj, err = self._extract_current_question()
        if err:
            self.dialog_info("Invalid Question", err)
            return
        self.new_quiz_data["questions"].append(q_obj)
        self._refresh_existing_questions()
        self._reset_add_question_form()
        self.toast(f"Question saved! Quiz now has {len(self.new_quiz_data['questions'])} questions.")

    def _save_question_and_review(self):
        if (self.input_question_text.value or "").strip():
            q_obj, err = self._extract_current_question()
            if not err and q_obj:
                self.new_quiz_data["questions"].append(q_obj)
        if not self.new_quiz_data.get("questions"):
            self.dialog_info("No Questions", "Please add at least one question to the quiz.")
            return
        self._set_body(self.build_review_publish(), show_nav=False)

    # ══════════════════════════════════════════════════════════════════
    # SCREEN 5: Review & Publish
    # ══════════════════════════════════════════════════════════════════
    def build_review_publish(self):
        header = self.build_header("Review Quiz", subtitle="Step 3 of 3: Summary",
                                    show_back=True, on_back=self.goto_add_questions)
        progress = ft.ProgressBar(value=1.0, height=4, color=PRIMARY, bgcolor=SURFACE_LOW)

        top_card = card(ft.Column([
            ft.Text(self.new_quiz_data.get("title", "Untitled Quiz"), size=16, weight=ft.FontWeight.W_800),
            ft.Text(
                f"Subject: {self.new_quiz_data.get('subject')}  ·  ⏱ {self.new_quiz_data.get('time_mins')} Mins  ·  "
                f"Difficulty: {self.new_quiz_data.get('difficulty')}",
                size=11, color=TEXT_MUTED, weight=ft.FontWeight.W_600,
            ),
        ], spacing=6))

        questions = self.new_quiz_data.get("questions", [])
        q_header = ft.Text(f"Questions to Save ({len(questions)})", size=15, weight=ft.FontWeight.W_800)

        self.review_q_list = ft.Column(self._build_review_question_cards(), spacing=12)

        add_more_btn = ft.Container(
            content=ft.Text("+ Add Another Question", size=13, weight=ft.FontWeight.BOLD, color=PRIMARY),
            bgcolor=SURFACE_LOW, border=ft.Border.all(2, PRIMARY, ), border_radius=12,
            height=44, alignment=ft.Alignment.CENTER, on_click=lambda e: self.goto_add_questions(), ink=True,
        )

        content = ft.ListView(
            controls=[top_card, q_header, self.review_q_list, add_more_btn, ft.Container(height=10)],
            spacing=14, padding=ft.Padding.symmetric(horizontal=20, vertical=16), expand=True,
        )

        draft_btn = ft.Container(
            content=ft.Text("Save Draft", size=13, weight=ft.FontWeight.BOLD, color=PRIMARY),
            bgcolor=SURFACE_LOW, border=ft.Border.all(1, PRIMARY), border_radius=12,
            height=48, expand=True, alignment=ft.Alignment.CENTER,
            on_click=lambda e: self._save_new_quiz_as_draft(), ink=True,
        )
        pub_label = "Update Quiz ✓" if self.editing_quiz_id else "Publish Quiz 🚀"
        pub_btn = ft.Container(
            content=ft.Text(pub_label, size=14, weight=ft.FontWeight.BOLD, color="white"),
            bgcolor=PRIMARY, border_radius=12, height=48, expand=True, alignment=ft.Alignment.CENTER,
            on_click=lambda e: self._publish_new_quiz(), ink=True,
        )
        bottom_bar = ft.Container(
            content=ft.Row([draft_btn, pub_btn], spacing=12),
            height=75, padding=ft.Padding.symmetric(horizontal=20, vertical=10),
            bgcolor=BG_SURFACE, border=ft.Border.only(top=ft.BorderSide(1, BORDER_COLOR)),
        )

        return ft.Column([header, progress, content, bottom_bar], expand=True, spacing=0)

    def _build_review_question_cards(self):
        questions = self.new_quiz_data.get("questions", [])
        cards = []
        for idx, q in enumerate(questions):
            opt_rows = []
            for o_idx, opt in enumerate(q.get("options", [])):
                is_correct = o_idx == q.get("correct_index", 0)
                opt_rows.append(
                    ft.Text(
                        f"[{LETTERS[o_idx]}] {opt}" + ("   ✓ (Correct Answer)" if is_correct else ""),
                        size=12, weight=ft.FontWeight.W_800 if is_correct else ft.FontWeight.W_500,
                        color=SUCCESS if is_correct else TEXT_VARIANT,
                    )
                )
            cards.append(
                card(ft.Column([
                    ft.Row([
                        ft.Text(f"Q{idx + 1}. {q['question']}", size=13, weight=ft.FontWeight.BOLD, expand=True),
                        kebab_menu([
                            ("✏️  Edit in Manager", lambda e, i=idx: self._edit_from_review(i)),
                            ("🗑️  Delete Question", lambda e, i=idx: self._delete_from_review(i)),
                        ]),
                    ]),
                    *opt_rows,
                ], spacing=6), padding=ft.Padding.symmetric(horizontal=14, vertical=12))
            )
        return cards

    def _edit_from_review(self, idx):
        self.goto_add_questions()
        self._load_question_for_editing(idx)

    def _delete_from_review(self, idx):
        if 0 <= idx < len(self.new_quiz_data.get("questions", [])):
            self.new_quiz_data["questions"].pop(idx)
            self._set_body(self.build_review_publish(), show_nav=False)

    def _publish_new_quiz(self):
        if not self.new_quiz_data.get("questions"):
            self.dialog_info("No Questions", "Please add at least one question to the quiz.")
            return
        saved_quiz = None
        if self.editing_quiz_id:
            for i, q in enumerate(self.quizzes):
                if q["id"] == self.editing_quiz_id:
                    self.quizzes[i].update({
                        "title": self.new_quiz_data["title"], "subject": self.new_quiz_data["subject"],
                        "category": self.new_quiz_data["subject"], "description": self.new_quiz_data.get("description", ""),
                        "difficulty": self.new_quiz_data.get("difficulty", "Medium"),
                        "time_mins": self.new_quiz_data.get("time_mins", 15),
                        "badge_color": self.new_quiz_data.get("cover_color", PRIMARY),
                        "edited": "Edited just now",
                        "questions": list(self.new_quiz_data["questions"]),
                    })
                    saved_quiz = self.quizzes[i]
                    break
            msg = f"'{self.new_quiz_data['title']}' has been updated successfully!"
        else:
            new_id = f"QUIZ{random.randint(100, 999)}"
            new_quiz = {
                "id": new_id, "code": new_id, "title": self.new_quiz_data["title"],
                "subject": self.new_quiz_data["subject"], "category": self.new_quiz_data["subject"],
                "description": self.new_quiz_data.get("description", "Created with Quiz Master Studio"),
                "difficulty": self.new_quiz_data.get("difficulty", "Medium"),
                "time_mins": self.new_quiz_data.get("time_mins", 15), "edited": "Just now",
                "badge_color": self.new_quiz_data.get("cover_color", PRIMARY), "badge_bg": PRIMARY_LIGHT,
                "icon": "📝", "students_taken": 0, "questions": list(self.new_quiz_data.get("questions", [])),
            }
            self.quizzes.insert(0, new_quiz)
            saved_quiz = new_quiz
            msg = f"'{self.new_quiz_data['title']}' has been published with Code: {new_id}!"

        self.editing_quiz_id = None
        self._save_local_cache()
        if saved_quiz:
            threading.Thread(target=self.cloud.save_quiz, args=(dict(saved_quiz),), daemon=True).start()
        self.goto_dashboard()
        self.dialog_info("Quiz Saved!", msg)

    def _save_new_quiz_as_draft(self):
        draft_entry = {
            "title": self.new_quiz_data.get("title", "Draft Quiz"), "subject": self.new_quiz_data.get("subject", "General Knowledge"),
            "description": self.new_quiz_data.get("description", ""), "difficulty": self.new_quiz_data.get("difficulty", "Medium"),
            "time_mins": self.new_quiz_data.get("time_mins", 15), "icon": "📄",
            "questions": list(self.new_quiz_data.get("questions", [])),
        }
        key = slugify(draft_entry["title"])
        existing_idx = next((i for i, d in enumerate(self.drafts) if d.get("_key") == key), None)
        draft_entry["_key"] = key
        if existing_idx is not None:
            self.drafts[existing_idx] = draft_entry
        else:
            self.drafts.insert(0, draft_entry)
        self.editing_quiz_id = None
        self._save_local_cache()
        cloud_payload = {k: v for k, v in draft_entry.items() if k != "_key"}
        threading.Thread(target=self.cloud.save_draft, args=(cloud_payload, key), daemon=True).start()
        self.goto_dashboard()
        self.dialog_info("Saved", f"'{draft_entry['title']}' saved to Recent Drafts!")

    # ══════════════════════════════════════════════════════════════════
    # SCREEN 6: Quiz Intro
    # ══════════════════════════════════════════════════════════════════
    def open_quiz_intro(self, quiz):
        self.current_quiz = quiz
        self._set_body(self.build_intro(), show_nav=False)

    def build_intro(self):
        q = self.current_quiz
        header = self.build_header("Quiz Overview", show_back=True, on_back=self.goto_dashboard)

        hero = card(ft.Column([
            ft.Container(
                content=ft.Text(q.get("icon", "📝"), size=32), width=70, height=70,
                bgcolor=SURFACE_LOW, border_radius=35, alignment=ft.Alignment.CENTER,
            ),
            # Added color="black"
            ft.Text(q["title"], size=20, weight=ft.FontWeight.W_800, color="black", text_align=ft.TextAlign.CENTER),
            ft.Text(q.get("description", "Comprehensive academic quiz."), size=13, color=TEXT_VARIANT,
                    text_align=ft.TextAlign.CENTER),
            ft.Container(
                bgcolor=SURFACE_LOW, border_radius=14, padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                content=ft.Column([
                    ft.Text(f"📋  {len(q['questions'])} Questions  ·  Multiple Choice", size=12,
                            weight=ft.FontWeight.W_800, color=PRIMARY),
                    ft.Text(f"⏱  {q.get('time_mins', 15)} Minutes  ·  Timed Assessment", size=12,
                            weight=ft.FontWeight.W_600),
                    ft.Text(f"📊  {q.get('difficulty', 'Intermediate')} Level", size=12, weight=ft.FontWeight.W_600),
                ], spacing=8),
            ),
            ft.Container(
                content=ft.Text("Start Quiz Now  ▶", size=16, weight=ft.FontWeight.BOLD, color="white"),
                bgcolor=PRIMARY, border_radius=14, height=52, alignment=ft.Alignment.CENTER,
                on_click=lambda e: self._start_live_quiz(), ink=True,
            ),
        ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=20, vertical=24), radius=24)

        content = ft.ListView(controls=[hero], padding=ft.Padding.all(24), expand=True)
        return ft.Column([header, content], expand=True, spacing=0)

    # ══════════════════════════════════════════════════════════════════
    # SCREEN 7: Live Quiz Taking
    # ══════════════════════════════════════════════════════════════════
    def _start_live_quiz(self):
        if not self.current_quiz or not self.current_quiz.get("questions"):
            self.dialog_info("Empty Quiz", "This quiz has no questions.")
            return
        self.quiz_question_idx = 0
        self.user_answers = [None] * len(self.current_quiz["questions"])
        self.quiz_total_seconds = self.current_quiz.get("time_mins", 15) * 60
        self.quiz_seconds_left = self.quiz_total_seconds
        self.timer_running = True
        self._set_body(self.build_taking_page(), show_nav=False)
        threading.Thread(target=self._timer_loop, daemon=True).start()

    def _timer_loop(self):
        while self.timer_running and self.quiz_seconds_left > 0:
            time.sleep(1)
            if not self.timer_running:
                return
            self.quiz_seconds_left -= 1
            try:
                mins, secs = divmod(max(0, self.quiz_seconds_left), 60)
                self.lbl_timer.value = f"⏱ {mins:02d}:{secs:02d}"
                self.lbl_timer.update()
            except Exception:
                return
        if self.timer_running and self.quiz_seconds_left <= 0:
            self.timer_running = False
            self._finish_quiz(timed_out=True)

    def build_taking_page(self):
        exit_btn = ft.Container(
            content=ft.Text("✕", size=14, weight=ft.FontWeight.BOLD, color=TEXT_MUTED),
            width=36, height=36, bgcolor=SURFACE_LOW, border_radius=18, alignment=ft.Alignment.CENTER,
            on_click=lambda e: self._prompt_exit_quiz(), ink=True,
        )
        mins, secs = divmod(self.quiz_seconds_left, 60)
        self.lbl_timer = ft.Text(f"⏱ {mins:02d}:{secs:02d}", size=13, weight=ft.FontWeight.BOLD, color=TEXT_ON_SURFACE)
        timer_chip = ft.Container(content=self.lbl_timer, bgcolor=SURFACE_HIGH, border_radius=12,
                                   padding=ft.Padding.symmetric(horizontal=10, vertical=4))
        header = ft.Container(
            height=60, padding=ft.Padding.symmetric(horizontal=16), bgcolor=BG_SURFACE,
            border=ft.Border.only(bottom=ft.BorderSide(1, BORDER_COLOR)),
            content=ft.Row([
                exit_btn, ft.Container(expand=True),
                ft.Text("Quiz Master", size=16, weight=ft.FontWeight.W_800, color=PRIMARY),
                ft.Container(expand=True), timer_chip,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        total = len(self.current_quiz["questions"])
        self.taking_progress = ft.ProgressBar(value=(self.quiz_question_idx + 1) / total, height=4,
                                               color=PRIMARY, bgcolor=SURFACE_LOW)

        self.lbl_q_step = ft.Text(f"QUESTION {self.quiz_question_idx + 1} OF {total}", size=11,
                                   weight=ft.FontWeight.W_800, color=PRIMARY)
        self.lbl_q_text = ft.Text("", size=16, weight=ft.FontWeight.W_800, color=TEXT_ON_SURFACE)

        self.taking_options_col = ft.Column(spacing=10)
        self.btn_next_q_text = ft.Text("Next Question →", size=15, weight=ft.FontWeight.BOLD, color="white")
        self.btn_next_q = ft.Container(
            content=self.btn_next_q_text, bgcolor=PRIMARY, border_radius=12, height=48, expand=True,
            alignment=ft.Alignment.CENTER, on_click=lambda e: self._submit_answer_and_next(), ink=True,
        )
        skip_btn = ft.Container(
            content=ft.Text("Skip", size=13, weight=ft.FontWeight.BOLD, color=PRIMARY),
            border=ft.Border.all(2, PRIMARY), border_radius=12, height=48, width=80,
            alignment=ft.Alignment.CENTER, on_click=lambda e: self._skip_question(), ink=True,
        )
        bottom_bar = ft.Container(
            content=ft.Row([skip_btn, self.btn_next_q], spacing=12),
            height=75, padding=ft.Padding.symmetric(horizontal=20, vertical=10),
            bgcolor=BG_SURFACE, border=ft.Border.only(top=ft.BorderSide(1, BORDER_COLOR)),
        )

        content = ft.ListView(
            controls=[self.lbl_q_step, self.lbl_q_text, self.taking_options_col],
            spacing=14, padding=ft.Padding.symmetric(horizontal=20, vertical=16), expand=True,
        )

        self._render_current_live_question()
        return ft.Column([header, self.taking_progress, content, bottom_bar], expand=True, spacing=0)

    def _render_current_live_question(self):
        questions = self.current_quiz["questions"]
        total = len(questions)
        curr = questions[self.quiz_question_idx]

        self.taking_progress.value = (self.quiz_question_idx + 1) / total
        self.lbl_q_step.value = f"QUESTION {self.quiz_question_idx + 1} OF {total}"
        self.lbl_q_text.value = curr["question"]

        selected_answer = self.user_answers[self.quiz_question_idx]
        self.live_option_buttons = []
        rows = []
        for idx, opt_text in enumerate(curr["options"]):
            row = self._build_live_option(idx, opt_text, selected_answer == idx)
            self.live_option_buttons.append(row)
            rows.append(row)
        self.taking_options_col.controls = rows

        self.btn_next_q_text.value = "Finish Quiz ✓" if self.quiz_question_idx == total - 1 else "Next Question →"

    def _build_live_option(self, idx, text, selected):
        letter = LETTERS[idx] if idx < len(LETTERS) else str(idx)
        if selected:
            bg, border_c, txt_c = PRIMARY_LIGHT, PRIMARY, PRIMARY
        else:
            bg, border_c, txt_c = BG_SURFACE, BORDER_COLOR, TEXT_ON_SURFACE
        return ft.Container(
            content=ft.Text(f"{letter}    {text}", size=13,
                             weight=ft.FontWeight.BOLD if selected else ft.FontWeight.W_500, color=txt_c),
            bgcolor=bg, border=ft.Border.all(2 if selected else 1, border_c), border_radius=14,
            padding=ft.Padding.symmetric(horizontal=14, vertical=16),
            on_click=lambda e, i=idx: self._select_live_option(i), ink=True,
        )

    def _select_live_option(self, opt_idx):
        self.user_answers[self.quiz_question_idx] = opt_idx
        self._render_current_live_question()
        self.taking_options_col.update()
        self.btn_next_q_text.update()

    def _skip_question(self):
        total = len(self.current_quiz["questions"])
        if self.quiz_question_idx < total - 1:
            self.quiz_question_idx += 1
            self._render_current_live_question()
            self.taking_options_col.update()
            self.lbl_q_step.update()
            self.lbl_q_text.update()
            self.taking_progress.update()
            self.btn_next_q_text.update()
        else:
            self._finish_quiz()

    def _submit_answer_and_next(self):
        total = len(self.current_quiz["questions"])
        if self.quiz_question_idx < total - 1:
            self.quiz_question_idx += 1
            self._render_current_live_question()
            self.taking_options_col.update()
            self.lbl_q_step.update()
            self.lbl_q_text.update()
            self.taking_progress.update()
            self.btn_next_q_text.update()
        else:
            self._finish_quiz()

    def _prompt_exit_quiz(self):
        def do_exit():
            self.timer_running = False
            self.goto_dashboard()
        self.dialog_confirm("Exit Quiz?", "Are you sure you want to exit? Your progress will be lost.", do_exit)

    def _finish_quiz(self, timed_out=False):
        self.timer_running = False
        questions = self.current_quiz["questions"]
        correct_count = sum(
            1 for i, q in enumerate(questions)
            if self.user_answers[i] is not None and self.user_answers[i] == q["correct_index"]
        )
        pct = int((correct_count / len(questions)) * 100) if questions else 0
        points = correct_count * 25
        elapsed = self.quiz_total_seconds - self.quiz_seconds_left
        mins, secs = divmod(max(0, elapsed), 60)

        self._set_body(self.build_results_page(pct, correct_count, len(questions), points, f"{mins}m {secs}s"))
        if timed_out:
            self.dialog_info("Time's Up!", "Quiz time has expired. Submitting your answers!")

    # ══════════════════════════════════════════════════════════════════
    # SCREEN 8: Results
    # ══════════════════════════════════════════════════════════════════
    def build_results_page(self, pct, correct, total, points, time_taken_str):
        header = self.build_header("Quiz Results", subtitle="Great effort!")

        top_box = ft.Column([
            ft.Container(content=ft.Text("🏆", size=30), width=64, height=64, bgcolor=SURFACE_LOW,
                         border_radius=32, alignment=ft.Alignment.CENTER),
            ft.Text("Quiz Complete!", size=22, weight=ft.FontWeight.W_800),
        ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        score_card = card(ft.Column([
            self.circular_progress(pct),
            ft.Text(f"{correct}/{total} Correct", size=18, weight=ft.FontWeight.W_800, color=PRIMARY),
            ft.Container(
                content=ft.Text(f"🪙  +{points} Points Earned", size=13, weight=ft.FontWeight.W_800, color=PRIMARY),
                bgcolor=PRIMARY_LIGHT, border_radius=12, padding=ft.Padding.symmetric(horizontal=14, vertical=6),
            ),
        ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.all(20), radius=20)

        def bento(icon_label, value):
            return card(ft.Column([
                ft.Text(icon_label, size=10, weight=ft.FontWeight.BOLD, color=TEXT_MUTED),
                ft.Text(value, size=14, weight=ft.FontWeight.W_800),
            ]), padding=ft.Padding.symmetric(horizontal=12, vertical=10), radius=14)

        bento_row = ft.Row([bento("⏱  TIME TAKEN", time_taken_str), bento("🔥  STREAK", "3 Days")], spacing=10)
        bento_row.controls[0].expand = True
        bento_row.controls[1].expand = True

        review_btn = ft.Container(
            content=ft.Text("👁  Review Answers", size=14, weight=ft.FontWeight.BOLD, color="white"),
            bgcolor=PRIMARY, border_radius=14, height=50, alignment=ft.Alignment.CENTER,
            on_click=lambda e: self._goto_answer_review(), ink=True,
        )
        retake_btn = ft.Container(
            content=ft.Text("🔄  Retake Quiz", size=14, weight=ft.FontWeight.BOLD, color=PRIMARY),
            border=ft.Border.all(2, PRIMARY), border_radius=14, height=48, alignment=ft.Alignment.CENTER,
            on_click=lambda e: self._start_live_quiz(), ink=True,
        )
        home_btn = ft.Container(
            content=ft.Text("🏠  Back to Dashboard", size=13, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
            height=44, alignment=ft.Alignment.CENTER, on_click=lambda e: self.goto_dashboard(), ink=True,
        )

        content = ft.ListView(
            controls=[top_box, score_card, bento_row, review_btn, retake_btn, home_btn],
            spacing=16, padding=ft.Padding.all(24), expand=True,
        )
        self._last_result = (pct, correct, total, points, time_taken_str)
        return ft.Column([header, content], expand=True, spacing=0)

    # ══════════════════════════════════════════════════════════════════
    # SCREEN 9: Answer Review
    # ══════════════════════════════════════════════════════════════════
    def _goto_answer_review(self):
        self._set_body(self.build_answer_review(), show_nav=False)

    def build_answer_review(self):
        header = self.build_header("Answer Breakdown", subtitle="Detailed Review",
                                    show_back=True, on_back=self._back_to_results)

        questions = self.current_quiz["questions"]
        cards = []
        for idx, q in enumerate(questions):
            user_idx = self.user_answers[idx]
            correct_idx = q["correct_index"]
            is_correct = user_idx == correct_idx
            user_ans_text = q["options"][user_idx] if user_idx is not None else "Skipped"

            status = ft.Container(
                content=ft.Text("✓ Correct" if is_correct else "✕ Incorrect", size=11, weight=ft.FontWeight.BOLD,
                                 color=SUCCESS if is_correct else ERROR),
                bgcolor=SUCCESS_CONTAINER if is_correct else ERROR_CONTAINER, border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            )
            children = [
                ft.Row([ft.Text(f"QUESTION {idx + 1}", size=10, weight=ft.FontWeight.BOLD, color=TEXT_MUTED),
                        ft.Container(expand=True), status]),
                ft.Text(q["question"], size=14, weight=ft.FontWeight.W_800),
                ft.Container(
                    content=ft.Text(f"Your Answer: {user_ans_text}", size=12, weight=ft.FontWeight.BOLD,
                                     color=SUCCESS if is_correct else ERROR),
                    bgcolor=SUCCESS_CONTAINER if is_correct else ERROR_CONTAINER, border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                ),
            ]
            if not is_correct:
                children.append(
                    ft.Container(
                        content=ft.Text(f"Correct Answer: {q['options'][correct_idx]}", size=12,
                                         weight=ft.FontWeight.BOLD, color=PRIMARY),
                        bgcolor=SURFACE_LOW, border=ft.Border.all(1, BORDER_COLOR), border_radius=10,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    )
                )
            cards.append(card(ft.Column(children, spacing=8), padding=ft.Padding.symmetric(horizontal=16, vertical=14)))

        back_btn = ft.Container(
            content=ft.Text("Back to Dashboard", size=14, weight=ft.FontWeight.BOLD, color="white"),
            bgcolor=PRIMARY, border_radius=14, height=50, alignment=ft.Alignment.CENTER,
            margin=ft.Margin.symmetric(horizontal=20, vertical=12),
            on_click=lambda e: self.goto_dashboard(), ink=True,
        )

        content = ft.ListView(controls=cards, spacing=14, padding=ft.Padding.symmetric(horizontal=20, vertical=16), expand=True)
        return ft.Column([header, content, back_btn], expand=True, spacing=0)

    def _back_to_results(self):
        pct, correct, total, points, time_taken_str = self._last_result
        self._set_body(self.build_results_page(pct, correct, total, points, time_taken_str))

    # ──────────────────────────────────────────────────────────────────
    # Global Navigation
    # ──────────────────────────────────────────────────────────────────
    def goto_dashboard(self):
        self.editing_quiz_id = None
        self.current_route = "dashboard"
        self._set_body(self.build_dashboard(), show_nav=True, active_nav=0)
        self._refresh_bottom_nav()

    def goto_library(self):
        self.editing_quiz_id = None
        self.current_route = "library"
        self._set_body(self.build_library(), show_nav=True, active_nav=1)
        self._refresh_bottom_nav()


def main(page: ft.Page):
    ProfQuizzerApp(page)


if __name__ == "__main__":
    ft.run(main)