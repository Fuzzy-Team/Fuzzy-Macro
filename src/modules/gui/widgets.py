"""Desktop controls shared by the configuration pages."""

import ctypes
import json
import math
import os
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from PIL import Image, ImageDraw, ImageFilter, ImageTk


FONT_DIR = os.path.join(os.path.dirname(__file__), 'fonts')
ASSET_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'webapp'))
THEMES = {
    'brown': ('#ab8062', '#cd9975', (171, 128, 98)),
    'purple': ('#9d8ec3', '#b4a6d6', (157, 142, 195)),
    'cream': ('#efda98', '#f4e3b2', (239, 218, 152)),
    'red': ('#cb4144', '#9f1a1a', (132, 9, 9)),
    'blue': ('#3fc1c3', '#3ab0b2', (63, 193, 195)),
    'commander': ('#5ad172', '#3d9c50', (50, 190, 78)),
    'basic black': ('#ffc800', '#ffd640', (255, 200, 0)),
    'gummy': ('#ff00ff', '#0ceb4f', (255, 0, 255)),
    'tadpole': ('#20bd96', '#3e8075', (32, 189, 150)),
    'gifted tad': ('#90f0e0', '#5ebdad', (144, 240, 224)),
    'spicy bee': ('#cf2013', '#eb1909', (207, 32, 19)),
}


def palette(theme):
    theme = str(theme).lower()
    theme = {'gifted tadpole': 'gifted tad', 'comander': 'commander'}.get(theme, theme)
    accent, hover, rgb = THEMES.get(theme, THEMES['brown'])
    selected = '#%02x%02x%02x' % tuple(round(value * .15 + 30 * .85) for value in rgb)
    return dict(bg='#121212', surface='#1e1e1e', hover='#2c2c2c',
                dim_surface='#141414', text='#e0e0e0', dim='#a0a0a0',
                border='#333333', input='#2b2b2b', accent=accent,
                accent_hover=hover, selected=selected)


def register_fonts():
    """Register the bundled fonts for this process, without installing them."""
    # Tk only selects normal or bold. Leaving Poppins Bold out makes bold
    # resolve to SemiBold, the 600 weight the web interface used.
    paths = [os.path.join(FONT_DIR, name) for name in os.listdir(FONT_DIR)
             if name.endswith(('.ttf', '.otf')) and name != 'Poppins-Bold.ttf']
    if sys.platform == 'darwin':
        cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        ct = ctypes.CDLL('/System/Library/Frameworks/CoreText.framework/CoreText')
        cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_bool]
        cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p]
        ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
        for path in paths:
            data = os.fsencode(path)
            url = cf.CFURLCreateFromFileSystemRepresentation(None, data, len(data), False)
            ct.CTFontManagerRegisterFontsForURL(url, 1, None)
            cf.CFRelease(url)
    elif sys.platform == 'win32':
        for path in paths:
            ctypes.windll.gdi32.AddFontResourceExW(ctypes.c_wchar_p(path), 0x10, 0)


def rounded_image(width, height, color, radius=6, border=None):
    width, height = max(1, width), max(1, height)
    # Only the corners need antialiasing. Keep the Lanczos filter's three-pixel
    # margin, then extend the uniform middle of each edge at native resolution.
    edge = radius + 3
    small_width = min(width, edge * 2 + 1)
    small_height = min(height, edge * 2 + 1)
    scale = 2
    image = Image.new('RGBA', (small_width * scale, small_height * scale))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, small_width * scale - 1, small_height * scale - 1),
                           radius=radius * scale, fill=color,
                           outline=border, width=scale if border else 1)
    resampling = getattr(Image, 'Resampling', Image)
    image = image.resize((small_width, small_height), resampling.LANCZOS)
    if width != small_width:
        expanded = Image.new('RGBA', (width, small_height))
        expanded.paste(image.crop((0, 0, edge, small_height)), (0, 0))
        expanded.paste(image.crop((edge, 0, edge + 1, small_height)).resize(
            (width - edge * 2, small_height), resampling.NEAREST), (edge, 0))
        expanded.paste(image.crop((small_width - edge, 0, small_width, small_height)), (width - edge, 0))
        image = expanded
    if height != small_height:
        expanded = Image.new('RGBA', (width, height))
        expanded.paste(image.crop((0, 0, width, edge)), (0, 0))
        expanded.paste(image.crop((0, edge, width, edge + 1)).resize(
            (width, height - edge * 2), resampling.NEAREST), (0, edge))
        expanded.paste(image.crop((0, small_height - edge, width, small_height)), (0, height - edge))
        image = expanded
    return ImageTk.PhotoImage(image)


