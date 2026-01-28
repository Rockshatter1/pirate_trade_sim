# core/ui_text.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pygame

Color = Tuple[int, int, int]


@dataclass(frozen=True)
class TextStyle:
    color: Color = (235, 235, 235)

    # "Dicke": simuliert durch mehrfaches Blit mit kleinen Offsets
    thickness: int = 1  # 1 = normal, 2-4 = dicker

    # Outline / Stroke
    outline_color: Optional[Color] = None
    outline_px: int = 2

    # Shadow
    shadow_color: Optional[Color] = (0, 0, 0)
    shadow_offset: Tuple[int, int] = (2, 2)
    shadow_alpha: int = 140  # 0..255

    # Gradient (vertikal)
    gradient_top: Optional[Color] = None
    gradient_bottom: Optional[Color] = None


class FontBank:
    """
    Zentraler Font-Cache.
    - Lädt optional eine TTF/OTF-Datei (UI_FONT_PATH)
    - Fallback: SysFont(fallback_name)
    """
    def __init__(self, font_path: Optional[str], fallback_name: str = "arial"):
        self.font_path = font_path
        self.fallback_name = fallback_name
        self._cache: Dict[Tuple[int, bool, bool], pygame.font.Font] = {}

    def get(self, size: int, *, bold: bool = False, italic: bool = False) -> pygame.font.Font:
        key = (size, bold, italic)
        if key in self._cache:
            return self._cache[key]

        font: pygame.font.Font
        if self.font_path and os.path.exists(self.font_path):
            font = pygame.font.Font(self.font_path, size)
        else:
            font = pygame.font.SysFont(self.fallback_name, size)

        font.set_bold(bold)
        font.set_italic(italic)

        self._cache[key] = font
        return font


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _make_vertical_gradient(size: Tuple[int, int], top: Color, bottom: Color) -> pygame.Surface:
    w, h = size
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    if h <= 1:
        surf.fill((*top, 255))
        return surf

    for y in range(h):
        t = y / (h - 1)
        c = (_lerp(top[0], bottom[0], t), _lerp(top[1], bottom[1], t), _lerp(top[2], bottom[2], t))
        pygame.draw.line(surf, (*c, 255), (0, y), (w - 1, y))
    return surf


def render_text(text: str, font: pygame.font.Font, style: Optional[TextStyle] = None, antialias: bool = True) -> pygame.Surface:
    """
    EIN Einstiegspunkt für alle Texte.
    Unterstützt: thickness, shadow, outline, gradient.
    Rückgabe ist eine convert_alpha()-Surface.
    """
    if style is None:
        style = TextStyle()

    # 1) Basis-Maske (Alpha) erzeugen
    base_mask = font.render(text, antialias, (255, 255, 255)).convert_alpha()

    # 2) Füllung (solid oder gradient) erzeugen
    if style.gradient_top and style.gradient_bottom:
        fill = _make_vertical_gradient(base_mask.get_size(), style.gradient_top, style.gradient_bottom).convert_alpha()
    else:
        fill = pygame.Surface(base_mask.get_size(), pygame.SRCALPHA)
        fill.fill((*style.color, 255))

    # Alpha der Maske auf Füllung übertragen
    # --- Alpha der Maske auf Füllung übertragen (ohne surfarray / numpy) ---
    mask = pygame.mask.from_surface(base_mask)
    alpha_surf = mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
    fill.blit(alpha_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)


    # 3) Dicke simulieren (Overdraw)
    thick = max(1, int(style.thickness))
    main = pygame.Surface((fill.get_width() + (thick - 1) * 2, fill.get_height() + (thick - 1) * 2), pygame.SRCALPHA)
    ox = (thick - 1)
    oy = (thick - 1)
    for dx in range(-ox, ox + 1):
        for dy in range(-oy, oy + 1):
            # kleiner Radius, damit es nicht "matschig" wird
            if abs(dx) + abs(dy) <= ox:
                main.blit(fill, (ox + dx, oy + dy))

    # 4) Outline (unter main)
    if style.outline_color and style.outline_px > 0:
        outline_px = int(style.outline_px)
        outline = font.render(text, antialias, style.outline_color).convert_alpha()

        out = pygame.Surface((outline.get_width() + outline_px * 2, outline.get_height() + outline_px * 2), pygame.SRCALPHA)
        # ringförmig blitten
        for dx in range(-outline_px, outline_px + 1):
            for dy in range(-outline_px, outline_px + 1):
                if dx * dx + dy * dy <= outline_px * outline_px:
                    out.blit(outline, (outline_px + dx, outline_px + dy))

        # main in die Mitte auf out
        combo = pygame.Surface(
            (max(out.get_width(), main.get_width()), max(out.get_height(), main.get_height())),
            pygame.SRCALPHA
        )
        combo.blit(out, (0, 0))
        combo.blit(main, ((combo.get_width() - main.get_width()) // 2, (combo.get_height() - main.get_height()) // 2))
        main = combo

    # 5) Shadow (unter alles) - ohne surfarray/numpy
    if style.shadow_color and style.shadow_alpha > 0:
        # Maske aus 'main' erzeugen
        mask = pygame.mask.from_surface(main)
        sh_shape = mask.to_surface(
            setcolor=(*style.shadow_color, int(style.shadow_alpha)),
            unsetcolor=(0, 0, 0, 0)
        ).convert_alpha()

        out = pygame.Surface(
            (main.get_width() + abs(style.shadow_offset[0]) + 4,
             main.get_height() + abs(style.shadow_offset[1]) + 4),
            pygame.SRCALPHA
        )
        out.blit(sh_shape, (2 + style.shadow_offset[0], 2 + style.shadow_offset[1]))
        out.blit(main, (2, 2))
        main = out


    return main.convert_alpha()
