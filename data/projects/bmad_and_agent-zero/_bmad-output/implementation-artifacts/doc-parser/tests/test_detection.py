"""Tests for detection.py - Architectural drawing detection.

Phase 2: Library-dependent tests using synthetic images.
All test images are generated programmatically using PIL/numpy.
"""
import pytest
import base64
import io
import re
from unittest.mock import patch, MagicMock

import numpy as np
from PIL import Image, ImageDraw

import detection
from detection import (
    DIMENSION_REGEX,
    ARCH_LABEL_REGEX,
    SCALE_REGEX,
    is_architectural_drawing,
    has_architectural_text,
    classify_image,
    extract_floorplan_candidates,
    _legacy_bw_check,
    _has_photo_characteristics,
    image_to_base64,
)


# ============================================================
# Synthetic Image Generators
# ============================================================

def make_blank_image(w=400, h=400, color=(255, 255, 255)):
    """Create a solid color image."""
    return Image.new("RGB", (w, h), color)


def make_line_drawing(w=400, h=400):
    """Create image with many straight lines (simulates floorplan edge structure).

    Black lines on white background - high edge density.
    """
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw a grid of lines
    for x in range(0, w, 20):
        draw.line([(x, 0), (x, h)], fill=(0, 0, 0), width=2)
    for y in range(0, h, 20):
        draw.line([(0, y), (w, y)], fill=(0, 0, 0), width=2)
    # Draw some diagonal lines
    for i in range(0, w, 40):
        draw.line([(i, 0), (w, h - i)], fill=(0, 0, 0), width=1)
    # Draw rectangles (rooms)
    draw.rectangle([50, 50, 150, 150], outline=(0, 0, 0), width=3)
    draw.rectangle([160, 50, 300, 200], outline=(0, 0, 0), width=3)
    draw.rectangle([50, 160, 150, 350], outline=(0, 0, 0), width=3)
    return img


def make_photo_like(w=400, h=400):
    """Create image with high color variance and different channel means.

    Simulates a photograph with natural color distribution.
    Requirements from source: avg_std > 45 AND channel_spread > 15.
    Uses smooth gradients (not noise) so cv2 edge detection sees few edges.
    """
    # Create smooth gradients with high variance and different channel means
    # Smooth gradients have high std but low edge density (few hard edges)
    y_coords = np.linspace(0, 1, h).reshape(h, 1)
    x_coords = np.linspace(0, 1, w).reshape(1, w)

    # Red: vertical gradient 30 to 250 (range 220, std ~64)
    r = (30 + 220 * y_coords * np.ones((1, w))).astype(np.uint8)
    # Green: horizontal gradient 10 to 200 (range 190, std ~55)
    g = (10 + 190 * np.ones((h, 1)) * x_coords).astype(np.uint8)
    # Blue: combined gradient 5 to 240 (range 235, std ~48)
    b = (5 + 235 * (0.5 * y_coords + 0.5 * x_coords)).astype(np.uint8)

    arr = np.stack([r, g, b], axis=2)
    return Image.fromarray(arr, "RGB")


def make_grid_image(w=400, h=400, rows=5, cols=5):
    """Create image with regular grid lines (simulates table)."""
    img = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    row_h = h // rows
    col_w = w // cols
    for r in range(rows + 1):
        draw.line([(0, r * row_h), (w, r * row_h)], fill=(0, 0, 0), width=2)
    for c in range(cols + 1):
        draw.line([(c * col_w, 0), (c * col_w, h)], fill=(0, 0, 0), width=2)
    return img


def make_small_image(w=50, h=50):
    """Create tiny image below 100x100 threshold."""
    return Image.new("RGB", (w, h), (200, 200, 200))


def make_grayscale_image(w=400, h=400):
    """Create a grayscale-like RGB image (all channels equal)."""
    gray = np.random.RandomState(42).randint(0, 256, (h, w), dtype=np.uint8)
    arr = np.stack([gray, gray, gray], axis=2)
    return Image.fromarray(arr, "RGB")