def mix(first, second, amount):
    """Blend two #rrggbb colors; amount is the share of the first."""
    a = [int(first[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(second[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x * amount + y * (1 - amount)) for x, y in zip(a, b))


def dashed_box(draw, box, radius, color, width, dash, gap):
    """Stroke a rounded rectangle outline in dashes, like a CSS dashed border."""
    x0, y0, x1, y1 = box
    points = []
    for cx, cy, start in ((x1 - radius, y0 + radius, -90), (x1 - radius, y1 - radius, 0),
                          (x0 + radius, y1 - radius, 90), (x0 + radius, y0 + radius, 180)):
        for step in range(0, 91, 5):
            angle = math.radians(start + step)
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    points.append(points[0])
    on, left = True, dash
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        length, done = math.hypot(bx - ax, by - ay), 0
        while done < length:
            step = min(left, length - done)
            if on:
                draw.line([(ax + (bx - ax) * done / length, ay + (by - ay) * done / length),
                           (ax + (bx - ax) * (done + step) / length, ay + (by - ay) * (done + step) / length)],
                          fill=color, width=width)
            done += step
            left -= step
            if left <= 0:
                on = not on
                left = dash if on else gap


def slot_image(size, box, radius, background, top, bottom, border, border_width, glow=None):
    """A hotbar frame: gradient fill, border, optional glow and the dashed empty-slot mark."""
    scale = 3
    width, height = size
    x0, y0, x1, y1 = [value * scale for value in box]
    image = Image.new("RGBA", (width * scale, height * scale), background)
    if glow:
        layer = Image.new("RGBA", image.size)
        ImageDraw.Draw(layer).rounded_rectangle((x0, y0 + 4 * scale, x1, y1 + 4 * scale),
                                                radius=radius * scale, fill=glow)
        image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(5 * scale)))
    gradient = Image.new("RGBA", (1, y1 - y0))
    for y in range(y1 - y0):
        color = mix(top, bottom, 1 - y / max(1, y1 - y0 - 1))
        gradient.putpixel((0, y), tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (255,))
    mask = Image.new("L", (x1 - x0, y1 - y0))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius=radius * scale, fill=255)
    image.paste(gradient.resize(mask.size), (x0, y0), mask)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((x0, y0, x1 - 1, y1 - 1), radius=radius * scale, outline=border,
                           width=border_width * scale)
    # The empty-slot mark: a 36px dashed square around a small plus.
    mark = mix("#ffffff", top, .28)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = 17 * scale
    dashed_box(draw, (cx - half, cy - half, cx + half, cy + half), 9 * scale, mark, 2 * scale,
                5 * scale, 3 * scale)
    arm = 7 * scale
    draw.line([(cx - arm, cy), (cx + arm, cy)], fill=mark, width=2 * scale)
    draw.line([(cx, cy - arm), (cx, cy + arm)], fill=mark, width=2 * scale)
    image = image.resize(size, getattr(Image, "Resampling", Image).LANCZOS)
    return ImageTk.PhotoImage(image)


