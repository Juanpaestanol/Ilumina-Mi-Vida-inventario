import io

from PIL import Image


def process_image(image_data: bytes, size: int) -> bytes:
    """Resize image to a square of 'size' pixels (center‑crop), return JPEG bytes."""
    with Image.open(io.BytesIO(image_data)) as img:
        img_rgb = img.convert("RGB") if img.mode in ("RGBA", "LA", "P") else img
        w, h = img_rgb.size
        if w > h:
            left = (w - h) // 2
            cropped_img = img_rgb.crop((left, 0, left + h, h))
        elif h > w:
            top = (h - w) // 2
            cropped_img = img_rgb.crop((0, top, w, top + w))
        else:
            cropped_img = img_rgb
        resized_img = cropped_img.resize((size, size), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        resized_img.save(buffer, format="JPEG", quality=70, optimize=True)
        return buffer.getvalue()
