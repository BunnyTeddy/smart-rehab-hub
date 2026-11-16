"""TV composition: full-height camera with small floating corner overlays.

Cached Pillow layers handle Vietnamese text. OpenCV fits the entire source frame
without cropping; only small overlay regions are blended on each new frame.
"""
from functools import lru_cache
from pathlib import Path
import json

BG = '#080f16'
PANEL = '#12242c'
MINT = '#a4e5cc'
WHITE = '#f5f8f6'
MUTED = '#a5b9b8'
AMBER = '#f2c985'


class TVRenderer:
    def __init__(self):
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont
        self.cv2, self.np = cv2, np
        self.Image, self.Draw, self.Font = Image, ImageDraw, ImageFont
        self.font_dir = Path(__file__).with_name('fonts')

    @lru_cache(maxsize=64)
    def font(self, size, bold=False):
        name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
        return self.Font.truetype(str(self.font_dir / name), max(10, size))

    @staticmethod
    def camera_rect(size):
        return 0, 0, size[0], size[1]

    @staticmethod
    def fit(source, rect):
        sw, sh = source
        x, y, w, h = rect
        scale = min(w / sw, h / sh)
        tw, th = max(1, round(sw * scale)), max(1, round(sh * scale))
        return x + (w - tw) // 2, y + (h - th) // 2, tw, th

    @lru_cache(maxsize=3)
    def _background(self, size):
        w, h = size
        # Quiet ambient lighting; there are no moving decorations during exercise.
        y, x = self.np.ogrid[0:h, 0:w]
        glow = self.np.exp(-(((x / w - .52) / .6) ** 2 + ((y / h - .42) / .58) ** 2) * 2)
        colors = [8 + 5 * glow, 15 + 17 * glow, 22 + 17 * glow]
        rgb = self.np.stack(self.np.broadcast_arrays(*colors), axis=-1).astype(self.np.uint8)
        return self.np.ascontiguousarray(rgb[:, :, ::-1])

    def _canvas(self, size, transparent=False):
        w, h = size
        scale = min(w / 1280, h / 720)
        ox, oy = (w - 1280 * scale) / 2, (h - 720 * scale) / 2
        if transparent:
            image = self.Image.new('RGBA', size, (0, 0, 0, 0))
        else:
            image = self.Image.fromarray(self._background(size)[:, :, ::-1].copy()).convert('RGBA')
        draw = self.Draw.Draw(image)

        def coords(values):
            return tuple(round(a * scale + (ox if i % 2 == 0 else oy)) for i, a in enumerate(values))

        def box(values, fill, radius=0, outline=None):
            draw.rounded_rectangle(coords(values), radius=round(radius * scale),
                                   fill=fill, outline=outline, width=max(1, round(scale)))

        def text(value, x, y, points=28, fill=WHITE, bold=False, width=None, anchor='lt'):
            value = str(value)
            font = self.font(round(points * scale), bold)
            while width and draw.textlength(value, font=font) > width * scale and points > 18:
                points -= 1
                font = self.font(round(points * scale), bold)
            draw.text((round(x * scale + ox), round(y * scale + oy)), value,
                      font=font, fill=fill, anchor=anchor)

        def lines(value, x, y, width, points=26, fill=WHITE, bold=False, center=False):
            font = self.font(round(points * scale), bold)
            parts, line = [], ''
            for word in value.split():
                candidate = (line + ' ' + word).strip()
                if line and draw.textlength(candidate, font=font) > width * scale:
                    parts.append(line)
                    line = word
                else:
                    line = candidate
            if line:
                parts.append(line)
            for i, part in enumerate(parts):
                text(part, x, y + i * (points + 10), points, fill, bold,
                     anchor='mt' if center else 'lt')
            return len(parts)

        def line(points, fill, width=3):
            draw.line(coords(points), fill=fill, width=max(1, round(width * scale)), joint='curve')

        return image, box, text, lines, line

    @lru_cache(maxsize=8)
    def _surface(self, size, encoded):
        view = json.loads(encoded)
        image, box, text, lines, line = self._canvas(size)
        accent = MINT if view.get('accent') == 'mint' else AMBER
        if view['mode'] == 'idle':
            shift = (-8, 0, 8)[view.get('drift', 0)]
            text('SMART REHAB', 640 + shift, 76, 23, MINT, True, anchor='mt')
            # A small phone is the action cue: the TV is viewed, the phone controls it.
            box((610 + shift, 204, 670 + shift, 302), '#152c32', 13, '#698e89')
            line((630 + shift, 217, 650 + shift, 217), MINT, 2)
            line((632 + shift, 288, 648 + shift, 288), MINT, 2)
            text(view['title'], 640 + shift, 345, 45, WHITE, True, width=1120, anchor='mt')
            hint = ('Chọn bài trên điện thoại để bắt đầu.' if view['accent'] == 'mint'
                    and view['title'] == 'Sẵn sàng tập luyện' else view['hint'])
            lines(hint, 640 + shift, 420, 1050, 25, MUTED, center=True)
            text('●', 540 + shift, 574, 16, accent)
            text('Hub đã kết nối' if view['accent'] == 'mint' else view['status'],
                 568 + shift, 573, 19, accent, width=620)
            text('Camera chỉ mở khi bắt đầu buổi tập', 640 + shift, 631, 17, MUTED, anchor='mt')
            if view.get('dim'):
                image = self.Image.blend(self.Image.new('RGBA', size, BG), image, .4)
        elif view['mode'] == 'summary':
            text('SMART REHAB', 640, 66, 20, MINT, True, anchor='mt')
            success = view.get('success', view['accent'] == 'mint')
            box((611, 147, 669, 205), '#17392f' if success else '#382f22', 29)
            if success:
                line((625, 175, 637, 187, 657, 164), MINT, 4)
            else:
                line((640, 160, 640, 178), AMBER, 4)
                box((638, 185, 642, 189), AMBER, 2)
            text(view['title'], 640, 239, 34, WHITE, True, width=1100, anchor='mt')
            text(view['exercise'], 640, 294, 22, MUTED, width=1100, anchor='mt')
            text(view['reps'], 640, 349, 116, WHITE, True, anchor='mt')
            text('lần hoàn thành', 640, 483, 23, MUTED, anchor='mt')
            detail = f"{view['time']} tập"
            if view['sets'] != '—':
                detail = f"{view['sets']} hiệp  ·  {detail}"
            text(detail, 640, 534, 26, accent, anchor='mt')
            if success or view.get('reason') == 'patient_stop':
                footer = 'Xem chi tiết trên điện thoại'
            else:
                footer = view['hint']
            lines(footer, 640, 608, 1090, 22, MUTED, center=True)
            if view['offline']:
                text('Kết quả đang lưu trên hub · chờ có mạng để đồng bộ', 640, 658, 16, AMBER, anchor='mt')
        else:
            text('Đang mở camera' if view['mode'] == 'preparing' else 'Đang chờ hình ảnh',
                 640, 335, 28, MUTED, anchor='mt')
        return self.np.ascontiguousarray(self.np.asarray(image.convert('RGB'))[:, :, ::-1])

    def _short_hint(self, view):
        if view.get('accent') == 'amber':
            return view['hint']
        if view['mode'] == 'preparing':
            return 'Nghe hướng dẫn và vào khung hình.'
        if view['mode'] == 'aligning':
            return view['hint']
        if view['mode'] == 'resting':
            return view['hint']
        if view['mode'] in ('stopping', 'complete'):
            return view['title']
        if view.get('motion_phase') in ('AT_TARGET', 'RETURNING'):
            return 'Về tư thế đầu để hoàn thành một lần.'
        return ''

    @lru_cache(maxsize=16)
    def _overlays(self, size, encoded):
        view = json.loads(encoded)
        image, box, text, lines, line = self._canvas(size, transparent=True)
        accent = MINT if view.get('accent') == 'mint' else AMBER
        # TV-safe edges; each floating item is independent, with no full-width bars.
        box((64, 48, 584, 127), (6, 15, 21, 205), 17)
        text(view['exercise'], 84, 64, 26, WHITE, True, width=478)
        status = view['side'] or ('Đang tập' if view['mode'] == 'working' else view['title'])
        text(status, 84, 100, 15, MUTED, width=475)
        countdown = view.get('countdown')
        if countdown is None:
            box((1004, 48, 1216, 211), (6, 15, 21, 225), 22, (170, 211, 198, 35))
            text(view['progress'], 1110, 68, 17, MUTED, width=180, anchor='mt')
            if '/' in view['number']:
                done, target = view['number'].split('/', 1)
                text(done, 1110, 102, 70, WHITE, True, anchor='mt')
                text('/ ' + target, 1189, 154, 24, MUTED, anchor='rt')
            else:
                text(view['number'], 1110, 109, 49, accent, True, width=180, anchor='mt')
        else:
            box((560, 233, 720, 451), (6, 15, 21, 220), 30)
            text('Bắt đầu sau', 640, 254, 19, MUTED, anchor='mt')
            text(countdown, 640, 297, 115, WHITE, True, anchor='mt')
        hint = self._short_hint(view) if countdown is None else ''
        if hint:
            # Place short feedback at the left edge, clear of the centre of the body.
            probe = self.Draw.Draw(self.Image.new('RGB', (1, 1)))
            font = self.font(23)
            width = min(680, max(290, round(probe.textlength(hint, font=font)) + 42))
            # Long diagnostic messages occupy two lines rather than tiny text.
            words, current, count = hint.split(), '', 1
            for word in words:
                candidate = (current + ' ' + word).strip()
                if current and probe.textlength(candidate, font=font) > width - 42:
                    count += 1
                    current = word
                else:
                    current = candidate
            height = count * 33 + 28
            box((64, 656-height, 64+width, 656), (6, 15, 21, 225), 16)
            lines(hint, 84, 671-height, width-40, 23, accent if view['accent']=='amber' else WHITE)
        # Precompute tightly cropped regions and alpha weights; full frame alpha
        # compositing would needlessly process millions of pixels on the Pi.
        alpha = self.np.asarray(image)[:, :, 3]
        masks = self.cv2.findContours((alpha > 0).astype(self.np.uint8), self.cv2.RETR_EXTERNAL,
                                      self.cv2.CHAIN_APPROX_SIMPLE)[0]
        rgba = self.np.asarray(image)
        result = []
        for contour in masks:
            x, y, w, h = self.cv2.boundingRect(contour)
            region = rgba[y:y+h, x:x+w]
            weight = region[:, :, 3:4].astype(self.np.float32) / 255
            result.append((x, y, w, h,
                           region[:, :, :3][:, :, ::-1].astype(self.np.float32) * weight, 1-weight))
        return result

    def render(self, size, view, frame=None):
        size = tuple(size)
        if view['mode'] in ('idle', 'summary'):
            return self._surface(size, json.dumps(view, ensure_ascii=False, sort_keys=True))
        result = (self._background(size) if frame is not None else
                  self._surface(size, json.dumps({'mode': view['mode']}))).copy()
        if frame is not None:
            x, y, w, h = self.fit((frame.shape[1], frame.shape[0]), self.camera_rect(size))
            result[y:y+h, x:x+w] = self.cv2.resize(frame, (w, h), interpolation=self.cv2.INTER_LINEAR)
        visible = {k: view.get(k) for k in ('exercise', 'side', 'title', 'accent', 'progress',
                   'number', 'countdown', 'mode', 'hint')}
        visible['motion_phase'] = 'RETURNING' if view.get('motion_phase') in ('AT_TARGET', 'RETURNING') else None
        for x, y, w, h, foreground, inverse in self._overlays(size, json.dumps(visible, ensure_ascii=False, sort_keys=True)):
            region = result[y:y+h, x:x+w]
            result[y:y+h, x:x+w] = (foreground + region * inverse).astype(self.np.uint8)
        return result

    def render_for_screen(self, screen_size, canvas_size, view, frame=None):
        """Compose cheaply, then fill Qt's viewport with a native-size image.

        The Pi's OpenCV Qt build centres undersized images on a grey canvas
        even in a free-ratio full-screen window. An explicit final resize is
        required; the expensive overlay composition still uses the small canvas.
        """
        result = self.render(canvas_size, view, frame)
        if tuple(screen_size) != tuple(canvas_size):
            result = self.cv2.resize(result, tuple(screen_size), interpolation=self.cv2.INTER_LINEAR)
        return result