def draw_hotbar_slot(canvas, colors, active):
    """Draw the web .boost-hotbar-slot-frame on an 80x82 canvas; the margin holds the glow and gap."""
    surface = colors['surface']
    canvas.image = slot_image((80, 82), (0, 3 if active else 4, 68, 71 if active else 72), 16, surface,
                              mix('#ffffff', surface, .14), mix('#ffffff', surface, .04),
                              mix(colors['accent'], surface, .5) if active else mix('#ffffff', surface, .18),
                              2, mix(colors['accent'], surface, .35) if active else None)
    canvas.delete('all')
    canvas.create_image(0, 0, image=canvas.image, anchor='nw')


def draw_hotbar_icon(canvas, fill):
    """Draw the web's empty .boost-hotbar-panel-icon on a 52x52 canvas."""
    canvas.image = slot_image((52, 52), (0, 0, 52, 52), 14, fill, mix('#ffffff', fill, .02),
                              mix('#ffffff', fill, .02), mix('#ffffff', fill, .12), 1)
    canvas.create_image(0, 0, image=canvas.image, anchor='nw')


def tooltip(widget, text, colors):
    pending, window = [None], [None]
    def hide(event=None):
        if pending[0]:
            widget.after_cancel(pending[0])
            pending[0] = None
        if window[0]:
            window[0].destroy()
            window[0] = None
    def show():
        pending[0] = None
        window[0] = tk.Toplevel(widget)
        window[0].overrideredirect(True)
        window[0].geometry('+%d+%d' % (widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height() + 4))
        tk.Label(window[0], text=text, font=('Helvetica', -12), bg=colors['input'], fg=colors['text'], padx=8, pady=6, wraplength=320).pack()
    def enter(event):
        hide()
        pending[0] = widget.after(500, show)
    for child in [widget] + widget.winfo_children():
        child.bind('<Enter>', enter, add='+')
        child.bind('<Leave>', hide, add='+')
    widget.bind('<Destroy>', hide, add='+')


def wrap_buttons(parent, buttons):
    def arrange(event):
        x, y = 0, 0
        for button in buttons:
            width = button.winfo_reqwidth()
            if x and x + width > event.width:
                x, y = 0, y + 40
            button.place(x=x, y=y)
            x += width + 8
        height = y + 32
        if int(parent.cget('height')) != height:
            parent.configure(height=height)
    parent.bind('<Configure>', arrange, add='+')


def repaint(widget):
    """Repaint visible children in order after remapping or resizing Tk frames."""
    if widget.winfo_ismapped():
        widget.event_generate('<Expose>', width=widget.winfo_width(), height=widget.winfo_height())
        for child in widget.winfo_children():
            repaint(child)


class Button(tk.Canvas):
    def __init__(self, parent, text, command, colors, font=None, width=None, fill=None, foreground=None, image=None,
                 align='center', trailing='', border=None, radius=6):
        self.colors = colors
        self.text = text
        self.command = command
        self.font = font or ('Helvetica', -14, 'bold')
        self.fill = fill or colors['accent']
        self.foreground = foreground or colors['bg']
        self.icon = image
        self.align = align
        self.trailing = trailing
        self.border = border
        self.radius = radius
        self.disabled = False
        self.auto_width = width is None
        measured = tkfont.Font(font=self.font).measure(text)
        super().__init__(parent, width=width or measured + 24 + (28 if image else 0), height=36,
                         bg=parent.cget('bg'), highlightthickness=0, bd=0, takefocus=True, cursor='hand2')
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Enter>', lambda e: self.draw(True))
        self.bind('<Leave>', lambda e: self.draw())
        self.bind('<ButtonRelease-1>', self.invoke)
        self.bind('<Return>', self.invoke)
        self.bind('<space>', self.invoke)
        self.bind('<FocusIn>', lambda e: self.draw())
        self.bind('<FocusOut>', lambda e: self.draw())
        self.draw()

    def draw(self, hover=False):
        self.delete('all')
        width = max(2, self.winfo_width() if self.winfo_width() > 1 else int(self.cget('width')))
        height = int(self.cget('height'))
        color = self.colors['hover'] if self.disabled else (self.colors['accent_hover'] if hover and self.fill == self.colors['accent'] else self.fill)
        self.background_image = rounded_image(width, height, color, self.radius,
                                              self.colors['accent'] if self.focus_get() is self else self.border)
        self.create_image(0, 0, image=self.background_image, anchor='nw')
        foreground = self.colors['dim'] if self.disabled else self.foreground
        if self.align == 'left':
            x = 9
            if self.icon:
                self.create_image(x + 10, height / 2, image=self.icon)
                x += 26
            self.create_text(x, height / 2, text=self.text, font=self.font, anchor='w', fill=foreground)
        else:
            if self.icon:
                self.create_image(26, height / 2, image=self.icon)
            self.create_text(52 if self.icon else width / 2, height / 2, text=self.text, font=self.font,
                             anchor='w' if self.icon else 'center', fill=foreground)
        if self.trailing:
            self.create_text(width - 9, height / 2, text=self.trailing, font=('Helvetica', -13), anchor='e', fill=foreground)

    def set_text(self, text):
        self.text = text
        if self.auto_width:
            self.configure(width=tkfont.Font(font=self.font).measure(text) + 24)
        self.draw()

    def set_enabled(self, enabled):
        self.disabled = not enabled
        self.configure(cursor='hand2' if enabled else 'arrow')
        self.draw()

    def invoke(self, event=None):
        if not self.disabled:
            self.focus_set()
            self.command()
        return 'break'


