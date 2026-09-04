import flet as ft
import config

CARD_SHADOW = ft.BoxShadow(
    blur_radius=12, offset=ft.Offset(0, 3), color="#00000014"
)


def card(content, padding=16, radius=16, bgcolor=None,
         border_color=None, shadow=True):
    """A bordered, softly-shadowed surface container — the workhorse of the UI.
    bgcolor/border_color default to the CURRENT theme's colors, resolved at
    call time, so cards repaint correctly after a dark/light mode toggle."""
    if bgcolor is None:
        bgcolor = config.BG_SURFACE
    if border_color is None:
        border_color = config.BORDER_COLOR
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=radius,
        bgcolor=bgcolor,
        border=ft.Border.all(1, border_color) if border_color else None,
        shadow=CARD_SHADOW if shadow else None,
    )


def field_label(text):
    return ft.Text(text, size=13, weight=ft.FontWeight.BOLD, color=config.TEXT_ON_SURFACE)


def pill(text, fg, bg, size=10):
    return ft.Container(
        content=ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=fg),
        bgcolor=bg, border_radius=6, padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def kebab_menu(items):
    """items: list of (label, on_click) tuples -> a small circular '⋮' popup menu."""
    return ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Text("⋮", size=16, weight=ft.FontWeight.W_900, color=config.TEXT_ON_SURFACE),
            width=28, height=28, bgcolor=config.SURFACE_LOW, border_radius=8,
            alignment=ft.Alignment.CENTER,
        ),
        items=[ft.PopupMenuItem(content=ft.Text(label, size=12, weight=ft.FontWeight.BOLD), on_click=cb)
               for label, cb in items],
    )


def hex_to_light_bg(hex_color, blend=0.85, dark=False):
    h = hex_color.lstrip("#")
    if len(h) < 6:
        return hex_color
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    if dark:
        base_r, base_g, base_b = 22, 31, 31
        lr = int(r * 0.22 + base_r * 0.78)
        lg = int(g * 0.22 + base_g * 0.78)
        lb = int(b * 0.22 + base_b * 0.78)
    else:
        lr = int(r + (255 - r) * blend)
        lg = int(g + (255 - g) * blend)
        lb = int(b + (255 - b) * blend)
    return f"#{lr:02x}{lg:02x}{lb:02x}"
