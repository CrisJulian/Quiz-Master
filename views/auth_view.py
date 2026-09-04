import flet as ft
import config
from components.common import card, field_label
from cloud_auth import PYREBASE_AVAILABLE


def build_login(app):
    is_signup = app.auth_mode == "signup"

    logo = ft.Container(
        content=ft.Image(src="logo.png", width=80, height=80, fit=ft.BoxFit.CONTAIN),
        width=104,
        height=104,
        bgcolor=config.PRIMARY_LIGHT,
        border_radius=52,
        alignment=ft.Alignment.CENTER,
    )
    title = ft.Text(
        "Quiz Master",
        size=24,
        weight=ft.FontWeight.W_800,
        color=config.PRIMARY,
        text_align=ft.TextAlign.CENTER,
    )
    subtitle = ft.Text(
        (
            "Create an account to sync your quizzes"
            if is_signup
            else "Log in to access your quizzes"
        ),
        size=13,
        color=config.TEXT_MUTED,
        text_align=ft.TextAlign.CENTER,
    )

    app.login_email = ft.TextField(
        label="Email",
        value="",
        height=48,
        border_radius=12,
        border_color=config.BORDER_COLOR,
        color=config.INPUT_TEXT_COLOR,
        content_padding=ft.Padding.symmetric(horizontal=12),
        autofocus=True,
        keyboard_type=ft.KeyboardType.EMAIL,
    )
    app.login_password = ft.TextField(
        label="Password",
        hint_text="Google accounts are detected automatically",
        password=True,
        can_reveal_password=True,
        height=48,
        border_radius=12,
        border_color=config.BORDER_COLOR,
        color=config.INPUT_TEXT_COLOR,
        content_padding=ft.Padding.symmetric(horizontal=12),
    )
    fields = [
        field_label("Email"),
        app.login_email,
        field_label("Password"),
        app.login_password,
    ]

    if is_signup:
        app.login_password_confirm = ft.TextField(
            label="Confirm Password",
            password=True,
            can_reveal_password=True,
            height=48,
            border_radius=12,
            border_color=config.BORDER_COLOR,
            color=config.INPUT_TEXT_COLOR,
            content_padding=ft.Padding.symmetric(horizontal=12),
        )
        fields += [
            field_label("Confirm Password"),
            app.login_password_confirm,
        ]
    else:
        forgot_btn = ft.TextButton(
            "Forgot password?",
            on_click=lambda e: app._handle_forgot_password(),
            style=ft.ButtonStyle(color=config.PRIMARY),
        )
        fields.append(ft.Row([ft.Container(expand=True), forgot_btn]))

    form_card = card(ft.Column(fields, spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))

    app.login_submit_text = ft.Text(
        "Sign Up" if is_signup else "Log In",
        size=15,
        weight=ft.FontWeight.BOLD,
        color="white",
    )
    submit_btn = ft.Container(
        content=app.login_submit_text,
        bgcolor=config.PRIMARY,
        border_radius=14,
        height=50,
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=lambda e: (
            app._do_signup(e) if is_signup else app._do_login(e)
        ),
    )

    # ---- Google OAuth Button & Divider ----
    divider_row = ft.Row(
        [
            ft.Container(
                expand=True, height=1, bgcolor=config.BORDER_COLOR
            ),
            ft.Text("OR", size=11, color=config.TEXT_MUTED, weight=ft.FontWeight.W_600),
            ft.Container(
                expand=True, height=1, bgcolor=config.BORDER_COLOR
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=10,
    )

    google_btn = ft.Container(
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.G_TRANSLATE, color=config.PRIMARY, size=20
                ),
                ft.Text(
                    "Continue with Google",
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color="black",
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
        ),
        bgcolor="white",
        border=ft.Border(
            top=ft.BorderSide(1, config.BORDER_COLOR),
            bottom=ft.BorderSide(1, config.BORDER_COLOR),
            left=ft.BorderSide(1, config.BORDER_COLOR),
            right=ft.BorderSide(1, config.BORDER_COLOR),
        ),
        border_radius=14,
        height=50,
        alignment=ft.Alignment.CENTER,
        ink=True,
        on_click=app.login_with_google,
    )

    toggle_row = ft.Row(
        [
            ft.Text(
                (
                    "Already have an account?"
                    if is_signup
                    else "Don't have an account?"
                ),
                size=12,
                color=config.TEXT_MUTED,
            ),
            ft.TextButton(
                "Log In" if is_signup else "Sign Up",
                on_click=lambda e: app._toggle_auth_mode(),
                style=ft.ButtonStyle(color=config.PRIMARY),
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=0,
    )

    offline_btn = ft.TextButton(
        "Continue without an account (local only)",
        on_click=lambda e: app._continue_offline(),
        style=ft.ButtonStyle(color=config.TEXT_MUTED),
    )

    firebase_ready = (
        PYREBASE_AVAILABLE
        and not app.cloud.config.get("apiKey", "").startswith("YOUR_")
    )
    notice = None
    if not firebase_ready:
        notice = ft.Container(
            content=ft.Text(
                "⚠ Firebase isn't configured yet — "
                "use 'Continue with Google' or 'Continue without an account' below.",
                size=11,
                color=config.TERTIARY,
                text_align=ft.TextAlign.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=8),
        )

    content_controls = [
        ft.Container(height=16),
        logo,
        title,
        subtitle,
        ft.Container(height=8),
        form_card,
        submit_btn,
        divider_row,
        google_btn,
        toggle_row,
    ]
    if notice:
        content_controls.append(notice)
    content_controls.append(offline_btn)

    auth_box = ft.Container(
        content=ft.Column(
            controls=content_controls,
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=420,
        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
    )

    content = ft.Container(
        content=ft.ListView(
            controls=[
                ft.Row([auth_box], alignment=ft.MainAxisAlignment.CENTER),
            ],
            expand=True,
            padding=ft.Padding.symmetric(vertical=12),
        ),
        expand=True,
        alignment=ft.Alignment.CENTER,
    )
    return ft.Column([content], expand=True, spacing=0)
