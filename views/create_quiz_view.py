import flet as ft
import config
from components.common import card, field_label, pill, kebab_menu


def build_create_setup(app):
    header = app.build_header("Setup Quiz", subtitle="Step 1 of 3: Quiz Basics",
                              show_back=True, on_back=app.goto_dashboard)
    progress = ft.ProgressBar(value=0.33, height=4, color=config.PRIMARY, bgcolor=config.SURFACE_LOW)

    app.input_new_title = ft.TextField(
        value=app.new_quiz_data.get("title", ""),
        hint_text="e.g. Introduction to Organic Chemistry",
        height=44,
        border_radius=12,
        border_color=config.BORDER_COLOR,
        content_padding=ft.Padding.only(left=12),
        color=config.INPUT_TEXT_COLOR,
    )

    app.combo_subject = ft.Dropdown(
        value=app.new_quiz_data.get("subject", "Science"),
        options=[ft.dropdown.Option(s) for s in app.subjects],
        height=44,
        border_radius=12,
        border_color=config.BORDER_COLOR,
        color=config.INPUT_TEXT_COLOR,
    )
    add_custom_btn = ft.TextButton(
        "+ Type Custom Subject",
        on_click=lambda e: app._prompt_add_subject_inline(),
        style=ft.ButtonStyle(color=config.PRIMARY),
    )

    app.input_new_desc = ft.TextField(
        value=app.new_quiz_data.get("description", ""),
        hint_text="Briefly describe what this quiz covers and instructions for students...",
        multiline=True,
        min_lines=3,
        max_lines=4,
        border_radius=12,
        border_color=config.BORDER_COLOR,
        color=config.INPUT_TEXT_COLOR,
    )

    basics_card = card(ft.Column([
        ft.Text("Quiz Basics", size=16, weight=ft.FontWeight.W_800, color=config.PRIMARY),
        field_label("Quiz Title"),
        app.input_new_title,
        ft.Row([field_label("Subject Category"), ft.Container(expand=True), add_custom_btn]),
        app.combo_subject,
        field_label("Description (Optional)"),
        app.input_new_desc,
    ], spacing=8))

    # Cover color swatches
    colors = [config.PRIMARY, config.SECONDARY, config.TERTIARY, "#8e44ad"]
    app.color_swatches = []
    swatch_row = []
    for c in colors:
        selected = c == app.color_choice
        sw = ft.Container(
            width=40,
            height=40,
            bgcolor=c,
            border_radius=20,
            border=ft.Border.all(2, "white" if not selected else config.TEXT_ON_SURFACE),
            content=ft.Text("✓", color="white", weight=ft.FontWeight.BOLD) if selected else None,
            alignment=ft.Alignment.CENTER,
            on_click=lambda e, col=c: app._select_cover_color(col),
            ink=True,
            data=c,
        )
        app.color_swatches.append(sw)
        swatch_row.append(sw)

    # Difficulty toggle
    app.diff_buttons = {}
    diff_row = []
    for d in ["Easy", "Medium", "Hard"]:
        active = d == app.current_difficulty
        btn = ft.Container(
            content=ft.Text(d, size=13, weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_600,
                             color="white" if active else config.TEXT_ON_SURFACE),
            bgcolor=config.PRIMARY if active else config.SURFACE_LOW,
            border=None if active else ft.Border.all(1, config.BORDER_COLOR),
            border_radius=10,
            height=38,
            expand=True,
            alignment=ft.Alignment.CENTER,
            on_click=lambda e, lvl=d: app._select_difficulty(lvl),
            ink=True,
        )
        app.diff_buttons[d] = btn
        diff_row.append(btn)

    app.input_new_time = ft.TextField(
        value=str(app.new_quiz_data.get("time_mins", 15)),
        height=44,
        border_radius=12,
        border_color=config.BORDER_COLOR,
        content_padding=ft.Padding.only(left=12),
        keyboard_type=ft.KeyboardType.NUMBER,
        color=config.INPUT_TEXT_COLOR,
    )

    settings_card = card(ft.Column([
        ft.Text("Visuals & Rules", size=16, weight=ft.FontWeight.W_800, color=config.PRIMARY),
        field_label("Cover Color Theme"),
        ft.Row(swatch_row, spacing=10),
        field_label("Difficulty Level"),
        ft.Row(diff_row, spacing=8),
        field_label("Time Limit (Minutes)"),
        app.input_new_time,
    ], spacing=8))

    next_btn = ft.Container(
        content=ft.Text("Continue to Questions →", size=15, weight=ft.FontWeight.BOLD, color="white"),
        bgcolor=config.PRIMARY,
        border_radius=14,
        height=50,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app._validate_and_goto_add_questions(),
        ink=True,
    )

    body_container = ft.Container(
        content=ft.Column([basics_card, settings_card, next_btn], spacing=16),
        expand=True,
    )

    content = ft.ListView(
        controls=[ft.Row([body_container], alignment=ft.MainAxisAlignment.CENTER, expand=True)],
        spacing=16,
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
        expand=True,
    )
    return ft.Column([header, progress, content], expand=True, spacing=0)


