import io
from pathlib import Path
from typing import Iterable, List, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.core.config import settings
from app.utils.http import RequestUtils


class CollectionPosterBuilder:
    """Generate a cinematic collection poster from a tilted poster wall."""

    WIDTH = 1000
    HEIGHT = 1500
    CARD_RADIUS = 30
    WALL_ANGLE = -13
    TITLE_TRACKING = 2
    _FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

    @classmethod
    def generate(cls, title: str, poster_urls: Iterable[str]) -> bytes:
        images = cls._download_images(poster_urls)
        if not images:
            raise ValueError("片单中没有可用于生成合集海报的图片")

        canvas = cls._poster_wall(images)
        cls._apply_bottom_up_gradient(
            canvas,
            start_y=720,
            bottom_alpha=252,
            color=(240, 243, 248),
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
    def _poster_wall(cls, images: List[Image.Image]) -> Image.Image:
        """Build a staggered, gently tilted wall of full-bleed posters."""

        wall_width = 1390
        wall_height = 1900
        card_width = 250
        card_height = 375
        gap_x = 26
        gap_y = 26
        column_offsets = (20, -145, -55, -205, -105)
        background = (226, 230, 237, 255)
        wall = Image.new("RGBA", (wall_width, wall_height), background)
        repeated = [images[index % len(images)] for index in range(25)]

        for index, image in enumerate(repeated):
            column = index % 5
            row = index // 5
            x = 18 + column * (card_width + gap_x)
            y = -120 + row * (card_height + gap_y) + column_offsets[column]
            cls._paste_card(
                wall,
                image,
                (x, y),
                (card_width, card_height),
            )

        rotated = wall.rotate(
            cls.WALL_ANGLE,
            resample=Image.Resampling.BICUBIC,
            expand=True,
            fillcolor=background,
        )
        left = max(0, (rotated.width - cls.WIDTH) // 2)
        top = max(0, (rotated.height - cls.HEIGHT) // 2 - 60)
        cropped = rotated.crop((left, top, left + cls.WIDTH, top + cls.HEIGHT))
        cropped = ImageEnhance.Color(cropped).enhance(1.08)
        return ImageEnhance.Contrast(cropped).enhance(1.03)

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
            (x + 5, y + 10, x + width + 5, y + height + 10),
            radius=cls.CARD_RADIUS + 2,
            fill=(32, 39, 52, 82),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        canvas.alpha_composite(shadow)

        panel = cls._cover(image.convert("RGB"), width, height).convert("RGBA")
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
            outline=(255, 255, 255, 118),
            width=1,
        )

    @classmethod
    def _draw_title(cls, canvas: Image.Image, title: str) -> None:
        draw = ImageDraw.Draw(canvas)
        font, lines, line_height = cls._fit_title(draw, title)
        total_height = line_height * len(lines)
        title_y = cls.HEIGHT - 92 - total_height

        # A short hairline gives the title a deliberate visual anchor without
        # adding another label or forcing artificial weight onto the glyphs.
        draw.rounded_rectangle(
            (72, title_y - 36, 146, title_y - 30),
            radius=3,
            fill=(53, 61, 75, 205),
        )
        for index, line in enumerate(lines):
            y = title_y + index * line_height
            cls._draw_text_with_tracking(
                draw,
                (72, y),
                line,
                font,
                fill=(30, 36, 48, 255),
                tracking=cls.TITLE_TRACKING,
            )

    @classmethod
    def _fit_title(
        cls, draw: ImageDraw.ImageDraw, title: str
    ) -> Tuple[ImageFont.ImageFont, List[str], int]:
        value = title.strip() or "智能合集"

        # Prefer a calm single-line lockup when the title can fit at a useful
        # display size. Long titles only move to two lines after this pass.
        for size in range(90, 55, -4):
            font = cls._font(size)
            lines = cls._wrap_text(draw, value, font, 850)
            line_height = size + 22
            if len(lines) == 1:
                return font, lines, line_height

        for size in range(78, 55, -4):
            font = cls._font(size)
            lines = cls._wrap_text(draw, value, font, 850)
            line_height = size + 22
            if len(lines) <= 2 and len(lines) * line_height <= 240:
                return font, lines, line_height
        font = cls._font(56)
        return font, cls._wrap_text(draw, value, font, 850)[:2], 74

    @classmethod
    def _apply_bottom_up_gradient(
        cls,
        canvas: Image.Image,
        start_y: int,
        bottom_alpha: int,
        color: Tuple[int, int, int],
    ) -> None:
        """Fade an opaque bottom wash upward into the poster wall."""

        overlay = Image.new("RGBA", canvas.size, (*color, 0))
        pixels = overlay.load()
        span = max(1, cls.HEIGHT - start_y)
        for y in range(max(0, start_y), cls.HEIGHT):
            progress = (y - start_y) / span
            alpha = round(bottom_alpha * (progress**1.45))
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
            if len(images) >= 12:
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
            cls._FONT_DIR / "NotoSansCJKsc-Medium.otf",
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
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
                    font = ImageFont.truetype(str(candidate), size=size)
                    if cls._supports_chinese(font):
                        return font
                except Exception:
                    continue
        raise RuntimeError("未找到可完整显示中文的合集海报字体，请重新安装插件")

    @staticmethod
    def _supports_chinese(font: ImageFont.ImageFont) -> bool:
        """Reject fonts that silently replace Chinese with the tofu glyph."""

        try:
            missing = bytes(font.getmask("\uffff"))
            return all(
                bytes(font.getmask(char)) != missing
                for char in "智能合集电影电视剧"
            )
        except Exception:
            return False

    @classmethod
    def _wrap_text(
        cls, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int
    ) -> List[str]:
        lines: List[str] = []
        current = ""
        for char in text.strip():
            candidate = f"{current}{char}"
            try:
                box = draw.textbbox((0, 0), candidate, font=font)
                width = box[2] - box[0] + max(0, len(candidate) - 1) * cls.TITLE_TRACKING
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
    def _draw_text_with_tracking(
        draw: ImageDraw.ImageDraw,
        position: Tuple[int, int],
        text: str,
        font: ImageFont.ImageFont,
        fill: Tuple[int, int, int, int],
        tracking: int,
    ) -> None:
        """Draw display text with restrained spacing instead of fake bolding."""

        x, y = position
        for char in text:
            draw.text((x, y), char, font=font, fill=fill)
            box = draw.textbbox((x, y), char, font=font)
            x += box[2] - box[0] + tracking
