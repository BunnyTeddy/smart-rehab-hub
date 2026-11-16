"""Display load shedding must not change camera coordinates or thermal stops."""
import unittest
from product_v1.display import Display, RenderBudget
from product_v1.tv_renderer import TVRenderer
from product_v1.tv_state import TVPresentation


class RenderBudgetTests(unittest.TestCase):
    def test_low_resolution_composition_fills_native_viewport_without_changing_camera(self):
        import numpy as np
        renderer=TVRenderer()
        p=TVPresentation(0)
        p.begin({'exercise':'squat','goal':{'mode':'time','duration_s':180}})
        p.progress(dict(workload_phase='working',tracking_status='tracking',phase='OUTBOUND',remaining_s=120),'running')
        view=p.view(0,dict(online=True,paired=True,audio_ready=True,storage_fault=False),True)
        frame=np.full((480,640,3),(20,60,90),dtype=np.uint8)
        original=frame.copy()
        for canvas in [(1280,720),(640,360)]:
            result=renderer.render_for_screen((1920,1080),canvas,view,frame)
            self.assertEqual(result.shape,(1080,1920,3))
            self.assertTrue(np.array_equal(result[540,960],frame[240,320]))
            self.assertLess(int(result[10,10].max()),60)
            self.assertTrue(np.array_equal(frame,original))

    def test_native_aspect_is_preserved_without_upscaling_small_screens(self):
        budget = RenderBudget()
        for screen, expected in [((1920,1080),(1280,720)), ((3840,2160),(1280,720)),
                                 ((1024,768),(960,720)), ((640,480),(640,480)),
                                 ((800,1280),(450,720))]:
            with self.subTest(screen=screen):
                size=budget.size(screen)
                self.assertEqual(size, expected)
                self.assertAlmostEqual(size[0]/size[1], screen[0]/screen[1], delta=.002)

    def test_hot_mode_uses_hysteresis_and_missing_probe_keeps_last_budget(self):
        d=Display()
        self.assertEqual(d.canvas_size((1920,1080)),(1280,720))
        for temperature, expected in [(69.9,(1280,720)), (70,(640,360)),
                                      (None,(640,360)), (68,(640,360)),
                                      (65.1,(640,360)), (65,(1280,720))]:
            d.set_temperature(temperature)
            self.assertEqual(d.canvas_size((1920,1080)),expected)
        # Render state is independent of the session, source frame and health gate.
        self.assertFalse(d.ready)
        self.assertIsNone(d.frame)


if __name__ == '__main__':
    unittest.main()