def build_add_questions(app):
    header = app.build_header("Manage Questions", subtitle="Step 2 of 3: Add & Edit Questions",
                              show_back=True, on_back=app.goto_create_setup_from_step2)
    progress = ft.ProgressBar(value=0.66, height=4, color=config.PRIMARY, bgcolor=config.SURFACE_LOW)

    q_count = len(app.new_quiz_data.get("questions", []))
    app.existing_q_header = ft.Text(f"Questions in this Quiz ({q_count}):", size=15,
                                      weight=ft.FontWeight.W_800, color=config.PRIMARY)
    app.existing_q_list = ft.Column(app._build_existing_question_rows(), spacing=8)

    app.q_form_header = ft.Text(
        f"Editing Question #{app.editing_question_idx + 1}" if app.editing_question_idx is not None
        else "+ Add New Question", size=15, weight=ft.FontWeight.W_800, color=config.PRIMARY,
    )

    app.input_question_text = ft.TextField(
        hint_text="Type question prompt here...",
        multiline=True,
        min_lines=3,
        max_lines=4,
        border_radius=12,
        border_color=config.BORDER_COLOR,
        color=config.INPUT_TEXT_COLOR,
    )
    q_card = card(ft.Column([field_label("Question Prompt"), app.input_question_text], spacing=8))

    # Question type toggle: Multiple Choice vs Fill in the Blank
    app.qtype_buttons = {}
    qtype_row = []
    for qt, label in [("multiple_choice", "Multiple Choice"), ("fill_blank", "Fill in the Blank")]:
        active = qt == app.current_question_type
        btn = ft.Container(
            content=ft.Text(label, size=12, weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_600,
                             color="white" if active else config.TEXT_ON_SURFACE),
            bgcolor=config.PRIMARY if active else config.SURFACE_LOW,
            border=None if active else ft.Border.all(1, config.BORDER_COLOR),
            border_radius=10,
            height=38,
            expand=True,
            alignment=ft.Alignment.CENTER,
            on_click=lambda e, t=qt: app._select_question_type(t),
            ink=True,
        )
        app.qtype_buttons[qt] = btn
        qtype_row.append(btn)
    qtype_card = card(ft.Column([
        field_label("Question Type"),
        ft.Row(qtype_row, spacing=8),
    ], spacing=8))

    app.opt_inputs = []
    app.opt_tags = []
    app.opt_rows = []
    radios_col = []
    for i in range(4):
        radio = ft.Radio(value=str(i))
        tag = ft.Container(
            content=ft.Text(f" {config.LETTERS[i]} ", size=12, weight=ft.FontWeight.W_800, color=config.PRIMARY),
            bgcolor=config.SURFACE_LOW,
            border_radius=6,
            padding=ft.Padding.symmetric(horizontal=6, vertical=4),
        )
        opt_edit = ft.TextField(
            hint_text=f"Option {config.LETTERS[i]} text...",
            height=40,
            border_radius=10,
            border_color=config.BORDER_COLOR,
            content_padding=ft.Padding.only(left=12),
            expand=True,
            color=config.INPUT_TEXT_COLOR,
        )
        app.opt_inputs.append(opt_edit)
        app.opt_tags.append(tag)
        row = ft.Container(
            content=ft.Row([radio, tag, opt_edit], spacing=8),
            border_radius=10,
            border=ft.Border.all(1.5, "transparent"),
            padding=ft.Padding.symmetric(horizontal=4),
        )
        app.opt_rows.append(row)
        radios_col.append(row)

    app.radio_group = ft.RadioGroup(
        content=ft.Column(radios_col, spacing=6),
        value=app.correct_option_idx,
        on_change=app._on_correct_radio_change,
    )
    opt_card = card(ft.Column([
        field_label("Options (select the radio button for the correct answer)"),
        app.radio_group,
    ], spacing=10))
    opt_card.visible = (app.current_question_type == "multiple_choice")
    app.opt_card_container = opt_card

    # Fill in the blank: single correct-answer text field
    app.input_blank_answer = ft.TextField(
        hint_text="Type the exact correct answer...",
        height=48,
        border_radius=12,
        border_color=config.BORDER_COLOR,
        content_padding=ft.Padding.only(left=12),
        color=config.INPUT_TEXT_COLOR,
    )
    blank_card = card(ft.Column([
        field_label("Correct Answer"),
        app.input_blank_answer,
        ft.Text("Students' typed answers aren't case-sensitive and ignore extra spaces.",
                size=11, color=config.TEXT_MUTED),
    ], spacing=8))
    blank_card.visible = (app.current_question_type == "fill_blank")
    app.blank_card_container = blank_card

    add_more_btn = ft.Container(
        content=ft.Text("+ Save & Add Question to Quiz", size=13, weight=ft.FontWeight.BOLD, color=config.PRIMARY),
        bgcolor=config.SURFACE_LOW,
        border=ft.Border.all(2, config.PRIMARY),
        border_radius=12,
        height=46,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app._save_question_and_add_another(),
        ink=True,
    )
    review_btn = ft.Container(
        content=ft.Text("Review & Save Quiz →", size=15, weight=ft.FontWeight.BOLD, color="white"),
        bgcolor=config.PRIMARY,
        border_radius=14,
        height=50,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app._save_question_and_review(),
        ink=True,
    )

    body_container = ft.Container(
        content=ft.Column([
            app.existing_q_header,
            app.existing_q_list,
            ft.Container(height=1, bgcolor=config.BORDER_COLOR),
            app.q_form_header,
            q_card,
            qtype_card,
            opt_card,
            blank_card,
            add_more_btn,
            review_btn,
        ], spacing=14),
        expand=True,
    )

    content = ft.ListView(
        controls=[ft.Row([body_container], alignment=ft.MainAxisAlignment.CENTER, expand=True)],
        spacing=14,
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
        expand=True,
    )
    return ft.Column([header, progress, content], expand=True, spacing=0)


