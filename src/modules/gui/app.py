"""Native configuration window. Macro actions remain in gui.py."""

import copy
import html
import json
import os
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk
from . import widgets
from .definitions import (TAB_DEFINITIONS, CONTROL_PRESENTATION, CONDITIONAL_CONTROLS,
                          CUSTOM_DEFINITIONS, CHOICES, GATHER_PATTERN_NOTICES,
                          LEGACY_DISCORD_BOT_DESCRIPTION, SECTION_PRESENTATION,
                          MEMORY_MATCH_REWARD_TYPES, MEMORY_MATCH_TYPE_BADGES, MEMORY_MATCH_TYPE_LABELS,
                          HOME_TASK_EMOJIS, HOME_FALLBACK_ORDER, FIELD_NECTARS)


# Apple HIToolbox Events.h virtual codes for the physical letter and digit keys.
MAC_PHYSICAL_KEYS = {0: 'A', 1: 'S', 2: 'D', 3: 'F', 4: 'H', 5: 'G', 6: 'Z', 7: 'X', 8: 'C', 9: 'V', 11: 'B', 12: 'Q', 13: 'W', 14: 'E', 15: 'R', 16: 'Y', 17: 'T', 18: '1', 19: '2', 20: '3', 21: '4', 22: '6', 23: '5', 25: '9', 26: '7', 28: '8', 29: '0', 31: 'O', 32: 'U', 34: 'I', 35: 'P', 37: 'L', 38: 'J', 40: 'K', 45: 'N', 46: 'M', 82: 'Numpad0', 83: 'Numpad1', 84: 'Numpad2', 85: 'Numpad3', 86: 'Numpad4', 87: 'Numpad5', 88: 'Numpad6', 89: 'Numpad7', 91: 'Numpad8', 92: 'Numpad9'}


MODIFIERS = ('Ctrl', 'Alt', 'Shift', 'Cmd')
KEYBIND_LABELS = {
    'start_keybind': 'Start Macro', 'pause_keybind': 'Pause/Resume Macro',
    'stop_keybind': 'Stop Macro', 'hotbar_buff_start_keybind': 'Start Hotbar Buff',
    'autoclicker_keybind': 'Start Auto Clicker',
    'auto_gifted_basic_bee_start_keybind': 'Start Auto Gifted Basic Bee',
}


def normalize_keybind(value):
    aliases = {'Control': 'Ctrl', 'Option': 'Alt', 'Meta': 'Cmd', 'Command': 'Cmd',
               'Esc': 'Escape', 'Del': 'Delete', 'Spacebar': 'Space'}
    keys = set()
    for raw in str(value or '').split('+'):
        key = raw.strip()
        key = aliases.get(key, key.upper() if len(key) == 1 or re.fullmatch(r'[fF]\d{1,2}', key) else key)
        if key and key != 'Fn':
            keys.add(key)
    return '+'.join([key for key in MODIFIERS if key in keys] + sorted(keys.difference(MODIFIERS)))


UNSET = object()
TABS = ('home', 'gather', 'collect', 'kill', 'boost', 'planters', 'quests', 'tools', 'config')


def plain_text(value):
    return html.unescape(re.sub('<[^>]*>', '', str(value).replace('<br>', '\n').replace('<br/>', '\n')))


def task_enabled(settings, task):
    if task.startswith('gather_'):
        field = task[7:].replace('_', ' ')
        return any(enabled and name == field for name, enabled in zip(settings['fields'], settings['fields_enabled']))
    if task.startswith('quest_'):
        return bool(settings.get(task[6:] + '_quest'))
    if task.startswith('kill_'):
        return bool(settings.get(task[5:]))
    if task.startswith('collect_'):
        key = {'sprouts': 'sprouts_enable', 'sticker_sprout': 'sticker_sprout_watch'}.get(task[8:], task[8:])
        return bool(settings.get(key))
    key = {'blender': 'blender_enable', 'planters': 'planters_mode', 'auto_field_boost': 'Auto_Field_Boost'}.get(task, task)
    return bool(settings.get(key))


