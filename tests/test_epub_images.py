import io

from PIL import Image

from epub_images import book_images, score_image_name, wave_png


def _open(data: bytes) -> Image.Image:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return Image.open(io.BytesIO(data))


def test_waves_are_small_light_grey_irregular_lines_that_differ_per_side():
    left, right = _open(wave_png("left")), _open(wave_png("right"))
    assert left.size == right.size
    assert left.size[0] <= 600 and left.size[1] <= 40
    assert left.tobytes() != right.tobytes()
    darkest = min(v for v in left.convert("LA").get_flattened_data() if v[1] == 255)[0]
    assert 140 <= darkest <= 190  # light grey, never black


def test_score_images_fill_one_square_per_point():
    names = [score_image_name(9.2), score_image_name(0.4), score_image_name(10)]
    assert names == ["images/score-09.png", "images/score-00.png", "images/score-10.png"]


def test_book_images_include_every_score_and_both_waves():
    images = book_images()
    assert "images/wave-left.png" in images and "images/wave-right.png" in images
    assert all(f"images/score-{n:02d}.png" in images for n in range(11))
    full, empty = _open(images["images/score-10.png"]), _open(images["images/score-00.png"])
    assert full.size == empty.size
    assert sum(full.convert("L").histogram()[:50]) > 2 * sum(empty.convert("L").histogram()[:50])
