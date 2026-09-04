import flet as ft
import config
from components.common import card


def build_settings(app):
    header = app.build_header("Settings", subtitle="App preferences",
                              show_back=True, on_back=app.goto_dashboard)

    dark_row = ft.Row([
        ft.Column([
            ft.Text("Dark Mode", size=14, weight=ft.FontWeight.W_800, color=config.TEXT_ON_SURFACE),
            ft.Text("Switch the whole app to a dark color theme.", size=11, color=config.TEXT_MUTED),
        ], spacing=2, expand=True),
        ft.Switch(value=app.dark_mode, on_change=app._toggle_dark_mode),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    random_row = ft.Row([
        ft.Column([
            ft.Text("Shuffle Questions", size=14, weight=ft.FontWeight.W_800, color=config.TEXT_ON_SURFACE),
            ft.Text("Show quiz questions in random order instead of creation order.",
                    size=11, color=config.TEXT_MUTED),
        ], spacing=2, expand=True),
        ft.Switch(value=app.randomize_questions, on_change=app._toggle_randomize),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    mode_row = ft.Row([
        ft.Column([
            ft.Text("Answer MC via Fill in the Blank", size=14, weight=ft.FontWeight.W_800, color=config.TEXT_ON_SURFACE),
            ft.Text("Default to typing answers for multiple-choice questions.",
                    size=11, color=config.TEXT_MUTED),
        ], spacing=2, expand=True),
        ft.Switch(value=(app.default_answer_mode == "fill_blank"), on_change=app._toggle_answer_mode),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    ui_mode_row = ft.Row([
        ft.Column([
            ft.Text("Desktop & Web Responsive Layout", size=14, weight=ft.FontWeight.W_800, color=config.TEXT_ON_SURFACE),
            ft.Text("Expand into a multi-column wide layout for Desktop PC, Mac, and Web browsers.",
                    size=11, color=config.TEXT_MUTED),
        ], spacing=2, expand=True),
        ft.Switch(value=(app.ui_mode == "desktop"), on_change=app._toggle_ui_mode),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    settings_card = card(ft.Column([
        ft.Text("Appearance & Quiz Behavior", size=15, weight=ft.FontWeight.W_800, color=config.PRIMARY),
        dark_row,
        ft.Container(height=1, bgcolor=config.BORDER_COLOR),
        random_row,
        ft.Container(height=1, bgcolor=config.BORDER_COLOR),
        mode_row,
        ft.Container(height=1, bgcolor=config.BORDER_COLOR),
        ui_mode_row,
    ], spacing=14))

    more_note = ft.Text("Preferences are saved automatically on this device.", size=11,
                         italic=True, color=config.TEXT_MUTED, text_align=ft.TextAlign.CENTER)

    body_container = ft.Container(
        content=ft.Column(
            [settings_card, more_note],
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        expand=True,
        alignment=ft.Alignment.TOP_CENTER,
    )

    content = ft.ListView(
        controls=[
            ft.Row([body_container], alignment=ft.MainAxisAlignment.CENTER, expand=True),
        ],
        spacing=16,
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
        expand=True,
    )
    return ft.Column([header, content], expand=True, spacing=0)