class NativeApp:
    def __init__(self, root, actions, manager):
        self.root = root
        self.actions = actions
        self.manager = manager
        self.settings = manager.loadAllSettings()
        self.fields = manager.loadFields()
        self.profile = manager.getCurrentProfile()
        self.palette = widgets.palette(self.settings.get('gui_theme'))
        self.controls = {}
        self.control_groups = {}
        self.rows = {}
        self.pages = {}
        self.subtab_selection = {}
        self.ui_state_path = manager.getUserDataPath('gui_state.json')
        try:
            with open(self.ui_state_path, encoding='utf-8') as source:
                ui_state = json.load(source)
        except (OSError, ValueError):
            ui_state = {}
        self.subtab_selection = ui_state.get('subtabs', {})
        self.images = {}
        self.display_logs = list(actions.getRecentLogs())
        self.pending = queue.Queue()
        self.closing = False
        self.destroyed = False
        self.stop_supervisor = threading.Event()
        self.supervisor_thread = None
        self.update_running = False
        self.close_callback = None
        self.failure = None
        self.timer_signature = None
        self.timer_labels = []
        self.recording = None
        self.recording_lock = threading.Lock()
        self.recorded_keys = set()
        self.field_slot = 0
        self.active_tab = ui_state.get('tab', 'home')
        if self.active_tab not in TABS:
            self.active_tab = 'home'
        root.title('Fuzzy Macro')
        root.geometry('1280x800')
        root.minsize(800, 640)
        root.configure(bg=self.palette['bg'])
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind_all('<MouseWheel>', self.wheel)
        root.bind_all('<KeyPress>', self.record_key)
        root.bind_all('<KeyRelease>', self.finish_key)
        root.bind_all('<ButtonPress-1>', self.cancel_recording_click, add='+')
        self.configure_styles()
        self.build_shell()
        root.bind('<Configure>', self.window_resized, add='+')
        self.poll_pending()

    def window_resized(self, event):
        if event.widget is self.root:
            self.root.after_idle(self.repaint_window)

    def repaint_window(self):
        self.root.update_idletasks()
        widgets.repaint(self.shell)

    def configure_styles(self):
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('Treeview', background=self.palette['input'], fieldbackground=self.palette['input'],
                        foreground=self.palette['text'], borderwidth=0, rowheight=32, font=('Poppins', -14))
        style.configure('Treeview.Heading', background=self.palette['surface'], foreground=self.palette['text'], font=('Poppins', -14, 'bold'))
        style.map('Treeview', background=[('selected', self.palette['selected'])], foreground=[('selected', self.palette['text'])])

    def image(self, path, size=None):
        if not os.path.isabs(path):
            module_path = os.path.normpath(os.path.join(os.path.dirname(__file__), path))
            path = module_path if os.path.isfile(module_path) else os.path.join(widgets.ASSET_ROOT, path.lstrip('./'))
        key = (path, size)
        if key not in self.images:
            with Image.open(path) as source:
                image = source.convert('RGBA')
                if size:
                    image.thumbnail(size, getattr(Image, 'Resampling', Image).LANCZOS)
                self.images[key] = ImageTk.PhotoImage(image)
        return self.images[key]

    def build_shell(self):
        for child in self.root.winfo_children():
            child.destroy()
        self.controls.clear()
        self.control_groups.clear()
        self.rows.clear()
        self.pages.clear()
        self.shell = tk.Frame(self.root, bg=self.palette['bg'])
        self.shell.pack(fill='both', expand=True)
        sidebar = tk.Frame(self.shell, width=240, bg=self.palette['surface'])
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        tk.Frame(self.shell, width=1, bg=self.palette['border']).pack(side='left', fill='y')
        tk.Label(sidebar, text='Fuzzy Macro', font=('Libre Franklin', -24, 'bold'), fg=self.palette['accent'], bg=self.palette['surface']).pack(pady=(16, 10))
        self.navigation = {}
        for tab in TABS:
            button = widgets.Button(sidebar, tab.title(), lambda tab=tab: self.show_tab(tab), self.palette,
                                    width=208, font=('Poppins', -15), fill=self.palette['surface'], foreground=self.palette['dim'],
                                    image=self.image('assets/sidebar/%s.png' % tab, (20, 20)))
            button.configure(height=46)
            button.pack(padx=16, pady=4)
            self.navigation[tab] = button
        credits = tk.Frame(sidebar, bg=self.palette['surface'])
        credits.pack(side='bottom', fill='x', padx=37, pady=16)
        self.label(credits, 'v' + self.actions.getMacroVersion(), dim=True).pack(pady=(0, 8))
        self.update_button = self.button(credits, 'Check for Updates', self.check_updates)
        self.update_button.pack(fill='x')
        self.update_text = self.label(credits, '', dim=True)
        self.progress = ttk.Progressbar(credits, maximum=100)
        self.content = tk.Frame(self.shell, bg=self.palette['bg'])
        self.content.pack(side='left', fill='both', expand=True)
        self.status_text = tk.StringVar(self.root)
        self.status_label = tk.Label(self.content, textvariable=self.status_text, font=('Poppins', -12), fg=self.palette['dim'], bg=self.palette['bg'], anchor='w')
        self.show_tab(self.active_tab)

    def show_tab(self, tab):
        self.stop_recording()
        for page in self.pages.values():
            page.pack_forget()
        self.active_tab = tab
        for name, button in self.navigation.items():
            button.fill = self.palette['selected'] if name == tab else self.palette['surface']
            button.foreground = self.palette['accent'] if name == tab else self.palette['dim']
            button.draw()
        if tab not in self.pages:
            page = widgets.Scroll(self.content, self.palette)
            page.canvas.configure(yscrollcommand=page.set_scroll)
            self.pages[tab] = page
            body = tk.Frame(page.body, bg=self.palette['bg'])
            body.pack(fill='both', expand=True, padx=32, pady=32)
            if tab == 'home':
                page.stretch = True
                self.build_home(body)
            elif tab == 'gather':
                self.build_gather(body)
            elif tab in ('planters', 'tools'):
                from . import editors
                getattr(editors, 'build_' + tab)(self, body)
            else:
                body.configure(padx=32, pady=32)
                definitions = TAB_DEFINITIONS[tab]
                self.subtabs(body, [(sub['id'], sub['title'], lambda parent, sub=sub: self.form(parent, sub['sections'])) for sub in definitions], tab)
        self.pages[tab].pack(fill='both', expand=True)
        self.update_conditions()
        # Repaint the embedded frame after Tk has finished remapping the page.
        self.pages[tab].update_idletasks()
        widgets.repaint(self.pages[tab])

    def label(self, parent, text, dim=False):
        return tk.Label(parent, text=plain_text(text), font=('Poppins', -14), fg=self.palette['dim' if dim else 'text'], bg=parent.cget('bg'), justify='left', anchor='w', bd=0, padx=0, pady=0)

    def button(self, parent, text, command):
        return widgets.Button(parent, text, command, self.palette)

    def card(self, parent, title, desc=''):
        card = widgets.Card(parent, self.palette, title, plain_text(desc))
        card.pack(fill='x', pady=(0, 16))
        return card.body

    def subtabs(self, parent, tabs, key):
        nav = tk.Frame(parent, bg=parent.cget('bg'))
        nav.pack(fill='x', pady=(0, 16))
        holder = tk.Frame(parent, bg=parent.cget('bg'))
        holder.pack(fill='both', expand=True)
        views, buttons = {}, {}

        def select(tab_id):
            self.stop_recording()
            self.subtab_selection[key] = tab_id
            for view in views.values():
                view.pack_forget()
            for name, button in buttons.items():
                button.fill = self.palette['selected'] if name == tab_id else parent.cget('bg')
                button.foreground = self.palette['accent'] if name == tab_id else self.palette['dim']
                button.draw()
            if tab_id not in views:
                frame = tk.Frame(holder, bg=holder.cget('bg'))
                views[tab_id] = frame
                next(builder for name, label, builder in tabs if name == tab_id)(frame)
            views[tab_id].pack(fill='both', expand=True)
            self.update_conditions()

        for tab_id, title, builder in tabs:
            button = self.button(nav, title, lambda tab_id=tab_id: select(tab_id))
            button.configure(height=32)
            buttons[tab_id] = button
        widgets.wrap_buttons(nav, list(buttons.values()))
        selected = self.subtab_selection.get(key, tabs[0][0])
        select(selected if selected in buttons else tabs[0][0])

    def form(self, parent, sections):
        body = None
        for section in sections:
            presentation = SECTION_PRESENTATION.get((self.active_tab, self.subtab_selection.get(self.active_tab), section['title']), {})
            if presentation.get('inline_separator'):
                tk.Frame(body, bg=self.palette['border'], height=1).pack(fill='x', pady=(24, 16))
                self.label(body, section['title']).pack(anchor='w', pady=(0, 8))
                self.label(body, section.get('desc', ''), dim=True).pack(anchor='w', pady=(0, 16))
            else:
                body = self.card(parent, section['title'], section.get('desc', ''))
            if presentation.get('image'):
                body.master.heading.configure(image=self.image(presentation['image'], (20, 20)), compound='left')
            for spec in section['controls']:
                if spec['kind'] == 'custom':
                    from .configuration import build_custom
                    control = build_custom(self, body, spec)
                    self.controls[spec['id']] = control
                    if spec.get('action') == 'task_priorities':
                        self.control_groups.setdefault(spec['id'], []).append(control)
                else:
                    self.add_control(body, spec)

    def add_control(self, parent, spec, value=UNSET, onchange=None):
        identifier = spec['id']
        kind = spec['kind']
        missing = value is UNSET and identifier not in (self.field_data if spec.get('scope') == 'field' else self.settings)
        if value is UNSET:
            if spec.get('scope') == 'field':
                value = self.field_data.get(identifier, '')
            else:
                value = self.settings.get(identifier, '')
        row = tk.Frame(parent, bg=parent.cget('bg'))
        row.pack(fill='x', pady=(0, 16))
        self.rows[identifier] = row
        row.grid_columnconfigure(0, weight=1)
        text = tk.Frame(row, bg=row.cget('bg'))
        text.grid(row=0, column=0, sticky='new', padx=(0, 24))
        title = self.label(text, spec.get('title', ''))
        title.configure(font=('Poppins', -15))
        title.pack(fill='x')
        title.bind('<Configure>', lambda event: title.configure(wraplength=max(1, event.width)))
        desc = spec.get('desc', '')
        if identifier == 'discord_bot_token' and self.actions.usesLegacyDiscordBot():
            desc += LEGACY_DISCORD_BOT_DESCRIPTION
        description = self.label(text, desc, dim=True)
        description.configure(font=('Poppins', -13))
        if desc:
            description.pack(fill='x')
            description.bind('<Configure>', lambda e: description.configure(wraplength=max(1, min(e.width, round(row.winfo_width() * .70)))))
        presentation = CONTROL_PRESENTATION.get(identifier, {})
        control = None

        def changed():
            if onchange:
                onchange(control.get())
            else:
                self.control_changed(spec, control)

        right = tk.Frame(row, bg=row.cget('bg'))
        right.grid(row=0, column=1, sticky='ne', pady=6, padx=(0, 24))
        if kind != 'multicheck':
            def align(event):
                right.grid_configure(padx=(0, round(event.width * (.10 if kind == 'checkbox' else .05))))
            row.bind('<Configure>', align)
        width = round((presentation.get('width_rem') or 10) * 16)
        if kind == 'checkbox':
            widget = widgets.Checkbox(right, value, changed, self.palette)
            widget.pack()
            control = widgets.Control(widget, widget.variable)
        elif kind == 'dropdown':
            choices = spec.get('choices', [])
            if spec.get('choices_key') == 'patterns':
                choices = [dict(label=item['label'], value=item['value']) for item in self.actions.getPatterns()]
            elif spec.get('choices_key') == 'default_patterns':
                choices = [dict(label=item['label'], value=item['value']) for item in self.actions.getDefaultPatterns()]
            if missing:
                value = [] if presentation.get('multiple', False) else 'none'
            widget = widgets.Choice(right, choices, value, changed, self.palette, multiple=presentation.get('multiple', False), width=width, image_loader=self.image)
            widget.pack()
            control = widgets.Control(widget, widget.variable)
        elif kind in ('textbox', 'textbox_with_button'):
            variable = tk.StringVar(self.root, str(value))
            widget = tk.Entry(right, textvariable=variable, font=('Poppins', -14), width=max(5, width // 9), fg=self.palette['text'], bg=self.palette['input'], insertbackground=self.palette['text'], bd=0, highlightthickness=1, highlightbackground=self.palette['border'], highlightcolor=self.palette['accent'])
            widget.pack(side='left', ipady=7)
            control = widgets.Control(widget, variable, spec.get('numeric'))
            control.committed_value = control.get()

            def commit(event=None):
                if control.get() != control.committed_value:
                    changed()
                    control.committed_value = control.get()

            widget.bind('<FocusOut>', commit)
            widget.bind('<Return>', lambda e: parent.focus_set())
            limit = spec.get('limit', 0)
            numeric = spec.get('numeric')
            if limit or numeric in ('int', 'float'):
                def validate(proposed, inserted):
                    return (not limit or len(proposed) <= limit) and (numeric not in ('int', 'float') or not inserted or all(c.isdigit() or numeric == 'float' and c == '.' for c in inserted)) and (numeric != 'float' or proposed.count('.') <= 1)
                widget.configure(validate='key', validatecommand=(widget.register(validate), '%P', '%S'))
            if kind == 'textbox_with_button':
                self.button(right, presentation.get('text', 'Update'), lambda: self.dispatch(spec.get('action'), spec, control)).pack(side='left', padx=(8, 0))
        elif kind == 'button':
            widget = self.button(right, presentation.get('text', spec.get('title', '')), lambda: self.dispatch(spec.get('action'), spec, control))
            widget.pack()
            control = widgets.Control(widget)
        elif kind == 'keybind':
            variable = tk.StringVar(self.root, str(value))
            widget = self.button(right, str(value).replace('+', ' + ') or 'Click to record', lambda: self.start_recording(identifier))
            widget.fill = self.palette['input']
            widget.foreground = self.palette['text']
            widget.draw()
            widget.pack(side='left')
            self.button(right, 'Clear', lambda: self.save_keybind(identifier, '')).pack(side='left', padx=(8, 0))
            control = widgets.Control(widget, variable)
        elif kind == 'multicheck':
            text.grid_configure(columnspan=2, padx=0)
            right.grid(row=1, column=0, columnspan=2, sticky='ew', padx=0)
            selected = list(value) if isinstance(value, (list, tuple)) else []
            variables = []
            choices = spec.get('choices', [])
            for index, item in enumerate(choices):
                tile = tk.Frame(right, bg=self.palette['input'])
                tile.grid(row=index // 6, column=index % 6, sticky='nsew', padx=3, pady=3)
                variable = tk.BooleanVar(self.root, item['value'] in selected)
                if item.get('image'):
                    image = self.image(item['image'], (44, 44))
                    label = tk.Label(tile, image=image, bg=self.palette['input'])
                    label.pack(padx=8, pady=6)
                if identifier == 'memory_match_rewards':
                    types = MEMORY_MATCH_REWARD_TYPES[item['value']]
                    badge = self.label(tile, '/'.join(MEMORY_MATCH_TYPE_BADGES[kind] for kind in types), dim=True)
                    badge.configure(font=('Poppins', -10, 'bold'))
                    badge.pack()
                    tooltip = item['label'] + ' - found in ' + ', '.join(MEMORY_MATCH_TYPE_LABELS[kind] for kind in types)
                    widgets.tooltip(tile, tooltip, self.palette)
                label = tk.Checkbutton(tile, text=item['label'], variable=variable, bg=self.palette['input'], fg=self.palette['text'], selectcolor=self.palette['accent'], activebackground=self.palette['hover'], font=('Poppins', -12), wraplength=110)
                label.pack(fill='both', expand=True, padx=4, pady=4)
                variables.append((item['value'], variable))

                def choose(variable=variable):
                    maximum = spec.get('max_selections', 0)
                    if maximum and sum(var.get() for val, var in variables) > maximum:
                        variable.set(False)
                    changed()

                label.configure(command=choose)
            tiles = right.winfo_children()
            def arrange_tiles(event):
                columns = max(1, min(6, event.width // 120))
                for index, tile in enumerate(tiles):
                    tile.grid_configure(row=index // columns, column=index % columns)
            right.bind('<Configure>', arrange_tiles)
            control = widgets.Control(right)
            control.get = lambda: [item for item, variable in variables if variable.get()]
            control.set = lambda values: [variable.set(item in values) for item, variable in variables]
        else:
            raise ValueError('Unsupported native control: ' + kind)
        self.controls[identifier] = control
        if kind != 'button' and spec.get('scope') in ('profile', 'general') and spec.get('action') not in ('set_gather_field_enabled', 'select_gather_field'):
            self.control_groups.setdefault(identifier, []).append(control)
        return control

    def control_changed(self, spec, control):
        action = spec.get('action')
        if action:
            self.dispatch(action, spec, control)
        elif spec.get('scope') in ('profile', 'general'):
            self.save(spec['id'], control.get(), spec['scope'])
        if spec.get('bind') and control.get():
            partner = spec['bind']
            self.save(partner, False, 'profile')
            if partner in self.controls:
                self.controls[partner].set(False)
        self.update_conditions()

    def save(self, key, value, scope='profile'):
        if scope == 'general':
            self.manager.saveGeneralSetting(key, value)
        elif scope == 'profile':
            self.manager.saveProfileSetting(key, value)
        else:
            raise ValueError('Setting has no persistence scope: ' + key)
        self.settings = self.manager.loadAllSettings()
        for control in self.control_groups.get(key, []):
            if control.widget.winfo_exists() and control.get() != self.settings[key]:
                control.set(self.settings[key])
        if self.active_tab == 'home':
            self.refresh_home()

    def action(self, name, *args):
        result = getattr(self.actions, name)(*args)
        if isinstance(result, dict) and result.get('ok') is False:
            raise ValueError(result.get('message', name + ' failed'))
        return result

    def dispatch(self, name, spec=None, control=None):
        try:
            identifier = spec['id'] if spec else ''
            value = control.get() if control and spec.get('kind') not in ('button', 'textbox_with_button') else None
            if name == 'save_gather_field':
                self.save_gather_field()
            elif name == 'set_gather_field_enabled':
                enabled = list(self.settings['fields_enabled'])
                enabled[self.field_slot] = value
                self.save('fields_enabled', enabled)
            elif name == 'select_gather_field':
                fields = list(self.settings['fields'])
                fields[self.field_slot] = value
                self.save('fields', fields)
                self.load_gather_field()
            elif name == 'select_gather_pattern':
                self.change_pattern(value)
            elif name == 'import_patterns':
                paths = filedialog.askopenfilenames(parent=self.root, filetypes=[('Gather patterns', '*.py *.ahk')])
                if paths:
                    patterns = []
                    for path in paths:
                        with open(path, encoding='utf-8') as source:
                            patterns.append(dict(name=os.path.basename(path), content=source.read()))
                    result = self.action('importPatterns', patterns)
                    messagebox.showinfo('Import Patterns', '\n'.join(result['saved'] + result['errors']), parent=self.root)
                    self.controls['shape'].widget.set_choices([dict(label=p['label'], value=p['value']) for p in self.actions.getPatterns()])
            elif name == 'export_field_settings':
                data = self.manager.exportFieldSettings(self.field_name)
                self.root.clipboard_clear()
                self.root.clipboard_append(data)
                self.status('Field settings copied to clipboard.')
            elif name == 'import_field_settings':
                self.paste_dialog('Import Field Settings', lambda text: self.manager.importFieldSettings(self.field_name, text))
            elif name == 'reset_field':
                if messagebox.askyesno('Reset Field', 'Reset this field to its defaults?', parent=self.root):
                    self.action('resetFieldToDefault', self.field_name)
                    self.load_gather_field()
            elif name in ('fuzzy_ai_tokens', 'sprout_ai_tokens'):
                from .editors import open_token_ranking
                open_token_ranking(self, self.field_name if name == 'fuzzy_ai_tokens' else self.settings['sprouts_field'], self.settings['ai_gather_model'] if name == 'fuzzy_ai_tokens' else self.settings['sprouts_ai_model'], sprouts=name == 'sprout_ai_tokens')
            elif name == 'select_sprout_ai_model':
                self.save(identifier, value, spec['scope'])
            elif name == 'reset_blender':
                self.action('clearBlender')
            elif name == 'reset_auto_field_boost':
                self.action('clearAFB')
            elif name == 'apply_theme':
                self.save(identifier, value, spec['scope'])
                self.palette = widgets.palette(value)
                self.configure_styles()
                self.build_shell()
            elif name == 'record_keybind':
                self.start_recording(identifier)
            else:
                from .configuration import handle_action
                if not handle_action(self, name, spec, control):
                    raise ValueError('Unknown GUI action: ' + str(name))
        except Exception as exc:
            messagebox.showerror('Fuzzy Macro', str(exc), parent=self.root)

    def update_conditions(self):
        state = dict(self.settings)
        state.update({key: control.get() for key, control in self.controls.items() if key in ('shape', 'return', 'infinite_gather', 'discord_delivery_mode', 'sprouts_ai_model')})
        for key, rules in CONDITIONAL_CONTROLS.items():
            if key not in self.rows or not self.rows[key].winfo_exists():
                continue
            visible = True
            for condition, expected in rules.get('visible_when', {}).items():
                visible = visible and state.get(condition) in expected
            for condition, expected in rules.get('hidden_when', {}).items():
                visible = visible and state.get(condition) not in expected
            row = self.rows[key]
            if visible and not row.winfo_manager():
                siblings = row.master.winfo_children()
                following = next((child for child in siblings[siblings.index(row) + 1:] if child.winfo_manager() == 'pack'), None)
                row.pack(fill='x', pady=(0, 16), **({'before': following} if following else {}))
            elif not visible:
                row.pack_forget()
            control = self.controls[key]
            disabled = any(state.get(condition) == expected for condition, expected in rules.get('disabled_when', {}).items())
            if isinstance(control.widget, tk.Entry):
                control.widget.configure(state='disabled' if disabled else 'normal')
        if 'gather' in self.pages:
            pattern = self.controls['shape'].get()
            for title, expected in (('AI Gathering', 'fuzzy_ai_gather'), ('BloomsAI', 'blooms_ai')):
                card = self.gather_sections[title]
                if pattern == expected and not card.winfo_manager():
                    following = next((child for child in self.gather_cards[self.gather_cards.index(card) + 1:] if child.winfo_manager() == 'pack'), None)
                    card.pack(fill='x', pady=(0, 16), **({'before': following} if following else {}))
                elif pattern != expected:
                    card.pack_forget()
            notice = next((item['text'] for item in GATHER_PATTERN_NOTICES if self.field_name in item['fields'] or pattern in item['patterns']), '')
            self.gather_notice.configure(text=notice)
            if notice:
                self.gather_notice.pack(fill='x', pady=(0, 16), before=self.gather_cards[0])
            else:
                self.gather_notice.pack_forget()

    def build_gather(self, parent):
        inner = tk.Frame(parent, bg=self.palette['bg'], padx=32, pady=32)
        inner.pack(fill='x')
        nav = tk.Frame(inner, bg=self.palette['bg'])
        nav.pack(fill='x', pady=(0, 16))
        self.field_buttons = []
        for index in range(5):
            button = self.button(nav, 'Field %d' % (index + 1), lambda index=index: self.select_field_slot(index))
            button.configure(height=32)
            button.pack(side='left', padx=(0, 8))
            self.field_buttons.append(button)
        self.button(nav, 'Import Patterns', lambda: self.dispatch('import_patterns')).pack(side='right')
        body = self.card(inner, '')
        self.field_name = self.settings['fields'][self.field_slot]
        self.field_data = copy.deepcopy(self.fields[self.field_name])
        self.gather_sections = {}
        self.gather_cards = []
        self.gather_notice = self.label(body, '', dim=True)
        for section in TAB_DEFINITIONS['gather'][0]['sections']:
            if section['title'] == '' and all(spec.get('action') == 'import_patterns' for spec in section['controls']):
                continue
            if not section['title']:
                footer = tk.Frame(body, bg=self.palette['surface'])
                footer.pack(pady=20)
                for spec in section['controls']:
                    button = self.button(footer, CONTROL_PRESENTATION[spec['id']]['text'], lambda spec=spec: self.dispatch(spec['action'], spec))
                    button.pack(side='left', padx=5)
                    self.controls[spec['id']] = widgets.Control(button)
                continue
            card = self.card(body, section['title'].replace('Gather Field', 'Gather Field %d' % (self.field_slot + 1)), section.get('desc', ''))
            self.gather_sections[section['title']] = card.master
            self.gather_cards.append(card.master)
            for spec in section['controls']:
                self.add_control(card, spec, value=self.field_data.get(spec['id'], UNSET))
        self.load_gather_field()

    def select_field_slot(self, index):
        self.field_slot = index
        self.load_gather_field()
        self.pages['gather'].canvas.yview_moveto(0)

    def load_gather_field(self):
        self.fields = self.manager.loadFields()
        self.field_name = self.settings['fields'][self.field_slot]
        self.field_data = copy.deepcopy(self.fields[self.field_name])
        self.controls['field'].set(self.field_name)
        self.controls['field_enable'].set(self.settings['fields_enabled'][self.field_slot])
        for key, value in self.field_data.items():
            if key in self.controls:
                self.controls[key].set(value)
        for index, button in enumerate(self.field_buttons):
            button.fill = self.palette['selected'] if index == self.field_slot else self.palette['bg']
            button.foreground = self.palette['accent'] if index == self.field_slot else self.palette['dim']
            button.draw()
        self.gather_sections['Gather Field'].heading.configure(text='Gather Field %d' % (self.field_slot + 1))
        self.update_conditions()

    def gather_values(self):
        values = copy.deepcopy(self.field_data)
        for section in TAB_DEFINITIONS['gather'][0]['sections']:
            for spec in section['controls']:
                if spec.get('scope') == 'field' and spec['kind'] not in ('button', 'custom') and spec['id'] not in ('field', 'field_enable'):
                    values[spec['id']] = self.controls[spec['id']].get()
        if values.get('goo_interval'):
            values['goo_interval'] = str(max(3, int(values['goo_interval'])))
            self.controls['goo_interval'].set(values['goo_interval'])
        return values

    def remember_pattern(self, data, pattern):
        presets = data.setdefault('pattern_presets', {})
        preset = copy.deepcopy(data)
        preset.pop('pattern_presets', None)
        preset['shape'] = pattern
        presets[pattern] = preset

    def save_gather_field(self):
        values = self.gather_values()
        self.remember_pattern(values, values['shape'])
        self.manager.saveField(self.field_name, values)
        self.field_data = values
        self.update_conditions()

    def change_pattern(self, selected):
        values = self.gather_values()
        previous = self.field_data['shape']
        self.remember_pattern(values, previous)
        preset = values['pattern_presets'].get(selected)
        if preset is None and selected in ('fuzzy_ai_gather', 'blooms_ai'):
            preset = self.manager.getDefaultFuzzyAIGatherPatternPreset() if selected == 'fuzzy_ai_gather' else self.manager.getDefaultBloomsAIPatternPreset()
        if preset:
            values.update(preset)
        values['shape'] = selected
        self.remember_pattern(values, selected)
        self.manager.saveField(self.field_name, values)
        self.load_gather_field()

    def build_home(self, parent):
        self._tasks = None
        self._log_signature = None
        self.timer_signature = None
        self.timer_labels = []
        top = tk.Frame(parent, bg=self.palette['bg'])
        top.pack(fill='x', pady=(0, 32))
        top.grid_columnconfigure((0, 1), weight=1, uniform='home')
        control_card = widgets.Card(top, self.palette)
        control_card.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        heading = self.label(control_card.body, 'Macro Control')
        heading.configure(font=('Poppins', -18, 'bold'))
        heading.pack(side='left', pady=10)
        self.start_button = self.button(control_card.body, '', self.start_stop)
        self.start_button.pack(side='right')
        mode_card = widgets.Card(top, self.palette)
        mode_card.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        heading = self.label(mode_card.body, 'Macro Mode')
        heading.configure(font=('Poppins', -18, 'bold'))
        heading.pack(side='left', pady=10)
        modes = [dict(label=label, value=value) for label, value in [('Normal Mode', 'normal'), ('Alt Mode', 'alt'), ('Field Mode', 'field'), ('Quest Mode', 'quest'), ('Bug Run Mode', 'bug')]]
        self.mode_choice = widgets.Choice(mode_card.body, modes, self.settings['macro_mode'], lambda: self.save('macro_mode', self.mode_choice.get(), 'general'), self.palette)
        self.mode_choice.pack(side='right')
        def arrange_home(event):
            narrow = event.width < 595
            if narrow != getattr(top, 'narrow', None):
                top.narrow = narrow
                control_card.grid_configure(columnspan=2 if narrow else 1, padx=0 if narrow else (0, 8))
                mode_card.grid_configure(row=1 if narrow else 0, column=0 if narrow else 1,
                                         columnspan=2 if narrow else 1, padx=0 if narrow else (8, 0),
                                         pady=(16, 0) if narrow else 0)
        top.bind('<Configure>', arrange_home)
        columns = tk.Frame(parent, bg=self.palette['bg'])
        columns.pack(fill='both', expand=True)
        columns.grid_columnconfigure((0, 1), weight=1, uniform='home')
        columns.grid_rowconfigure(0, weight=1)
        left = tk.Frame(columns, bg=self.palette['bg'])
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        right = tk.Frame(columns, bg=self.palette['bg'])
        right.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        task_card = widgets.Card(left, self.palette, 'Tasks', grow=True)
        task_card.pack(fill='both', expand=True, pady=(0, 16))
        self.tasks_body = task_card.body
        log_card = widgets.Card(right, self.palette, 'Logs', grow=True)
        log_card.pack(fill='both', expand=True, pady=(0, 16))
        self.logs_body = log_card.body
        toolbar = log_card.header
        for title, command in [('Clear', self.clear_logs), ('Export', self.export_logs)]:
            button = self.button(toolbar, title, command)
            button.configure(height=26)
            button.pack(side='right', padx=(4, 0))
        self.log_filter = tk.StringVar(self.root)
        search = tk.Entry(self.logs_body, textvariable=self.log_filter, font=('Poppins', -14), bg=self.palette['input'], fg=self.palette['text'], insertbackground=self.palette['text'], bd=0, relief='flat', highlightthickness=1, highlightbackground=self.palette['border'], highlightcolor=self.palette['accent'])
        search.pack(fill='x', ipady=4, pady=(0, 8))
        hint = tk.Label(search, text='Search logs (e.g. claimed Hive)', font=('Poppins', -13), bg=self.palette['input'], fg=self.palette['dim'], bd=0, padx=8)
        hint.place(x=0, y=4)
        hint.bind('<Button-1>', lambda event: search.focus_set())
        search.bind('<FocusIn>', lambda event: hint.place_forget())
        search.bind('<FocusOut>', lambda event: hint.place(x=0, y=4) if not self.log_filter.get() else None)
        self.log_count = self.label(self.logs_body, '', dim=True)
        self.log_count.pack(fill='x')
        self.logs_text = tk.Text(self.logs_body, height=14, wrap='word', bg=self.palette['surface'], fg=self.palette['text'], font=('Poppins', -14), bd=0, highlightthickness=0, state='disabled')
        self.logs_text.pack(fill='both', expand=True)
        self.log_filter.trace_add('write', lambda *args: self.render_logs())
        self.timers_card = widgets.Card(right, self.palette, 'Planter Timers')
        self.timers_body = self.timers_card.body
        self.button(self.timers_body, 'Reset All Timers', self.reset_planter_timers).pack(anchor='e')
        self.timer_rows = tk.Frame(self.timers_body, bg=self.palette['surface'])
        self.timer_rows.pack(fill='x')
        self.refresh_home()

    def task_enabled(self, task):
        return task_enabled(self.settings, task)

    def home_tasks(self):
        mode = self.settings['macro_mode']
        if mode == 'alt':
            return [('Alt Mode', 'Gathers the host-assigned field indefinitely'), ('Host Controlled', 'The host assigns the field before every Alt Mode run')]
        order = self.settings.get('task_priority_order', [])
        tasks = []
        fallback = mode == 'normal' and not order
        if mode == 'field':
            tasks.append(('Field Only Mode', '🌾 Gathering in fields only'))
            gather = [task for task in order if task.startswith('gather_') and self.task_enabled(task)]
            if not gather:
                gather = ['gather_' + field.replace(' ', '_') for field, enabled in zip(self.settings['fields'], self.settings['fields_enabled']) if enabled]
            for index, task in enumerate(gather):
                tasks.append(('Gather %d' % (index + 1), next(item['label'] for item in CHOICES['field'] if item['value'] == task[7:].replace('_', ' '))))
            return tasks
        if mode == 'quest':
            tasks.append(('Quest Mode', '📜 Doing quests only'))
            for giver, emoji in (('honey_bee', '🐝'), ('bucko_bee', '🏴‍☠️'), ('riley_bee', '🎸'), ('polar_bear', '🐻'), ('brown_bear', '🐻'), ('black_bear', '🐻')):
                if self.settings[giver + '_quest']:
                    name = giver.replace('_', ' ').title() + ' Quest'
                    tasks.append((name, emoji + ' ' + name))
            return tasks
        elif mode == 'bug':
            tasks.append(('Bug Run Mode', '🐞 Doing bug runs only (including bosses)'))
            order = [task for task in order if task.startswith('kill_') or task in ('ant_challenge', 'stinger_hunt')]
        elif not order:
            order = list(HOME_FALLBACK_ORDER)
        for task in order:
            if not self.task_enabled(task):
                continue
            if task.startswith('gather_'):
                field = task[7:].replace('_', ' ')
                for index, (name, enabled) in enumerate(zip(self.settings['fields'], self.settings['fields_enabled'])):
                    if enabled and name == field:
                        choice = next(item for item in CHOICES['field'] if item['value'] == field)
                        tasks.append(('Gather %d' % (index + 1), choice['label']))
            elif task == 'planters':
                tasks.append(('Planters', 'Manual' if int(self.settings['planters_mode']) == 1 else 'Auto'))
            elif task == 'blender':
                items = list(dict.fromkeys(self.settings['blender_item_%d' % slot] for slot in range(1, 6) if self.settings['blender_item_%d' % slot] != 'none'))
                tasks.append(('Blender', '\n'.join(item.title() for item in items)))
            else:
                title = 'Quest' if task.startswith('quest_') else 'Kill' if task.startswith('kill_') or task in ('ant_challenge', 'stinger_hunt') else 'Collect Buff' if task in ('collect_sticker_stack', 'auto_field_boost') else 'Collect'
                name = task.split('_', 1)[1] if task.startswith(('collect_', 'kill_', 'quest_')) else task
                name = name.replace('rhinobeetle', 'rhino beetle').replace('_', ' ').title()
                if fallback and task == 'auto_field_boost':
                    title = 'Collect'
                elif fallback and task in ('collect_blue_booster', 'collect_red_booster', 'collect_mountain_booster'):
                    title = 'Collect Buff'
                emoji = HOME_TASK_EMOJIS.get(task, '')
                if fallback and task in ('collect_blue_booster', 'collect_red_booster', 'collect_mountain_booster'):
                    emoji = {'collect_blue_booster': '🔵', 'collect_red_booster': '🔴', 'collect_mountain_booster': '⚪'}[task]
                tasks.append((title, (emoji + ' ' + name).strip()))
        if fallback:
            for index, (field, enabled) in enumerate(zip(self.settings['fields'], self.settings['fields_enabled'])):
                if enabled:
                    tasks.append(('Gather %d' % (index + 1), next(item['label'] for item in CHOICES['field'] if item['value'] == field)))
        return tasks

    def refresh_home(self):
        if 'home' not in self.pages:
            return
        state = self.actions.getRunState()
        text = 'Stopping...' if state == 0 else 'Stop [%s]' % self.settings['stop_keybind'] if state == 2 else 'Unpause [%s]' % self.settings['pause_keybind'] if state == 6 else 'Start [%s]' % self.settings['start_keybind']
        self.start_button.set_text(text)
        self.start_button.set_enabled(state != 0)
        self.mode_choice.set(self.settings['macro_mode'])
        tasks = self.home_tasks()
        if tasks != getattr(self, '_tasks', None):
            self._tasks = tasks
            for child in self.tasks_body.winfo_children()[2:]:
                child.destroy()
            for title, description in tasks:
                label = self.label(self.tasks_body, title)
                label.configure(font=('Poppins', -17))
                label.pack(fill='x', pady=(12, 3))
                if title == 'Blender' or description == 'Sticker Stack':
                    for item in description.split('\n'):
                        label = self.label(self.tasks_body, item, dim=True)
                        label.configure(image=self.image('assets/icons/%s.png' % item.lower().replace(' ', '_'), (20, 20)), compound='left')
                        label.pack(fill='x', pady=(0, 6))
                else:
                    description = re.sub(r'[A-Za-z0-9_]\S*', lambda match: match.group()[0].upper() + match.group()[1:].lower(), description)
                    label = self.label(self.tasks_body, description, dim=True)
                    label.pack(fill='x', pady=(0, 6))
                    label.bind('<Configure>', lambda event: event.widget.configure(wraplength=max(1, event.width)))
                tk.Frame(self.tasks_body, height=1, bg='#949393').pack(fill='x')
        self.render_logs()
        self.refresh_timers()

    def start_stop(self):
        state = self.actions.getRunState()
        try:
            self.action('stop' if state == 2 else 'resume' if state == 6 else 'start')
        except Exception as exc:
            messagebox.showerror('Macro Control', str(exc), parent=self.root)
        self.refresh_home()

    def render_logs(self):
        if not hasattr(self, 'logs_text') or not self.logs_text.winfo_exists():
            return
        logs = self.display_logs
        terms = self.log_filter.get().lower().split()
        signature = (repr(logs), tuple(terms))
        if signature == getattr(self, '_log_signature', None):
            return
        self._log_signature = signature
        self.logs_text.configure(state='normal')
        self.logs_text.delete('1.0', 'end')
        count = 0
        for entry in logs:
            text = '[%s] %s\n%s' % (entry.get('time', ''), entry.get('title', ''), entry.get('desc', ''))
            text = plain_text(text)
            if not all(term in text.lower() for term in terms):
                continue
            count += 1
            color = entry.get('color', 'ffffff').lstrip('#')
            tag = 'color_' + color
            if re.fullmatch('[0-9a-fA-F]{6}', color):
                self.logs_text.tag_configure(tag, foreground='#' + color)
            self.logs_text.insert('end', '▪ ', tag)
            self.logs_text.insert('end', text + '\n')
        self.logs_text.configure(state='disabled')
        self.logs_text.see('end')
        self.log_count.configure(text='%d of %d' % (count, len(logs)) if terms else '')

    def export_logs(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension='.log', filetypes=[('Log', '*.log')])
        if path:
            with open(path, 'w', encoding='utf-8') as output:
                for entry in self.display_logs:
                    output.write(plain_text('[%s] %s\n%s\n' % (entry.get('time', ''), entry.get('title', ''), entry.get('desc', ''))))

    def clear_logs(self):
        if messagebox.askyesno('Clear Logs', 'Clear all logs?', parent=self.root):
            self.action('clearRecentLogs')
            self.display_logs.clear()
            self.render_logs()

    def add_log(self, timestamp, message, color):
        self.display_logs.append(dict(time=timestamp, title=message, desc='', color=color))
        self.render_logs()

    def refresh_timers(self):
        mode = int(self.settings['planters_mode'])
        if not mode:
            self.timers_card.pack_forget()
            return
        self.timers_card.pack(fill='x', pady=(0, 16))
        if mode == 1:
            data = self.actions.getManualPlanterData()
            slots = [(planter, data['fields'][index], data['harvestTimes'][index], index) for index, planter in enumerate(data.get('planters', [])) if planter] if data else []
        else:
            slots = [(slot['planter'], slot['field'], slot['harvest_time'], index) for index, slot in enumerate(self.actions.getAutoPlanterData()['planters']) if slot['planter']]
        signature = (mode, slots)
        if signature == self.timer_signature:
            for label, harvest in self.timer_labels:
                label.configure(text=self.timer_text(harvest))
            return
        self.timer_signature = signature
        self.timer_labels = []
        for child in self.timer_rows.winfo_children():
            child.destroy()
        for planter, field, harvest, index in slots:
            frame = tk.Frame(self.timer_rows, bg=self.palette['surface'])
            frame.pack(side='left', expand=True, padx=6, pady=12)
            image = self.image('assets/icons/%s_planter.png' % planter.replace(' ', '_'), (56, 56))
            tk.Label(frame, image=image, bg=self.palette['surface']).pack()
            nectar = FIELD_NECTARS.get(field)
            if nectar:
                nectar_image = self.image('assets/icons/%s.png' % nectar, (20, 20))
                tk.Label(frame, image=nectar_image, bg=self.palette['surface']).place(x=0, y=40)
            self.label(frame, field.title()).pack()
            label = self.label(frame, self.timer_text(harvest), dim=True)
            label.pack()
            self.timer_labels.append((label, harvest))
            self.button(frame, 'Reset', lambda index=index: self.reset_planter_timer(index)).pack(pady=8)

    def timer_text(self, harvest):
        seconds = harvest - time.time()
        return 'Ready!' if seconds < 0 else '%dh %dm' % (seconds // 3600, seconds % 3600 // 60)

    def reset_planter_timer(self, index):
        self.action('resetManualPlanterTimer' if int(self.settings['planters_mode']) == 1 else 'resetAutoPlanterTimer', index)
        self.refresh_timers()

    def reset_planter_timers(self):
        if messagebox.askyesno('Reset Planter Timers', 'Reset all planter timers?', parent=self.root):
            self.action('clearManualPlanters' if int(self.settings['planters_mode']) == 1 else 'clearAutoPlanters')
            self.refresh_timers()

    def status(self, text):
        self.status_text.set(text)
        self.status_label.pack(side='bottom', fill='x', padx=32, pady=(0, 8))

    def refresh(self):
        self.settings = self.manager.loadAllSettings()
        self.fields = self.manager.loadFields()
        profile = self.manager.getCurrentProfile()
        palette = widgets.palette(self.settings.get('gui_theme'))
        if profile != self.profile or palette != self.palette:
            self.stop_recording()
            self.profile, self.palette = profile, palette
            self._tasks = None
            self._log_signature = None
            self.configure_styles()
            self.build_shell()
            return
        focused = self.root.focus_get()
        for key, group in self.control_groups.items():
            if key not in self.settings:
                continue
            value = self.settings[key]
            for control in group:
                if control.widget.winfo_exists() and control.widget is not focused and key != self.recording and control.get() != value:
                    control.set(value)
        if 'gather' in self.pages:
            field = self.settings['fields'][self.field_slot]
            enabled = self.settings['fields_enabled'][self.field_slot]
            if self.controls['field_enable'].get() != enabled:
                self.controls['field_enable'].set(enabled)
            if field != self.field_name or self.fields[field] != self.field_data:
                self.load_gather_field()
        if 'planters' in self.pages:
            self.refresh_planters()
        self.update_conditions()
        self.refresh_home()

    def enqueue(self, function, *args):
        self.pending.put((function, args))

    def poll_pending(self):
        if self.destroyed:
            return
        try:
            while not self.pending.empty():
                function, args = self.pending.get_nowait()
                function(*args)
                if self.destroyed:
                    return
        finally:
            if not self.destroyed:
                self.root.after(16, self.poll_pending)

    def run_async(self, function, on_done, on_error=None):
        def work():
            try:
                result = function()
            except Exception as exc:
                if on_error:
                    self.enqueue(on_error, exc)
                else:
                    self.enqueue(lambda error=exc: messagebox.showerror('Fuzzy Macro', str(error), parent=self.root))
            else:
                self.enqueue(on_done, result)
        threading.Thread(target=work, daemon=True).start()

    def check_updates(self):
        if self.update_running:
            return
        self.update_running = True
        self.update_button.set_enabled(False)
        self.update_text.configure(text='Checking for updates...')

        def done(info):
            self.update_text.configure(text='')
            if info is None:
                messagebox.showerror('Check for Updates', 'Could not check for updates.', parent=self.root)
            elif info['available']:
                if messagebox.askyesno('Update Available', 'Install the available update?', parent=self.root):
                    self.install_update()
                    return
            else:
                messagebox.showinfo('Check for Updates', 'No update available.', parent=self.root)
            self.reset_update()

        self.run_async(self.actions.checkForUpdates, done, self.update_failed)

    def update_failed(self, error):
        self.reset_update()
        messagebox.showerror('Update', str(error), parent=self.root)

    def install_update(self):
        self.update_running = True
        self.update_button.set_enabled(False)
        self.update_progress(0, 'Starting update')
        def done(result):
            if result:
                self.close()
            else:
                self.reset_update()
                self.update_text.configure(text='Update failed.')
        self.run_async(self.actions.update, done, self.update_failed)

    def check_startup_update(self):
        if self.update_running or self.actions.getAutoUpdateCheckDisabled():
            return
        self.update_running = True
        self.update_button.set_enabled(False)
        def done(info):
            self.reset_update()
            if info and info['available']:
                self.show_update_dialog(info)
        self.run_async(self.actions.checkForUpdates, done, lambda error: self.reset_update())

    def show_update_dialog(self, info):
        self.stop_recording()
        dialog = tk.Toplevel(self.root)
        dialog.title('Update Available')
        dialog.configure(bg=self.palette['surface'])
        dialog.transient(self.root)
        body = tk.Frame(dialog, bg=self.palette['surface'], padx=32, pady=32)
        body.pack(fill='both', expand=True)
        self.label(body, 'A new version of Fuzzy Macro is available!').pack(anchor='w')
        self.label(body, 'Current version: %s\nLatest version: %s' % (info['current_version'], info['latest_version'])).pack(anchor='w', pady=20)
        disabled = tk.BooleanVar(dialog, False)
        tk.Checkbutton(body, text="Don't show this again", variable=disabled, bg=self.palette['surface'], fg=self.palette['text'], selectcolor=self.palette['input'], font=('Poppins', -14)).pack(anchor='w')
        buttons = tk.Frame(body, bg=self.palette['surface'])
        buttons.pack(fill='x', pady=(24, 0))
        def dismiss():
            if disabled.get():
                self.actions.disableAutoUpdateCheck()
            dialog.destroy()
        def install():
            if self.update_running:
                return
            dialog.destroy()
            self.install_update()
        self.button(buttons, 'Update Now', install).pack(side='right')
        self.button(buttons, 'Close', dismiss).pack(side='right', padx=8)
        dialog.protocol('WM_DELETE_WINDOW', dismiss)
        dialog.bind('<Escape>', lambda event: dismiss())

    def update_progress(self, percent, message):
        self.update_text.configure(text='%s  %d%%' % (message, percent))
        self.update_text.pack(fill='x', pady=(8, 0))
        self.progress['value'] = percent
        self.progress.pack(fill='x', pady=(8, 0))

    def reset_update(self):
        self.update_running = False
        self.update_button.set_enabled(True)
        self.update_text.configure(text='')
        self.update_text.pack_forget()
        self.progress.pack_forget()

    def paste_dialog(self, title, save):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=self.palette['surface'])
        dialog.transient(self.root)
        self.label(dialog, 'Paste your JSON settings below:').pack(fill='x', padx=24, pady=16)
        text = tk.Text(dialog, width=60, height=15, bg=self.palette['input'], fg=self.palette['text'], insertbackground=self.palette['text'])
        text.pack(fill='both', expand=True, padx=24)

        def confirm():
            try:
                result = save(text.get('1.0', 'end').strip())
                if result is False or isinstance(result, (tuple, list)) and not result[0]:
                    raise ValueError(result[1] if isinstance(result, (tuple, list)) else 'Invalid settings.')
                dialog.destroy()
                self.refresh()
            except Exception as exc:
                messagebox.showerror(title, str(exc), parent=dialog)

        buttons = tk.Frame(dialog, bg=self.palette['surface'])
        buttons.pack(fill='x', padx=24, pady=24)
        self.button(buttons, 'Import', confirm).pack(side='right')
        self.button(buttons, 'Cancel', dialog.destroy).pack(side='right', padx=8)
        dialog.bind('<Escape>', lambda e: dialog.destroy())

    def open_image(self, path):
        if not os.path.isabs(path):
            local = os.path.normpath(os.path.join(os.path.dirname(__file__), path))
            path = local if os.path.exists(local) else os.path.join(widgets.ASSET_ROOT, path.lstrip('./'))
        with Image.open(path) as source:
            image = source.convert('RGBA')
        window = tk.Toplevel(self.root)
        window.title('Guide')
        window.geometry('900x650')
        window.configure(bg=self.palette['bg'])
        window.transient(self.root)
        controls = tk.Frame(window, bg=self.palette['bg'])
        controls.pack(fill='x', padx=16, pady=16)
        canvas = tk.Canvas(window, bg=self.palette['bg'], highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        scale = [min(1, 850 / image.width, 550 / image.height)]
        original_scale = scale[0]
        offset = [0, 0]

        def render():
            canvas.delete('all')
            canvas.photo = ImageTk.PhotoImage(image.resize((max(1, round(image.width * scale[0])), max(1, round(image.height * scale[0]))), getattr(Image, 'Resampling', Image).LANCZOS))
            canvas.create_image(canvas.winfo_width() / 2 + offset[0], canvas.winfo_height() / 2 + offset[1], image=canvas.photo)

        def zoom(factor, event=None):
            before = scale[0]
            scale[0] = max(original_scale * .5, min(original_scale * 5, before * factor))
            if event:
                ratio = scale[0] / before
                offset[0] = offset[0] * ratio - (event.x - canvas.winfo_width() / 2) * (ratio - 1)
                offset[1] = offset[1] * ratio - (event.y - canvas.winfo_height() / 2) * (ratio - 1)
            else:
                offset[:] = [0, 0]
            render()

        def reset():
            scale[0] = original_scale
            offset[:] = [0, 0]
            render()

        for text, command in [('+', lambda: zoom(1.2)), ('−', lambda: zoom(1 / 1.2)), ('Reset', reset), ('Close', window.destroy)]:
            self.button(controls, text, command).pack(side='left', padx=4)
        canvas.bind('<Configure>', lambda e: render())
        canvas.bind('<MouseWheel>', lambda e: zoom(1.1 if e.delta > 0 else 1 / 1.1, e))
        window.bind('<Escape>', lambda e: window.destroy())

    def wheel(self, event):
        if isinstance(event.widget, (tk.Text, tk.Listbox)):
            return
        widget = event.widget
        while widget is not None:
            if isinstance(widget, widgets.Scroll):
                widget.wheel(event)
                return 'break'
            widget = getattr(widget, 'master', None)

    def start_recording(self, identifier):
        self.stop_recording()
        with self.recording_lock:
            self.recording = identifier
        self.recorded_keys = set()
        self.controls[identifier].widget.set_text('Recording...')
        self.controls[identifier].widget.focus_set()
        self.controls[identifier].widget.bind('<FocusOut>', lambda event: self.stop_recording())

    def is_recording(self):
        with self.recording_lock:
            return self.recording is not None

    def stop_recording(self):
        with self.recording_lock:
            identifier, self.recording = self.recording, None
        if identifier and identifier in self.controls and self.controls[identifier].widget.winfo_exists():
            self.controls[identifier].widget.set_text(str(self.controls[identifier].get()).replace('+', ' + ') or 'Click to record')

    def record_key(self, event):
        if not self.is_recording():
            return
        aliases = {'Control_L': 'Ctrl', 'Control_R': 'Ctrl', 'Alt_L': 'Alt', 'Alt_R': 'Alt', 'Option_L': 'Alt', 'Option_R': 'Alt', 'Shift_L': 'Shift', 'Shift_R': 'Shift', 'Meta_L': 'Cmd', 'Meta_R': 'Cmd', 'Super_L': 'Cmd', 'Super_R': 'Cmd', 'Caps_Lock': 'CapsLock', 'space': 'Space', 'Return': 'Enter', 'Prior': 'PageUp', 'Next': 'PageDown', 'Left': 'ArrowLeft', 'Right': 'ArrowRight', 'Up': 'ArrowUp', 'Down': 'ArrowDown', 'comma': ',', 'period': '.', 'backslash': '\\'}
        key = aliases.get(event.keysym, event.keysym.upper() if len(event.keysym) == 1 else event.keysym)
        if key not in ('Ctrl', 'Alt', 'Shift', 'Cmd', 'Fn') and hasattr(event, 'keycode'):
            if os.sys.platform == 'darwin':
                version = tuple(int(part) for part in self.root.tk.call('package', 'provide', 'Tk').split('.')[:3])
                # Tk 8.6.11 changed the packing from virtual << 16 to virtual << 24.
                virtual = (event.keycode >> (24 if version >= (8, 6, 11) else 16)) & 0xff
                key = MAC_PHYSICAL_KEYS.get(virtual, key)
            elif os.sys.platform == 'win32':
                if 0x30 <= event.keycode <= 0x39 or 0x41 <= event.keycode <= 0x5a:
                    key = chr(event.keycode)
                elif 0x60 <= event.keycode <= 0x69:
                    key = 'Numpad' + str(event.keycode - 0x60)
        if key.startswith('KP_') and key[3:].isdigit():
            key = 'Numpad' + key[3:]
        if key in ('Delete', 'BackSpace'):
            self.save_keybind(self.recording, '')
            return 'break'
        if event.state & 4:
            self.recorded_keys.add('Ctrl')
        if event.state & 1:
            self.recorded_keys.add('Shift')
        if event.state & (16 if os.sys.platform == 'darwin' else 0x20000):
            self.recorded_keys.add('Alt')
        if os.sys.platform == 'darwin' and event.state & 8:
            self.recorded_keys.add('Cmd')
        if key != 'Fn':
            self.recorded_keys.add(key)
        self.controls[self.recording].widget.set_text(' + '.join(self.sorted_keys()))
        return 'break'

    def sorted_keys(self):
        return [key for key in MODIFIERS if key in self.recorded_keys] + sorted(self.recorded_keys.difference(MODIFIERS))

    def finish_key(self, event):
        if not self.is_recording():
            return
        keys = self.sorted_keys()
        nonmodifiers = set(keys).difference(('Ctrl', 'Alt', 'Shift', 'Cmd'))
        if not nonmodifiers:
            return 'break'
        keybind = '+'.join(keys)
        reserved = set('ADEFIORSW0123456789') | {'Space', 'Enter', 'Escape', 'PageUp', 'PageDown', 'F7', ',', '.', '\\', 'F5', 'F11', 'F12'}
        shortcuts = {'Ctrl+L', 'Ctrl+N', 'Ctrl+O', 'Ctrl+P', 'Ctrl+R', 'Ctrl+S', 'Ctrl+T', 'Ctrl+W', 'Ctrl+Shift+C', 'Ctrl+Shift+I', 'Ctrl+Shift+J', 'Ctrl+Shift+N', 'Ctrl+Shift+P', 'Ctrl+Shift+T', 'Cmd+H', 'Cmd+L', 'Cmd+M', 'Cmd+N', 'Cmd+O', 'Cmd+P', 'Cmd+Q', 'Cmd+R', 'Cmd+S', 'Cmd+Space', 'Cmd+T', 'Cmd+W', 'Alt+F4', 'Alt+Tab', 'Cmd+Tab'}
        conflict = next((name for name in KEYBIND_LABELS if name != self.recording and normalize_keybind(self.settings.get(name)) == keybind), None)
        error = ''
        if conflict:
            error = 'That keybind is already assigned to %s.' % KEYBIND_LABELS[conflict]
        elif nonmodifiers.intersection(reserved.difference({'F5', 'F11', 'F12'})):
            error = 'That key is used by the macro while it runs. Choose a different keybind.'
        elif nonmodifiers.intersection({'F5', 'F11', 'F12'}) or keybind in shortcuts:
            error = 'That shortcut is reserved by the browser or operating system. Choose a different keybind.'
        if error:
            self.stop_recording()
            messagebox.showerror('Keybind', error, parent=self.root)
            self.recorded_keys.clear()
            return 'break'
        self.save_keybind(self.recording, keybind)
        return 'break'

    def cancel_recording_click(self, event):
        if self.recording and event.widget is not self.controls[self.recording].widget:
            self.stop_recording()

    def save_keybind(self, identifier, keybind):
        self.stop_recording()
        self.save(identifier, keybind, 'general')
        self.controls[identifier].widget.set_text(keybind.replace('+', ' + ') or 'Click to record')
        self.refresh_home()

    def run_event_loop(self, tick, close):
        self.close_callback = close
        self.root.after(0, self.check_startup_update)
        def supervise():
            try:
                while not self.stop_supervisor.is_set():
                    interval = tick()
                    self.enqueue(self.refresh_home)
                    self.stop_supervisor.wait(interval)
            except BaseException as exc:
                self.failure = exc
                self.enqueue(self.close)
            finally:
                try:
                    close()
                except BaseException as exc:
                    self.failure = self.failure or exc
                self.enqueue(self.finish_close)

        self.supervisor_thread = threading.Thread(target=supervise, daemon=True)
        self.supervisor_thread.start()
        try:
            self.root.mainloop()
        finally:
            self.stop_supervisor.set()
            self.supervisor_thread.join()
            self.finish_close()
        if self.failure:
            raise self.failure

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.stop_recording()
        if self.supervisor_thread is not None:
            self.stop_supervisor.set()
            self.status('Stopping...')
            return
        try:
            if self.close_callback:
                self.close_callback()
        finally:
            self.finish_close()

    def finish_close(self):
        if not self.destroyed:
            self.destroyed = True
            try:
                with open(self.ui_state_path, 'w', encoding='utf-8') as output:
                    json.dump(dict(tab=self.active_tab, subtabs=self.subtab_selection), output)
            finally:
                self.root.destroy()
