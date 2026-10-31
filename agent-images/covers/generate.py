"""Geração das capas padrão do catálogo a partir dos logos oficiais.

Uso (requer Pillow, só em desenvolvimento):

    python3 agent-images/covers/generate.py

Cada capa é um PNG 1200x400 com fundo em gradiente na cor predominante da
marca e o logo centralizado em branco, sem texto. O seed do portal
(`backend/app/services/image_covers.py`) copia esses PNGs versionados para o
diretório de uploads e os associa às entradas do catálogo — o portal nunca
gera imagem em tempo de execução.
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

COVER_WIDTH = 1200
COVER_HEIGHT = 400
LOGO_BOX = 280
OUT_DIR = Path(__file__).resolve().parent
LOGOS_DIR = OUT_DIR / "logos"


@dataclass(frozen=True)
class CoverSpec:
    key: str
    logo_file: str
    brand_color: str


# Chaves idênticas às de backend/app/services/image_covers.py.
COVERS: tuple[CoverSpec, ...] = (
    CoverSpec("claude", "claude.png", "#D97757"),
    CoverSpec("hermes", "hermes-wing.png", "#1D4ED8"),
    CoverSpec("agy", "agy.png", "#2E7BE6"),
    CoverSpec("opencode", "opencode.png", "#101828"),
    CoverSpec("oh-my-pi", "oh-my-pi.png", "#6D28D9"),
    CoverSpec("xfce", "xfce.png", "#2284F2"),
    CoverSpec("kde", "kde.png", "#1D99F3"),
    CoverSpec("mate", "mate.png", "#87B260"),
    CoverSpec("gnome", "gnome.png", "#4A86CF"),
    CoverSpec("cinnamon", "cinnamon.png", "#DC682E"),
    CoverSpec("lxde", "lxde.png", "#0A7BBB"),
    CoverSpec("lxqt", "lxqt.png", "#0284C7"),
    CoverSpec("i3", "i3.png", "#52C0FF"),
    CoverSpec("sway", "sway.png", "#68751C"),
    CoverSpec("generic", "generic.png", "#1565C0"),
)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _shade(hex_color: str, factor: float) -> tuple[int, int, int]:
    r, g, b = _hex_to_rgb(hex_color)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    r2, g2, b2 = colorsys.hls_to_rgb(h, max(0.0, min(1.0, l * factor)), s)
    return tuple(int(c * 255) for c in (r2, g2, b2))  # type: ignore[return-value]


def _gradient(width: int, height: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (width, height))
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        ImageDraw.Draw(image).line([(0, y), (width, y)], fill=color)
    return image


def _tinted_logo(path: Path, color: tuple[int, int, int], box: int) -> Image.Image:
    logo = Image.open(path).convert("RGBA")
    logo.thumbnail((box, box))
    solid = Image.new("RGBA", logo.size, color + (255,))
    solid.putalpha(logo.getchannel("A"))
    return solid


def _build_cover(spec: CoverSpec) -> Image.Image:
    dark = _shade(spec.brand_color, 0.35)
    light = _shade(spec.brand_color, 0.72)
    cover = _gradient(COVER_WIDTH, COVER_HEIGHT, dark, light)

    # Brilho radial suave atrás do logo, na própria cor da marca.
    glow = Image.new("L", (COVER_WIDTH // 2, COVER_HEIGHT // 2), 0)
    ImageDraw.Draw(glow).ellipse(
        (0, 0, COVER_WIDTH // 2 - 1, COVER_HEIGHT // 2 - 1), fill=40
    )
    glow = glow.resize((COVER_WIDTH, COVER_HEIGHT))
    glow = glow.filter(__import__("PIL.ImageFilter", fromlist=["GaussianBlur"]).GaussianBlur(60))
    brand = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), _hex_to_rgb(spec.brand_color))
    cover = Image.composite(brand, cover, glow)

    logo = _tinted_logo(LOGOS_DIR / spec.logo_file, (255, 255, 255), LOGO_BOX)
    x = (COVER_WIDTH - logo.width) // 2
    y = (COVER_HEIGHT - logo.height) // 2
    cover.paste(logo, (x, y), logo)
    return cover


def main() -> None:
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    for spec in COVERS:
        source = LOGOS_DIR / spec.logo_file
        if not source.exists():
            raise SystemExit(f"logo ausente para {spec.key}: {source}")
        cover = _build_cover(spec)
        out = OUT_DIR / f"{spec.key}.png"
        cover.save(out)
        print(f"{out.relative_to(OUT_DIR.parent.parent)} {cover.size[0]}x{cover.size[1]}")


if __name__ == "__main__":
    main()