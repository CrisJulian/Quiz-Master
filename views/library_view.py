import flet as ft
import config
from components.common import card, CARD_SHADOW


def build_library(app):
    header = app.build_header("Quiz Library", subtitle="All Quizzes & Subjects",
                              show_back=True, on_back=app.goto_dashboard)

    app.code_input = ft.TextField(
        hint_text="Enter Quiz Code (e.g. BIO101, MATH101)",
        height=44,
        border_radius=12,
        bgcolor=config.SURFACE_LOW,
        border_color=config.BORDER_COLOR,
        content_padding=ft.Padding.only(left=12),
        text_size=13,
        text_style=ft.TextStyle(color=config.INPUT_TEXT_COLOR),
    )
    join_card = card(ft.Column([
        ft.Text("Launch Quiz by Code", size=15, weight=ft.FontWeight.W_800),
        ft.Row([
            ft.Container(content=app.code_input, expand=True),
            ft.Container(
                content=ft.Text("Launch", size=13, weight=ft.FontWeight.BOLD, color="white"),
                width=70,
                height=44,
                bgcolor=config.PRIMARY,
                border_radius=12,
                alignment=ft.Alignment.CENTER,
                on_click=app._handle_join_quiz,
                ink=True,
            ),
        ], spacing=8),
    ], spacing=8))

    chips = app._library_chip_row()
    search_field = ft.TextField(
        hint_text="🔍  Search topics, subjects...",
        value=app.lib_search_text,
        height=42,
        border_radius=12,
        border_color=config.BORDER_COLOR,
        bgcolor=config.BG_SURFACE,
        content_padding=ft.Padding.only(left=12),
        text_size=13,
        text_style=ft.TextStyle(color=config.INPUT_TEXT_COLOR),
        on_change=app._on_lib_search,
    )

    app.lib_cards_container = ft.ResponsiveRow(
        app._get_library_card_controls(),
        spacing=12,
        run_spacing=12,
    )

    fab = ft.Container(
        content=ft.Icon(ft.Icons.ADD, color="white", size=28),
        width=54,
        height=54,
        bgcolor=config.PRIMARY,
        border_radius=27,
        alignment=ft.Alignment.CENTER,
        shadow=CARD_SHADOW,
        ink=True,
        on_click=lambda e: app.goto_create_setup(),
    )

    content = ft.ListView(
        controls=[
            join_card,
            chips,
            search_field,
            app.lib_cards_container,
            ft.Container(height=60),
        ],
        spacing=16,
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
        expand=True,
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