def make_colorful_image(w=400, h=400):
    """Create a highly colorful image with very different channel values."""
    rng = np.random.RandomState(42)
    r = rng.randint(200, 256, (h, w), dtype=np.uint8)
    g = rng.randint(0, 56, (h, w), dtype=np.uint8)
    b = rng.randint(100, 156, (h, w), dtype=np.uint8)
    arr = np.stack([r, g, b], axis=2)
    return Image.fromarray(arr, "RGB")


# ============================================================
# Regex Pattern Tests
# ============================================================

class TestDimensionRegex:
    """Tests for DIMENSION_REGEX pattern."""

    @pytest.mark.parametrize("text", [
        "12\'-6\"",
        "10\' x 12\'",
        "3.5m",
        "3660mm",
        "12 ft 6 in",
        "10\'-0\"",
        "25\'-3\"",
        "450mm",
        "2.0m",
        "8 ft 0 in",
    ])
    def test_matches_valid_dimensions(self, text):
        """DIMENSION_REGEX matches valid dimension strings."""
        assert DIMENSION_REGEX.search(text) is not None

    @pytest.mark.parametrize("text", [
        "123",
        "hello",
        "abc def",
        "no dimensions here",
        "",
    ])
    def test_does_not_match_invalid(self, text):
        """DIMENSION_REGEX does NOT match plain numbers or random text."""
        assert DIMENSION_REGEX.search(text) is None


class TestArchLabelRegex:
    """Tests for ARCH_LABEL_REGEX pattern."""

    @pytest.mark.parametrize("text", [
        "bedroom",
        "KITCHEN",
        "Bathroom",
        "w.i.c",
        "Living room area",
        "MASTER suite",
        "garage door",
    ])
    def test_matches_architectural_labels(self, text):
        """ARCH_LABEL_REGEX matches architectural room labels."""
        assert ARCH_LABEL_REGEX.search(text.upper()) is not None

    @pytest.mark.parametrize("text", [
        "computer",
        "table",
        "random words",
        "xyz123",
        "",
    ])
    def test_does_not_match_non_labels(self, text):
        """ARCH_LABEL_REGEX does NOT match non-architectural words."""
        assert ARCH_LABEL_REGEX.search(text.upper()) is None


class TestScaleRegex:
    """Tests for SCALE_REGEX pattern."""

    @pytest.mark.parametrize("text", [
        "scale: 1/4",
        "Scale=100",
        "1:100",
        "NTS",
        "scale 200",
    ])
    def test_matches_scale_notations(self, text):
        """SCALE_REGEX matches scale notation strings."""
        assert SCALE_REGEX.search(text) is not None

    @pytest.mark.parametrize("text", [
        "no scale here",
        "random text",
        "",
    ])
    def test_does_not_match_non_scale(self, text):
        """SCALE_REGEX does NOT match non-scale text."""
        assert SCALE_REGEX.search(text) is None


# ============================================================
# is_architectural_drawing Tests
# ============================================================

class TestIsArchitecturalDrawing:
    """Tests for is_architectural_drawing function."""

    def test_line_drawing_returns_true(self):
        """Line drawing image returns True (high edge density + many lines)."""
        img = make_line_drawing(400, 400)
        result = is_architectural_drawing(img)
        assert result == True

    def test_photo_like_returns_false(self):
        """Photo-like image returns False (smooth gradients)."""
        img = make_photo_like(400, 400)
        result = is_architectural_drawing(img)
        assert result == False

    def test_blank_white_returns_false(self):
        """Blank white image returns False (no edges)."""
        img = make_blank_image(400, 400)
        result = is_architectural_drawing(img)
        assert result == False

    def test_small_image_returns_false(self):
        """Small image (<100x100) returns False."""
        img = make_small_image(50, 50)
        result = is_architectural_drawing(img)
        assert result == False

    def test_custom_edge_threshold_lower(self):
        """Lower edge_threshold makes detection more permissive."""
        img = make_line_drawing(400, 400)  # Dense lines, many edges
        # With very low threshold, should definitely pass
        result = is_architectural_drawing(img, edge_threshold=0.01)
        assert result == True

    def test_custom_edge_threshold_higher(self):
        """Higher edge_threshold makes detection more strict."""
        img = make_blank_image(400, 400)
        result = is_architectural_drawing(img, edge_threshold=0.99)
        assert result == False

    def test_fallback_when_cv2_unavailable(self):
        """When HAS_CV2 is False, falls back to _legacy_bw_check."""
        img = make_grayscale_image(400, 400)
        with patch.object(detection, "HAS_CV2", False):
            result = is_architectural_drawing(img)
            # Legacy check on grayscale image should return True
            assert result == True

    def test_fallback_when_numpy_unavailable(self):
        """When both cv2 and numpy unavailable, still returns a boolean."""
        img = make_blank_image(400, 400)
        with patch.object(detection, "HAS_CV2", False), \
             patch.object(detection, "HAS_NUMPY", False):
            result = is_architectural_drawing(img)
            # _legacy_bw_check without numpy returns True
            assert result == True