def build_review_publish(app):
    header = app.build_header("Review Quiz", subtitle="Step 3 of 3: Summary",
                              show_back=True, on_back=app.goto_add_questions)
    progress = ft.ProgressBar(value=1.0, height=4, color=config.PRIMARY, bgcolor=config.SURFACE_LOW)

    top_card = card(ft.Column([
        ft.Text(app.new_quiz_data.get("title", "Untitled Quiz"), size=16, weight=ft.FontWeight.W_800),
        ft.Text(
            f"Subject: {app.new_quiz_data.get('subject')}  ·  ⏱ {app.new_quiz_data.get('time_mins')} Mins  ·  "
            f"Difficulty: {app.new_quiz_data.get('difficulty')}",
            size=11,
            color=config.TEXT_MUTED,
            weight=ft.FontWeight.W_600,
        ),
    ], spacing=6))

    questions = app.new_quiz_data.get("questions", [])
    q_header = ft.Text(f"Questions to Save ({len(questions)})", size=15, weight=ft.FontWeight.W_800)

    app.review_q_list = ft.Column(app._build_review_question_cards(), spacing=12)

    add_more_btn = ft.Container(
        content=ft.Text("+ Add Another Question", size=13, weight=ft.FontWeight.BOLD, color=config.PRIMARY),
        bgcolor=config.SURFACE_LOW,
        border=ft.Border.all(2, config.PRIMARY),
        border_radius=12,
        height=44,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app.goto_add_questions(),
        ink=True,
    )

    draft_btn = ft.Container(
        content=ft.Text("Save Draft", size=13, weight=ft.FontWeight.BOLD, color=config.PRIMARY),
        bgcolor=config.SURFACE_LOW,
        border=ft.Border.all(1, config.PRIMARY),
        border_radius=12,
        height=48,
        expand=True,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app._save_new_quiz_as_draft(),
        ink=True,
    )
    pub_label = "Update Quiz ✓" if app.editing_quiz_id else "Publish Quiz 🚀"
    pub_btn = ft.Container(
        content=ft.Text(pub_label, size=14, weight=ft.FontWeight.BOLD, color="white"),
        bgcolor=config.PRIMARY,
        border_radius=12,
        height=48,
        expand=True,
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: app._publish_new_quiz(),
        ink=True,
    )

    body_container = ft.Container(
        content=ft.Column([top_card, q_header, app.review_q_list, add_more_btn, ft.Container(height=10)], spacing=14),
        expand=True,
    )

    content = ft.ListView(
        controls=[ft.Row([body_container], alignment=ft.MainAxisAlignment.CENTER, expand=True)],
        spacing=14,
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
        expand=True,
    )

    bottom_bar = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Row([draft_btn, pub_btn], spacing=12),
                expand=True,
            )
        ], alignment=ft.MainAxisAlignment.CENTER),
        height=75,
        padding=ft.Padding.symmetric(horizontal=20, vertical=10),
        bgcolor=config.BG_SURFACE,
        border=ft.Border.only(top=ft.BorderSide(1, config.BORDER_COLOR)),
    )

    return ft.Column([header, progress, content, bottom_bar], expand=True, spacing=0)
