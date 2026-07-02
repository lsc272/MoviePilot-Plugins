import io
from pathlib import Path
from typing import Iterable, List, Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from app.core.config import settings
from app.utils.http import RequestUtils


class CollectionPosterBuilder:
    """Generate a portrait collection poster from source item artwork."""

    WIDTH = 1000
    HEIGHT = 1500
    TILE_WIDTH = 500
    TILE_HEIGHT = 500

    @classmethod
    def generate(cls, title: str, poster_urls: Iterable[str]) -> bytes:
        images = cls._download_images(poster_urls)
        if not images:
            raise ValueError("片单中没有可用于生成合集海报的图片")

        canvas = Image.new("RGB", (cls.WIDTH, cls.HEIGHT), (20, 20, 28))
        repeated = [images[index % len(images)] for index in range(6)]
        for index, image in enumerate(repeated):
            tile = cls._cover(image, cls.TILE_WIDTH, cls.TILE_HEIGHT)
            tile = ImageEnhance.Color(tile).enhance(0.9)
            x = (index % 2) * cls.TILE_WIDTH
            y = (index // 2) * cls.TILE_HEIGHT
            canvas.paste(tile, (x, y))

        alpha_line = Image.new("L", (1, cls.HEIGHT), 0)
        alpha_pixels = alpha_line.load()
        for y in range(cls.HEIGHT):
            start = int(cls.HEIGHT * 0.48)
            alpha = 0 if y < start else min(225, int((y - start) * 225 / (cls.HEIGHT - start)))
            alpha_pixels[0, y] = alpha
        overlay = Image.new("RGBA", canvas.size, (8, 10, 18, 255))
        overlay.putalpha(alpha_line.resize(canvas.size))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay)

        draw = ImageDraw.Draw(canvas)
        title_font = cls._font(76)
        label_font = cls._font(28)
        title_lines = cls._wrap_text(draw, str(title or "智能合集"), title_font, 820)[:3]
        line_height = 96
        title_y = cls.HEIGHT - 180 - line_height * len(title_lines)
        draw.rounded_rectangle(
            (68, title_y - 42, 932, cls.HEIGHT - 76),
            radius=32,
            fill=(7, 9, 16, 190),
        )
        draw.text((104, title_y - 4), "SMART COLLECTION", font=label_font, fill=(143, 106, 255, 255))
        for index, line in enumerate(title_lines):
            cls._draw_text_safe(
                draw,
                (100, title_y + 48 + index * line_height),
                line,
                title_font,
                (255, 255, 255, 255),
            )

        output = io.BytesIO()
        canvas.convert("RGB").save(output, format="JPEG", quality=92, optimize=True)
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
            if len(images) >= 6:
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
    def _font(size: int) -> ImageFont.ImageFont:
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        for candidate in candidates:
            if Path(candidate).exists():
                try:
                    return ImageFont.truetype(candidate, size=size)
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

    @staticmethod
    def _draw_text_safe(draw, position, text, font, fill) -> None:
        try:
            draw.text(position, text, font=font, fill=fill)
        except UnicodeEncodeError:
            draw.text(position, "SMART COLLECTION", font=font, fill=fill)
