import copy
import json
import random
import threading
import time
import flet as ft

import config
import models
from cloud_auth import CloudStore, FIREBASE_CONFIG, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, run_google_oauth_flow
from components.common import card, pill, kebab_menu, hex_to_light_bg, CARD_SHADOW
from views.auth_view import build_login
from views.dashboard_view import build_dashboard
from views.library_view import build_library
from views.settings_view import build_settings
from views.create_quiz_view import build_create_setup, build_add_questions, build_review_publish
from views.quiz_taking_view import build_intro, build_taking_page, build_results_page, build_answer_review

class ProfQuizzerApp:
    def __init__(self, page: ft.Page):
        self.page = page

        settings = config.load_settings()
        self.dark_mode = bool(settings.get("dark_mode", False))
        self.randomize_questions = bool(settings.get("randomize_questions", False))
        self.default_answer_mode = settings.get("default_answer_mode", "standard")
        self.ui_mode = settings.get("ui_mode", "desktop" if getattr(page, "web", False) else "mobile")
        self.quiz_answering_mode = self.default_answer_mode
        self.question_answer_modes = {}
        config.apply_theme(self.dark_mode)

        page.title = "Quiz Master"
        page.bgcolor = config.SURFACE_MID
        page.padding = 0
        page.spacing = 0
        page.theme = ft.Theme(font_family=config.FONT_FAMILY)
        try:
            page.window.width = 476 if self.ui_mode == "mobile" else 1050
            page.window.height = 860
            page.window.min_width = 356
            page.window.icon = "assets/icon.png"
        except Exception:
            pass

        self.auth_mode = "login"

        self.quizzes = []
        self.drafts = []
        self.subjects = [
            "Science",
            "Biology",
            "Mathematics",
            "History",
            "Computer Science",
            "Literature",
            "General Knowledge",
        ]
        self.cache_file = None

        self.cloud = CloudStore(FIREBASE_CONFIG)
        self.logged_in = False
        self.user_email = None
        self.user_name = None
        self.auth_busy = False
        self.current_route = "login"

        self.current_quiz = None
        self.quiz_question_idx = 0
        self.user_answers = []
        self.quiz_seconds_left = 0
        self.quiz_total_seconds = 0
        self.timer_running = False

        self.editing_quiz_id = None
        self.new_quiz_data = self._blank_quiz_data()
        self.current_difficulty = "Medium"
        self.color_choice = config.PRIMARY
        self.dash_search_text = ""
        self.current_lib_cat = "All Subjects"
        self.lib_search_text = ""
        self.editing_question_idx = None
        self.correct_option_idx = "0"
        self.current_question_type = "multiple_choice"

        self.active_nav = 0
        self.body = ft.Container(expand=True)
        self.bottom_nav = self._build_bottom_nav()

        shell_width = 460 if self.ui_mode == "mobile" else None
        shell_max_width = 460 if self.ui_mode == "mobile" else 1140
        self.app_shell = ft.Container(
            content=ft.Column([self.body, self.bottom_nav], expand=True, spacing=0),
            width=shell_width,
            expand=(self.ui_mode == "desktop"),
            bgcolor=config.BG_APP,
            shadow=CARD_SHADOW,
        )

        page.add(
            ft.Row(
                [self.app_shell],
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                expand=True,
            )
        )
        self._apply_ui_window_mode()
        try:
            page.run_task(page.window.center)
        except Exception:
            pass

        saved_session = config.load_session()
        if saved_session and (saved_session.get("email") or saved_session.get("uid")):
            self.logged_in = True
            self.user_email = saved_session.get("email")
            self.user_name = (self.user_email or "User").split("@")[0]
            self._load_local_cache_for_user(self.user_email or saved_session.get("uid"))
            self.goto_dashboard()
            threading.Thread(target=self._try_auto_login, daemon=True).start()
        else:
            self.goto_login()

    def login_with_google(self, e=None):
        if self.auth_busy:
            return
        self.auth_busy = True
        self.page.update()
        threading.Thread(target=self._google_login_worker, daemon=True).start()

    def _try_auto_login(self):
        session = config.load_session()
        if not session or not session.get("refresh_token"):
            return
        ok, err = self.cloud.refresh_session(session["refresh_token"], session.get("email"))
        if not ok:
            config.clear_session()
            self.logged_in = False
            self.user_email = None
            self.user_name = None
            self.goto_login()
            self.toast("Session expired. Please log in again.", bgcolor=config.ERROR)
            return
        self.logged_in = True
        self.user_email = self.cloud.email or session.get("email")
        self.user_name = (self.user_email or "User").split("@")[0]
        config.save_session(self.cloud.refresh_token, self.cloud.uid, self.user_email)
        threading.Thread(target=self._sync_after_login, daemon=True).start()

    def _google_login_worker(self):
        id_token, access_token, err = run_google_oauth_flow(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
        if err or not id_token:
            self.auth_busy = False
            self.toast(f"Google sign-in failed: {err or 'unknown error'}", bgcolor=config.ERROR)
            self.page.update()
            return

        ok, fb_err = self.cloud.sign_in_with_google(id_token)
        self.auth_busy = False
        if not ok:
            self.toast(f"Google sign-in failed: {fb_err}", bgcolor=config.ERROR)
            self.page.update()
            return

        self.logged_in = True
        self.user_email = self.cloud.email or "Google User"
        self.user_name = self.user_email.split("@")[0]
        config.save_session(self.cloud.refresh_token, self.cloud.uid, self.user_email)
        self._after_auth_success(self.user_email)
        self.toast(f"Welcome, {self.user_email}!")

    def _after_auth_success(self, email_or_uid):
        self._load_local_cache_for_user(email_or_uid)
        threading.Thread(target=self._sync_after_login, daemon=True).start()
        self.goto_dashboard()

    def _load_local_cache_for_user(self, email_or_uid):
        self.cache_file = models.cache_path_for(email_or_uid)
        self.quizzes = copy.deepcopy(models.SAMPLE_QUIZZES)
        self.drafts = copy.deepcopy(models.SAMPLE_DRAFTS)
        self.subjects = [
            "Science",
            "Biology",
            "Mathematics",
            "History",
            "Computer Science",
            "Literature",
            "General Knowledge",
        ]
        try:
            if self.cache_file.exists():
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                if data.get("quizzes"):
                    self.quizzes = data["quizzes"]
                if data.get("drafts"):
                    self.drafts = data["drafts"]
                if data.get("subjects"):
                    self.subjects = data["subjects"]
        except Exception as e:
            print("Local cache unavailable, using bundled samples:", e)

    def _save_local_cache(self):
        if not self.cache_file:
            return
        try:
            self.cache_file.write_text(
                json.dumps(
                    {
                        "quizzes": self.quizzes,
                        "drafts": self.drafts,
                        "subjects": self.subjects,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            print("Could not write local cache:", e)

    def _sync_after_login(self):
        result = self.cloud.fetch_all()
        if not result:
            err = self.cloud.last_error or ""
            print("Cloud sync unavailable (running in local offline mode):", err if err else "Firebase database offline")
            return
        cloud_quizzes, cloud_drafts, cloud_subjects = result

        # Smart merge for quizzes by 'id'
        merged_quizzes_map = {}
        for q in (cloud_quizzes or []):
            if isinstance(q, dict) and q.get("id"):
                merged_quizzes_map[q["id"]] = q

        need_cloud_push_quizzes = []
        for q in self.quizzes:
            if isinstance(q, dict) and q.get("id"):
                qid = q["id"]
                if qid not in merged_quizzes_map:
                    merged_quizzes_map[qid] = q
                    need_cloud_push_quizzes.append(q)
                else:
                    cloud_q = merged_quizzes_map[qid]
                    local_st = q.get("students_taken", 0)
                    cloud_st = cloud_q.get("students_taken", 0)
                    if local_st > cloud_st:
                        merged_quizzes_map[qid]["students_taken"] = local_st
                        need_cloud_push_quizzes.append(merged_quizzes_map[qid])

        if merged_quizzes_map:
            self.quizzes = list(merged_quizzes_map.values())

        # Smart merge for drafts by '_key' or slug
        merged_drafts_map = {}
        for d in (cloud_drafts or []):
            if isinstance(d, dict):
                k = d.get("_key") or models.slugify(d.get("title", "draft"))
                d["_key"] = k
                merged_drafts_map[k] = d

        need_cloud_push_drafts = []
        for d in self.drafts:
            if isinstance(d, dict):
                k = d.get("_key") or models.slugify(d.get("title", "draft"))
                d["_key"] = k
                if k not in merged_drafts_map:
                    merged_drafts_map[k] = d
                    need_cloud_push_drafts.append(d)

        self.drafts = list(merged_drafts_map.values())

        # Smart merge for subjects (union)
        combined_subjects = set(self.subjects)
        if cloud_subjects:
            combined_subjects.update(cloud_subjects)
        need_cloud_push_subjects = len(combined_subjects) > len(cloud_subjects or [])
        self.subjects = sorted(list(combined_subjects))

        self._save_local_cache()

        # Push any offline local updates to cloud
        for q in need_cloud_push_quizzes:
            threading.Thread(target=self.cloud.save_quiz, args=(dict(q),), daemon=True).start()
        for d in need_cloud_push_drafts:
            key = d.get("_key")
            payload = {k: v for k, v in d.items() if k != "_key"}
            threading.Thread(target=self.cloud.save_draft, args=(payload, key), daemon=True).start()
        if need_cloud_push_subjects:
            threading.Thread(target=self.cloud.save_subjects, args=(list(self.subjects),), daemon=True).start()

        self._on_cloud_synced()

    def _on_cloud_synced(self):
        try:
            self.toast("☁ Synced with the cloud")
        except Exception:
            pass
        if self.current_route == "dashboard" and hasattr(self, "quiz_cards_container"):
            try:
                self.quiz_cards_container.controls = self._get_quiz_card_controls()
                self.quiz_cards_container.update()
                self.page.update()
            except Exception:
                pass
        elif self.current_route == "library" and hasattr(self, "lib_cards_container"):
            try:
                self.lib_cards_container.controls = self._get_library_card_controls()
                self.lib_cards_container.update()
                self.page.update()
            except Exception:
                pass

    def _blank_quiz_data(self):
        return {
            "title": "", "subject": "Science", "description": "",
            "time_mins": 15, "difficulty": "Medium", "cover_color": config.PRIMARY,
            "questions": [],
        }

    def _persist_settings(self):
        config.save_settings({
            "dark_mode": self.dark_mode,
            "randomize_questions": self.randomize_questions,
            "default_answer_mode": self.default_answer_mode,
            "ui_mode": self.ui_mode,
        })

    def _toggle_dark_mode(self, e):
        self.dark_mode = e.control.value
        config.apply_theme(self.dark_mode)
        self._persist_settings()
        self._refresh_theme()

    def _toggle_randomize(self, e):
        self.randomize_questions = e.control.value
        self._persist_settings()

    def _toggle_answer_mode(self, e):
        self.default_answer_mode = "fill_blank" if e.control.value else "standard"
        self.quiz_answering_mode = self.default_answer_mode
        self._persist_settings()

    def _apply_ui_window_mode(self):
        try:
            if self.ui_mode == "mobile":
                self.app_shell.width = 460
                self.app_shell.max_width = 460
                self.app_shell.expand = False
                try:
                    self.page.window.resizable = False
                    self.page.window.maximizable = False
                    self.page.window.width = 476
                    self.page.window.height = 860
                    self.page.window.min_width = 476
                    self.page.window.max_width = 476
                    self.page.window.min_height = 860
                    self.page.window.max_height = 860
                except Exception:
                    pass
            else:
                self.app_shell.width = None
                self.app_shell.max_width = 1140
                self.app_shell.expand = True
                try:
                    self.page.window.resizable = True
                    self.page.window.maximizable = True
                    self.page.window.min_width = 400
                    self.page.window.max_width = None
                    self.page.window.min_height = 500
                    self.page.window.max_height = None
                    if (self.page.window.width or 0) <= 476:
                        self.page.window.width = 1050
                        self.page.window.height = 860
                except Exception:
                    pass
        except Exception:
            pass

    def _toggle_ui_mode(self, e):
        self.ui_mode = "desktop" if e.control.value else "mobile"
        self._persist_settings()
        self._apply_ui_window_mode()
        self.app_shell.update()
        self.page.update()

    def _refresh_theme(self):
        self.page.bgcolor = config.SURFACE_MID
        self.app_shell.bgcolor = config.BG_APP
        self.app_shell.update()
        self._rebuild_bottom_nav_colors()
        if self.current_route == "dashboard":
            self._set_body(build_dashboard(self), active_nav=0)
        elif self.current_route == "library":
            self._set_body(build_library(self), active_nav=1)
        elif self.current_route == "settings":
            self._set_body(build_settings(self), show_nav=True, active_nav=2)
        elif self.current_route == "login":
            self._set_body(build_login(self), show_nav=False)
        else:
            self.page.update()

    def _rebuild_bottom_nav_colors(self):
        self.nav_home_btn = self._nav_button("🏠", "Home", 0, self.goto_dashboard)
        self.nav_lib_btn = self._nav_button("📚", "Library", 1, self.goto_library)
        self.nav_prof_btn = self._nav_button("⚙", "Settings", 2, self.goto_settings)
        self.bottom_nav.content = ft.Row(
            [self.nav_home_btn, self.nav_lib_btn, self.nav_prof_btn], spacing=12,
        )
        self.bottom_nav.bgcolor = config.BG_SURFACE
        self.bottom_nav.border = ft.Border.only(top=ft.BorderSide(1, config.BORDER_COLOR))
        self.bottom_nav.update()

    def goto_settings(self):
        self.current_route = "settings"
        self._set_body(build_settings(self), show_nav=True, active_nav=2)
        self._refresh_bottom_nav()

    def toast(self, message, bgcolor=None, duration=1000):
        if bgcolor is None:
            bgcolor = config.PRIMARY
        self.page.overlay.append(
            ft.SnackBar(
                content=ft.Text(message, color="white"),
                bgcolor=bgcolor,
                duration=duration,
                open=True,
            )
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
                                style=ft.ButtonStyle(bgcolor=config.PRIMARY, color="white")),
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
                                style=ft.ButtonStyle(bgcolor=config.PRIMARY, color="white")),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def avatar(self, text="P", size=34, color=config.PRIMARY):
        return ft.CircleAvatar(
            content=ft.Text(text, color="white", weight=ft.FontWeight.BOLD, size=size * 0.4),
            bgcolor=color, radius=size / 2,
        )

    def circular_progress(self, pct=80, size=170):
        return ft.Stack(
            [
                ft.ProgressRing(value=pct / 100, width=size, height=size,
                                 stroke_width=12, color=config.PRIMARY, bgcolor=config.SURFACE_HIGH),
                ft.Container(
                    content=ft.Text(f"{int(pct)}%", size=26, weight=ft.FontWeight.BOLD, color=config.TEXT_ON_SURFACE),
                    width=size, height=size, alignment=ft.Alignment.CENTER,
                ),
            ],
            width=size, height=size,
        )

    def build_header(self, title, subtitle=None, show_back=False, on_back=None, show_logo=False):
        left_controls = []

        if show_back:
            left_controls.append(
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                    icon_size=18,
                    icon_color=config.PRIMARY,
                    on_click=on_back,
                )
            )

        if show_logo:
            left_controls.append(
                ft.Image(src="logo.png", width=44, height=44, fit=ft.BoxFit.CONTAIN)
            )

        title_column = ft.Column(
            [
                ft.Text(title, size=20, weight=ft.FontWeight.BOLD, color=config.PRIMARY),
                *( [ft.Text(subtitle, size=12, color=config.TEXT_MUTED)] if subtitle else [] )
            ],
            spacing=2,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        left_controls.append(title_column)

        right_controls = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.NOTIFICATIONS_OUTLINED,
                    icon_color=config.PRIMARY,
                    icon_size=22,
                    on_click=lambda e: self.toast("No new notifications"),
                ),
                ft.Container(
                    content=ft.CircleAvatar(
                        content=ft.Text("PQ", size=12, weight=ft.FontWeight.BOLD, color="white"),
                        bgcolor=config.PRIMARY,
                        radius=16,
                    ),
                    on_click=lambda e: self._show_profile(),
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
            bgcolor=config.BG_SURFACE,
        )

    def _build_bottom_nav(self):
        self.nav_home_btn = self._nav_button("🏠", "Home", 0, self.goto_dashboard)
        self.nav_lib_btn = self._nav_button("📚", "Library", 1, self.goto_library)
        self.nav_prof_btn = self._nav_button("⚙", "Settings", 2, self.goto_settings)
        row = ft.Row(
            [self.nav_home_btn, self.nav_lib_btn, self.nav_prof_btn],
            spacing=12,
        )
        return ft.Container(
            content=row, height=68, padding=ft.Padding.symmetric(horizontal=16, vertical=6),
            bgcolor=config.BG_SURFACE, border=ft.Border.only(top=ft.BorderSide(1, config.BORDER_COLOR)),
        )

    def _nav_button(self, icon, label, idx, on_click):
        active = self.active_nav == idx
        return ft.Container(
            content=ft.Row(
                [ft.Text(icon, size=14), ft.Text(label, size=13,
                                                  weight=ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL,
                                                  color="white" if active else config.TEXT_MUTED)],
                alignment=ft.MainAxisAlignment.CENTER, spacing=6,
            ),
            bgcolor=config.PRIMARY if active else "transparent",
            border_radius=14, height=44, expand=True, alignment=ft.Alignment.CENTER,
            on_click=lambda e: on_click(), ink=True,
            data=idx,
        )

    def _refresh_bottom_nav(self):
        for idx, btn in [(0, self.nav_home_btn), (1, self.nav_lib_btn), (2, self.nav_prof_btn)]:
            active = self.active_nav == idx
            btn.bgcolor = config.PRIMARY if active else "transparent"
            row = btn.content
            row.controls[0].color = "white" if active else config.TEXT_MUTED
            row.controls[1].color = "white" if active else config.TEXT_MUTED
            row.controls[1].weight = ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL
        self.bottom_nav.update()

    def _show_profile(self):
        def _confirm_logout(e):
            self.page.pop_dialog()
            self.dialog_confirm("Log Out", "Are you sure you want to log out?", self._logout)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Profile", weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"Signed in as: {self.user_email}\n"
                f"Active Quizzes: {len(self.quizzes)}\n"
                f"Total Students: {sum(q.get('students_taken', 0) for q in self.quizzes)}"
            ),
            actions=[
                ft.TextButton("Log Out", on_click=_confirm_logout,
                              style=ft.ButtonStyle(color=config.ERROR)),
                ft.TextButton("Close", on_click=lambda e: self.page.pop_dialog()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(dlg)

    def _set_body(self, control, show_nav=True, active_nav=None):
        self.body.content = control
        self.bottom_nav.visible = show_nav
        if active_nav is not None:
            self.active_nav = active_nav
        self.page.update()

    def goto_login(self):
        self.current_route = "login"
        self._set_body(build_login(self), show_nav=False)

    def _toggle_auth_mode(self):
        self.auth_mode = "login" if self.auth_mode == "signup" else "signup"
        self._set_body(build_login(self), show_nav=False)

    def _set_login_loading(self, loading):
        self.auth_busy = loading
        try:
            self.login_submit_text.value = "Please wait…" if loading else (
                "Sign Up" if self.auth_mode == "signup" else "Log In"
            )
            self.login_submit_text.update()
        except Exception:
            pass

    def _do_login(self, e):
        if self.auth_busy:
            return
        email = (self.login_email.value or "").strip()
        password = self.login_password.value or ""
        if not email or not password:
            self.dialog_info("Missing Info", "Please enter both your email and password.")
            return
        self._set_login_loading(True)
        threading.Thread(target=self._login_worker, args=(email, password), daemon=True).start()

    def _login_worker(self, email, password):
        ok, err = self.cloud.sign_in(email, password)
        if not ok and err and self._is_google_account_error(err):
            self._set_login_loading(False)
            self.toast(
                f"'{email}' uses Google Sign-In. Launching Google…",
                bgcolor=config.SECONDARY,
                duration=3000,
            )
            self.page.update()
            id_token, _, google_err = run_google_oauth_flow(
                GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, login_hint=email
            )
            if google_err or not id_token:
                self.toast(f"Google sign-in failed: {google_err or 'unknown error'}", bgcolor=config.ERROR)
                self.page.update()
                return
            fb_ok, fb_err = self.cloud.sign_in_with_google(id_token)
            self.auth_busy = False
            if not fb_ok:
                self.toast(f"Google sign-in failed: {fb_err}", bgcolor=config.ERROR)
                self.page.update()
                return
            self.logged_in = True
            self.user_email = self.cloud.email or email
            self.user_name = self.user_email.split("@")[0]
            config.save_session(self.cloud.refresh_token, self.cloud.uid, self.user_email)
            self._after_auth_success(self.user_email)
            self.toast(f"Welcome, {self.user_email}!")
            return
        self._after_auth_attempt(ok, err, email)

    @staticmethod
    def _is_google_account_error(err_msg):
        """Returns True when Firebase's error indicates the account exists but has no
        email/password credential — i.e. it was created via Google (or another provider)."""
        google_signals = [
            "INVALID_LOGIN_CREDENTIALS",
            "INVALID_PASSWORD",
            "EMAIL_NOT_FOUND",
            "USER_DISABLED",
            "FEDERATED_USER_ID_ALREADY_LINKED",
        ]
        return any(sig in err_msg for sig in google_signals)

    def _do_signup(self, e):
        if self.auth_busy:
            return
        email = (self.login_email.value or "").strip()
        password = self.login_password.value or ""
        confirm = self.login_password_confirm.value or ""
        if not email or not password:
            self.dialog_info("Missing Info", "Please enter both your email and password.")
            return
        if len(password) < 6:
            self.dialog_info("Weak Password", "Your password should be at least 6 characters.")
            return
        if password != confirm:
            self.dialog_info("Password Mismatch", "Those passwords don't match. Please try again.")
            return
        self._set_login_loading(True)
        threading.Thread(target=self._signup_worker, args=(email, password), daemon=True).start()

    def _signup_worker(self, email, password):
        ok, err = self.cloud.sign_up(email, password)
        if not ok and err and "EMAIL_EXISTS" in err:
            self._set_login_loading(False)
            self.page.update()
            def _launch_google(e=None):
                try:
                    self.page.pop_dialog()
                except Exception:
                    pass
                self.auth_busy = True
                self.page.update()
                threading.Thread(target=self._google_login_hint_worker, args=(email,), daemon=True).start()

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Account Already Exists", weight=ft.FontWeight.BOLD),
                content=ft.Text(
                    f"{email} is already registered — probably via Google Sign-In.\n\n"
                    "Would you like to sign in with Google instead?"
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
                    ft.FilledButton(
                        "Sign in with Google",
                        on_click=_launch_google,
                        style=ft.ButtonStyle(bgcolor=config.PRIMARY, color="white"),
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            self.page.show_dialog(dlg)
            return
        self._after_auth_attempt(ok, err, email)

    def _google_login_hint_worker(self, email):
        """Google OAuth flow pre-filled with a known email (skips account picker)."""
        id_token, _, err = run_google_oauth_flow(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, login_hint=email)
        if err or not id_token:
            self.auth_busy = False
            self.toast(f"Google sign-in failed: {err or 'unknown error'}", bgcolor=config.ERROR)
            self.page.update()
            return
        fb_ok, fb_err = self.cloud.sign_in_with_google(id_token)
        self.auth_busy = False
        if not fb_ok:
            self.toast(f"Google sign-in failed: {fb_err}", bgcolor=config.ERROR)
            self.page.update()
            return
        self.logged_in = True
        self.user_email = self.cloud.email or email
        self.user_name = self.user_email.split("@")[0]
        config.save_session(self.cloud.refresh_token, self.cloud.uid, self.user_email)
        self._after_auth_success(self.user_email)
        self.toast(f"Welcome, {self.user_email}!")

    def _after_auth_attempt(self, ok, err, email):
        self._set_login_loading(False)
        if not ok:
            self.dialog_info("Sign-in Failed", err or "Something went wrong. Please try again.")
            return
        self.logged_in = True
        self.user_email = email
        config.save_session(self.cloud.refresh_token, self.cloud.uid, email)
        self._load_local_cache_for_user(email)
        self.goto_dashboard()
        self.toast(f"Welcome, {email}!")
        threading.Thread(target=self._sync_after_login, daemon=True).start()

    def _handle_forgot_password(self):
        email = (self.login_email.value or "").strip()
        if not email:
            self.dialog_info("Enter Your Email", "Type your email above first, then tap 'Forgot password?' again.")
            return

        def worker():
            ok, err = self.cloud.send_password_reset(email)
            if ok:
                self.dialog_info("Check Your Inbox", f"A password reset link has been sent to {email}.")
            else:
                self.dialog_info("Couldn't Send Reset Email", err or "Please try again later.")
        threading.Thread(target=worker, daemon=True).start()

    def _continue_offline(self):
        self.logged_in = True
        self.user_email = "Guest (local only)"
        self._load_local_cache_for_user("guest")
        self.goto_dashboard()
        self.toast("Using local storage only — no cloud sync in guest mode.", bgcolor=config.TERTIARY)

    def _logout(self):
        self.timer_running = False
        self.cloud.sign_out()
        config.clear_session()
        self.logged_in = False
        self.user_email = None
        self.quizzes = []
        self.drafts = []
        self.current_quiz = None
        self.cache_file = None
        self.auth_mode = "login"
        self.goto_login()

    def _filtered_dash_quizzes(self):
        t = self.dash_search_text.lower()
        return [q for q in self.quizzes if t in q["title"].lower() or t in q["subject"].lower()]

    def _stat_card(self, icon, value, label, color):
        return card(
            ft.Column([
                ft.Row([ft.Text(icon, size=22), ft.Container(expand=True),
                        ft.Text(value, size=24, weight=ft.FontWeight.W_800, color=color)]),
                ft.Text(label, size=10, weight=ft.FontWeight.W_800, color=config.TEXT_ON_SURFACE),
            ], spacing=6),
            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        )

    def _get_quiz_card_controls(self):
        filtered = self._filtered_dash_quizzes()
        if filtered:
            return [
                ft.Container(
                    content=self._dashboard_quiz_card(q),
                    col={"xs": 12, "sm": 12, "md": 6, "lg": 6},
                )
                for q in filtered
            ]
        return [
            ft.Container(
                content=ft.Text("No active quizzes match your search.", color=config.TEXT_MUTED, size=13),
                col={"xs": 12, "sm": 12, "md": 12, "lg": 12},
                padding=ft.Padding.symmetric(vertical=10),
            )
        ]

    def _on_dash_search(self, e):
        self.dash_search_text = e.control.value or ""
        self.quiz_cards_container.controls = self._get_quiz_card_controls()
        self.quiz_cards_container.update()

    def _quiz_badge_colors(self, q):
        color = q.get("cover_color") or q.get("badge_color")
        if not color or color in (config.LIGHT_THEME["PRIMARY"], config.DARK_THEME["PRIMARY"], "PRIMARY"):
            return config.PRIMARY, config.PRIMARY_LIGHT
        return color, hex_to_light_bg(color, dark=self.dark_mode)

    def _dashboard_quiz_card(self, q):
        badge_fg, badge_bg = self._quiz_badge_colors(q)
        top_row = ft.Row([
            pill(q["subject"].upper(), badge_fg, badge_bg),
            ft.Text(f"{len(q['questions'])} Questions", size=11, weight=ft.FontWeight.W_600, color=config.TEXT_MUTED),
            ft.Container(expand=True),
            kebab_menu([
                ("✏️  Edit Quiz", lambda e, qz=q: self.open_quiz_editor(qz)),
                ("🗑️  Delete Quiz", lambda e, qz=q: self._confirm_delete_quiz(qz)),
            ]),
        ])
        bottom_row = ft.Row([
            ft.Text(f"🕐 {q.get('edited', 'Recently')}  ·  ⏱ {q.get('time_mins', 15)}m",
                    size=11, weight=ft.FontWeight.W_500, color=config.TEXT_MUTED),
            ft.Container(expand=True),
            ft.Container(
                content=ft.Text("▶ Take Quiz", size=11, weight=ft.FontWeight.BOLD, color="white"),
                bgcolor=config.PRIMARY, border_radius=8, padding=ft.Padding.symmetric(horizontal=12, vertical=5),
                on_click=lambda e, qz=q: self.open_quiz_intro(qz), ink=True,
            ),
        ])
        return card(ft.Column([
            top_row,
            ft.Text(q["title"], size=15, weight=ft.FontWeight.W_800, color=config.TEXT_ON_SURFACE),
            bottom_row,
        ], spacing=8), padding=ft.Padding.symmetric(horizontal=16, vertical=12))

    def _draft_card(self, d):
        q_len = len(d.get("questions", []))
        return ft.Container(
            width=145, height=115, bgcolor=config.BG_SURFACE, border_radius=14,
            border=ft.Border.all(1, config.BORDER_COLOR), padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            content=ft.Column([
                ft.Row([
                    ft.Text(d.get("icon", "📄"), size=18),
                    ft.Container(expand=True),
                    ft.Container(
                        content=ft.Text("✕", size=10, weight=ft.FontWeight.BOLD, color=config.TEXT_MUTED),
                        on_click=lambda e, dd=d: self._delete_draft(dd), ink=True,
                    ),
                ]),
                ft.Text(d.get("title", "Draft"), size=11, weight=ft.FontWeight.W_800,
                        color=config.TEXT_ON_SURFACE, max_lines=2),
                ft.Text(f"{q_len} Questions added" if q_len else "Empty draft",
                        size=9, color=config.TEXT_MUTED, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=ft.Text("Resume →", size=10, weight=ft.FontWeight.BOLD, color=config.PRIMARY),
                    bgcolor=config.PRIMARY_LIGHT, border_radius=6, height=22, alignment=ft.Alignment.CENTER,
                    on_click=lambda e, dd=d: self.open_draft_in_maker(dd), ink=True,
                ),
            ], spacing=2),
        )

    def _add_draft_card(self):
        return ft.Container(
            width=100, height=115, bgcolor=config.SURFACE_LOW, border_radius=14,
            border=ft.Border.all(2, config.BORDER_COLOR),
            content=ft.Column(
                [ft.Text("+", size=20, color=config.PRIMARY, weight=ft.FontWeight.BOLD),
                 ft.Text("New Quiz", size=12, color=config.PRIMARY, weight=ft.FontWeight.BOLD)],
                alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=lambda e: self.goto_create_setup(), ink=True,
        )

    def _delete_draft(self, draft):
        def do_delete():
            self.drafts = [d for d in self.drafts if d is not draft]
            self._save_local_cache()
            key = draft.get("_key") or models.slugify(draft.get("title", "draft"))
            threading.Thread(target=self.cloud.delete_draft, args=(key,), daemon=True).start()
            self._set_body(build_dashboard(self))
        self.dialog_confirm("Delete Draft", f"Remove draft '{draft.get('title', 'Untitled')}'?", do_delete)

    def open_draft_in_maker(self, draft):
        self.editing_quiz_id = None
        self.new_quiz_data = {
            "title": draft.get("title", ""), "subject": draft.get("subject", "General Knowledge"),
            "description": draft.get("description", ""), "time_mins": draft.get("time_mins", 15),
            "difficulty": draft.get("difficulty", "Medium"), "cover_color": config.PRIMARY,
            "questions": [dict(q) for q in draft.get("questions", [])],
        }
        self.current_difficulty = self.new_quiz_data["difficulty"]
        self.color_choice = config.PRIMARY
        if self.new_quiz_data["questions"]:
            self.goto_add_questions()
        else:
            self.goto_create_setup(reset=False)

    def _confirm_delete_quiz(self, quiz):
        def do_delete():
            self.quizzes = [q for q in self.quizzes if q["id"] != quiz["id"]]
            self._save_local_cache()
            threading.Thread(target=self.cloud.delete_quiz, args=(quiz["id"],), daemon=True).start()
            self._set_body(build_dashboard(self))
            self.toast(f"'{quiz['title']}' has been deleted.", bgcolor=config.ERROR)
        self.dialog_confirm("Delete Quiz", f"Are you sure you want to delete '{quiz['title']}'?\nThis cannot be undone.", do_delete)

    def _library_chip_row(self):
        cats = ["All Subjects"] + sorted(set(self.subjects))
        chips = []
        for cat in cats:
            active = cat == self.current_lib_cat
            chips.append(
                ft.Container(
                    content=ft.Text(cat, size=11, weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_600,
                                     color="white" if active else config.TEXT_VARIANT),
                    bgcolor=config.PRIMARY if active else config.BG_SURFACE,
                    border=None if active else ft.Border.all(1, config.BORDER_COLOR),
                    border_radius=14, padding=ft.Padding.symmetric(horizontal=14, vertical=6),
                    on_click=lambda e, c=cat: self._filter_library_by_cat(c), ink=True,
                )
            )
        chips.append(
            ft.Container(
                content=ft.Text("+ New Subject", size=11, weight=ft.FontWeight.BOLD, color=config.PRIMARY),
                bgcolor=config.PRIMARY_LIGHT, border=ft.Border.all(1, config.PRIMARY), border_radius=14,
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                on_click=lambda e: self._prompt_add_custom_subject(), ink=True,
            )
        )
        return ft.Row(chips, spacing=8, scroll=ft.ScrollMode.AUTO)

    def _filter_library_by_cat(self, cat):
        self.current_lib_cat = cat
        self._set_body(build_library(self), active_nav=1)

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
            self._set_body(build_library(self), active_nav=1)
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
            results.append(
                ft.Container(
                    content=self._library_quiz_card(q),
                    col={"xs": 12, "sm": 12, "md": 6, "lg": 6},
                )
            )

        if not results:
            return [
                ft.Container(
                    content=ft.Text(
                        "No quizzes match this filter.", color=config.TEXT_MUTED, size=13
                    ),
                    col={"xs": 12, "sm": 12, "md": 12, "lg": 12},
                    padding=ft.Padding.symmetric(vertical=10),
                )
            ]
        return results

    def _library_quiz_card(self, q):
        badge_fg, badge_bg = self._quiz_badge_colors(q)
        top_row = ft.Row([
            pill(q["subject"].upper(), badge_fg, badge_bg),
            ft.Container(expand=True),
            ft.Text(f"Code: {q.get('code', q['id'])}", size=10, weight=ft.FontWeight.BOLD, color=config.TEXT_MUTED),
            kebab_menu([
                ("✏️  Edit Quiz", lambda e, qz=q: self.open_quiz_editor(qz)),
                ("🗑️  Delete Quiz", lambda e, qz=q: self._confirm_delete_quiz(qz)),
            ]),
        ])
        meta_row = ft.Row([
            ft.Text(f"⏱ {q.get('time_mins', 15)} Mins", size=11, weight=ft.FontWeight.W_600, color=config.TEXT_MUTED),
            ft.Text(f"📊 {q.get('difficulty', 'Intermediate')}", size=11, weight=ft.FontWeight.W_600, color=config.TEXT_MUTED),
            ft.Container(expand=True),
            ft.Container(
                content=ft.Text("Start Quiz →", size=11, weight=ft.FontWeight.BOLD, color="white"),
                bgcolor=config.PRIMARY, border_radius=8, padding=ft.Padding.symmetric(horizontal=14, vertical=5),
                on_click=lambda e, qz=q: self.open_quiz_intro(qz), ink=True,
            ),
        ])
        return card(ft.Column([
            top_row,
            ft.Text(q["title"], size=15, weight=ft.FontWeight.W_800, color=config.TEXT_ON_SURFACE),
            ft.Text(q.get("description", ""), size=12, color=config.TEXT_VARIANT),
            meta_row,
        ], spacing=8), padding=ft.Padding.symmetric(horizontal=16, vertical=14))

    def _handle_join_quiz(self, e):
        code = (self.code_input.value or "").strip().upper()
        if not code:
            self.dialog_info("Quiz Code", "Please enter a valid quiz code or ID.")
            return
        match = next((q for q in self.quizzes if q.get("code", "").upper() == code or q.get("id", "").upper() == code), None)
        if match:
            self.open_quiz_intro(match)
        else:
            avail = [q.get("code") or q.get("id") for q in self.quizzes if q.get("code") or q.get("id")]
            hint_str = ", ".join(avail[:4]) if avail else "BIO101"
            self.dialog_info("Quiz Not Found", f"No quiz with code '{code}' was found.\nAvailable codes in your library: {hint_str}")

    def goto_create_setup(self, reset=True):
        self.editing_quiz_id = None
        if reset:
            self.new_quiz_data = self._blank_quiz_data()
            self.current_difficulty = "Medium"
            self.color_choice = config.PRIMARY
            self.current_question_type = "multiple_choice"
        self._set_body(build_create_setup(self), show_nav=False)

    def open_quiz_editor(self, quiz):
        self.editing_quiz_id = quiz["id"]
        self.new_quiz_data = {
            "id": quiz["id"], "title": quiz["title"], "subject": quiz["subject"],
            "description": quiz.get("description", ""), "time_mins": quiz.get("time_mins", 15),
            "difficulty": quiz.get("difficulty", "Medium"), "cover_color": quiz.get("badge_color", config.PRIMARY),
            "questions": [dict(item) for item in quiz["questions"]],
        }
        self.current_difficulty = self.new_quiz_data["difficulty"]
        self.color_choice = self.new_quiz_data["cover_color"]
        self._set_body(build_create_setup(self), show_nav=False)

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
            sw.border = ft.Border.all(2, "white" if not selected else config.TEXT_ON_SURFACE)
            sw.content = ft.Text("✓", color="white", weight=ft.FontWeight.BOLD) if selected else None
            sw.update()

    def _select_difficulty(self, diff):
        self.current_difficulty = diff
        for d, btn in self.diff_buttons.items():
            active = d == diff
            btn.bgcolor = config.PRIMARY if active else config.SURFACE_LOW
            btn.border = None if active else ft.Border.all(1, config.BORDER_COLOR)
            btn.content.value = d
            btn.content.color = "white" if active else config.TEXT_ON_SURFACE
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

    def goto_add_questions(self):
        self.editing_question_idx = None
        self._set_body(build_add_questions(self), show_nav=False)

    def goto_create_setup_from_step2(self):
        self._set_body(build_create_setup(self), show_nav=False)

    def _select_question_type(self, qtype):
        self.current_question_type = qtype
        for qt, btn in self.qtype_buttons.items():
            active = qt == qtype
            btn.bgcolor = config.PRIMARY if active else config.SURFACE_LOW
            btn.border = None if active else ft.Border.all(1, config.BORDER_COLOR)
            btn.content.color = "white" if active else config.TEXT_ON_SURFACE
            btn.content.weight = ft.FontWeight.BOLD if active else ft.FontWeight.W_600
            btn.update()
        self.opt_card_container.visible = (qtype == "multiple_choice")
        self.blank_card_container.visible = (qtype == "fill_blank")
        self.opt_card_container.update()
        self.blank_card_container.update()

    def _on_correct_radio_change(self, e):
        self.correct_option_idx = e.control.value
        self._refresh_option_row_styles()

    def _refresh_option_row_styles(self):
        theme_color = self.new_quiz_data.get("cover_color", config.PRIMARY)
        light_bg = hex_to_light_bg(theme_color, dark=self.dark_mode)
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
                inp.color = config.INPUT_TEXT_COLOR
            else:
                row.bgcolor = None
                row.border = ft.Border.all(1.5, "transparent")
                tag.bgcolor = config.SURFACE_LOW
                tag.content.color = config.TEXT_MUTED
                inp.border_color = config.BORDER_COLOR
                inp.border_width = 1
                inp.color = config.INPUT_TEXT_COLOR
            row.update()
            tag.update()
            inp.update()

    def _build_existing_question_rows(self):
        questions = self.new_quiz_data.get("questions", [])
        if not questions:
            return [ft.Text("No questions added yet. Use the form below to add questions.",
                             size=12, italic=True, color=config.TEXT_MUTED)]
        rows = []
        for idx, q in enumerate(questions):
            q_type = q.get("question_type", "multiple_choice")
            type_label = "Fill Blank" if q_type == "fill_blank" else "MC"
            rows.append(
                ft.Container(
                    bgcolor=config.BG_SURFACE, border=ft.Border.all(1, config.BORDER_COLOR), border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    content=ft.Row([
                        pill(type_label, config.PRIMARY, config.PRIMARY_LIGHT, size=9),
                        ft.Text(f"Q{idx + 1}: {q['question']}", size=12, color=config.TEXT_ON_SURFACE, expand=True),
                        kebab_menu([
                            ("✏️  Edit Question", lambda e, i=idx: self._load_question_for_editing(i)),
                            ("🗑️  Delete Question", lambda e, i=idx: self._delete_question_from_new_quiz(i)),
                        ]),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
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
        q_type = target.get("question_type", "multiple_choice")
        self.input_question_text.value = target["question"]

        self.current_question_type = q_type
        for qt, btn in self.qtype_buttons.items():
            active = qt == q_type
            btn.bgcolor = config.PRIMARY if active else config.SURFACE_LOW
            btn.border = None if active else ft.Border.all(1, config.BORDER_COLOR)
            btn.content.color = "white" if active else config.TEXT_ON_SURFACE
            btn.content.weight = ft.FontWeight.BOLD if active else ft.FontWeight.W_600
            btn.update()
        self.opt_card_container.visible = (q_type == "multiple_choice")
        self.blank_card_container.visible = (q_type == "fill_blank")
        self.opt_card_container.update()
        self.blank_card_container.update()

        if q_type == "fill_blank":
            self.input_blank_answer.value = target.get("correct_answer", "")
            self.input_blank_answer.update()
        else:
            for i, opt in enumerate(self.opt_inputs):
                opt.value = target["options"][i] if i < len(target["options"]) else ""
            corr = target.get("correct_index", 0)
            self.correct_option_idx = str(corr if corr < len(self.opt_inputs) else 0)
            self.radio_group.value = self.correct_option_idx
            for opt in self.opt_inputs:
                opt.update()
            self.radio_group.update()
            self._refresh_option_row_styles()

        self.new_quiz_data["questions"].pop(q_idx)
        self.editing_question_idx = q_idx
        self.q_form_header.value = f"Editing Question #{q_idx + 1}"
        self._refresh_existing_questions()
        self.input_question_text.update()
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
        self.input_blank_answer.value = ""
        self.q_form_header.update()
        self.input_question_text.update()
        for opt in self.opt_inputs:
            opt.update()
        self.radio_group.update()
        self.input_blank_answer.update()
        self._refresh_option_row_styles()

    def _extract_current_question(self):
        q_text = (self.input_question_text.value or "").strip()
        if not q_text:
            return None, "Please enter question text."
        if self.current_question_type == "fill_blank":
            answer = (self.input_blank_answer.value or "").strip()
            if not answer:
                return None, "Please enter the correct answer for this fill-in-the-blank question."
            return {
                "question_type": "fill_blank",
                "question": q_text,
                "correct_answer": answer,
                "explanation": f'Correct answer is "{answer}".',
            }, ""
        options = [inp.value.strip() for inp in self.opt_inputs if (inp.value or "").strip()]
        if len(options) < 2:
            return None, "Please provide at least 2 options for the question."
        correct_idx = int(self.correct_option_idx)
        if correct_idx >= len(options) or correct_idx < 0:
            correct_idx = 0
        return {
            "question_type": "multiple_choice",
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
        self.toast("Question added to quiz!")

    def _save_question_and_review(self):
        if (self.input_question_text.value or "").strip():
            q_obj, err = self._extract_current_question()
            if not err and q_obj:
                self.new_quiz_data["questions"].append(q_obj)
        if not self.new_quiz_data.get("questions"):
            self.dialog_info("No Questions", "Please add at least one question to the quiz.")
            return
        self._set_body(build_review_publish(self), show_nav=False)

    def _build_review_question_cards(self):
        questions = self.new_quiz_data.get("questions", [])
        cards = []
        for idx, q in enumerate(questions):
            q_type = q.get("question_type", "multiple_choice")
            type_tag = pill("Fill in the Blank" if q_type == "fill_blank" else "Multiple Choice",
                             config.PRIMARY, config.PRIMARY_LIGHT, size=9)
            if q_type == "fill_blank":
                body_rows = [
                    ft.Text(f'Correct Answer: "{q.get("correct_answer", "")}"', size=12,
                            weight=ft.FontWeight.W_800, color=config.SUCCESS),
                ]
            else:
                body_rows = []
                for o_idx, opt in enumerate(q.get("options", [])):
                    is_correct = o_idx == q.get("correct_index", 0)
                    body_rows.append(
                        ft.Text(
                            f"[{config.LETTERS[o_idx]}] {opt}" + ("   ✓ (Correct Answer)" if is_correct else ""),
                            size=12, weight=ft.FontWeight.W_800 if is_correct else ft.FontWeight.W_500,
                            color=config.SUCCESS if is_correct else config.TEXT_VARIANT,
                        )
                    )
            cards.append(
                card(ft.Column([
                    ft.Row([
                        ft.Column([
                            type_tag,
                            ft.Text(f"Q{idx + 1}. {q['question']}", size=13, weight=ft.FontWeight.BOLD),
                        ], spacing=4, expand=True),
                        kebab_menu([
                            ("✏️  Edit in Manager", lambda e, i=idx: self._edit_from_review(i)),
                            ("🗑️  Delete Question", lambda e, i=idx: self._delete_from_review(i)),
                        ]),
                    ]),
                    *body_rows,
                ], spacing=6), padding=ft.Padding.symmetric(horizontal=14, vertical=12))
            )
        return cards

    def _edit_from_review(self, idx):
        self.goto_add_questions()
        self._load_question_for_editing(idx)

    def _delete_from_review(self, idx):
        if 0 <= idx < len(self.new_quiz_data.get("questions", [])):
            self.new_quiz_data["questions"].pop(idx)
            self._set_body(build_review_publish(self), show_nav=False)

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
                        "badge_color": self.new_quiz_data.get("cover_color", config.PRIMARY),
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
                "cover_color": self.new_quiz_data.get("cover_color", config.PRIMARY),
                "badge_color": self.new_quiz_data.get("cover_color", config.PRIMARY),
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
        key = models.slugify(draft_entry["title"])
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

    def open_quiz_intro(self, quiz):
        self.current_quiz = quiz
        self.quiz_answering_mode = self.default_answer_mode
        self._set_body(build_intro(self), show_nav=False)

    def _set_intro_answer_mode(self, mode):
        self.quiz_answering_mode = mode
        self._set_body(build_intro(self), show_nav=False)

    def _start_live_quiz(self):
        if not self.current_quiz or not self.current_quiz.get("questions"):
            self.dialog_info("Empty Quiz", "This quiz has no questions.")
            return
        if self.randomize_questions:
            shuffled = list(self.current_quiz["questions"])
            random.shuffle(shuffled)
            self.current_quiz = dict(self.current_quiz, questions=shuffled)
        self.quiz_question_idx = 0
        self.user_answers = [None] * len(self.current_quiz["questions"])
        self.question_answer_modes = {}
        for idx, q in enumerate(self.current_quiz["questions"]):
            if self.quiz_answering_mode == "fill_blank" and q.get("options"):
                self.question_answer_modes[idx] = "fill_blank"
            else:
                self.question_answer_modes[idx] = q.get("question_type", "multiple_choice")

        self.quiz_total_seconds = self.current_quiz.get("time_mins", 15) * 60
        self.quiz_seconds_left = self.quiz_total_seconds
        self.timer_running = True
        self._set_body(build_taking_page(self), show_nav=False)
        threading.Thread(target=self._timer_loop, daemon=True).start()

    def _timer_loop(self):
        while self.timer_running and self.quiz_seconds_left > 0:
            time.sleep(1)
            if not self.timer_running:
                return
            self.quiz_seconds_left -= 1
            try:
                mins, secs = divmod(max(0, self.quiz_seconds_left), 60)
                is_urgent = self.quiz_seconds_left <= 60
                self.lbl_timer.value = f"⏱ {mins:02d}:{secs:02d}"
                self.lbl_timer.color = config.ERROR if is_urgent else config.TEXT_ON_SURFACE
                if hasattr(self, "timer_chip") and self.timer_chip:
                    self.timer_chip.bgcolor = config.ERROR_CONTAINER if is_urgent else config.SURFACE_HIGH
                    self.timer_chip.border = ft.Border.all(1, config.ERROR) if is_urgent else None
                    self.timer_chip.update()
                else:
                    self.lbl_timer.update()
            except Exception:
                return
        if self.timer_running and self.quiz_seconds_left <= 0:
            self.timer_running = False
            self._finish_quiz(timed_out=True)

    def _switch_question_mode(self, q_idx, mode):
        self.question_answer_modes[q_idx] = mode
        self._render_current_live_question()
        self.taking_options_col.update()

    def _render_current_live_question(self):
        questions = self.current_quiz["questions"]
        total = len(questions)
        curr = questions[self.quiz_question_idx]
        q_type = curr.get("question_type", "multiple_choice")
        has_mc_options = bool(curr.get("options"))

        self.taking_progress.value = (self.quiz_question_idx + 1) / total
        self.lbl_q_step.value = f"QUESTION {self.quiz_question_idx + 1} OF {total}"
        self.lbl_q_text.value = curr["question"]

        selected_answer = self.user_answers[self.quiz_question_idx]
        effective_mode = self.question_answer_modes.get(self.quiz_question_idx, q_type)

        mode_header_controls = []
        if has_mc_options:
            is_fb = effective_mode == "fill_blank"
            btn_mc = ft.Container(
                content=ft.Row([
                    ft.Text("🔘", size=11),
                    ft.Text("Multiple Choice", size=11, weight=ft.FontWeight.BOLD if not is_fb else ft.FontWeight.W_500,
                            color="white" if not is_fb else config.TEXT_MUTED),
                ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
                bgcolor=config.PRIMARY if not is_fb else config.SURFACE_LOW,
                border=None if not is_fb else ft.Border.all(1, config.BORDER_COLOR),
                border_radius=8, height=32, padding=ft.Padding.symmetric(horizontal=10),
                alignment=ft.Alignment.CENTER,
                on_click=lambda e: self._switch_question_mode(self.quiz_question_idx, "multiple_choice"), ink=True,
            )
            btn_fb = ft.Container(
                content=ft.Row([
                    ft.Text("✍️", size=11),
                    ft.Text("Fill in Blank", size=11, weight=ft.FontWeight.BOLD if is_fb else ft.FontWeight.W_500,
                            color="white" if is_fb else config.TEXT_MUTED),
                ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
                bgcolor=config.PRIMARY if is_fb else config.SURFACE_LOW,
                border=None if is_fb else ft.Border.all(1, config.BORDER_COLOR),
                border_radius=8, height=32, padding=ft.Padding.symmetric(horizontal=10),
                alignment=ft.Alignment.CENTER,
                on_click=lambda e: self._switch_question_mode(self.quiz_question_idx, "fill_blank"), ink=True,
            )
            mode_header_controls = [
                ft.Container(
                    content=ft.Row([
                        ft.Text("Answer Style:", size=11, weight=ft.FontWeight.BOLD, color=config.TEXT_MUTED),
                        ft.Container(expand=True),
                        btn_mc,
                        btn_fb,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.Padding.only(bottom=4),
                )
            ]

        if effective_mode == "fill_blank":
            self.taking_options_col.controls = mode_header_controls + [
                self._build_fill_blank_input(selected_answer, is_converted_mc=has_mc_options)
            ]
        else:
            self.live_option_buttons = []
            rows = []
            for idx, opt_text in enumerate(curr.get("options", [])):
                row = self._build_live_option(idx, opt_text, selected_answer == idx)
                self.live_option_buttons.append(row)
                rows.append(row)
            self.taking_options_col.controls = mode_header_controls + rows

        self.btn_next_q_text.value = "Finish Quiz ✓" if self.quiz_question_idx == total - 1 else "Next Question →"

    def _build_fill_blank_input(self, current_value, is_converted_mc=False):
        field = ft.TextField(
            value=current_value if isinstance(current_value, str) else "",
            hint_text="Type answer (or option letter)..." if is_converted_mc else "Type your answer here...",
            height=52, border_radius=14, border_color=config.BORDER_COLOR, bgcolor=config.BG_SURFACE,
            content_padding=ft.Padding.symmetric(horizontal=16), text_size=14,
            text_align=ft.TextAlign.CENTER,
            color=config.INPUT_TEXT_COLOR, autofocus=True,
            on_change=self._on_fill_blank_change,
        )
        self.fill_blank_field = field
        controls = [field]
        if is_converted_mc:
            controls.append(
                ft.Text("💡 You can type the full answer text or the option letter (A, B, C, D).",
                        size=11, color=config.TEXT_MUTED, text_align=ft.TextAlign.CENTER)
            )
        return ft.Container(
            content=ft.Column(controls, spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(vertical=4),
        )

    def _on_fill_blank_change(self, e):
        self.user_answers[self.quiz_question_idx] = e.control.value

    def _build_live_option(self, idx, text, selected):
        letter = config.LETTERS[idx] if idx < len(config.LETTERS) else str(idx)
        if selected:
            bg, border_c, txt_c = config.PRIMARY_LIGHT, config.PRIMARY, config.PRIMARY
        else:
            bg, border_c, txt_c = config.BG_SURFACE, config.BORDER_COLOR, config.TEXT_ON_SURFACE
        return ft.Container(
            content=ft.Text(f"{letter}    {text}", size=13,
                             weight=ft.FontWeight.BOLD if selected else ft.FontWeight.W_500, color=txt_c,
                             text_align=ft.TextAlign.CENTER),
            alignment=ft.Alignment.CENTER,
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

    def _is_answer_correct(self, q, user_answer):
        q_type = q.get("question_type", "multiple_choice")
        if isinstance(user_answer, str):
            if not user_answer.strip():
                return False
            given = " ".join(user_answer.strip().lower().split())
            if q_type == "fill_blank":
                correct = " ".join(str(q.get("correct_answer", "")).strip().lower().split())
                return given == correct
            else:
                correct_idx = q.get("correct_index", 0)
                options = q.get("options", [])
                correct_opt = options[correct_idx] if 0 <= correct_idx < len(options) else ""
                correct = " ".join(str(correct_opt).strip().lower().split())
                if given == correct:
                    return True
                if 0 <= correct_idx < len(config.LETTERS):
                    letter = config.LETTERS[correct_idx].lower()
                    if given in (letter, f"option {letter}", f"[{letter}]", str(correct_idx + 1)):
                        return True
                return False
        elif isinstance(user_answer, int):
            return user_answer == q.get("correct_index")
        return False

    def _finish_quiz(self, timed_out=False):
        self.timer_running = False
        questions = self.current_quiz["questions"]
        correct_count = sum(
            1 for i, q in enumerate(questions)
            if self._is_answer_correct(q, self.user_answers[i])
        )
        pct = int((correct_count / len(questions)) * 100) if questions else 0
        points = correct_count * 25
        elapsed = self.quiz_total_seconds - self.quiz_seconds_left
        mins, secs = divmod(max(0, elapsed), 60)

        if self.current_quiz:
            qid = self.current_quiz.get("id")
            self.current_quiz["students_taken"] = self.current_quiz.get("students_taken", 0) + 1
            for q in self.quizzes:
                if q.get("id") == qid:
                    q["students_taken"] = q.get("students_taken", 0) + 1
                    threading.Thread(target=self.cloud.save_quiz, args=(dict(q),), daemon=True).start()
                    break
            self._save_local_cache()

        streak = config.record_quiz_completion_and_get_streak()
        streak_str = f"{streak} Day" if streak == 1 else f"{streak} Days"
        self.current_streak_str = streak_str

        self._set_body(build_results_page(self, pct, correct_count, len(questions), points, f"{mins}m {secs}s", streak_str=streak_str))
        if timed_out:
            self.dialog_info("Time's Up!", "Quiz time has expired. Submitting your answers!")

    def _goto_answer_review(self):
        self._set_body(build_answer_review(self), show_nav=False)

    def _back_to_results(self):
        pct, correct, total, points, time_taken_str = self._last_result
        self._set_body(build_results_page(self, pct, correct, total, points, time_taken_str))

    def goto_dashboard(self):
        self.editing_quiz_id = None
        self.current_route = "dashboard"
        self._set_body(build_dashboard(self), show_nav=True, active_nav=0)
        self._refresh_bottom_nav()

    def goto_library(self):
        self.editing_quiz_id = None
        self.current_route = "library"
        self._set_body(build_library(self), show_nav=True, active_nav=1)
        self._refresh_bottom_nav()

def main(page: ft.Page):
    ProfQuizzerApp(page)

if __name__ == "__main__":
    ft.run(main, port=8550, assets_dir="assets")