import io
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.core.config import settings
from app.utils.http import RequestUtils


class CollectionPosterBuilder:
    """Generate a cinematic collection poster without cropping source artwork."""

    WIDTH = 1000
    HEIGHT = 1500
    ART_HEIGHT = 1080
    MARGIN = 54
    GAP = 22
    CARD_RADIUS = 28
    _FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

    @classmethod
    def generate(cls, title: str, poster_urls: Iterable[str]) -> bytes:
        images = cls._download_images(poster_urls)
        if not images:
            raise ValueError("片单中没有可用于生成合集海报的图片")

        canvas = cls._background(images[0])
        repeated = [images[index % len(images)] for index in range(4)]
        card_width = (cls.WIDTH - cls.MARGIN * 2 - cls.GAP) // 2
        card_height = (cls.ART_HEIGHT - cls.MARGIN * 2 - cls.GAP) // 2

        for index, image in enumerate(repeated):
            x = cls.MARGIN + (index % 2) * (card_width + cls.GAP)
            y = cls.MARGIN + (index // 2) * (card_height + cls.GAP)
            cls._paste_card(canvas, image, (x, y), (card_width, card_height))

        cls._apply_vertical_gradient(
            canvas,
            start_y=720,
            start_alpha=0,
            end_alpha=246,
            color=(7, 10, 18),
        )
        cls._draw_title(canvas, str(title or "智能合集"))

        output = io.BytesIO()
        canvas.convert("RGB").save(output, format="JPEG", quality=94, optimize=True)
        return output.getvalue()

    @classmethod
    def normalize_upload(cls, content: bytes) -> bytes:
        if not content:
            raise ValueError("上传的海报为空")
        if len(content) > 15 * 1024 * 1024:
            raise ValueError("上传海报不能超过 15MB")
        try:
            with Image.open(io.BytesIO(content)) as image:
                image = image.convert("RGB")
                image.thumbnail((2000, 3000), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=94, optimize=True)
                return output.getvalue()
        except Exception as exc:
            raise ValueError("上传文件不是有效图片") from exc

    @classmethod
    def _background(cls, image: Image.Image) -> Image.Image:
        background = cls._cover(image, cls.WIDTH, cls.HEIGHT)
        background = background.filter(ImageFilter.GaussianBlur(54))
        background = ImageEnhance.Color(background).enhance(0.68)
        background = ImageEnhance.Brightness(background).enhance(0.30).convert("RGBA")
        tint = Image.new("RGBA", background.size, (10, 14, 27, 112))
        return Image.alpha_composite(background, tint)

    @classmethod
    def _paste_card(
        cls,
        canvas: Image.Image,
        image: Image.Image,
        position: Tuple[int, int],
        size: Tuple[int, int],
    ) -> None:
        x, y = position
        width, height = size

        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle(
            (x + 4, y + 12, x + width + 4, y + height + 12),
            radius=cls.CARD_RADIUS + 2,
            fill=(0, 0, 0, 170),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(16))
        canvas.alpha_composite(shadow)

        panel = cls._panel(image, width, height)
        mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, width - 1, height - 1),
            radius=cls.CARD_RADIUS,
            fill=255,
        )
        canvas.paste(panel, (x, y), mask)

        border = ImageDraw.Draw(canvas)
        border.rounded_rectangle(
            (x, y, x + width - 1, y + height - 1),
            radius=cls.CARD_RADIUS,
            outline=(231, 206, 158, 105),
            width=2,
        )

    @classmethod
    def _panel(cls, image: Image.Image, width: int, height: int) -> Image.Image:
        """Use a softened fill behind a fully visible, contained poster."""

        panel = cls._cover(image, width, height)
        panel = panel.filter(ImageFilter.GaussianBlur(22))
        panel = ImageEnhance.Color(panel).enhance(0.74)
        panel = ImageEnhance.Brightness(panel).enhance(0.48).convert("RGBA")
        panel = Image.alpha_composite(
            panel, Image.new("RGBA", panel.size, (6, 9, 16, 72))
        )

        foreground = cls._contain(image, width - 28, height - 28).convert("RGBA")
        fx = (width - foreground.width) // 2
        fy = (height - foreground.height) // 2

        foreground_shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(foreground_shadow)
        shadow_draw.rounded_rectangle(
            (fx + 6, fy + 8, fx + foreground.width + 6, fy + foreground.height + 8),
            radius=16,
            fill=(0, 0, 0, 150),
        )
        foreground_shadow = foreground_shadow.filter(ImageFilter.GaussianBlur(12))
        panel = Image.alpha_composite(panel, foreground_shadow)

        foreground_mask = Image.new("L", foreground.size, 0)
        ImageDraw.Draw(foreground_mask).rounded_rectangle(
            (0, 0, foreground.width - 1, foreground.height - 1),
            radius=14,
            fill=255,
        )
        panel.paste(foreground, (fx, fy), foreground_mask)
        return panel

    @classmethod
    def _draw_title(cls, canvas: Image.Image, title: str) -> None:
        draw = ImageDraw.Draw(canvas)
        accent = (215, 184, 124, 230)
        label_font = cls._font(28)
        label = "S M A R T   C O L L E C T I O N"
        label_box = draw.textbbox((0, 0), label, font=label_font)
        label_width = label_box[2] - label_box[0]
        label_y = 1144
        draw.line((118, label_y - 30, 882, label_y - 30), fill=(215, 184, 124, 115), width=2)
        draw.text(
            ((cls.WIDTH - label_width) // 2, label_y),
            label,
            font=label_font,
            fill=accent,
        )

        font, lines, line_height = cls._fit_title(draw, title)
        total_height = line_height * len(lines)
        title_y = 1210 + max(0, (245 - total_height) // 2)

        text_mask = Image.new("L", canvas.size, 0)
        mask_draw = ImageDraw.Draw(text_mask)
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        for index, line in enumerate(lines):
            box = mask_draw.textbbox((0, 0), line, font=font)
            width = box[2] - box[0]
            x = (cls.WIDTH - width) // 2
            y = title_y + index * line_height
            shadow_draw.text(
                (x + 3, y + 7),
                line,
                font=font,
                fill=(0, 0, 0, 205),
                stroke_width=2,
                stroke_fill=(0, 0, 0, 170),
            )
            mask_draw.text((x, y), line, font=font, fill=255)
        shadow = shadow.filter(ImageFilter.GaussianBlur(5))
        canvas.alpha_composite(shadow)

        title_fill = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        fill_pixels = title_fill.load()
        top = max(0, title_y)
        bottom = min(cls.HEIGHT, title_y + total_height)
        span = max(1, bottom - top)
        for y in range(top, bottom):
            progress = (y - top) / span
            color = (
                round(251 - 35 * progress),
                round(247 - 56 * progress),
                round(235 - 92 * progress),
                255,
            )
            for x in range(cls.WIDTH):
                fill_pixels[x, y] = color
        canvas.alpha_composite(Image.composite(title_fill, Image.new("RGBA", canvas.size), text_mask))

    @classmethod
    def _fit_title(
        cls, draw: ImageDraw.ImageDraw, title: str
    ) -> Tuple[ImageFont.ImageFont, List[str], int]:
        value = title.strip() or "智能合集"
        for size in range(86, 49, -4):
            font = cls._font(size)
            lines = cls._wrap_text(draw, value, font, 850)
            line_height = size + 22
            if len(lines) <= 3 and len(lines) * line_height <= 255:
                return font, lines, line_height
        font = cls._font(50)
        return font, cls._wrap_text(draw, value, font, 850)[:3], 68

    @classmethod
    def _apply_vertical_gradient(
        cls,
        canvas: Image.Image,
        start_y: int,
        start_alpha: int,
        end_alpha: int,
        color: Tuple[int, int, int],
    ) -> None:
        overlay = Image.new("RGBA", canvas.size, (*color, 0))
        pixels = overlay.load()
        span = max(1, cls.HEIGHT - start_y)
        for y in range(max(0, start_y), cls.HEIGHT):
            progress = (y - start_y) / span
            alpha = round(start_alpha + (end_alpha - start_alpha) * progress)
            for x in range(cls.WIDTH):
                pixels[x, y] = (*color, alpha)
        canvas.alpha_composite(overlay)

    @classmethod
    def _download_images(cls, poster_urls: Iterable[str]) -> List[Image.Image]:
        images: List[Image.Image] = []
        for url in dict.fromkeys(str(value or "").strip() for value in poster_urls):
            if not url:
                continue
            try:
                response = RequestUtils(
                    ua=settings.USER_AGENT,
                    proxies=settings.PROXY,
                    timeout=20,
                ).get_res(url=url)
                if not response or response.status_code != 200 or not response.content:
                    continue
                with Image.open(io.BytesIO(response.content)) as image:
                    images.append(image.convert("RGB"))
            except Exception:
                continue
            if len(images) >= 4:
                break
        return images

    @staticmethod
    def _cover(image: Image.Image, width: int, height: int) -> Image.Image:
        ratio = max(width / image.width, height / image.height)
        resized = image.resize(
            (max(width, round(image.width * ratio)), max(height, round(image.height * ratio))),
            Image.Resampling.LANCZOS,
        )
        left = max(0, (resized.width - width) // 2)
        top = max(0, (resized.height - height) // 2)
        return resized.crop((left, top, left + width, top + height))

    @staticmethod
    def _contain(image: Image.Image, width: int, height: int) -> Image.Image:
        ratio = min(width / image.width, height / image.height)
        return image.resize(
            (
                max(1, round(image.width * ratio)),
                max(1, round(image.height * ratio)),
            ),
            Image.Resampling.LANCZOS,
        )

    @classmethod
    def _font(cls, size: int) -> ImageFont.ImageFont:
        candidates = [
            cls._FONT_DIR / "ZCOOLXiaoWei-Regular.ttf",
            Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-SemiBold.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"),
            Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
            Path("C:/Windows/Fonts/simkai.ttf"),
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        for candidate in candidates:
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size=size)
                except Exception:
                    continue
        return ImageFont.load_default()

    @classmethod
    def _wrap_text(
        cls, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int
    ) -> List[str]:
        lines: List[str] = []
        current = ""
        for char in text.strip():
            candidate = f"{current}{char}"
            try:
                width = draw.textbbox((0, 0), candidate, font=font)[2]
            except Exception:
                width = len(candidate) * 40
            if current and width > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines or ["智能合集"]
