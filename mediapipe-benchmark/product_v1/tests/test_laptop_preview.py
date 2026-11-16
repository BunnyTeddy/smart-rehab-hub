import json
import os
import subprocess
import unittest
from unittest.mock import patch
from product_v1.display import display_available, preview_connected


class LaptopPreviewTests(unittest.TestCase):
    def test_hdmi_remains_primary_even_without_preview_or_server(self):
        with patch('product_v1.display.hdmi_connected', return_value=True), \
                patch('product_v1.display.preview_connected') as preview:
            self.assertTrue(display_available())
            preview.assert_not_called()

    def test_no_monitor_is_rejected_by_default(self):
        with patch.dict(os.environ, {'SMART_REHAB_LAPTOP_PREVIEW': '0'}), \
                patch('product_v1.display.hdmi_connected', return_value=False), \
                patch('product_v1.display.subprocess.check_output') as query:
            self.assertFalse(display_available())
            query.assert_not_called()

    def test_opt_in_still_requires_viewer_and_captured_virtual_output(self):
        output = dict(name='NOOP-1', captured=True, width=1920, height=1080)
        cases = [([], [], False), ([{'id': 1}], [output], True),
                 ([{'id': 1}], [{**output, 'captured': False}], False),
                 ([{'id': 1}], [{**output, 'name': 'HDMI-A-1'}], False),
                 ([{'id': 1}], [{**output, 'width': 0}], False)]
        with patch.dict(os.environ, {'SMART_REHAB_LAPTOP_PREVIEW': '1'}):
            for clients, outputs, expected in cases:
                with self.subTest(clients=clients, outputs=outputs), \
                        patch('product_v1.display.subprocess.check_output',
                              side_effect=[json.dumps(clients), json.dumps(outputs)]):
                    self.assertEqual(preview_connected(), expected)

    def test_server_failure_does_not_leave_display_ready(self):
        with patch.dict(os.environ, {'SMART_REHAB_LAPTOP_PREVIEW': '1'}):
            for error in (FileNotFoundError(), subprocess.TimeoutExpired('wayvncctl', .7), ValueError()):
                with patch('product_v1.display.subprocess.check_output', side_effect=error):
                    self.assertFalse(preview_connected())
