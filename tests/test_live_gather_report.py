import io
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageDraw


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from modules.submacros.liveGatherReport import LiveGatherReport


class LiveGatherReportCaptureTests(unittest.TestCase):
    def _capture_at_backing_scale(self, backing_scale):
        roblox_window = SimpleNamespace(
            mx=10,
            my=20,
            mw=1710,
            mh=1073,
            yOffset=21,
            multi=backing_scale,
        )
        report = LiveGatherReport("", roblox_window)
        captured_region = None

        def fake_screenshot(x, y, width, height):
            nonlocal captured_region
            captured_region = (x, y, width, height)
            image = Image.new(
                "RGBA",
                (width * backing_scale, height * backing_scale),
                (0, 0, 0, 0),
            )
            draw = ImageDraw.Draw(image)
            honey_box = report._scale_box(
                report.REFERENCE_HUD_CARDS[0], backing_scale, backing_scale
            )
            pollen_box = report._scale_box(
                report.REFERENCE_HUD_CARDS[1], backing_scale, backing_scale
            )
            draw.rectangle(honey_box, fill=(255, 0, 0, 255))
            draw.rectangle(pollen_box, fill=(0, 0, 255, 255))
            return image

        with patch(
            "modules.submacros.liveGatherReport.mssScreenshot",
            side_effect=fake_screenshot,
        ):
            image = Image.open(io.BytesIO(report._capture_honey_pollen())).convert("RGBA")

        return captured_region, image

    def test_capture_coordinates_stay_logical_on_retina(self):
        captured_region, _ = self._capture_at_backing_scale(2)

        self.assertEqual(captured_region, (545, 41, 650, 100))

    def test_standard_density_crops_complete_hud_cards(self):
        _, image = self._capture_at_backing_scale(1)

        self.assertEqual(image.size, (295, 80))
        self.assertEqual(image.getpixel((147, 20)), (255, 0, 0, 255))
        self.assertEqual(image.getpixel((147, 60)), (0, 0, 255, 255))

    def test_retina_crops_use_returned_bitmap_scale(self):
        _, image = self._capture_at_backing_scale(2)

        self.assertEqual(image.size, (590, 160))
        self.assertEqual(image.getpixel((295, 40)), (255, 0, 0, 255))
        self.assertEqual(image.getpixel((295, 120)), (0, 0, 255, 255))


if __name__ == "__main__":
    unittest.main()