# ============================================================
# has_architectural_text Tests
# ============================================================

class TestHasArchitecturalText:
    """Tests for has_architectural_text function."""

    def test_text_with_dimensions_returns_true(self):
        """Text containing dimension patterns should be detected."""
        img = make_blank_image()
        with patch.object(detection, "HAS_TESSERACT", True), \
             patch("detection.pytesseract", create=True) as mock_tess:
            mock_tess.image_to_string.return_value = (
                "Room dimensions: 12'-6\" x 10'-0\" with bedroom and kitchen layout"
            )
            result = has_architectural_text(img)
            assert result == True

    def test_text_with_room_labels_returns_true(self):
        """Text with 2+ room labels should be detected."""
        img = make_blank_image()
        with patch.object(detection, "HAS_TESSERACT", True), \
             patch("detection.pytesseract", create=True) as mock_tess:
            mock_tess.image_to_string.return_value = (
                "BEDROOM area next to KITCHEN and BATHROOM with scale: 1/4"
            )
            result = has_architectural_text(img)
            assert result == True

    def test_random_text_returns_false(self):
        """Random text without architectural patterns should not match."""
        img = make_blank_image()
        with patch.object(detection, "HAS_TESSERACT", True), \
             patch("detection.pytesseract", create=True) as mock_tess:
            mock_tess.image_to_string.return_value = (
                "The quick brown fox jumps over the lazy dog repeatedly in this paragraph"
            )
            result = has_architectural_text(img)
            assert result == False

    def test_empty_text_returns_false(self):
        """Empty OCR result should return False."""
        img = make_blank_image()
        with patch.object(detection, "HAS_TESSERACT", True), \
             patch("detection.pytesseract", create=True) as mock_tess:
            mock_tess.image_to_string.return_value = ""
            result = has_architectural_text(img)
            assert result == False

    def test_short_text_returns_false(self):
        """Text shorter than 10 chars should return False."""
        img = make_blank_image()
        with patch.object(detection, "HAS_TESSERACT", True), \
             patch("detection.pytesseract", create=True) as mock_tess:
            mock_tess.image_to_string.return_value = "hi"
            result = has_architectural_text(img)
            assert result == False

    def test_no_tesseract_returns_true(self):
        """When HAS_TESSERACT is False, returns True (permissive fallback)."""
        img = make_blank_image()
        with patch.object(detection, "HAS_TESSERACT", False):
            result = has_architectural_text(img)
            assert result == True

    def test_tesseract_exception_returns_true(self):
        """When pytesseract raises exception, returns True (permissive)."""
        img = make_blank_image()
        with patch.object(detection, "HAS_TESSERACT", True), \
             patch("detection.pytesseract", create=True) as mock_tess:
            mock_tess.image_to_string.side_effect = RuntimeError("Tesseract failed")
            result = has_architectural_text(img)
            assert result == True

    def test_labels_plus_scale_sufficient(self):
        """2 labels (score 2) + scale (score 2) + text length (score 1) = 5 >= 3."""
        img = make_blank_image()
        with patch.object(detection, "HAS_TESSERACT", True), \
             patch("detection.pytesseract", create=True) as mock_tess:
            mock_tess.image_to_string.return_value = (
                "BEDROOM and KITCHEN layout with scale: 1/4 notation shown here"
            )
            result = has_architectural_text(img)
            assert result == True

    def test_single_label_insufficient(self):
        """Only 1 label (needs 2) and no dimensions = score too low."""
        img = make_blank_image()
        with patch.object(detection, "HAS_TESSERACT", True), \
             patch("detection.pytesseract", create=True) as mock_tess:
            mock_tess.image_to_string.return_value = (
                "This is a bedroom with some random text that is long enough to pass length check"
            )
            result = has_architectural_text(img)
            assert result == False


