"""
CampusX PowerPoint Generator - 17-slide dark theme presentation
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ── Theme Colors ──────────────────────────────────────────────────────────────
BG_DARK = RGBColor(0x0B, 0x0F, 0x1A)
BG_CARD = RGBColor(0x11, 0x18, 0x27)
CYAN = RGBColor(0x1D, 0xA1, 0xF2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GRAY = RGBColor(0x9C, 0xA3, 0xAF)
LIGHT_GRAY = RGBColor(0xD1, 0xD5, 0xDB)
GREEN = RGBColor(0x22, 0xC5, 0x5E)
ORANGE = RGBColor(0xF9, 0x73, 0x16)
PURPLE = RGBColor(0xA7, 0x8B, 0xFA)
RED = RGBColor(0xEF, 0x44, 0x44)
YELLOW = RGBColor(0xFA, 0xCC, 0x15)
DARK_CARD = RGBColor(0x1E, 0x29, 0x3B)
BORDER_COLOR = RGBColor(0x1F, 0x29, 0x37)

LOGO_PATH = os.path.join(os.path.dirname(__file__), "public", "campusx-cx-icon.png")
FONT_NAME = "Calibri"

# ── Helper Functions ──────────────────────────────────────────────────────────

def set_bg(slide, color=BG_DARK):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_text(slide, left, top, width, height, text, font_size=14, color=WHITE,
             bold=False, alignment=PP_ALIGN.LEFT, font_name=FONT_NAME, line_spacing=1.15):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = alignment
    p.space_after = Pt(0)
    p.space_before = Pt(0)
    if line_spacing != 1.0:
        p.line_spacing = line_spacing
    return txBox


def add_multiline_text(slide, left, top, width, height, lines, font_size=12, color=WHITE,
                       bold=False, alignment=PP_ALIGN.LEFT, line_spacing=1.2):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, line_data in enumerate(lines):
        if isinstance(line_data, tuple):
            txt, clr, bld, sz = line_data[0], line_data[1] if len(line_data) > 1 else color, \
                                line_data[2] if len(line_data) > 2 else bold, \
                                line_data[3] if len(line_data) > 3 else font_size
        else:
            txt, clr, bld, sz = line_data, color, bold, font_size
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = txt
        p.font.size = Pt(sz)
        p.font.color.rgb = clr
        p.font.bold = bld
        p.font.name = FONT_NAME
        p.alignment = alignment
        p.space_after = Pt(2)
        p.line_spacing = line_spacing
    return txBox


def add_bullet_list(slide, left, top, width, height, items, font_size=11, color=LIGHT_GRAY,
                    bullet_color=CYAN, spacing=1.2):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = f"•  {item}"
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
        p.font.name = FONT_NAME
        p.space_after = Pt(3)
        p.line_spacing = spacing
    return txBox


def add_rect(slide, left, top, width, height, fill_color=BG_CARD, border_color=BORDER_COLOR, corner_radius=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.color.rgb = border_color if border_color else RGBColor(0x2D, 0x3A, 0x4F)
    shape.line.width = Pt(1)
    shape.shadow.inherit = False
    return shape


def add_arrow(slide, left, top, width, height, color=CYAN):
    shape = slide.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_right_arrow(slide, left, top, width, height, color=CYAN):
    shape = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_notes(slide, text):
    notes_slide = slide.notes_slide
    notes_slide.notes_text_frame.text = text


def add_slide_number(slide, num):
    add_text(slide, Inches(12.4), Inches(7.05), Inches(0.8), Inches(0.35),
             str(num), font_size=10, color=GRAY, alignment=PP_ALIGN.RIGHT)


def add_section_badge(slide, text, left, top):
    w, h = Inches(1.8), Inches(0.32)
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = CYAN
    shape.line.fill.background()
    tf = shape.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(10)
    p.font.color.rgb = WHITE
    p.font.bold = True
    p.font.name = FONT_NAME
    p.alignment = PP_ALIGN.CENTER
    tf.margin_top = Pt(2)
    tf.margin_bottom = Pt(2)
    return shape


def add_campusx_logo(slide, left, top, size=Inches(0.4)):
    if os.path.exists(LOGO_PATH):
        try:
            slide.shapes.add_picture(LOGO_PATH, left, top, size, size)
            return True
        except Exception:
            pass
    # Fallback: CX circle
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, left, top, size, size)
    shape.fill.solid()
    shape.fill.fore_color.rgb = CYAN
    shape.line.fill.background()
    tf = shape.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.text = "CX"
    p.font.size = Pt(11)
    p.font.color.rgb = WHITE
    p.font.bold = True
    p.font.name = FONT_NAME
    p.alignment = PP_ALIGN.CENTER
    return shape


def add_cyan_line(slide, left, top, width, height=Pt(3)):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = CYAN
    shape.line.fill.background()
    return shape


def add_colored_number_card(slide, left, top, width, height, number, title, desc, badge_color):
    card = add_rect(slide, left, top, width, height, BG_CARD, BORDER_COLOR)
    badge = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left + Inches(0.15), top + Inches(0.15),
                                   Inches(0.45), Inches(0.35))
    badge.fill.solid()
    badge.fill.fore_color.rgb = badge_color
    badge.line.fill.background()
    tf = badge.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.text = number
    p.font.size = Pt(12)
    p.font.color.rgb = WHITE
    p.font.bold = True
    p.font.name = FONT_NAME
    p.alignment = PP_ALIGN.CENTER
    add_text(slide, left + Inches(0.15), top + Inches(0.55), width - Inches(0.3), Inches(0.3),
             title, font_size=12, color=WHITE, bold=True)
    add_text(slide, left + Inches(0.15), top + Inches(0.85), width - Inches(0.3), height - Inches(1.0),
             desc, font_size=9, color=GRAY)


# ── Slide Builders ────────────────────────────────────────────────────────────

def build_slide_1(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    set_bg(slide)
    add_campusx_logo(slide, Inches(0.45), Inches(0.3), Inches(0.45))
    add_text(slide, Inches(0.45), Inches(0.9), Inches(10), Inches(0.8),
             "CampusX", font_size=44, color=WHITE, bold=True)
    add_text(slide, Inches(0.45), Inches(1.65), Inches(8), Inches(0.5),
             "AI-Powered Academic Intelligence Platform", font_size=22, color=CYAN, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(2.25), Inches(3.5))
    add_text(slide, Inches(0.45), Inches(2.5), Inches(8), Inches(0.4),
             "Smarter Education. Brighter Futures.", font_size=16, color=LIGHT_GRAY)

    # Team info placeholders
    team_labels = ["Team Name:", "Institution:", "Members:", "Guide:"]
    team_y = Inches(3.4)
    for label in team_labels:
        add_text(slide, Inches(0.45), team_y, Inches(2.5), Inches(0.3),
                 label, font_size=11, color=GRAY)
        # Underline placeholder
        add_cyan_line(slide, Inches(2.8), team_y + Inches(0.22), Inches(2.0), Pt(1))
        team_y += Inches(0.38)

    # Platform highlights card
    card_left, card_top = Inches(7.5), Inches(1.2)
    card_w, card_h = Inches(5.2), Inches(5.5)
    add_rect(slide, card_left, card_top, card_w, card_h, BG_CARD, BORDER_COLOR)
    add_text(slide, card_left + Inches(0.2), card_top + Inches(0.15), card_w - Inches(0.4), Inches(0.4),
             "Platform Highlights", font_size=16, color=CYAN, bold=True)

    highlights = [
        ("6", "Prediction Systems", "SGPA, Attendance, Marks, Risk, Performance, Career"),
        ("3", "Role-Based Portals", "Student, Faculty, Admin dashboards"),
        ("GenAI", "Copilot", "Natural language academic assistant"),
        ("52", "Backend Services", "Enterprise-grade FastAPI microservices"),
        ("30+", "Pages", "Comprehensive platform coverage"),
        ("21+", "Database Tables", "Structured PostgreSQL schema"),
    ]
    y_off = card_top + Inches(0.65)
    for num, title, desc in highlights:
        add_text(slide, card_left + Inches(0.3), y_off, Inches(0.9), Inches(0.35),
                 num, font_size=18, color=CYAN, bold=True)
        add_text(slide, card_left + Inches(1.3), y_off, Inches(3.5), Inches(0.3),
                 title, font_size=13, color=WHITE, bold=True)
        add_text(slide, card_left + Inches(1.3), y_off + Inches(0.3), Inches(3.5), Inches(0.3),
                 desc, font_size=9, color=GRAY)
        y_off += Inches(0.78)

    add_notes(slide, "Welcome to CampusX. This presentation covers 6 prediction systems, 3 role-based portals, "
              "a GenAI copilot, and a full production tech stack. Built for smarter education and brighter futures.")
    add_slide_number(slide, 1)


def build_slide_2(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "PROBLEM STATEMENT", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "The Challenges We Solve", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    problems = [
        ("01", "Scattered Academic Data",
         "Students juggle multiple spreadsheets, portals, and paper records. No single source of truth for grades, attendance, or progress."),
        ("02", "No Early Risk Warning",
         "By the time poor performance is noticed, it's too late. There's no predictive system to alert students or faculty before failures occur."),
        ("03", "Subject Performance Uncertainty",
         "Students don't know which subjects they'll struggle with next semester. No data-driven prediction of future marks."),
        ("04", "Generic Career Guidance",
         "Career advice is one-size-fits-all. No personalized recommendations based on actual academic performance and skills."),
        ("05", "Faculty Lack Analytics",
         "Teachers have no dashboards showing class performance trends, at-risk students, or workload distribution."),
        ("06", "No 24/7 Academic Assistant",
         "Students can't get instant answers to academic questions outside office hours. No AI-powered support."),
    ]

    cols, rows = 3, 2
    card_w, card_h = Inches(3.9), Inches(2.6)
    start_x, start_y = Inches(0.45), Inches(1.6)
    gap_x, gap_y = Inches(0.15), Inches(0.15)

    for i, (num, title, desc) in enumerate(problems):
        col = i % cols
        row = i // cols
        x = start_x + col * (card_w + gap_x)
        y = start_y + row * (card_h + gap_y)
        colors = [CYAN, RED, ORANGE, PURPLE, GREEN, YELLOW]
        add_colored_number_card(slide, x, y, card_w, card_h, num, title, desc, colors[i])

    add_notes(slide, "Six real problems CampusX solves: scattered academic data, no early risk warning, "
              "subject performance uncertainty, generic career guidance, faculty lacking analytics, "
              "and no 24/7 academic assistant.")
    add_slide_number(slide, 2)


def build_slide_3(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "SOLUTION OVERVIEW", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "How CampusX Solves It", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    # Top row: 3 user boxes
    user_roles = [("Students", CYAN), ("Faculty", GREEN), ("Admins", PURPLE)]
    box_w, box_h = Inches(3.2), Inches(1.0)
    top_y = Inches(1.8)
    start_x = Inches(0.9)
    gap = Inches(0.4)

    for i, (role, color) in enumerate(user_roles):
        x = start_x + i * (box_w + gap)
        shape = add_rect(slide, x, top_y, box_w, box_h, BG_CARD, color)
        add_text(slide, x, top_y + Inches(0.3), box_w, Inches(0.4),
                 role, font_size=16, color=color, bold=True, alignment=PP_ALIGN.CENTER)

    # Arrows down
    arrow_y = top_y + box_h + Inches(0.1)
    for i in range(3):
        x = start_x + i * (box_w + gap) + box_w / 2 - Inches(0.15)
        add_arrow(slide, x, arrow_y, Inches(0.3), Inches(0.4), CYAN)

    # Central box
    central_y = arrow_y + Inches(0.55)
    central_w, central_h = Inches(11.0), Inches(1.2)
    central_x = Inches(1.15)
    add_rect(slide, central_x, central_y, central_w, central_h, BG_CARD, CYAN)
    add_text(slide, central_x, central_y + Inches(0.15), central_w, Inches(0.4),
             "CampusX Platform", font_size=22, color=CYAN, bold=True, alignment=PP_ALIGN.CENTER)
    add_text(slide, central_x, central_y + Inches(0.6), central_w, Inches(0.4),
             "Unified Data Ingestion  →  ML Predictions  →  GenAI Copilot  →  Role-Based Portals",
             font_size=12, color=LIGHT_GRAY, alignment=PP_ALIGN.CENTER)

    # Arrows down from central
    arrow_y2 = central_y + central_h + Inches(0.1)
    for i in range(4):
        x = Inches(1.8) + i * Inches(2.8)
        add_arrow(slide, x, arrow_y2, Inches(0.3), Inches(0.4), CYAN)

    # Bottom row: 4 capability boxes
    caps = [
        ("ML Predictions", "6 trained models", CYAN),
        ("Dashboards", "3 role-based portals", GREEN),
        ("GenAI Copilot", "24/7 AI assistant", ORANGE),
        ("Career Guidance", "Personalized paths", PURPLE),
    ]
    cap_y = arrow_y2 + Inches(0.55)
    cap_w, cap_h = Inches(2.7), Inches(1.2)
    cap_start_x = Inches(0.45)
    cap_gap = Inches(0.2)

    for i, (name, desc, color) in enumerate(caps):
        x = cap_start_x + i * (cap_w + cap_gap)
        add_rect(slide, x, cap_y, cap_w, cap_h, BG_CARD, color)
        add_text(slide, x, cap_y + Inches(0.2), cap_w, Inches(0.35),
                 name, font_size=13, color=color, bold=True, alignment=PP_ALIGN.CENTER)
        add_text(slide, x, cap_y + Inches(0.6), cap_w, Inches(0.35),
                 desc, font_size=10, color=GRAY, alignment=PP_ALIGN.CENTER)

    add_notes(slide, "CampusX centralizes scattered data, runs ML predictions, and delivers personalized "
              "insights to three user roles: Students, Faculty, and Admins through dedicated portals.")
    add_slide_number(slide, 3)


def build_slide_4(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "PLATFORM OVERVIEW", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "By The Numbers", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    stats = [
        ("6", "Prediction Systems", "ML models serving real-time predictions"),
        ("3", "Role-Based Portals", "Student, Faculty, Admin dashboards"),
        ("30+", "Pages", "Comprehensive platform coverage"),
        ("52", "Backend Services", "Enterprise-grade FastAPI endpoints"),
        ("21+", "Database Tables", "Structured PostgreSQL schema"),
        ("15+", "Chatbot Tools", "GenAI copilot tool registry"),
    ]

    cols, rows = 3, 2
    card_w, card_h = Inches(3.9), Inches(2.4)
    start_x, start_y = Inches(0.45), Inches(1.6)
    gap_x, gap_y = Inches(0.15), Inches(0.15)

    for i, (num, label, desc) in enumerate(stats):
        col = i % cols
        row = i // cols
        x = start_x + col * (card_w + gap_x)
        y = start_y + row * (card_h + gap_y)
        add_rect(slide, x, y, card_w, card_h, BG_CARD, BORDER_COLOR)
        add_text(slide, x, y + Inches(0.3), card_w, Inches(0.8),
                 num, font_size=48, color=CYAN, bold=True, alignment=PP_ALIGN.CENTER)
        add_text(slide, x, y + Inches(1.15), card_w, Inches(0.35),
                 label, font_size=14, color=WHITE, bold=True, alignment=PP_ALIGN.CENTER)
        add_text(slide, x, y + Inches(1.55), card_w, Inches(0.35),
                 desc, font_size=10, color=GRAY, alignment=PP_ALIGN.CENTER)

    add_notes(slide, "Bird's eye view of CampusX: 6 prediction systems, 3 role-based portals, "
              "30+ pages, 52 backend services, 21+ database tables, and 15+ chatbot tools.")
    add_slide_number(slide, 4)


def build_slide_5(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "STUDENT PORTAL", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "Student Dashboard", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    # Left column: 10 features
    features = [
        "Overview Dashboard", "Academic Analytics", "Report Card",
        "Subject Performance", "Attendance Tracker", "Timetable Viewer",
        "ML Predictions", "Career Guidance", "Goal Setting", "Notifications"
    ]
    y = Inches(1.55)
    for feat in features:
        add_rect(slide, Inches(0.45), y, Inches(5.6), Inches(0.48), BG_CARD, BORDER_COLOR)
        add_text(slide, Inches(0.6), y + Inches(0.08), Inches(5.0), Inches(0.35),
                 feat, font_size=12, color=WHITE, bold=False)
        y += Inches(0.52)

    # Right column: Key Metrics
    rx = Inches(6.4)
    add_rect(slide, rx, Inches(1.55), Inches(6.2), Inches(3.8), BG_CARD, BORDER_COLOR)
    add_text(slide, rx + Inches(0.2), Inches(1.65), Inches(5.5), Inches(0.35),
             "Key Metrics Card", font_size=15, color=CYAN, bold=True)

    metrics = ["SGPA Tracker", "Attendance %", "Backlog Status",
               "Credits Earned", "Health Score", "Priority Tasks"]
    my = Inches(2.15)
    for m in metrics:
        add_rect(slide, rx + Inches(0.2), my, Inches(2.6), Inches(0.42), DARK_CARD, BORDER_COLOR)
        add_text(slide, rx + Inches(0.35), my + Inches(0.06), Inches(2.2), Inches(0.3),
                 m, font_size=10, color=LIGHT_GRAY)
        my += Inches(0.48)

    # Screenshot placeholder
    add_rect(slide, Inches(0.45), Inches(6.95), Inches(12.2), Inches(0.4), DARK_CARD, BORDER_COLOR)
    add_text(slide, Inches(0.65), Inches(6.97), Inches(6), Inches(0.35),
             "[Screenshot: Student Dashboard]", font_size=10, color=GRAY, alignment=PP_ALIGN.LEFT)

    add_notes(slide, "Student portal is the most feature-rich. ML insights predict SGPA, attendance risk, "
              "and career fit. What-if simulator lets students model scenarios before making decisions.")
    add_slide_number(slide, 5)


def build_slide_6(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "FACULTY PORTAL", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "Faculty Dashboard", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    features = [
        "Class Overview", "Student Performance Analytics", "Attendance Analytics",
        "Marks Entry", "Attendance Entry", "Workload Dashboard",
        "At-Risk Students", "Subject Comparison", "Export Reports", "Notifications"
    ]
    y = Inches(1.55)
    for feat in features:
        add_rect(slide, Inches(0.45), y, Inches(5.6), Inches(0.48), BG_CARD, BORDER_COLOR)
        add_text(slide, Inches(0.6), y + Inches(0.08), Inches(5.0), Inches(0.35),
                 feat, font_size=12, color=WHITE, bold=False)
        y += Inches(0.52)

    # Analytics Capabilities
    rx = Inches(6.4)
    add_rect(slide, rx, Inches(1.55), Inches(6.2), Inches(3.8), BG_CARD, BORDER_COLOR)
    add_text(slide, rx + Inches(0.2), Inches(1.65), Inches(5.5), Inches(0.35),
             "Analytics Capabilities", font_size=15, color=GREEN, bold=True)

    caps = ["Class Performance Trends", "At-Risk Student Alerts",
            "Subject Difficulty Analysis", "Attendance Pattern Mining",
            "Marks Distribution", "Workload Distribution",
            "Comparative Analytics", "Export & Reporting"]
    cy = Inches(2.15)
    for c in caps:
        add_rect(slide, rx + Inches(0.2), cy, Inches(5.7), Inches(0.38), DARK_CARD, BORDER_COLOR)
        add_text(slide, rx + Inches(0.35), cy + Inches(0.04), Inches(5.2), Inches(0.3),
                 f"•  {c}", font_size=10, color=LIGHT_GRAY)
        cy += Inches(0.42)

    add_rect(slide, Inches(0.45), Inches(6.95), Inches(12.2), Inches(0.4), DARK_CARD, BORDER_COLOR)
    add_text(slide, Inches(0.65), Inches(6.97), Inches(6), Inches(0.35),
             "[Screenshot: Faculty Dashboard]", font_size=10, color=GRAY)

    add_notes(slide, "Faculty portal: performance/attendance analytics, workload tracking, "
              "marks and attendance entry. Faculty can identify at-risk students early.")
    add_slide_number(slide, 6)


def build_slide_7(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "ADMIN PORTAL", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "Admin Dashboard", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    features = [
        "Institution Overview", "Risk Donut Chart", "ML System Monitor",
        "Student Management", "Faculty Management", "Course Management",
        "Analytics Dashboard", "System Health", "Bulk Operations", "Audit Logs"
    ]
    y = Inches(1.55)
    for feat in features:
        add_rect(slide, Inches(0.45), y, Inches(5.6), Inches(0.48), BG_CARD, BORDER_COLOR)
        add_text(slide, Inches(0.6), y + Inches(0.08), Inches(5.0), Inches(0.35),
                 feat, font_size=12, color=WHITE, bold=False)
        y += Inches(0.52)

    # Intelligence Dashboard
    rx = Inches(6.4)
    add_rect(slide, rx, Inches(1.55), Inches(6.2), Inches(3.8), BG_CARD, BORDER_COLOR)
    add_text(slide, rx + Inches(0.2), Inches(1.65), Inches(5.5), Inches(0.35),
             "Intelligence Dashboard", font_size=15, color=PURPLE, bold=True)

    caps = ["Institution-Wide Risk Analysis", "ML Model Performance",
            "Prediction Accuracy Metrics", "System Health Monitoring",
            "User Activity Analytics", "Data Pipeline Status",
            "Capacity Planning", "Compliance Reporting"]
    cy = Inches(2.15)
    for c in caps:
        add_rect(slide, rx + Inches(0.2), cy, Inches(5.7), Inches(0.38), DARK_CARD, BORDER_COLOR)
        add_text(slide, rx + Inches(0.35), cy + Inches(0.04), Inches(5.2), Inches(0.3),
                 f"•  {c}", font_size=10, color=LIGHT_GRAY)
        cy += Inches(0.42)

    add_rect(slide, Inches(0.45), Inches(6.95), Inches(12.2), Inches(0.4), DARK_CARD, BORDER_COLOR)
    add_text(slide, Inches(0.65), Inches(6.97), Inches(6), Inches(0.35),
             "[Screenshot: Admin Dashboard]", font_size=10, color=GRAY)

    add_notes(slide, "Admin portal: institution-wide analytics, risk donut visualization, "
              "ML intelligence monitoring. Full system health and compliance reporting.")
    add_slide_number(slide, 7)


def build_slide_8(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "AI / ML SYSTEMS", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "Core Differentiator: 6 Prediction Systems", font_size=26, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    models = [
        ("M1 V3", "SGPA Predictor", "Linear Regression", "Predicts next-semester SGPA from historical marks", "Trained ML", CYAN),
        ("M2-TP", "Attendance Risk", "Gradient Boosting", "Flags students likely to fall below 75% attendance", "Trained ML", GREEN),
        ("M3 V2", "Marks Predictor", "Decision Tree", "Predicts per-subject marks with early warning", "Trained ML", ORANGE),
        ("M3 V3", "Early Warning", "Random Forest", "Multi-risk assessment with confidence scores", "Trained ML", PURPLE),
        ("M4", "Performance Engine", "Rule-Based Logic", "Fallback scoring when ML models unavailable", "NOT ML - Rule-Based", RED),
        ("M5", "Career Fit", "Cosine Similarity", "Maps skills and grades to career pathways", "Trained ML", YELLOW),
    ]

    cols, rows = 3, 2
    card_w, card_h = Inches(3.9), Inches(2.5)
    start_x, start_y = Inches(0.45), Inches(1.6)
    gap_x, gap_y = Inches(0.15), Inches(0.15)

    for i, (name, title, algo, desc, badge, color) in enumerate(models):
        col = i % cols
        row = i // cols
        x = start_x + col * (card_w + gap_x)
        y = start_y + row * (card_h + gap_y)
        add_rect(slide, x, y, card_w, card_h, BG_CARD, color)
        add_text(slide, x + Inches(0.15), y + Inches(0.1), card_w - Inches(0.3), Inches(0.3),
                 name, font_size=14, color=color, bold=True)
        add_text(slide, x + Inches(0.15), y + Inches(0.4), card_w - Inches(0.3), Inches(0.3),
                 title, font_size=12, color=WHITE, bold=True)
        add_text(slide, x + Inches(0.15), y + Inches(0.7), card_w - Inches(0.3), Inches(0.25),
                 f"Algorithm: {algo}", font_size=9, color=GRAY)
        add_text(slide, x + Inches(0.15), y + Inches(1.0), card_w - Inches(0.3), Inches(0.6),
                 desc, font_size=9, color=LIGHT_GRAY)
        # Badge
        badge_shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                             x + Inches(0.15), y + Inches(1.7),
                                             Inches(2.5), Inches(0.32))
        badge_shape.fill.solid()
        badge_shape.fill.fore_color.rgb = color
        badge_shape.line.fill.background()
        tf = badge_shape.text_frame
        tf.word_wrap = False
        p = tf.paragraphs[0]
        p.text = badge
        p.font.size = Pt(8)
        p.font.color.rgb = WHITE
        p.font.bold = True
        p.font.name = FONT_NAME
        p.alignment = PP_ALIGN.CENTER

    add_notes(slide, "Core differentiator: 6 ML prediction systems. M4 is NOT ML - it's a rule-based "
              "fallback engine. All ML models use scikit-learn 1.9.0 pinned. Trained on real student data.")
    add_slide_number(slide, 8)


def build_slide_9(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "PROBLEM → SOLUTION", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "Every Problem Has a CampusX Solution", font_size=26, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    pairs = [
        ("No Early Warning", "Students fail without notice", "M3 V3 Early Warning", "Predicts risk 4 weeks before failure"),
        ("Scattered Data", "Multiple portals, no unified view", "Unified Dashboard", "Single source of truth for all data"),
        ("Generic Guidance", "One-size-fits-all career advice", "M5 Career Fit", "Personalized pathways from real data"),
        ("No Predictions", "Students guess their performance", "M1 V3 SGPA Predictor", "Predicted SGPA with confidence"),
        ("Faculty Blind Spots", "No class-level analytics", "Faculty Analytics", "At-risk alerts and trends"),
        ("No AI Support", "No instant academic answers", "GenAI Copilot", "24/7 role-aware assistant"),
    ]

    cols, rows = 3, 2
    card_w, card_h = Inches(3.9), Inches(2.6)
    start_x, start_y = Inches(0.45), Inches(1.6)
    gap_x, gap_y = Inches(0.15), Inches(0.15)

    for i, (prob_title, prob_desc, sol_title, sol_desc) in enumerate(pairs):
        col = i % cols
        row = i // cols
        x = start_x + col * (card_w + gap_x)
        y = start_y + row * (card_h + gap_y)
        add_rect(slide, x, y, card_w, card_h, BG_CARD, BORDER_COLOR)

        add_text(slide, x + Inches(0.15), y + Inches(0.1), card_w - Inches(0.3), Inches(0.25),
                 f"Problem: {prob_title}", font_size=11, color=RED, bold=True)
        add_text(slide, x + Inches(0.15), y + Inches(0.38), card_w - Inches(0.3), Inches(0.3),
                 prob_desc, font_size=9, color=GRAY)

        add_right_arrow(slide, x + card_w / 2 - Inches(0.2), y + Inches(0.8), Inches(0.4), Inches(0.28), CYAN)

        add_text(slide, x + Inches(0.15), y + Inches(1.2), card_w - Inches(0.3), Inches(0.25),
                 "CampusX Solution:", font_size=10, color=GREEN, bold=True)
        add_text(slide, x + Inches(0.15), y + Inches(1.48), card_w - Inches(0.3), Inches(0.25),
                 sol_title, font_size=12, color=WHITE, bold=True)
        add_text(slide, x + Inches(0.15), y + Inches(1.78), card_w - Inches(0.3), Inches(0.5),
                 sol_desc, font_size=9, color=LIGHT_GRAY)

    add_notes(slide, "Each pair is a concrete implemented capability. M3 V3 early warning predicts risk "
              "before exams. M1 V3 gives predicted SGPA. M5 maps to career paths. Copilot answers 24/7.")
    add_slide_number(slide, 9)


def build_slide_10(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "TECH STACK", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "Production-Grade Technology Stack", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    stack = [
        ("Frontend", CYAN, "Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui", "BFF pattern, Server Components"),
        ("Backend", GREEN, "FastAPI (Python 3.11), Pydantic v2, asyncpg, Celery", "Async-first, auto-generated OpenAPI"),
        ("Database", PURPLE, "PostgreSQL 15, SQLAlchemy 2.0, Alembic", "21+ tables, parameterized queries"),
        ("ML / AI", ORANGE, "scikit-learn 1.9.0, pandas, joblib, numpy", "6 models, joblib cached singletons"),
        ("GenAI", CYAN, "OpenAI GPT-4o-mini, Tool Registry, System Prompts", "Intent routing, verified context"),
        ("Security", RED, "HMAC-SHA256 JWT, bcrypt, HttpOnly, RBAC", "Rate limiting, token revocation"),
        ("DevOps", YELLOW, "Docker, Docker Compose, Health Checks", "One-command deployment, auto-restart"),
    ]

    y = Inches(1.55)
    for name, color, techs, note in stack:
        add_rect(slide, Inches(0.45), y, Inches(12.2), Inches(0.72), BG_CARD, BORDER_COLOR)
        add_text(slide, Inches(0.65), y + Inches(0.08), Inches(1.8), Inches(0.28),
                 name, font_size=13, color=color, bold=True)
        add_text(slide, Inches(2.5), y + Inches(0.08), Inches(5.5), Inches(0.28),
                 techs, font_size=10, color=LIGHT_GRAY)
        add_text(slide, Inches(8.2), y + Inches(0.08), Inches(4.2), Inches(0.28),
                 note, font_size=9, color=GRAY)
        y += Inches(0.78)

    add_notes(slide, "Production stack: BFF pattern for security. asyncpg for database. "
              "scikit-learn 1.9.0 pinned for reproducibility. Docker with health checks.")
    add_slide_number(slide, 10)


def build_slide_11(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "ARCHITECTURE", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "System Architecture", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    # Layer 1: Users
    user_roles = [("Students", CYAN), ("Faculty", GREEN), ("Admins", PURPLE)]
    uy = Inches(1.7)
    ux_start = Inches(1.5)
    uw = Inches(2.8)
    for i, (role, clr) in enumerate(user_roles):
        x = ux_start + i * (uw + Inches(0.3))
        add_rect(slide, x, uy, uw, Inches(0.7), BG_CARD, clr)
        add_text(slide, x, uy + Inches(0.18), uw, Inches(0.35),
                 role, font_size=13, color=clr, bold=True, alignment=PP_ALIGN.CENTER)

    # Arrow down
    ay = uy + Inches(0.8)
    add_arrow(slide, Inches(6.3), ay, Inches(0.35), Inches(0.35), CYAN)

    # Layer 2: Next.js Frontend
    fy = ay + Inches(0.45)
    add_rect(slide, Inches(1.5), fy, Inches(10.0), Inches(0.7), BG_CARD, CYAN)
    add_text(slide, Inches(1.5), fy + Inches(0.18), Inches(10.0), Inches(0.35),
             "Next.js 15 Frontend  (Server Components + BFF)", font_size=14, color=CYAN,
             bold=True, alignment=PP_ALIGN.CENTER)

    # Arrow + "BFF fetch" label
    ay2 = fy + Inches(0.8)
    add_arrow(slide, Inches(6.3), ay2, Inches(0.35), Inches(0.35), CYAN)
    add_text(slide, Inches(6.8), ay2, Inches(2.0), Inches(0.35),
             "BFF fetch", font_size=10, color=GRAY)

    # Layer 3: FastAPI Backend
    by = ay2 + Inches(0.45)
    add_rect(slide, Inches(1.5), by, Inches(10.0), Inches(0.7), BG_CARD, GREEN)
    add_text(slide, Inches(1.5), by + Inches(0.18), Inches(10.0), Inches(0.35),
             "FastAPI Backend  (52 Services, JWT Auth, Rate Limiting)", font_size=14, color=GREEN,
             bold=True, alignment=PP_ALIGN.CENTER)

    # Arrow + "Security Layer"
    ay3 = by + Inches(0.8)
    add_arrow(slide, Inches(6.3), ay3, Inches(0.35), Inches(0.35), CYAN)
    add_text(slide, Inches(6.8), ay3, Inches(2.0), Inches(0.35),
             "Security Layer", font_size=10, color=GRAY)

    # Layer 4: PostgreSQL + ML Pipeline side by side
    ly = ay3 + Inches(0.45)
    add_rect(slide, Inches(1.5), ly, Inches(4.7), Inches(0.7), BG_CARD, PURPLE)
    add_text(slide, Inches(1.5), ly + Inches(0.18), Inches(4.7), Inches(0.35),
             "PostgreSQL  (21+ Tables)", font_size=13, color=PURPLE, bold=True, alignment=PP_ALIGN.CENTER)

    add_rect(slide, Inches(6.5), ly, Inches(5.0), Inches(0.7), BG_CARD, ORANGE)
    add_text(slide, Inches(6.5), ly + Inches(0.18), Inches(5.0), Inches(0.35),
             "ML Pipeline  (6 Models, joblib cache)", font_size=13, color=ORANGE, bold=True, alignment=PP_ALIGN.CENTER)

    # Arrow down to GenAI
    ay4 = ly + Inches(0.8)
    add_arrow(slide, Inches(6.3), ay4, Inches(0.35), Inches(0.35), CYAN)

    # Layer 5: GenAI
    gy = ay4 + Inches(0.45)
    add_rect(slide, Inches(1.5), gy, Inches(10.0), Inches(0.6), BG_CARD, YELLOW)
    add_text(slide, Inches(1.5), gy + Inches(0.14), Inches(10.0), Inches(0.35),
             "GenAI Layer  (OpenAI GPT-4o-mini, Tool Registry, Intent Router)", font_size=13,
             color=YELLOW, bold=True, alignment=PP_ALIGN.CENTER)

    add_notes(slide, "BFF pattern: Server components fetch from FastAPI. No client-side API keys. "
              "JWT auth at every layer. ML pipeline runs server-side with joblib cached models.")
    add_slide_number(slide, 11)


def build_slide_12(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "DATA FLOW", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "ML Inference Data Flow", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    # Top: 5 horizontal flow steps
    steps = ["Data\nCollection", "Feature\nEngineering", "ML\nInference", "Result\nValidation", "Dashboard\nDisplay"]
    step_w = Inches(2.0)
    step_h = Inches(0.9)
    sx = Inches(0.45)
    sy = Inches(1.7)
    for i, step in enumerate(steps):
        x = sx + i * (step_w + Inches(0.35))
        add_rect(slide, x, sy, step_w, step_h, BG_CARD, CYAN)
        add_text(slide, x, sy + Inches(0.15), step_w, Inches(0.6),
                 step, font_size=11, color=WHITE, bold=True, alignment=PP_ALIGN.CENTER)
        if i < 4:
            add_right_arrow(slide, x + step_w + Inches(0.05), sy + Inches(0.28),
                            Inches(0.25), Inches(0.3), CYAN)

    # Bottom: 10 numbered steps in 2 columns
    flow_steps = [
        "1. Student requests SGPA prediction",
        "2. Frontend sends BFF request (server-side)",
        "3. Backend validates JWT & RBAC permissions",
        "4. Feature extraction from PostgreSQL",
        "5. Data shaped to 38-feature contract",
        "6. ML model loaded from joblib cache",
        "7. Prediction generated with confidence",
        "8. Result validated against business rules",
        "9. Response returned to Next.js server",
        "10. Dashboard renders predicted SGPA",
    ]

    col_x = [Inches(0.45), Inches(6.6)]
    fy = Inches(3.0)
    for i, step in enumerate(flow_steps):
        col = i // 5
        row = i % 5
        x = col_x[col]
        y = fy + row * Inches(0.85)
        add_rect(slide, x, y, Inches(5.9), Inches(0.72), BG_CARD, BORDER_COLOR)
        add_text(slide, x + Inches(0.15), y + Inches(0.15), Inches(5.5), Inches(0.4),
                 step, font_size=11, color=LIGHT_GRAY)

    add_notes(slide, "ML inference happens server-side. Joblib cached singletons for fast loading. "
              "Real DB data feeds into 38-feature contract. Results validated before display.")
    add_slide_number(slide, 12)


def build_slide_13(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "AI COPILOT", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "GenAI Academic Copilot", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    # Top: 6-step architecture flow
    arch_steps = ["User\nQuery", "Intent\nRouter", "Tool\nRegistry", "Verified\nContext",
                  "GenAI\nProvider", "Response"]
    step_w = Inches(1.7)
    step_h = Inches(0.8)
    sx = Inches(0.45)
    sy = Inches(1.65)
    for i, step in enumerate(arch_steps):
        x = sx + i * (step_w + Inches(0.3))
        add_rect(slide, x, sy, step_w, step_h, BG_CARD, CYAN)
        add_text(slide, x, sy + Inches(0.12), step_w, Inches(0.55),
                 step, font_size=10, color=WHITE, bold=True, alignment=PP_ALIGN.CENTER)
        if i < 5:
            add_right_arrow(slide, x + step_w + Inches(0.02), sy + Inches(0.25),
                            Inches(0.22), Inches(0.28), CYAN)

    # Bottom left: 3 role tool tables
    roles = [
        ("Student Tools", ["SGPA Prediction", "Attendance Check", "Subject Analysis", "Career Guidance"]),
        ("Faculty Tools", ["Class Analytics", "At-Risk Alerts", "Marks Entry", "Workload View"]),
        ("Admin Tools", ["Institution Overview", "ML Monitor", "Risk Analysis", "System Health"]),
    ]
    ry = Inches(2.8)
    for role_name, tools in roles:
        add_rect(slide, Inches(0.45), ry, Inches(3.8), Inches(1.2), BG_CARD, BORDER_COLOR)
        add_text(slide, Inches(0.6), ry + Inches(0.08), Inches(3.5), Inches(0.25),
                 role_name, font_size=11, color=CYAN, bold=True)
        for j, tool in enumerate(tools):
            tx = Inches(0.6) + (j % 2) * Inches(1.8)
            ty = ry + Inches(0.38) + (j // 2) * Inches(0.35)
            add_text(slide, tx, ty, Inches(1.8), Inches(0.3),
                     f"•  {tool}", font_size=8, color=LIGHT_GRAY)
        ry += Inches(1.3)

    # Bottom right: 4 security invariants
    sx2 = Inches(4.6)
    add_rect(slide, sx2, Inches(2.8), Inches(8.0), Inches(4.0), BG_CARD, RED)
    add_text(slide, sx2 + Inches(0.2), Inches(2.9), Inches(7.5), Inches(0.3),
             "Security Invariants", font_size=14, color=RED, bold=True)

    invariants = [
        "1. No API keys exposed to client (BFF pattern)",
        "2. All tool calls verified against RBAC permissions",
        "3. Verified context only - no raw DB access",
        "4. Rate limiting on all Copilot endpoints",
        "5. JWT validation on every request",
        "6. Tool registry is role-gated",
        "7. No data leakage across tenants",
        "8. Audit logging for all AI interactions",
    ]
    iy = Inches(3.3)
    for inv in invariants:
        add_text(slide, sx2 + Inches(0.2), iy, Inches(7.5), Inches(0.3),
                 inv, font_size=10, color=LIGHT_GRAY)
        iy += Inches(0.35)

    add_notes(slide, "Not a ChatGPT wrapper. Intent Router → Tool Registry → Verified Context → LLM. "
              "All tool calls verified against RBAC. No API keys exposed to client.")
    add_slide_number(slide, 13)


def build_slide_14(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "UI SCREENS", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "Live Platform Screenshots", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    pages = [
        "Student Dashboard", "Academic Analytics", "ML Predictions",
        "Report Card", "Faculty Dashboard", "Attendance Analytics",
        "Admin Overview", "GenAI Copilot"
    ]

    cols, rows = 4, 2
    card_w, card_h = Inches(2.95), Inches(2.4)
    start_x, start_y = Inches(0.45), Inches(1.6)
    gap_x, gap_y = Inches(0.12), Inches(0.12)

    for i, page in enumerate(pages):
        col = i % cols
        row = i // cols
        x = start_x + col * (card_w + gap_x)
        y = start_y + row * (card_h + gap_y)
        add_rect(slide, x, y, card_w, card_h, DARK_CARD, BORDER_COLOR)
        add_text(slide, x, y + Inches(0.85), card_w, Inches(0.5),
                 f"Screenshot:", font_size=12, color=GRAY, alignment=PP_ALIGN.CENTER)
        add_text(slide, x, y + Inches(1.25), card_w, Inches(0.5),
                 page, font_size=13, color=CYAN, bold=True, alignment=PP_ALIGN.CENTER)

    add_notes(slide, "Live screenshots, not mockups. SplashCursor animation on hero. "
              "shadcn/ui components. Dark theme consistent across all portals.")
    add_slide_number(slide, 14)


def build_slide_15(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "SECURITY", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "Enterprise-Grade Security", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    # Left column: 9 security features
    security_features = [
        "HMAC-SHA256 JWT Signing",
        "HttpOnly Cookies (No XSS)",
        "bcrypt Password Hashing",
        "Role-Based Access Control",
        "Rate Limiting (Per Endpoint)",
        "Token Revocation & Expiry",
        "Data Isolation (Tenant-Safe)",
        "Audit Logging (All Actions)",
        "CORS & Security Headers",
    ]
    y = Inches(1.55)
    for feat in security_features:
        add_rect(slide, Inches(0.45), y, Inches(5.6), Inches(0.52), BG_CARD, BORDER_COLOR)
        add_text(slide, Inches(0.65), y + Inches(0.1), Inches(5.2), Inches(0.35),
                 feat, font_size=11, color=LIGHT_GRAY)
        y += Inches(0.56)

    # Right column: Docker deployment diagram
    rx = Inches(6.4)
    add_rect(slide, rx, Inches(1.55), Inches(6.2), Inches(4.8), BG_CARD, BORDER_COLOR)
    add_text(slide, rx + Inches(0.2), Inches(1.65), Inches(5.8), Inches(0.35),
             "Docker Deployment", font_size=15, color=YELLOW, bold=True)

    # Docker box
    add_rect(slide, rx + Inches(0.3), Inches(2.2), Inches(5.5), Inches(0.7), DARK_CARD, YELLOW)
    add_text(slide, rx + Inches(0.3), Inches(2.35), Inches(5.5), Inches(0.35),
             "Docker Container", font_size=12, color=YELLOW, bold=True, alignment=PP_ALIGN.CENTER)

    add_arrow(slide, rx + Inches(2.85), Inches(2.95), Inches(0.3), Inches(0.3), CYAN)

    # Docker Compose
    add_rect(slide, rx + Inches(0.3), Inches(3.35), Inches(5.5), Inches(0.7), DARK_CARD, GREEN)
    add_text(slide, rx + Inches(0.3), Inches(3.5), Inches(5.5), Inches(0.35),
             "Docker Compose", font_size=12, color=GREEN, bold=True, alignment=PP_ALIGN.CENTER)

    add_arrow(slide, rx + Inches(2.85), Inches(4.1), Inches(0.3), Inches(0.3), CYAN)

    # Services
    services = [("Next.js", CYAN), ("FastAPI", GREEN), ("PostgreSQL", PURPLE)]
    svc_y = Inches(4.45)
    for svc_name, svc_color in services:
        add_rect(slide, rx + Inches(0.3), svc_y, Inches(1.6), Inches(0.5), DARK_CARD, svc_color)
        add_text(slide, rx + Inches(0.3), svc_y + Inches(0.08), Inches(1.6), Inches(0.35),
                 svc_name, font_size=10, color=svc_color, bold=True, alignment=PP_ALIGN.CENTER)
        svc_y += Inches(0.55)

    add_notes(slide, "Security from day one. HMAC-SHA256 JWT signing. HttpOnly cookies prevent XSS. "
              "bcrypt for passwords. RBAC at every endpoint. Docker one-command deployment.")
    add_slide_number(slide, 15)


def build_slide_16(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "IMPACT", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "Measurable Impact", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    # Table header
    header_y = Inches(1.65)
    col_widths = [Inches(4.0), Inches(4.0), Inches(4.2)]
    col_x = [Inches(0.45), Inches(4.6), Inches(8.8)]
    headers = ["Area", "Without CampusX", "With CampusX"]
    header_colors = [GRAY, RED, GREEN]

    for i, (hdr, clr) in enumerate(zip(headers, header_colors)):
        add_rect(slide, col_x[i], header_y, col_widths[i], Inches(0.45), DARK_CARD, BORDER_COLOR)
        add_text(slide, col_x[i], header_y + Inches(0.06), col_widths[i], Inches(0.35),
                 hdr, font_size=12, color=clr, bold=True, alignment=PP_ALIGN.CENTER)

    rows = [
        ("Data Access", "Multiple portals, spreadsheets", "Single unified dashboard"),
        ("Performance Risk", "Detected after failure", "Predicted 4 weeks early"),
        ("Career Guidance", "Generic, one-size-fits-all", "Personalized, ML-driven"),
        ("Faculty Analytics", "Manual tracking, spreadsheets", "Real-time dashboards"),
        ("Student Support", "Office hours only", "24/7 GenAI Copilot"),
        ("Academic Prediction", "No prediction capability", "6 ML prediction systems"),
        ("Institution Oversight", "Reactive reporting", "Proactive risk monitoring"),
    ]

    ry = header_y + Inches(0.5)
    for area, without, with_cx in rows:
        add_rect(slide, col_x[0], ry, col_widths[0], Inches(0.55), BG_CARD, BORDER_COLOR)
        add_text(slide, col_x[0] + Inches(0.15), ry + Inches(0.1), col_widths[0] - Inches(0.3), Inches(0.35),
                 area, font_size=11, color=WHITE, bold=True)

        add_rect(slide, col_x[1], ry, col_widths[1], Inches(0.55), BG_CARD, BORDER_COLOR)
        add_text(slide, col_x[1] + Inches(0.15), ry + Inches(0.1), col_widths[1] - Inches(0.3), Inches(0.35),
                 without, font_size=10, color=GRAY)

        add_rect(slide, col_x[2], ry, col_widths[2], Inches(0.55), BG_CARD, GREEN)
        add_text(slide, col_x[2] + Inches(0.15), ry + Inches(0.1), col_widths[2] - Inches(0.3), Inches(0.35),
                 with_cx, font_size=10, color=GREEN, bold=True)

        ry += Inches(0.6)

    add_notes(slide, "Reactive to proactive. M3 predicts before exams. M1 gives predicted marks. "
              "24/7 copilot replaces office-hours-only support. Single dashboard replaces scattered data.")
    add_slide_number(slide, 16)


def build_slide_17(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide)
    add_section_badge(slide, "CONCLUSION", Inches(0.45), Inches(0.3))
    add_text(slide, Inches(0.45), Inches(0.75), Inches(12), Inches(0.5),
             "What We Built & What's Next", font_size=28, color=WHITE, bold=True)
    add_cyan_line(slide, Inches(0.45), Inches(1.3), Inches(3.0))

    # Left: What We Built
    add_rect(slide, Inches(0.45), Inches(1.65), Inches(5.9), Inches(5.0), BG_CARD, CYAN)
    add_text(slide, Inches(0.65), Inches(1.75), Inches(5.5), Inches(0.35),
             "What We Built", font_size=18, color=CYAN, bold=True)

    built_items = [
        "6 production ML prediction systems (scikit-learn 1.9.0)",
        "3 role-based portals (Student, Faculty, Admin)",
        "GenAI Academic Copilot with tool registry",
        "52 backend services on FastAPI",
        "21+ database tables with PostgreSQL",
        "Enterprise security: JWT, RBAC, rate limiting",
    ]
    by = Inches(2.25)
    for item in built_items:
        add_text(slide, Inches(0.8), by, Inches(5.3), Inches(0.45),
                 f"✓  {item}", font_size=11, color=LIGHT_GRAY)
        by += Inches(0.48)

    # Right: Future Scope
    add_rect(slide, Inches(6.65), Inches(1.65), Inches(6.0), Inches(5.0), BG_CARD, PURPLE)
    add_text(slide, Inches(6.85), Inches(1.75), Inches(5.5), Inches(0.35),
             "Future Scope", font_size=18, color=PURPLE, bold=True)

    future_items = [
        "📱  Mobile App (React Native)",
        "👨‍👩‍👧  Parent Portal with alerts",
        "☁️  Cloud deployment (AWS/GCP)",
        "🔄  Automated model retraining",
        "📊  Advanced analytics (cohort analysis)",
        "🤝  LMS integration (Moodle, Canvas)",
    ]
    fy = Inches(2.25)
    for item in future_items:
        add_text(slide, Inches(6.85), fy, Inches(5.6), Inches(0.45),
                 item, font_size=11, color=LIGHT_GRAY)
        fy += Inches(0.48)

    # Bottom tagline
    add_rect(slide, Inches(0.45), Inches(6.85), Inches(12.2), Inches(0.5), BG_CARD, CYAN)
    add_text(slide, Inches(0.45), Inches(6.88), Inches(12.2), Inches(0.45),
             "CampusX — Smarter Education. Brighter Futures.  |  Thank You!",
             font_size=16, color=CYAN, bold=True, alignment=PP_ALIGN.CENTER)

    add_notes(slide, "Working platform: 6 prediction systems, 3 portals, GenAI copilot. "
              "Future: mobile app, parent portal, cloud deployment, automated retraining, LMS integration.")
    add_slide_number(slide, 17)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    builders = [
        build_slide_1, build_slide_2, build_slide_3, build_slide_4,
        build_slide_5, build_slide_6, build_slide_7, build_slide_8,
        build_slide_9, build_slide_10, build_slide_11, build_slide_12,
        build_slide_13, build_slide_14, build_slide_15, build_slide_16,
        build_slide_17,
    ]

    for builder in builders:
        builder(prs)

    output_path = os.path.join(os.path.dirname(__file__), "CampusX_Final_Presentation.pptx")
    prs.save(output_path)
    size_kb = os.path.getsize(output_path) / 1024
    print(f"Saved: {output_path}")
    print(f"  Slides: {len(prs.slides)}")
    print(f"  Size: {size_kb:.1f} KB")
    return output_path


if __name__ == "__main__":
    main()