class Card(tk.Frame):
    def __init__(self, parent, colors, title='', description='', grow=False, radius=12, padding=24):
        self.colors = colors
        self.grow = grow
        self.radius = radius
        self.padding = padding
        super().__init__(parent, bg=parent.cget('bg'), width=1, height=1, bd=0)
        self.background = tk.Canvas(self, bg=parent.cget('bg'), highlightthickness=0, bd=0)
        self.background.place(x=0, y=0, relwidth=1, relheight=1)
        self.background_item = self.background.create_image(0, 0, anchor='nw')
        self.body = tk.Frame(self, bg=colors['surface'])
        self.top_padding = 16 if title else padding
        self.bind('<Configure>', self.resize)
        self.body.bind('<Configure>', self.resize)
        if title:
            self.header = tk.Frame(self.body, bg=colors['surface'])
            self.header.pack(fill='x', pady=(0, 10))
            self.heading = tk.Label(self.header, text=title, font=('Helvetica', -18, 'bold'), fg=colors['text'], bg=colors['surface'], anchor='w', bd=0, padx=0, pady=0)
            self.heading.pack(side='left')
            self.rule = tk.Frame(self.body, bg=colors['border'], height=1)
            self.rule.pack(fill='x', pady=(0, 16))
        if description:
            self.description = label = tk.Label(self.body, text=description, font=('Helvetica', -16), fg=colors['dim'], bg=colors['surface'], justify='left', anchor='w', bd=0, padx=0)
            label.pack(fill='x', pady=(0, 8))
            label.bind('<Configure>', lambda e: label.configure(wraplength=max(1, e.width)))

    def resize(self, event=None):
        width = max(50, self.winfo_width())
        padding = self.top_padding + self.padding
        requested = self.body.winfo_reqheight() + padding
        height = max(requested, self.winfo_height()) if self.grow else requested
        if int(self.cget('height')) != requested:
            self.configure(height=requested)
        self.body.place(x=self.padding + 1, y=self.top_padding, width=max(1, width - self.padding * 2 - 2),
                        height=max(1, height - padding) if self.grow else self.body.winfo_reqheight())
        self.body.lift()
        size = (width, height)
        if getattr(self, '_size', None) != size:
            self._size = size
            self.background_image = rounded_image(width, height, self.colors['surface'], self.radius, self.colors['border'])
            self.background.itemconfigure(self.background_item, image=self.background_image)

    def set_border(self, color):
        self.colors = dict(self.colors, border=color)
        self._size = None
        self.resize()


