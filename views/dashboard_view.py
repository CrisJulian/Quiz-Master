import flet as ft
import config
from components.common import CARD_SHADOW


def build_dashboard(app):
    header = app.build_header("Quiz Master", show_logo=True)

    search_row = ft.TextField(
        hint_text="🔍  Search quizzes by title or topic...",
        value=app.dash_search_text,
        height=46,
        border_radius=14,
        border_color=config.BORDER_COLOR,
        bgcolor=config.BG_SURFACE,
        content_padding=ft.Padding.only(left=14),
        text_size=13,
        text_style=ft.TextStyle(color=config.INPUT_TEXT_COLOR),
        on_change=app._on_dash_search,
    )

    stats_row = ft.ResponsiveRow(
        [
            ft.Container(
                content=app._stat_card("📄", str(len(app.quizzes)), "TOTAL QUIZZES", config.PRIMARY),
                col={"xs": 6, "sm": 6, "md": 6, "lg": 6},
            ),
            ft.Container(
                content=app._stat_card(
                    "👥",
                    str(sum(q.get("students_taken", 0) for q in app.quizzes)),
                    "QUIZ TAKEN",
                    config.TERTIARY,
                ),
                col={"xs": 6, "sm": 6, "md": 6, "lg": 6},
            ),
        ],
        spacing=14,
        run_spacing=14,
    )

    active_header = ft.Row([
        ft.Text("Active Quizzes", size=17, weight=ft.FontWeight.W_800, color=config.TEXT_ON_SURFACE),
        ft.Container(expand=True),
        ft.TextButton("View All", on_click=lambda e: app.goto_library(),
                      style=ft.ButtonStyle(color=config.PRIMARY)),
    ])

    app.quiz_cards_container = ft.ResponsiveRow(app._get_quiz_card_controls(), spacing=12, run_spacing=12)

    drafts_header = ft.Text("Recent Drafts", size=17, color=config.TEXT_ON_SURFACE, weight=ft.FontWeight.W_800)
    drafts_row = ft.Row(
        [app._draft_card(d) for d in app.drafts] + [app._add_draft_card()],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
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
            search_row,
            stats_row,
            active_header,
            app.quiz_cards_container,
            drafts_header,
            ft.Container(content=drafts_row, height=125),
            ft.Container(height=60),
        ],
        spacing=18,
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