# ============================================================
# classify_image Tests
# ============================================================

class TestClassifyImage:
    """Tests for classify_image function."""

    def test_floorplan_classification(self):
        """Floorplan: is_architectural_drawing=True AND has_architectural_text=True."""
        img = make_line_drawing()
        with patch("detection.is_architectural_drawing", return_value=True), \
             patch("detection.has_architectural_text", return_value=True):
            result = classify_image(img)
            assert result == "floorplan"

    def test_photo_classification(self):
        """Photo-like image classified as site_photo."""
        img = make_photo_like()
        with patch("detection.is_architectural_drawing", return_value=False), \
             patch("detection._has_photo_characteristics", return_value=True):
            result = classify_image(img)
            assert result == "site_photo"

    def test_diagram_classification(self):
        """Drawing without text classified as diagram."""
        img = make_line_drawing()
        with patch("detection.is_architectural_drawing", return_value=True), \
             patch("detection.has_architectural_text", return_value=False):
            result = classify_image(img)
            assert result == "diagram"

    def test_table_classification(self):
        """Grid image classified as table."""
        img = make_grid_image()
        with patch("detection.is_architectural_drawing", return_value=False), \
             patch("detection._has_photo_characteristics", return_value=False), \
             patch("detection._has_table_structure", return_value=True):
            result = classify_image(img)
            assert result == "table"

    def test_unknown_classification(self):
        """Image that matches nothing classified as unknown."""
        img = make_blank_image()
        with patch("detection.is_architectural_drawing", return_value=False), \
             patch("detection._has_photo_characteristics", return_value=False), \
             patch("detection._has_table_structure", return_value=False):
            result = classify_image(img)
            assert result == "unknown"

    def test_cv2_unavailable_photo(self):
        """When cv2 unavailable, photo detection still works via fallback."""
        img = make_photo_like()
        with patch.object(detection, "HAS_CV2", False), \
             patch("detection._has_photo_characteristics", return_value=True), \
             patch("detection._legacy_bw_check", return_value=False):
            result = classify_image(img)
            assert result == "site_photo"

    def test_cv2_unavailable_unknown(self):
        """When cv2 unavailable and no photo characteristics, returns unknown."""
        img = make_blank_image()
        with patch.object(detection, "HAS_CV2", False), \
             patch("detection._has_photo_characteristics", return_value=False), \
             patch("detection._legacy_bw_check", return_value=False), \
             patch("detection._has_table_structure", return_value=False):
            result = classify_image(img)
            assert result == "unknown"

    def test_exception_returns_unknown(self):
        """When classification raises exception, returns unknown."""
        img = make_blank_image()
        with patch("detection.is_architectural_drawing", side_effect=Exception("boom")):
            result = classify_image(img)
            assert result == "unknown"


# ============================================================
# extract_floorplan_candidates Tests
# ============================================================