class Scroll(tk.Frame):
    def __init__(self, parent, colors):
        super().__init__(parent, bg=colors['bg'])
        self.canvas = tk.Canvas(self, bg=colors['bg'], highlightthickness=0, bd=0)
        style = ttk.Style(self)
        style.layout('Native.Vertical.TScrollbar', [('Vertical.Scrollbar.trough', {'sticky': 'ns', 'children': [('Vertical.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})]})])
        style.configure('Native.Vertical.TScrollbar', background=colors['border'], troughcolor=colors['bg'], bordercolor=colors['bg'], darkcolor=colors['border'], lightcolor=colors['border'], borderwidth=0, width=8)
        self.bar = ttk.Scrollbar(self, command=self.canvas.yview, style='Native.Vertical.TScrollbar')
        self.canvas.configure(yscrollcommand=self.set_scroll)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.body = tk.Frame(self.canvas, bg=colors['bg'])
        self.window = self.canvas.create_window(0, 0, window=self.body, anchor='nw')
        self.stretch = False
        self.body.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', self.resize)

    def resize(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        if self.stretch:
            self.canvas.itemconfigure(self.window, height=max(event.height, self.body.winfo_reqheight()))

    def set_scroll(self, first, last):
        self.bar.set(first, last)
        if float(first) == 0 and float(last) == 1:
            self.bar.place_forget()
        elif not self.bar.winfo_manager():
            self.bar.place(relx=1, x=-8, y=0, width=8, relheight=1)
            self.bar.lift()

    def wheel(self, event):
        delta = event.delta
        if sys.platform != 'darwin':
            delta = int(delta / 120) if delta else (1 if getattr(event, 'num', 0) == 4 else -1)
        self.canvas.yview_scroll(-int(delta), 'units')


class Checkbox(tk.Canvas):
    def __init__(self, parent, value, command, colors):
        self.variable = tk.BooleanVar(parent, bool(value))
        self.colors = colors
        self.command = command
        # The web checkbox is an 18px box at the left of a 28px-wide label.
        super().__init__(parent, width=28, height=20, highlightthickness=0, bd=0, bg=parent.cget('bg'), cursor='hand2', takefocus=True)
        self.bind('<ButtonRelease-1>', self.toggle)
        self.bind('<space>', self.toggle)
        self.variable.trace_add('write', lambda *args: self.draw())
        self.draw()

    def draw(self):
        self.delete('all')
        checked = self.variable.get()
        self.background_image = rounded_image(18, 18, self.colors['accent'] if checked else self.colors['input'], 3,
                                              self.colors['accent'] if checked else self.colors['border'])
        self.create_image(0, 1, image=self.background_image, anchor='nw')
        if checked:
            self.create_line(5, 10, 8, 13, 13, 6, width=2, fill=self.colors['bg'])

    def toggle(self, event=None):
        self.focus_set()
        self.variable.set(not self.variable.get())
        self.command()
        return 'break'


class Choice(tk.Frame):
    def __init__(self, parent, choices, value, command, colors, multiple=False, width=160, image_loader=None):
        super().__init__(parent, bg=parent.cget('bg'))
        self.choices = choices
        self.value = value
        self.variable = tk.StringVar(self, str(value))
        self.command = command
        self.colors = colors
        self.multiple = multiple
        self.image_loader = image_loader
        self.popup = None
        self.button = Button(self, '', self.open, colors, font=('Helvetica', -14), width=width, fill=colors['input'],
                             foreground=colors['text'], align='left', trailing='>', border=colors['border'], radius=4)
        self.button.configure(height=34)
        self.button.pack(fill='x')
        self.set(value)

    def get(self):
        return list(self.value) if self.multiple and isinstance(self.value, (list, tuple)) else self.value

    def set(self, value):
        if self.multiple and not isinstance(value, (list, tuple)):
            if value in (None, '', 'none', 0, '0'):
                value = []
            elif isinstance(value, str) and value.startswith('['):
                value = json.loads(value)
            else:
                value = str(value).split(',')
            value = [int(item) if str(item).strip().isdigit() else str(item).strip().lower() for item in value]
        self.value = value
        self.variable.set(str(value))
        selected = value if self.multiple and isinstance(value, (list, tuple)) else [value]
        labels = [item['label'] for item in self.choices if item['value'] in selected or str(item['value']) in [str(x) for x in selected]]
        item = next((item for item in self.choices if str(item['value']) == str(value)), None)
        self.button.icon = self.image_loader(item['image'], (20, 20)) if item and item.get('image') and self.image_loader else None
        self.button.set_text(', '.join(labels) if labels else 'None' if self.multiple or value in (None, 'none') else str(value or ''))

    def set_choices(self, choices):
        self.choices = choices
        self.set(self.value)

    def open(self):
        if self.popup is not None:
            self.close()
            return
        popup = self.popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.transient(self.winfo_toplevel())
        popup.configure(bg=self.colors['border'])
        height = min(200, len(self.choices) * 34 + 4)
        width = max(self.winfo_width(), max((tkfont.Font(font=('Helvetica', -14)).measure(x['label']) + 34 for x in self.choices), default=160))
        x, y = self.winfo_rootx(), self.winfo_rooty() + self.winfo_height()
        if y + height > self.winfo_screenheight():
            y = self.winfo_rooty() - height
        popup.geometry('%dx%d+%d+%d' % (width, height, x, y))
        scroll = Scroll(popup, self.colors)
        scroll.pack(fill='both', expand=True, padx=1, pady=1)
        selected = self.value if self.multiple and isinstance(self.value, (list, tuple)) else [self.value]
        self.option_labels = []
        for item in self.choices:
            label = tk.Label(scroll.body, text=('✓ ' if item['value'] in selected else '') + item['label'], bg=self.colors['input'], fg=self.colors['text'], anchor='w', padx=12, pady=7, font=('Helvetica', -14))
            if item.get('image') and self.image_loader:
                label.configure(image=self.image_loader(item['image'], (20, 20)), compound='left')
            label.pack(fill='x')
            self.option_labels.append(label)
            label.bind('<Enter>', lambda e: e.widget.configure(bg=self.colors['hover']))
            label.bind('<Leave>', lambda e: e.widget.configure(bg=self.colors['input']))
            label.bind('<ButtonRelease-1>', lambda e, item=item: self.choose(item['value']))
        popup.bind('<Escape>', lambda e: self.close())
        def lost_focus():
            focused = self.focus_get()
            if focused is not None and focused.winfo_toplevel() is not popup:
                self.close()
        popup.bind('<FocusOut>', lambda e: self.after_idle(lost_focus))
        def outside(event):
            if not (x <= event.x_root < x + width and y <= event.y_root < y + height):
                self.close()
                return 'break'
        popup.bind('<ButtonPress-1>', outside)
        popup.bind('<MouseWheel>', scroll.wheel)
        popup.wait_visibility()
        popup.grab_set()
        popup.focus_force()

    def choose(self, value):
        if self.multiple:
            values = list(self.value) if isinstance(self.value, (list, tuple)) else []
            if value in values:
                values.remove(value)
            else:
                values.append(value)
            self.set(values)
        else:
            self.set(value)
        if self.multiple:
            for label, item in zip(self.option_labels, self.choices):
                label.configure(text=('✓ ' if item['value'] in self.value else '') + item['label'])
        else:
            self.close()
        self.command()

    def close(self):
        if self.popup is not None:
            self.popup.grab_release()
            self.popup.destroy()
            self.popup = None


class Control:
    def __init__(self, widget, variable=None, numeric=None):
        self.widget = widget
        self.variable = variable
        self.numeric = numeric

    def get(self):
        if isinstance(self.widget, Choice):
            return self.widget.get()
        if self.variable is not None:
            value = self.variable.get()
            return 0 if value == '' and self.numeric in ('int', 'float') else value
        return self.widget.get()

    def set(self, value):
        if isinstance(self.widget, Choice):
            self.widget.set(value)
        elif self.variable is not None:
            self.variable.set(value)
        else:
            self.widget.set(value)
        if hasattr(self, 'committed_value'):
            self.committed_value = self.get()
