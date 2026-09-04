import flet as ft
import config
from components.common import card, pill


def build_intro(app):
    q = app.current_quiz
    header = app.build_header("Quiz Overview", show_back=True, on_back=app.goto_dashboard)

    has_mc = any(
        qq.get("question_type", "multiple_choice") == "multiple_choice" or bool(qq.get("options"))
        for qq in q["questions"]
    )
    q_types_present = set(qq.get("question_type", "multiple_choice") for qq in q["questions"])
    if q_types_present == {"fill_blank"}:
        format_label = "Fill in the Blank"
    elif q_types_present == {"multiple_choice"}:
        format_label = "Multiple Choice"
    else:
        format_label = "Mixed Format"

    mode_selector_section = []
    if has_mc:
        is_mc_mode = app.quiz_answering_mode != "fill_blank"
        btn_mc = ft.Container(
            content=ft.Row([
                ft.Text("🔘", size=13),
                ft.Text(
                    "Multiple Choice",
                    size=12,
                    weight=ft.FontWeight.BOLD if is_mc_mode else ft.FontWeight.W_500,
                    color="white" if is_mc_mode else config.TEXT_ON_SURFACE,
                ),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=config.PRIMARY if is_mc_mode else config.SURFACE_LOW,
            border=None if is_mc_mode else ft.Border.all(1, config.BORDER_COLOR),
            border_radius=10,
            height=40,
            expand=True,
            alignment=ft.Alignment.CENTER,
            on_click=lambda e: app._set_intro_answer_mode("standard"),
            ink=True,
        )
        btn_fb = ft.Container(
            content=ft.Row([
                ft.Text("✍️", size=13),
                ft.Text(
                    "Fill in Blank",
                    size=12,
                    weight=ft.FontWeight.BOLD if not is_mc_mode else ft.FontWeight.W_500,
                    color="white" if not is_mc_mode else config.TEXT_ON_SURFACE,
                ),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=config.PRIMARY if not is_mc_mode else config.SURFACE_LOW,
            border=None if not is_mc_mode else ft.Border.all(1, config.BORDER_COLOR),
            border_radius=10,
            height=40,
            expand=True,
            alignment=ft.Alignment.CENTER,
            on_click=lambda e: app._set_intro_answer_mode("fill_blank"),
            ink=True,
        )
        mode_selector_section = [
            ft.Container(height=4),
            ft.Text("MC Question Answering Style:", size=12, weight=ft.FontWeight.BOLD, color=config.TEXT_ON_SURFACE),
            ft.Row([btn_mc, btn_fb], spacing=8),
            ft.Text(
                "Choose to answer multiple-choice questions by clicking options or typing the answers.",
                size=11,
                color=config.TEXT_MUTED,
                text_align=ft.TextAlign.CENTER,
            ),
        ]

    hero = card(
        ft.Column([
            ft.Container(
                content=ft.Text(q.get("icon", "📝"), size=32),
                width=70,
                height=70,
                bgcolor=config.SURFACE_LOW,
                border_radius=35,
                alignment=ft.Alignment.CENTER,
            ),
            ft.Text(
                q["title"],
                size=20,
                weight=ft.FontWeight.W_800,
                color=config.TEXT_ON_SURFACE,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Text(
                q.get("description", "Comprehensive academic quiz."),
                size=13,
                color=config.TEXT_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(
                bgcolor=config.SURFACE_LOW,
                border_radius=14,
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                content=ft.Column([
                    ft.Text(
                        f"📋  {len(q['questions'])} Questions  ·  {format_label}",
                        size=12,
                        weight=ft.FontWeight.W_800,
                        color=config.PRIMARY,
                    ),
                    ft.Text(
                        f"⏱  {q.get('time_mins', 15)} Minutes  ·  Timed Assessment",
                        size=12,
                        weight=ft.FontWeight.W_600,
                    ),
                    ft.Text(
                        f"📊  {q.get('difficulty', 'Intermediate')} Level",
                        size=12,
                        weight=ft.FontWeight.W_600,
                    ),
                ], spacing=8),
            ),
            *mode_selector_section,
            ft.Container(
                content=ft.Text("Start Quiz Now  ▶", size=16, weight=ft.FontWeight.BOLD, color="white"),
                bgcolor=config.PRIMARY,
                border_radius=14,
                height=52,
                alignment=ft.Alignment.CENTER,
                on_click=lambda e: app._start_live_quiz(),
                ink=True,
            ),
        ], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=20, vertical=24),
        radius=24,
    )

    body_container = ft.Container(
        content=hero,
        expand=True,
        alignment=ft.Alignment.CENTER,
    )
    content = ft.ListView(
        controls=[ft.Row([body_container], alignment=ft.MainAxisAlignment.CENTER, expand=True)],
        padding=ft.Padding.all(24),
        expand=True,
    )
    return ft.Column([header, content], expand=True, spacing=0)


def build_taking_page(app):
    exit_btn = ft.Container(
        content=ft.Text("✕", size=14, weight=ft.FontWeight.BOLD, color=config.TEXT_MUTED),
        width=36,
        height=36,
        bgcolor=config.SURFACE_LOW,
        border_radius=18,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app._prompt_exit_quiz(),
        ink=True,
    )
    mins, secs = divmod(app.quiz_seconds_left, 60)
    is_urgent = app.quiz_seconds_left <= 60
    app.lbl_timer = ft.Text(
        f"⏱ {mins:02d}:{secs:02d}",
        size=13,
        weight=ft.FontWeight.BOLD,
        color=config.ERROR if is_urgent else config.TEXT_ON_SURFACE,
    )
    app.timer_chip = ft.Container(
        content=app.lbl_timer,
        bgcolor=config.ERROR_CONTAINER if is_urgent else config.SURFACE_HIGH,
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border=ft.Border.all(1, config.ERROR) if is_urgent else None,
    )
    header = ft.Container(
        height=60,
        padding=ft.Padding.symmetric(horizontal=16),
        bgcolor=config.BG_SURFACE,
        border=ft.Border.only(bottom=ft.BorderSide(1, config.BORDER_COLOR)),
        content=ft.Row([
            exit_btn,
            ft.Container(expand=True),
            ft.Text("Quiz Master", size=16, weight=ft.FontWeight.W_800, color=config.PRIMARY),
            ft.Container(expand=True),
            app.timer_chip,
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )

    total = len(app.current_quiz["questions"])
    app.taking_progress = ft.ProgressBar(
        value=(app.quiz_question_idx + 1) / total,
        height=4,
        color=config.PRIMARY,
        bgcolor=config.SURFACE_LOW,
    )

    app.lbl_q_step = ft.Text(
        f"QUESTION {app.quiz_question_idx + 1} OF {total}",
        size=11,
        weight=ft.FontWeight.W_800,
        color=config.PRIMARY,
    )
    app.lbl_q_text = ft.Text("", size=16, weight=ft.FontWeight.W_800, color=config.TEXT_ON_SURFACE)

    app.taking_options_col = ft.Column(spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    app.btn_next_q_text = ft.Text("Next Question →", size=15, weight=ft.FontWeight.BOLD, color="white")
    app.btn_next_q = ft.Container(
        content=app.btn_next_q_text,
        bgcolor=config.PRIMARY,
        border_radius=12,
        height=48,
        expand=True,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app._submit_answer_and_next(),
        ink=True,
    )
    skip_btn = ft.Container(
        content=ft.Text("Skip", size=13, weight=ft.FontWeight.BOLD, color=config.PRIMARY),
        border=ft.Border.all(2, config.PRIMARY),
        border_radius=12,
        height=48,
        width=80,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app._skip_question(),
        ink=True,
    )
    bottom_bar = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Row([skip_btn, app.btn_next_q], spacing=12),
                expand=True,
            )
        ], alignment=ft.MainAxisAlignment.CENTER),
        height=75,
        padding=ft.Padding.symmetric(horizontal=20, vertical=10),
        bgcolor=config.BG_SURFACE,
        border=ft.Border.only(top=ft.BorderSide(1, config.BORDER_COLOR)),
    )

    body_container = ft.Container(
        content=ft.Column([app.lbl_q_step, app.lbl_q_text, app.taking_options_col], spacing=14),
        expand=True,
    )

    content = ft.ListView(
        controls=[ft.Row([body_container], alignment=ft.MainAxisAlignment.CENTER, expand=True)],
        spacing=14,
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
        expand=True,
    )

    app._render_current_live_question()
    return ft.Column([header, app.taking_progress, content, bottom_bar], expand=True, spacing=0)


def build_results_page(app, pct, correct, total, points, time_taken_str, streak_str=None):
    if not streak_str:
        streak_str = getattr(app, "current_streak_str", "1 Day")
    header = app.build_header("Quiz Results", subtitle="Great effort!")

    top_box = ft.Column([
        ft.Container(
            content=ft.Text("🏆", size=30),
            width=64,
            height=64,
            bgcolor=config.SURFACE_LOW,
            border_radius=32,
            alignment=ft.Alignment.CENTER,
        ),
        ft.Text("Quiz Complete!", size=22, weight=ft.FontWeight.W_800),
    ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    score_card = card(
        ft.Column([
            app.circular_progress(pct),
            ft.Text(f"{correct}/{total} Correct", size=18, weight=ft.FontWeight.W_800, color=config.PRIMARY),
            ft.Container(
                content=ft.Text(f"🪙  +{points} Points Earned", size=13, weight=ft.FontWeight.W_800, color=config.PRIMARY),
                bgcolor=config.PRIMARY_LIGHT,
                border_radius=12,
                padding=ft.Padding.symmetric(horizontal=14, vertical=6),
            ),
        ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.all(20),
        radius=20,
    )

    def bento(icon_label, value):
        return card(
            ft.Column([
                ft.Text(icon_label, size=10, weight=ft.FontWeight.BOLD, color=config.TEXT_MUTED),
                ft.Text(value, size=14, weight=ft.FontWeight.W_800),
            ]),
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            radius=14,
        )

    bento_row = ft.Row([bento("⏱  TIME TAKEN", time_taken_str), bento("🔥  STREAK", streak_str)], spacing=10)
    bento_row.controls[0].expand = True
    bento_row.controls[1].expand = True

    review_btn = ft.Container(
        content=ft.Text("👁  Review Answers", size=14, weight=ft.FontWeight.BOLD, color="white"),
        bgcolor=config.PRIMARY,
        border_radius=14,
        height=50,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app._goto_answer_review(),
        ink=True,
    )
    retake_btn = ft.Container(
        content=ft.Text("🔄  Retake Quiz", size=14, weight=ft.FontWeight.BOLD, color=config.PRIMARY),
        border=ft.Border.all(2, config.PRIMARY),
        border_radius=14,
        height=48,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app._start_live_quiz(),
        ink=True,
    )
    home_btn = ft.Container(
        content=ft.Text("🏠  Back to Dashboard", size=13, weight=ft.FontWeight.W_600, color=config.TEXT_MUTED),
        height=44,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app.goto_dashboard(),
        ink=True,
    )

    body_container = ft.Container(
        content=ft.Column([top_box, score_card, bento_row, review_btn, retake_btn, home_btn], spacing=16),
        expand=True,
    )

    content = ft.ListView(
        controls=[ft.Row([body_container], alignment=ft.MainAxisAlignment.CENTER, expand=True)],
        spacing=16,
        padding=ft.Padding.all(24),
        expand=True,
    )
    app._last_result = (pct, correct, total, points, time_taken_str)
    return ft.Column([header, content], expand=True, spacing=0)


def build_answer_review(app):
    header = app.build_header(
        "Answer Breakdown",
        subtitle="Detailed Review",
        show_back=True,
        on_back=app._back_to_results,
    )

    questions = app.current_quiz["questions"]
    cards = []
    for idx, q in enumerate(questions):
        q_type = q.get("question_type", "multiple_choice")
        user_val = app.user_answers[idx]
        is_correct = app._is_answer_correct(q, user_val)

        if isinstance(user_val, str):
            user_ans_text = user_val.strip() if user_val.strip() else "Skipped"
        elif isinstance(user_val, int) and 0 <= user_val < len(q.get("options", [])):
            user_ans_text = f"[{config.LETTERS[user_val]}] {q['options'][user_val]}"
        else:
            user_ans_text = "Skipped"

        if q_type == "fill_blank":
            correct_display = q.get("correct_answer", "")
        else:
            c_idx = q.get("correct_index", 0)
            options = q.get("options", [])
            correct_opt = options[c_idx] if 0 <= c_idx < len(options) else ""
            letter = config.LETTERS[c_idx] if c_idx < len(config.LETTERS) else ""
            correct_display = f"[{letter}] {correct_opt}" if letter else correct_opt

        status = ft.Container(
            content=ft.Text(
                "✓ Correct" if is_correct else "✕ Incorrect",
                size=11,
                weight=ft.FontWeight.BOLD,
                color=config.SUCCESS if is_correct else config.ERROR,
            ),
            bgcolor=config.SUCCESS_CONTAINER if is_correct else config.ERROR_CONTAINER,
            border_radius=6,
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        )
        children = [
            ft.Row([
                ft.Text(f"QUESTION {idx + 1}", size=10, weight=ft.FontWeight.BOLD, color=config.TEXT_MUTED),
                ft.Container(expand=True),
                status,
            ]),
            ft.Text(q["question"], size=14, weight=ft.FontWeight.W_800),
            ft.Container(
                content=ft.Text(
                    f"Your Answer: {user_ans_text}",
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=config.SUCCESS if is_correct else config.ERROR,
                ),
                bgcolor=config.SUCCESS_CONTAINER if is_correct else config.ERROR_CONTAINER,
                border_radius=10,
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            ),
        ]
        if not is_correct:
            children.append(
                ft.Container(
                    content=ft.Text(
                        f"Correct Answer: {correct_display}",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=config.PRIMARY,
                    ),
                    bgcolor=config.SURFACE_LOW,
                    border=ft.Border.all(1, config.BORDER_COLOR),
                    border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                )
            )
        cards.append(card(ft.Column(children, spacing=8), padding=ft.Padding.symmetric(horizontal=16, vertical=14)))

    back_btn = ft.Container(
        content=ft.Text("Back to Dashboard", size=14, weight=ft.FontWeight.BOLD, color="white"),
        bgcolor=config.PRIMARY,
        border_radius=14,
        height=50,
        alignment=ft.Alignment.CENTER,
        margin=ft.Margin.symmetric(horizontal=20, vertical=12),
        on_click=lambda e: app.goto_dashboard(),
        ink=True,
    )

    body_container = ft.Container(
        content=ft.Column(cards + [back_btn], spacing=14),
        expand=True,
    )

    content = ft.ListView(
        controls=[ft.Row([body_container], alignment=ft.MainAxisAlignment.CENTER, expand=True)],
        spacing=14,
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
        expand=True,
    )
    return ft.Column([header, content], expand=True, spacing=0)
