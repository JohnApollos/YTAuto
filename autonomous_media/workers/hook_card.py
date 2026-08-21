"""
autonomous_media/workers/hook_card.py

Generates a sleek, high-resolution dark-mode Reddit post UI hook card as a PNG image.
Composited over the top of the video in the first 0-3 seconds to instantly hook viewers.
"""

from __future__ import annotations

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def _format_count(n: int) -> str:
    """Format counts into human-readable shorthand (e.g. 14200 -> 14.2k)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(max(1, n))


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Wrap text to fit within max_width pixels."""
    words = text.split()
    if not words:
        return []

    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_w = bbox[2] - bbox[0]
        if line_w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []

    if current_line:
        lines.append(" ".join(current_line))

    # Cap to max 4 lines so it fits neatly on screen
    if len(lines) > 4:
        lines = lines[:3] + [lines[3] + "..."]

    return lines


def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Try resolving clean system fonts (Montserrat, Segoe UI, Arial, Roboto) with fallback."""
    font_names = (
        ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "Roboto-Bold.ttf"]
        if bold
        else ["segoeui.ttf", "arial.ttf", "calibri.ttf", "Roboto-Regular.ttf"]
    )
    for name in font_names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def generate_reddit_hook_card(
    title: str,
    subreddit: str = "AmItheAsshole",
    author: str = "Anonymous",
    upvotes: int = 14200,
    comments_count: int = 840,
    out_path: str | Path = "hook_card.png",
    width: int = 960,
) -> Path:
    """
    Renders an authentic, sleek Reddit dark-mode post card widget.
    Returns the Path to the generated transparent PNG image.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Clean formatting
    subreddit_name = subreddit.replace("r/", "").strip() or "AmItheAsshole"
    author_name = author.replace("u/", "").strip() or "Anonymous"
    clean_title = title.strip().replace("[AITA]", "").replace("(UPDATE)", "").strip()

    # Create scratch surface for measuring text
    scratch_img = Image.new("RGBA", (width, 1000), (0, 0, 0, 0))
    scratch_draw = ImageDraw.Draw(scratch_img)

    header_sub_font = _get_font(26, bold=True)
    header_meta_font = _get_font(22, bold=False)
    title_font = _get_font(34, bold=True)
    footer_font = _get_font(22, bold=True)

    # Wrap title
    padding_x = 44
    text_width = width - (padding_x * 2)
    title_lines = _wrap_text(clean_title, title_font, text_width, scratch_draw)

    # Calculate dynamic height
    header_h = 75
    line_h = 46
    title_h = max(len(title_lines) * line_h, 50)
    footer_h = 60
    total_height = header_h + title_h + footer_h + 30

    # Create final transparent canvas
    card_img = Image.new("RGBA", (width, total_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card_img)

    # Colors (Reddit Dark Mode palette)
    bg_color = (26, 26, 27, 248)       # #1A1A1B with subtle alpha
    border_color = (52, 53, 54, 255)   # #343536
    subreddit_color = (255, 255, 255, 255)
    meta_color = (129, 131, 132, 255)  # #818384
    title_color = (215, 218, 220, 255) # #D7DADC
    pill_bg = (39, 39, 41, 255)        # #272729
    reddit_orange = (255, 69, 0, 255)  # #FF4500

    # Draw rounded card container
    corner_radius = 24
    draw.rounded_rectangle(
        [(0, 0), (width - 1, total_height - 1)],
        radius=corner_radius,
        fill=bg_color,
        outline=border_color,
        width=2,
    )

    # Draw Subreddit Avatar (Orange icon circle with white 'r/')
    avatar_x, avatar_y = padding_x, 26
    avatar_radius = 18
    draw.ellipse(
        [
            (avatar_x, avatar_y),
            (avatar_x + avatar_radius * 2, avatar_y + avatar_radius * 2),
        ],
        fill=reddit_orange,
    )
    # Draw 'r/' symbol inside avatar
    avatar_font = _get_font(20, bold=True)
    draw.text((avatar_x + 8, avatar_y + 4), "r/", fill=(255, 255, 255, 255), font=avatar_font)

    # Draw Subreddit Name & Author
    text_x = avatar_x + avatar_radius * 2 + 14
    draw.text((text_x, 22), f"r/{subreddit_name}", fill=subreddit_color, font=header_sub_font)
    draw.text((text_x, 48), f"• Posted by u/{author_name}", fill=meta_color, font=header_meta_font)

    # Draw Post Title
    curr_y = header_h + 10
    for line in title_lines:
        draw.text((padding_x, curr_y), line, fill=title_color, font=title_font)
        curr_y += line_h

    # Draw Footer Action Pills (Upvotes & Comments)
    footer_y = curr_y + 12
    upvote_str = f"▲ {_format_count(upvotes)}"
    comments_str = f"💬 {_format_count(comments_count)} comments"

    # Upvotes pill
    upvote_bbox = draw.textbbox((0, 0), upvote_str, font=footer_font)
    upvote_w = (upvote_bbox[2] - upvote_bbox[0]) + 30
    draw.rounded_rectangle(
        [(padding_x, footer_y), (padding_x + upvote_w, footer_y + 36)],
        radius=18,
        fill=pill_bg,
    )
    draw.text((padding_x + 14, footer_y + 6), upvote_str, fill=reddit_orange, font=footer_font)

    # Comments pill
    comments_x = padding_x + upvote_w + 14
    comments_bbox = draw.textbbox((0, 0), comments_str, font=footer_font)
    comments_w = (comments_bbox[2] - comments_bbox[0]) + 30
    draw.rounded_rectangle(
        [(comments_x, footer_y), (comments_x + comments_w, footer_y + 36)],
        radius=18,
        fill=pill_bg,
    )
    draw.text((comments_x + 14, footer_y + 6), comments_str, fill=meta_color, font=footer_font)

    card_img.save(out_path, format="PNG")
    return out_path