class TestExtractFloorplanCandidates:
    """Tests for extract_floorplan_candidates function."""

    def test_floorplan_images_returned(self):
        """List with floorplan images returns them as candidates."""
        img1 = make_line_drawing()
        img2 = make_line_drawing()
        with patch("detection.is_architectural_drawing", return_value=True),              patch("detection.has_architectural_text", return_value=True):
            result = extract_floorplan_candidates([(1, img1), (2, img2)])
            assert len(result) == 2

    def test_mixed_images_filtered(self):
        """List with mixed images filters correctly."""
        img1 = make_line_drawing()
        img2 = make_photo_like()
        img3 = make_line_drawing()
        # First and third are architectural drawings with text, second is not
        with patch("detection.is_architectural_drawing", side_effect=[True, False, True]),              patch("detection.has_architectural_text", side_effect=[True, True]):
            result = extract_floorplan_candidates([(1, img1), (2, img2), (3, img3)])
            assert len(result) == 2

    def test_empty_list_returns_empty(self):
        """Empty list returns empty."""
        result = extract_floorplan_candidates([])
        assert result == []

    def test_classification_failure_includes_candidate(self):
        """When classification fails, includes image as candidate (data loss prevention)."""
        img = make_blank_image()
        with patch("detection.is_architectural_drawing", side_effect=Exception("error")):
            result = extract_floorplan_candidates([(1, img)])
            # Should include the image despite error (data loss prevention)
            assert len(result) == 1


# ============================================================
# _legacy_bw_check Tests
# ============================================================

class TestLegacyBwCheck:
    """Tests for _legacy_bw_check function."""

    def test_grayscale_returns_true(self):
        """Grayscale image (low channel variance) returns True."""
        img = make_grayscale_image(400, 400)
        result = _legacy_bw_check(img)
        assert result == True

    def test_colorful_returns_false(self):
        """Highly colorful image (high channel variance) returns False."""
        img = make_colorful_image(400, 400)
        result = _legacy_bw_check(img)
        assert result == False

    def test_numpy_unavailable_returns_true(self):
        """When numpy unavailable, returns True."""
        img = make_blank_image(400, 400)
        with patch.object(detection, "HAS_NUMPY", False):
            result = _legacy_bw_check(img)
            assert result == True


# ============================================================
# _has_photo_characteristics Tests
# ============================================================

class TestHasPhotoCharacteristics:
    """Tests for _has_photo_characteristics function."""

    def test_photo_like_returns_true(self):
        """Photo-like image (high std, high channel spread) returns True."""
        img = make_photo_like(400, 400)
        result = _has_photo_characteristics(img)
        assert result == True

    def test_line_drawing_returns_false(self):
        """Line drawing (low color variance) returns False."""
        img = make_line_drawing(400, 400)
        result = _has_photo_characteristics(img)
        assert result == False

    def test_blank_image_returns_false(self):
        """Blank image returns False."""
        img = make_blank_image(400, 400)
        result = _has_photo_characteristics(img)
        assert result == False

    def test_numpy_unavailable_uses_getcolors(self):
        """When numpy unavailable, uses getcolors fallback."""
        img = make_photo_like(400, 400)
        with patch.object(detection, "HAS_NUMPY", False):
            result = _has_photo_characteristics(img)
            # Photo with >10000 colors -> getcolors returns None -> True
            assert result == True

    def test_numpy_unavailable_few_colors_returns_false(self):
        """When numpy unavailable and few colors, returns False."""
        img = make_blank_image(400, 400)  # Single color
        with patch.object(detection, "HAS_NUMPY", False):
            result = _has_photo_characteristics(img)
            assert result == False


# ============================================================
# image_to_base64 Tests
# ============================================================

class TestImageToBase64:
    """Tests for image_to_base64 function."""

    def test_returns_valid_base64(self):
        """Returns valid base64 string."""
        img = make_blank_image(100, 100)
        result = image_to_base64(img)
        assert isinstance(result, str)
        # Should be valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_roundtrip_decode(self):
        """Can be decoded back to image."""
        img = make_blank_image(100, 100, (128, 64, 32))
        b64 = image_to_base64(img)
        decoded = base64.b64decode(b64)
        restored = Image.open(io.BytesIO(decoded))
        assert restored.size == (100, 100)

    def test_jpeg_format(self):
        """Default format produces valid image data."""
        img = make_blank_image(100, 100)
        b64 = image_to_base64(img)
        decoded = base64.b64decode(b64)
        restored = Image.open(io.BytesIO(decoded))
        assert restored.size == (100, 100)
