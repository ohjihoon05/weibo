"""Pillow-based image processor for Weibo uploads."""

from io import BytesIO

from PIL import Image, ImageOps

TARGET_MAX_BYTES = 4 * 1024 * 1024


def process_image(input_path: str) -> bytes:
    """Open an image, fix orientation, resize, and compress to JPEG bytes.

    Processing steps:
        1. Open the image from *input_path*.
        2. Apply EXIF transpose to fix orientation.
        3. Convert to RGB (handles PNG with alpha, RGBA, etc.).
        4. Thumbnail to a maximum of 1080 px on the longest side.
        5. Save as JPEG, starting at quality 85 and stepping down by 10
           until the result fits under 4 MB (minimum quality 50).

    Args:
        input_path: Filesystem path to the source image.

    Returns:
        JPEG-encoded image as ``bytes``.

    Raises:
        ValueError: If the image still exceeds 4 MB at quality 50.
    """
    img = Image.open(input_path)
    img = ImageOps.exif_transpose(img)

    if img.mode != "RGB":
        img = img.convert("RGB")

    img.thumbnail((1080, 1080), Image.Resampling.LANCZOS)

    quality = 85
    while quality >= 50:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        data = buf.getvalue()
        if len(data) <= TARGET_MAX_BYTES:
            return data
        quality -= 10

    raise ValueError("Image too large after compression")
