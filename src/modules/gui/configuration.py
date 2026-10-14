"""Native custom configuration workflows and their button actions.

build_custom() renders the CUSTOM_DEFINITIONS widgets that need more than a
single control: profiles, task priorities, hotbar, quest overrides, model
downloads and the two cheat sheets. handle_action() runs the config actions
that are not custom widgets. Both follow config.js, boost.js, script.js and
the tab HTML, and reuse the settingsManager API through app.manager.
"""

import base64
import math
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

from .definitions import CONTROL_PRESENTATION, CUSTOM_DEFINITIONS
from .widgets import Button, Choice, Scroll, rounded_image


TITLE = "Fuzzy Macro"
STATUS_COLORS = {"success": "#43b581", "error": "#f04747"}
STATUS_SECONDS = 5
GLITTER_SLOT_IDS = ("field_booster_glitter_slot", "AFB_slotG", "tad_alt_glitter_slot")
# The web list also names this task, which CHOICES does not list.
EXTRA_TASK_NAMES = {"collect_sticker_sprout": "Collect: Sticker Sprout"}
CATEGORY_COLORS = {"gather": ("#5865f2", "#ffffff"), "collect": ("#57f287", "#121212"),
                   "kill": ("#ed4245", "#ffffff"), "quest": ("#fee75c", "#121212"),
                   "special": ("#eb459e", "#ffffff")}
LOCK_TEXT = ("Handled automatically — order doesn't matter.")
HEADERS = {"quest": "Quests", "planter": "Planters"}
GUIDE_MAX_WIDTH = {"petals_guide": 600, "sprout_guide": 755}
_GUIDE_CACHE = {}


# ---------------------------------------------------------------------------
# JavaScript value rules that the source relies on
# ---------------------------------------------------------------------------

def _truthy(value):
    if isinstance(value, (list, dict, tuple)):
        return True
    if isinstance(value, float) and math.isnan(value):
        return False
    return bool(value)


def _number(value):
    """Number(value) for the setting values the source passes to it."""
    if value is None:
        return 0.0
    if isinstance(value, (bool, int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return float("nan")


def _parse_int(value):
    """parseInt(value, 10): None when the source would give NaN."""
    match = re.match(r"\s*([+-]?\d+)", str(value))
    return int(match.group(1)) if match else None


def _mix(first, second, amount):
    """Blend two #rrggbb colors; amount is the share of the first."""
    a = [int(first[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(second[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x * amount + y * (1 - amount)) for x, y in zip(a, b))


class CustomControl(object):
    """The Control interface for widgets that hold their own state."""

    def __init__(self, widget, getter=None, setter=None):
        self.widget = widget
        self.variable = None
        self.numeric = None
        self._getter = getter
        self._setter = setter

    def get(self):
        return self._getter() if self._getter else None

    def set(self, value):
        if self._setter:
            self._setter(value)


# ---------------------------------------------------------------------------
# Shared widgets and dialogs
# ---------------------------------------------------------------------------

def _frame(app, parent):
    return tk.Frame(parent, bg=app.palette["surface"])


def _entry(app, parent, variable=None, width=28):
    palette = app.palette
    return tk.Entry(parent, textvariable=variable, width=width, bg=palette["input"], fg=palette["text"],
                    insertbackground=palette["text"], relief="flat", font=("Poppins", -14),
                    highlightthickness=1, highlightbackground=palette["border"],
                    highlightcolor=palette["accent"])


def _button(app, parent, text, command, fill=None, foreground=None):
    return Button(parent, text, command, app.palette, fill=fill, foreground=foreground)


def _secondary_button(app, parent, text, command):
    return _button(app, parent, text, command, fill="#4f545c", foreground="#ffffff")


def _status_label(app, parent):
    label = tk.Label(parent, text="", bg=app.palette["surface"], anchor="w", justify="left",
                     font=("Poppins", -13))
    label.pack(fill="x", pady=(8, 0))
    return label


def _flash(label, text, kind):
    """Show a success or error message that clears itself after five seconds."""
    if not label.winfo_exists():
        return
    previous = getattr(label, "_clear_job", None)
    if previous:
        label.after_cancel(previous)
    label.configure(text=text, fg=STATUS_COLORS[kind])
    label._clear_job = label.after(STATUS_SECONDS * 1000, lambda: label.winfo_exists() and label.configure(text=""))


def _modal(app, title):
    window = tk.Toplevel(app.root)
    window.title(title)
    window.transient(app.root)
    window.configure(bg=app.palette["surface"], padx=24, pady=20)
    window.resizable(False, False)
    window.bind("<Escape>", lambda event: window.destroy())
    return window


def _present(app, window, width):
    """Size, center over the main window and make the dialog modal."""
    window.update_idletasks()
    x = app.root.winfo_rootx() + max(0, (app.root.winfo_width() - width) // 2)
    window.geometry("{}x{}+{}+{}".format(width, window.winfo_reqheight(), x, app.root.winfo_rooty() + 120))
    window.wait_visibility()
    window.grab_set()


def _modal_label(app, window, text, width, dim=False):
    palette = app.palette
    label = tk.Label(window, text=text, bg=palette["surface"], fg=palette["dim" if dim else "text"],
                     anchor="w", justify="left", wraplength=width - 48, font=("Poppins", -14))
    label.pack(fill="x", pady=(0, 6))
    return label


def _modal_buttons(app, window, cancel_text, confirm_text, confirm):
    row = _frame(app, window)
    row.pack(fill="x", pady=(14, 0))
    _button(app, row, confirm_text, confirm).pack(side="right")
    _secondary_button(app, row, cancel_text, window.destroy).pack(side="right", padx=(0, 10))


def _run_async(app, function, done):
    """Run function off the GUI thread; done(ok, value_or_error) runs on it."""
    def work():
        try:
            return True, function()
        except Exception as error:
            return False, error

    def finished(result, error=None):
        done(*((False, error) if error is not None else result))

    app.run_async(work, finished)


def _reset_feedback(control, milliseconds=700):
    """Disable a reset button briefly, like the source's active class."""
    widget = control.widget if control else None
    if widget is None or not hasattr(widget, "set_enabled"):
        return
    widget.set_enabled(False)
    widget.after(milliseconds, lambda: widget.winfo_exists() and widget.set_enabled(True))


# ---------------------------------------------------------------------------
# Task priority order (script.js lock rules, config.js list behavior)
# ---------------------------------------------------------------------------

def is_priority_locked(task_id):
    return bool(task_id) and (str(task_id).startswith("quest_") or task_id == "planters")


def normalize_priority_grouping(order):
    """Gather every quest at the position of the first quest."""
    if not isinstance(order, (list, tuple)):
        return []
    order = list(order)
    quests = [i for i in order if str(i).startswith("quest_")]
    if not quests:
        return order
    first = next(n for n, i in enumerate(order) if str(i).startswith("quest_"))
    insert_at = len([i for i in order[:first] if not str(i).startswith("quest_")])
    rest = [i for i in order if not str(i).startswith("quest_")]
    rest[insert_at:insert_at] = quests
    return rest


def priority_lock_state(order):
    order = normalize_priority_grouping(order)
    unlocked = 0
    state = dict(order=order, quest_anchor=None, planter_anchor=None, quest_before_planter=True,
                 quest_ids=[i for i in order if str(i).startswith("quest_")],
                 has_planters="planters" in order)
    seen_quest = seen_planter = False
    for task_id in order:
        if str(task_id).startswith("quest_"):
            if state["quest_anchor"] is None:
                state["quest_anchor"] = unlocked
                if seen_planter:
                    state["quest_before_planter"] = False
            seen_quest = True
        elif task_id == "planters":
            if state["planter_anchor"] is None:
                state["planter_anchor"] = unlocked
                if not seen_quest:
                    state["quest_before_planter"] = False
            seen_planter = True
        else:
            unlocked += 1
    return state


def arrange_priority(unlocked, state, quest_block, planter_block):
    """Place the locked groups at their stored anchors among unlocked ids."""
    out = []
    quests_done = not state["quest_ids"]
    planters_done = not state["has_planters"]

    def locked_here(index):
        nonlocal quests_done, planters_done
        at_quest = not quests_done and state["quest_anchor"] == index
        at_planter = not planters_done and state["planter_anchor"] == index
        groups = []
        if at_quest:
            groups.append(("quest", quest_block))
        if at_planter:
            groups.append(("planter", planter_block))
        if at_quest and at_planter and not state["quest_before_planter"]:
            groups.reverse()
        for name, block in groups:
            out.extend(block)
            if name == "quest":
                quests_done = True
            else:
                planters_done = True

    for index, task_id in enumerate(unlocked):
        locked_here(index)
        out.append(task_id)
    locked_here(len(unlocked))
    if not quests_done:
        out.extend(quest_block)
    if not planters_done:
        out.extend(planter_block)
    return out


def merge_priority_order(unlocked, state):
    return arrange_priority(unlocked, state, list(state["quest_ids"]), ["planters"])


def task_category(task_id):
    for prefix in ("gather", "collect", "kill", "quest"):
        if task_id.startswith(prefix + "_"):
            return prefix
    return "special"


def task_enabled(task_id, settings):
    """window._isTaskEnabledForSettings from script.js."""
    get = settings.get
    if task_id.startswith("gather_"):
        field = task_id.replace("gather_", "", 1).replace("_", " ", 1)
        enabled, fields = get("fields_enabled"), get("fields")
        if isinstance(enabled, (list, tuple)) and isinstance(fields, (list, tuple)):
            return any(_truthy(on) and n < len(fields) and fields[n] == field
                       for n, on in enumerate(enabled))
        return False
    if task_id.startswith("collect_"):
        name = task_id.replace("collect_", "", 1)
        key = {"sprouts": "sprouts_enable", "sticker_sprout": "sticker_sprout_watch"}.get(name, name)
        return _truthy(get(key))
    if task_id.startswith("kill_"):
        return _truthy(get(task_id.replace("kill_", "", 1)))
    if task_id.startswith("quest_"):
        return _truthy(get(task_id.replace("quest_", "", 1) + "_quest"))
    if task_id == "blender":
        return _truthy(get("blender_enable")) or _truthy(get("blender"))
    if task_id == "planters":
        mode = _number(get("planters_mode"))
        return _truthy(get("planters")) or (math.isfinite(mode) and mode > 0)
    return task_id in ("mondo_buff", "stinger_hunt", "auto_field_boost", "ant_challenge") and _truthy(get(task_id))


class PriorityList(object):
    """Drag-ordered task list with search, Top/Bottom buttons and locked groups."""

    def __init__(self, app, parent, spec, definition):
        self.app = app
        self.key = spec["id"]
        self.definition = definition
        self.names = {c["value"]: c["label"] for c in definition["choices"]}
        self.names.update(EXTRA_TASK_NAMES)
        self.unlocked = []
        self.state = priority_lock_state([])
        self.rows = {}
        self.headers = {}
        self.drag = None
        self.scroll_job = None
        palette = self.palette = app.palette
        self.frame = _frame(app, parent)
        self.frame.pack(fill="x")
        top = _frame(app, self.frame)
        top.pack(fill="x", pady=(0, 10))
        self.search = tk.StringVar(self.frame)
        self.placeholder = definition["search_placeholder"]
        self.showing_placeholder = False
        self.entry = _entry(app, top, self.search, width=40)
        self.entry.pack(side="left", ipady=4)
        self.entry.bind("<FocusIn>", self._hide_placeholder)
        self.entry.bind("<FocusOut>", self._show_placeholder)
        app.button(top, definition["reset_text"], self.reset).pack(side="left", padx=(12, 0))
        self.list = tk.Frame(self.frame, bg=palette["surface"], highlightthickness=1,
                             highlightbackground=palette["border"])
        self.list.pack(fill="x")
        self._show_placeholder()
        self.search.trace_add("write", lambda *args: self._layout())
        self.frame.bind("<Map>", lambda event: self.refresh_highlights())
        self.set(app.settings.get(self.key))

    # search box with placeholder text -----------------------------------
    def _hide_placeholder(self, event=None):
        if self.showing_placeholder:
            self.showing_placeholder = False
            self.entry.delete(0, "end")
            self.entry.configure(fg=self.palette["text"])

    def _show_placeholder(self, event=None):
        if not self.entry.get():
            self.showing_placeholder = True
            self.entry.configure(fg=self.palette["dim"])
            self.entry.insert(0, self.placeholder)

    def query(self):
        return "" if self.showing_placeholder else self.search.get().lower().strip()

    # state -----------------------------------------------------------------
    def get(self):
        return merge_priority_order(self.unlocked, self.state)

    def set(self, order):
        if not isinstance(order, (list, tuple)):
            return
        self.state = priority_lock_state(order)
        self.unlocked = [i for i in self.state["order"] if not is_priority_locked(i)]
        for child in self.list.winfo_children():
            child.destroy()
        self.rows = {task_id: self._make_row(task_id) for task_id in self.unlocked}
        self.headers = {}
        if self.state["quest_ids"]:
            self.headers["quest"] = self._make_header("quest")
        if self.state["has_planters"]:
            self.headers["planter"] = self._make_header("planter")
        # Loading an order clears the search, like loadDragListOrder.
        self.showing_placeholder = False
        self.entry.delete(0, "end")
        self.entry.configure(fg=self.palette["text"])
        self._show_placeholder()
        self._layout()

    def _save(self):
        order = self.get()
        try:
            self.app.manager.saveDictProfileSettings({self.key: order})
            self.app.settings[self.key] = list(order)
        except Exception as error:
            self.app.status("Could not save task priority order: {}".format(error))

    # rows --------------------------------------------------------------------
    def _make_header(self, group):
        palette = self.palette
        accent = _mix(palette["accent"], palette["surface"], .3)
        frame = tk.Frame(self.list, bg=_mix(palette["accent"], palette["surface"], .06),
                         highlightthickness=1, highlightbackground=accent)
        badge = tk.Label(frame, text="LOCKED", font=("Poppins", -11, "bold"), fg=palette["text"],
                         bg=_mix(palette["accent"], palette["surface"], .18), padx=6, pady=1)
        badge.pack(side="left", anchor="n", padx=(10, 10), pady=10)
        copy = tk.Frame(frame, bg=frame.cget("bg"))
        copy.pack(side="left", fill="x", pady=8)
        tk.Label(copy, text=HEADERS[group], font=("Poppins", -14, "bold"), fg=palette["text"],
                 bg=frame.cget("bg"), anchor="w").pack(fill="x")
        tk.Label(copy, text=LOCK_TEXT, font=("Poppins", -13), fg=palette["dim"], bg=frame.cget("bg"),
                 anchor="w").pack(fill="x")
        frame.search_text = "locked\n{}\n{}".format(HEADERS[group], LOCK_TEXT).lower()
        return frame

    def _make_row(self, task_id):
        palette = self.palette
        name = self.names.get(task_id, task_id)
        category = task_category(task_id)
        row = tk.Frame(self.list, highlightthickness=1, highlightbackground=palette["border"])
        handle = tk.Label(row, text="⋮⋮", font=("Poppins", -14), cursor="fleur")
        handle.pack(side="left", padx=(12, 12), pady=10)
        badge_bg, badge_fg = CATEGORY_COLORS[category]
        badge = tk.Label(row, text=self.definition["category_badges"][category], bg=badge_bg, fg=badge_fg,
                         font=("Poppins", -11, "bold"), padx=6, pady=2)
        badge.pack(side="left", padx=(0, 8))
        label = tk.Label(row, text=name, font=("Poppins", -14), anchor="w")
        label.pack(side="left")
        actions = tk.Frame(row)
        actions.pack(side="right", padx=(0, 10))
        for text, command in ((self.definition["move_to_top_text"], lambda: self.move(task_id, 0)),
                              (self.definition["move_to_bottom_text"], lambda: self.move(task_id, None))):
            button = tk.Label(actions, text=text, bg=palette["accent"], fg=palette["bg"], padx=8, pady=3,
                              font=("Poppins", -12, "bold"), cursor="hand2")
            button.pack(side="left", padx=(8, 0))
            button.bind("<ButtonRelease-1>", lambda event, command=command: command())
            button.bind("<Enter>", lambda event, b=button: b.configure(bg=palette["accent_hover"]))
            button.bind("<Leave>", lambda event, b=button: b.configure(bg=palette["accent"]))
        row.parts = (row, handle, label, actions)
        row.search_text = name.lower()
        for widget in (row, handle, badge, label):
            widget.bind("<ButtonPress-1>", lambda event, i=task_id: self._press(i))
            widget.bind("<B1-Motion>", self._motion)
            widget.bind("<ButtonRelease-1>", self._release)
            widget.bind("<Enter>", lambda event, i=task_id: self._style(i))
            widget.bind("<Leave>", lambda event, i=task_id: self._style(i))
        self._style(task_id, row=row)
        return row

    def _style(self, task_id, row=None):
        """Enabled tasks are normal; disabled ones are dimmed. Hover/drag add the accent border."""
        row = row or self.rows.get(task_id)
        if row is None or not row.winfo_exists():
            return
        palette = self.palette
        enabled = task_enabled(task_id, self.app.settings)
        x, y = row.winfo_pointerxy()
        hot = (self.drag and self.drag["id"] == task_id) or (
            row.winfo_rootx() <= x < row.winfo_rootx() + row.winfo_width()
            and row.winfo_rooty() <= y < row.winfo_rooty() + row.winfo_height())
        background = palette["hover"] if hot and enabled else ("#262626" if enabled else palette["dim_surface"])
        for widget in row.parts:
            widget.configure(bg=background)
        row.parts[1].configure(fg=palette["dim"])
        row.parts[2].configure(fg=palette["text"] if enabled else palette["dim"])
        row.configure(highlightbackground=palette["accent"] if hot else palette["border"])

    def refresh_highlights(self):
        for task_id in self.rows:
            self._style(task_id)

    # layout and search -------------------------------------------------------
    def _visible(self, widget):
        query = self.query()
        return not query or query in widget.search_text

    def _layout(self):
        seq = arrange_priority(self.unlocked, self.state, ["quest"] if self.state["quest_ids"] else [],
                               ["planter"] if self.state["has_planters"] else [])
        widgets = [(self.headers if i in self.headers else self.rows)[i] for i in seq]
        shown = [w for w in widgets if self._visible(w)]
        for widget in list(self.rows.values()) + list(self.headers.values()):
            if widget not in shown:
                widget.pack_forget()
        previous = None
        for widget in shown:
            if widget.winfo_manager() != "pack":
                widget.pack(fill="x", padx=8, pady=(12, 4) if widget in self.headers.values() else 4)
            if previous is None:
                first = self.list.pack_slaves()[0]
                if first is not widget:
                    widget.pack_configure(before=first)
            else:
                widget.pack_configure(after=previous)
            previous = widget

    # ordering ------------------------------------------------------------------
    def move(self, task_id, index):
        """Top/Bottom button: index 0 is the top, None the bottom."""
        order = [i for i in self.unlocked if i != task_id]
        order.insert(len(order) if index is None else index, task_id)
        self.unlocked = order
        self._layout()
        self._save()

    def _press(self, task_id):
        self.drag = {"id": task_id, "moved": False, "y": 0}

    def _motion(self, event):
        if not self.drag:
            return
        self.drag.update(moved=True, y=event.y_root)
        self._style(self.drag["id"])
        self._reorder()
        self._autoscroll()

    def _release(self, event):
        drag, self.drag = self.drag, None
        if self.scroll_job:
            self.frame.after_cancel(self.scroll_job)
            self.scroll_job = None
        if drag:
            self._style(drag["id"])
            if drag["moved"]:
                self._save()

    def _reorder(self):
        """Drop before the first visible row whose middle is below the pointer."""
        dragged, y = self.drag["id"], self.drag["y"]
        order = [i for i in self.unlocked if i != dragged]
        target = None
        for task_id in order:
            row = self.rows[task_id]
            if self._visible(row) and y < row.winfo_rooty() + row.winfo_height() / 2:
                target = task_id
                break
        order.insert(order.index(target) if target else len(order), dragged)
        if order != self.unlocked:
            self.unlocked = order
            self._layout()
            self.list.update_idletasks()

    def _scroller(self):
        widget = self.frame
        while widget is not None and not hasattr(widget, "yview_scroll"):
            widget = widget.master
        return widget

    def _autoscroll(self):
        """Scroll the page while a row is held near its top or bottom edge."""
        canvas = self._scroller()
        if not self.drag or canvas is None or self.scroll_job:
            return
        top = canvas.winfo_rooty()
        y = self.drag["y"]
        if y < top + 40:
            canvas.yview_scroll(-1, "units")
        elif y > top + canvas.winfo_height() - 40:
            canvas.yview_scroll(1, "units")
        else:
            return

        def tick():
            self.scroll_job = None
            if self.drag:
                self._reorder()
                self._autoscroll()
        self.scroll_job = self.frame.after(60, tick)

    # reset -----------------------------------------------------------------------
    def reset(self):
        app = self.app
        if not messagebox.askyesno(TITLE, "Are you sure you want to reset task priorities to default "
                                   "values? This action cannot be undone.", parent=app.root):
            return
        try:
            done = app.action("resetTaskPrioritiesToDefault")
        except Exception:
            messagebox.showerror(TITLE, "An error occurred while resetting task priorities.", parent=app.root)
            return
        if not done:
            messagebox.showerror(TITLE, "Failed to reset task priorities. Default order may be missing.",
                                 parent=app.root)
            return
        app.settings.update(app.manager.loadAllSettings())
        if self.frame.winfo_exists():
            self.set(app.settings.get(self.key))
        app.refresh()
        messagebox.showinfo(TITLE, "Successfully reset task priorities to defaults.", parent=app.root)


def _build_task_priorities(app, parent, spec):
    view = PriorityList(app, parent, spec, CUSTOM_DEFINITIONS["task_priorities"])
    return CustomControl(view.frame, view.get, view.set)


# ---------------------------------------------------------------------------
# Hotbar and quest overrides
# ---------------------------------------------------------------------------

def _blank(control):
    """The same control inside a compact row, whose heading is drawn by the row."""
    return dict(control, title="", desc="")


def _build_hotbar(app, parent, spec):
    definition = CUSTOM_DEFINITIONS["hotbar"]
    palette = app.palette
    shell = _frame(app, parent)
    shell.pack(fill="x")
    strip = _frame(app, shell)
    strip.pack(anchor="w", pady=(4, 24))
    holder = _frame(app, shell)
    holder.pack(fill="x")
    slots = []
    state = {"current": None}

    def draw(index):
        number, canvas, selected = slots[index]
        number.configure(fg=palette["accent"] if selected() else palette["dim"])
        canvas.delete("all")
        canvas.image = rounded_image(64, 64, "#262626", 16, palette["accent"] if selected() else "#3a3a3a")
        canvas.create_image(0, 0, image=canvas.image, anchor="nw")
        canvas.create_rectangle(16, 16, 48, 48, outline="#5a5a5a", dash=(3, 3), width=2)
        canvas.create_line(26, 32, 38, 32, fill="#5a5a5a", width=2)
        canvas.create_line(32, 26, 32, 38, fill="#5a5a5a", width=2)

    def show(index):
        if state["current"] is not None:
            panels[state["current"]].pack_forget()
        state["current"] = index
        panels[index].pack(fill="x")
        for n in range(len(slots)):
            draw(n)

    panels = []
    for index, section in enumerate(definition["sections"]):
        column = _frame(app, strip)
        column.pack(side="left", padx=(0, 12))
        number = tk.Label(column, text=definition["slot_labels"][index], bg=palette["surface"],
                          font=("Poppins", -13, "bold"))
        number.pack()
        canvas = tk.Canvas(column, width=64, height=64, bg=palette["surface"], highlightthickness=0,
                           bd=0, cursor="hand2")
        canvas.pack(pady=(3, 0))
        slots.append((number, canvas, lambda n=index: state["current"] == n))
        canvas.bind("<ButtonRelease-1>", lambda event, n=index: show(n))

        panel = tk.Frame(holder, bg=palette["surface"], highlightthickness=1,
                         highlightbackground=palette["border"], padx=20, pady=19)
        head = _frame(app, panel)
        head.pack(fill="x", pady=(0, 16))
        icon = tk.Canvas(head, width=52, height=52, bg=palette["surface"], highlightthickness=0, bd=0)
        icon.image = rounded_image(52, 52, "#1f1f1f", 14, "#3a3a3a")
        icon.create_image(0, 0, image=icon.image, anchor="nw")
        icon.create_rectangle(10, 10, 42, 42, outline="#5a5a5a", dash=(3, 3), width=2)
        icon.pack(side="left", padx=(0, 16))
        copy = _frame(app, head)
        copy.pack(side="left")
        tk.Label(copy, text=section["title"], bg=palette["surface"], fg=palette["text"],
                 font=("Poppins", -18, "bold"), anchor="w").pack(fill="x")
        tk.Label(copy, text=section["desc"], bg=palette["surface"], fg=palette["dim"],
                 font=("Poppins", -14), anchor="w").pack(fill="x")
        when, value, unit = section["controls"]
        app.add_control(panel, when)
        row = _frame(app, panel)
        row.pack(fill="x", pady=(16, 0))
        text = _frame(app, row)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=value["title"], bg=palette["surface"], fg=palette["text"],
                 font=("Poppins", -14), anchor="w").pack(fill="x")
        tk.Label(text, text=value["desc"], bg=palette["surface"], fg=palette["dim"],
                 font=("Poppins", -13), anchor="w").pack(fill="x")
        for control in (value, unit):
            cell = _frame(app, row)
            cell.pack(side="left", padx=(0, 8))
            app.add_control(cell, _blank(control))
        panels.append(panel)
    show(0)
    return CustomControl(shell, lambda: state["current"] + 1, lambda value: None)


def _build_quest_overrides(app, parent, spec):
    definition = CUSTOM_DEFINITIONS["quest_overrides"]
    palette = app.palette
    table = _frame(app, parent)
    table.pack(fill="x")
    for column, weight in enumerate((4, 3, 3)):
        table.grid_columnconfigure(column, weight=weight, uniform="quest")
    for column, title in enumerate(definition["columns"]):
        tk.Label(table, text=title, bg=palette["surface"], fg=palette["dim"], anchor="w",
                 font=("Poppins", -14, "bold")).grid(row=0, column=column, sticky="w", pady=(0, 6))
    for number, row in enumerate(definition["rows"], 1):
        tk.Label(table, text=row["title"], bg=palette["surface"], fg=palette["text"], anchor="w",
                 font=("Poppins", -14)).grid(row=number, column=0, sticky="w", pady=4)
        for column, control in enumerate(row["controls"], 1):
            cell = _frame(app, table)
            cell.grid(row=number, column=column, sticky="w", pady=4)
            app.add_control(cell, _blank(control))
    return CustomControl(table)


# ---------------------------------------------------------------------------
# Cheat sheets
# ---------------------------------------------------------------------------

def _guide_image(path):
    if path not in _GUIDE_CACHE:
        image = Image.open(path).convert("RGBA")
        image.thumbnail((1400, 1400), getattr(Image, "Resampling", Image).LANCZOS)
        _GUIDE_CACHE[path] = image
    return _GUIDE_CACHE[path]


def _build_guide(app, parent, spec):
    definition = CUSTOM_DEFINITIONS[spec["action"]]
    path = os.path.normpath(os.path.join(os.path.dirname(__file__), definition["image"]))
    label = tk.Label(parent, bg=app.palette["surface"], cursor="hand2", text=definition["alt"],
                     fg=app.palette["dim"], font=("Poppins", -14))
    label.pack(pady=(8, 0))
    shown = {"width": 0}

    def render(event=None):
        width = min(GUIDE_MAX_WIDTH[spec["action"]], max(200, label.master.winfo_width() - 8))
        if width == shown["width"]:
            return
        shown["width"] = width
        source = _guide_image(path)
        height = max(1, round(source.height * width / source.width))
        resample = getattr(Image, "Resampling", Image).LANCZOS
        label.image = ImageTk.PhotoImage(source.resize((width, height), resample))
        label.configure(image=label.image, text="")

    label.master.bind("<Map>", render)
    label.master.bind("<Configure>", render)
    label.bind("<ButtonRelease-1>", lambda event: app.open_image(path))
    return CustomControl(label)


# ---------------------------------------------------------------------------
# AI model downloads
# ---------------------------------------------------------------------------

MODEL_COLORS = {"installed": "#77c66e", "missing": "#e0a85e", "error": "#e06c75"}


def _format_model_size(size_bytes):
    return "" if not size_bytes else "{:.1f} MB".format(size_bytes / (1024 * 1024))


def model_groups(models, definition):
    """Group backend model dicts like loadModelStatus(); unknown names go in Other."""
    grouped = {}
    for model in models:
        presentation = definition["models"].get(model["name"], {"group": "Other", "label": "AI Model"})
        grouped.setdefault(presentation["group"], []).append((model, presentation["label"]))
    order = list(definition["groups"]) + [g for g in grouped if g not in definition["groups"]]
    return [(group, grouped[group]) for group in order if grouped.get(group)]


def _build_model_downloads(app, parent, spec):
    definition = CUSTOM_DEFINITIONS["model_downloads"]
    palette = app.palette
    # This custom section owns its card's heading and description so only the
    # summary remains visible while collapsed, like the source <details>.
    for child in parent.pack_slaves():
        child.pack_forget()
    body = _frame(app, parent)
    body.pack(fill="x")
    header = tk.Frame(body, bg=palette["surface"], cursor="hand2", takefocus=True)
    header.pack(fill="x")
    title = tk.Label(header, text="AI Models", bg=palette["surface"], fg=palette["text"],
                     font=("Poppins", -18, "bold"), cursor="hand2")
    title.pack(side="left")
    arrow = tk.Label(header, text="⌄", bg=palette["surface"], fg=palette["dim"],
                     font=("Poppins", -22), cursor="hand2")
    arrow.pack(side="right", padx=(12, 0))
    summary = tk.Label(header, text="Checking…", bg=palette["surface"], fg=palette["dim"],
                       font=("Poppins", -13), cursor="hand2")
    summary.pack(side="right")
    content = _frame(app, body)

    def toggle(event=None):
        if content.winfo_manager():
            content.pack_forget()
            arrow.configure(text="⌄")
        else:
            content.pack(fill="x", pady=(12, 0))
            arrow.configure(text="⌃")
        return "break"

    for widget in (header, title, summary, arrow):
        widget.bind("<ButtonRelease-1>", toggle)
    header.bind("<space>", toggle)
    header.bind("<Return>", toggle)
    tk.Frame(content, bg=palette["border"], height=1).pack(fill="x", pady=(0, 8))
    description = tk.Label(content, text="Download only the AI models that are missing from this Mac.",
                           bg=palette["surface"], fg=palette["dim"], anchor="w", justify="left",
                           font=("Poppins", -14))
    description.pack(fill="x", pady=(0, 8))
    description.bind("<Configure>", lambda event: description.configure(wraplength=max(1, event.width)))
    buttons = []
    download_all = _button(app, content, definition["download_missing_text"], lambda: download(None))
    download_all.pack(anchor="w", pady=(0, 8))
    status = tk.Label(content, text="Checking installed models…", bg=palette["surface"], fg=palette["dim"],
                      anchor="w", font=("Poppins", -13))
    status.pack(fill="x", pady=(0, 8))
    listing = _frame(app, content)
    listing.pack(fill="x")

    def say(text, error=False):
        if status.winfo_exists():
            status.configure(text=text, fg=MODEL_COLORS["error"] if error else palette["dim"])

    def lock(locked):
        for button in [download_all] + buttons:
            if button.winfo_exists():
                button.set_enabled(not locked)

    def render(models):
        buttons[:] = []
        for child in listing.winfo_children():
            child.destroy()
        for group, items in model_groups(models, definition):
            tk.Label(listing, text="{} Models".format(group), bg=palette["surface"], fg=palette["text"],
                     font=("Poppins", -14, "bold"), anchor="w").pack(fill="x", pady=(10, 4))
            for model, label in items:
                row = tk.Frame(listing, bg=palette["surface"], highlightthickness=1,
                               highlightbackground=palette["border"])
                row.pack(fill="x", pady=2)
                copy = _frame(app, row)
                copy.pack(side="left", padx=12, pady=8)
                tk.Label(copy, text=label, bg=palette["surface"], fg=palette["text"],
                         font=("Poppins", -14, "bold"), anchor="w").pack(fill="x")
                if model["installed"]:
                    size = _format_model_size(model.get("size_bytes"))
                    text = "Installed" + (" · " + size if size else "")
                else:
                    text = "Missing"
                tk.Label(copy, text=text, bg=palette["surface"], anchor="w", font=("Poppins", -13),
                         fg=MODEL_COLORS["installed" if model["installed"] else "missing"]).pack(fill="x")
                if not model["installed"]:
                    button = _button(app, row, definition["download_text"],
                                     lambda name=model["name"]: download([name]))
                    button.pack(side="right", padx=12, pady=6)
                    buttons.append(button)

    def load():
        _run_async(app, lambda: app.actions.getModelStatus(), loaded)

    def loaded(ok, result):
        if not body.winfo_exists():
            return
        if not ok:
            say("Could not check installed models.", True)
            summary.configure(text="Unavailable")
            lock(False)
            return
        models = result.get("models", [])
        missing = len([m for m in models if not m["installed"]])
        say("{} model{} missing.".format(missing, "" if missing == 1 else "s") if missing
            else "All supported models are installed.")
        summary.configure(text="{} missing".format(missing) if missing else "All installed")
        render(models)
        lock(False)

    def download(names):
        lock(True)
        say("Downloading models… This can take a few minutes.")
        _run_async(app, lambda: app.actions.downloadMissingModels(names), downloaded)

    def downloaded(ok, result):
        if not body.winfo_exists():
            return
        if not ok:
            say("Could not download models: {}".format(result), True)
            lock(False)
        elif not result.get("ok"):
            say("Some models could not be downloaded. Check your internet connection and try again."
                if result.get("failures") else (result.get("message") or "Could not download models."), True)
            lock(False)
        else:
            say(result.get("message") or "Model download complete.")
            load()

    load()
    return CustomControl(body, setter=lambda value: load())


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def _views(app):
    return app.__dict__.setdefault("profile_views", [])


def _register(app, widget, reload):
    """Reload this profile section on show and whenever any profile changes."""
    _views(app).append((widget, reload))
    widget.bind("<Map>", lambda event: reload())


def _reload_profiles(app):
    live = [(w, r) for w, r in _views(app) if w.winfo_exists()]
    _views(app)[:] = live
    for widget, reload in live:
        reload()


def _profile_names(app):
    return list(app.manager.listProfiles()), app.manager.getCurrentProfile()


def _build_current_profile(app, parent, spec):
    palette = app.palette
    label = tk.Label(parent, bg=palette["surface"], fg=palette["accent"], anchor="w",
                     font=("Poppins", -20, "bold"))
    label.pack(fill="x")

    def reload():
        label.configure(text=app.manager.getCurrentProfile())
    reload()
    _register(app, label, reload)
    return CustomControl(label, lambda: app.manager.getCurrentProfile(), lambda value: reload())


def _build_switch_profile(app, parent, spec):
    definition = CUSTOM_DEFINITIONS["switch_profile"]
    palette = app.palette
    body = _frame(app, parent)
    body.pack(fill="x")
    scroller = Scroll(body, dict(palette, bg=palette["surface"]))
    scroller.pack(fill="x")
    scroller.canvas.configure(height=1, yscrollcommand=scroller.set_scroll)
    listing = scroller.body
    listing.bind("<Configure>", lambda event: scroller.canvas.configure(height=min(400, event.height)), add="+")
    status = _status_label(app, body)

    def switch(name):
        try:
            ok, message = app.manager.switchProfile(name)
        except Exception as error:
            _flash(status, "Error: {}".format(error), "error")
            return
        _flash(status, message, "success" if ok else "error")
        if ok:
            app.refresh()
            _reload_profiles(app)
            app.status(message)

    def delete(name):
        if not messagebox.askyesno(TITLE, 'Are you sure you want to delete the profile "{}"? '
                                   "This action cannot be undone.".format(name), parent=app.root):
            return
        try:
            ok, message = app.manager.deleteProfile(name)
        except Exception as error:
            _flash(status, "Error: {}".format(error), "error")
            return
        _flash(status, message, "success" if ok else "error")
        if ok:
            _reload_profiles(app)

    def reload():
        for child in listing.winfo_children():
            child.destroy()
        profiles, current = _profile_names(app)
        for name in profiles:
            active = name == current
            row = tk.Frame(listing, bg=_mix(palette["accent"], palette["surface"], .1) if active
                           else palette["hover"], highlightthickness=1,
                           highlightbackground=palette["accent"] if active else palette["hover"])
            row.pack(fill="x", pady=3)
            left = tk.Frame(row, bg=row.cget("bg"))
            left.pack(side="left", padx=14, pady=10)
            tk.Label(left, text=name, bg=row.cget("bg"), fg=palette["text"], font=("Poppins", -14)).pack(side="left")
            if active:
                tk.Label(left, text=definition["active_text"], bg=palette["accent"], fg=palette["bg"],
                         font=("Poppins", -11, "bold"), padx=5, pady=1).pack(side="left", padx=(8, 0))
                continue
            actions = tk.Frame(row, bg=row.cget("bg"))
            actions.pack(side="right", padx=10, pady=4)
            if len(profiles) > 1:
                _secondary_button(app, actions, definition["delete_text"],
                                  lambda n=name: delete(n)).pack(side="right", padx=(8, 0))
            _button(app, actions, definition["switch_text"], lambda n=name: switch(n)).pack(side="right")
    reload()
    _register(app, body, reload)
    return CustomControl(body, setter=lambda value: reload())


def _name_row(app, parent, definition, placeholder_key="placeholder"):
    """An entry with placeholder text, like the profile name inputs."""
    palette = app.palette
    entry = _entry(app, parent, width=26)
    placeholder = definition[placeholder_key]

    def show_placeholder(event=None):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.configure(fg=palette["dim"])

    def hide_placeholder(event=None):
        if entry.cget("fg") == palette["dim"]:
            entry.delete(0, "end")
            entry.configure(fg=palette["text"])

    def value():
        return "" if entry.cget("fg") == palette["dim"] else entry.get().strip()

    def clear():
        entry.delete(0, "end")
        entry.configure(fg=palette["text"])
        if entry.focus_get() is not entry:
            show_placeholder()
    entry.bind("<FocusIn>", hide_placeholder)
    entry.bind("<FocusOut>", show_placeholder)
    show_placeholder()
    return entry, value, clear


def _profile_choice(app, parent, command=lambda: None, width=180):
    profiles, current = _profile_names(app)
    choice = Choice(parent, [dict(label=n, value=n) for n in profiles], current, command, app.palette,
                    width=width)

    def reload():
        names, active = _profile_names(app)
        choice.set_choices([dict(label=n, value=n) for n in names])
        choice.set(active)
    return choice, reload


def create_profile(app, name):
    """Create from the typed name; returns (ok, message) like the source."""
    name = name.strip()
    if not name:
        return False, "Please enter a profile name"
    return app.manager.createProfile(name)


def duplicate_profile(app, source, name):
    name = name.strip()
    if not name:
        return False, "Please enter a new profile name"
    return app.manager.duplicateProfile(source, name)


def export_profile(app, name, path_for):
    """Write the manager's export (private values already blanked) to a chosen file.

    path_for(filename) returns the destination or an empty value if cancelled;
    returns (ok, message), or None when the user cancelled.
    """
    if not name:
        return False, "Please select a profile to export"
    result = app.manager.exportProfile(name)
    if not result[0]:
        return False, result[1]
    path = path_for(result[2])
    if not path:
        return None
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(result[1])
    return True, "Profile exported as {}".format(os.path.basename(path))


def import_profile(app, path, name):
    name = name.strip()
    if not name:
        return False, "Please enter a profile name"
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read()
    return app.manager.importProfileContent(content, name)


def _build_create_profile(app, parent, spec):
    definition = CUSTOM_DEFINITIONS["create_profile"]
    body = _frame(app, parent)
    body.pack(fill="x")
    row = _frame(app, body)
    row.pack(fill="x")
    entry, value, clear = _name_row(app, row, definition)
    entry.pack(side="left", ipady=5)
    status = _status_label(app, body)

    def create():
        try:
            ok, message = create_profile(app, value())
        except Exception as error:
            _flash(status, "Error: {}".format(error), "error")
            return
        _flash(status, message, "success" if ok else "error")
        if ok:
            clear()
            _reload_profiles(app)
    _button(app, row, definition["button_text"], create).pack(side="left", padx=(12, 0))
    entry.bind("<Return>", lambda event: create())
    return CustomControl(body)


def _build_duplicate_profile(app, parent, spec):
    definition = CUSTOM_DEFINITIONS["duplicate_profile"]
    palette = app.palette
    body = _frame(app, parent)
    body.pack(fill="x")
    row = _frame(app, body)
    row.pack(fill="x")
    source, reload = _profile_choice(app, row, width=150)
    source.pack(side="left")
    tk.Label(row, text="→", bg=palette["surface"], fg=palette["dim"]).pack(side="left", padx=10)
    entry, value, clear = _name_row(app, row, definition)
    entry.pack(side="left", ipady=5)
    status = _status_label(app, body)

    def duplicate():
        try:
            ok, message = duplicate_profile(app, source.get(), value())
        except Exception as error:
            _flash(status, "Error: {}".format(error), "error")
            return
        _flash(status, message, "success" if ok else "error")
        if ok:
            clear()
            _reload_profiles(app)
    _button(app, row, definition["button_text"], duplicate).pack(side="left", padx=(12, 0))
    entry.bind("<Return>", lambda event: duplicate())
    _register(app, body, reload)
    return CustomControl(body, source.get, source.set)


def _build_export_profile(app, parent, spec):
    definition = CUSTOM_DEFINITIONS["export_profile"]
    body = _frame(app, parent)
    body.pack(fill="x")
    row = _frame(app, body)
    row.pack(fill="x")
    choice, reload = _profile_choice(app, row, width=200)
    choice.pack(side="left")
    status = _status_label(app, body)

    def ask(filename):
        return filedialog.asksaveasfilename(parent=app.root, title=definition["button_text"],
                                            initialfile=filename, defaultextension=".json",
                                            filetypes=[("JSON", "*.json")])

    def export():
        try:
            result = export_profile(app, choice.get(), ask)
        except Exception as error:
            _flash(status, "Error: {}".format(error), "error")
            return
        if result is not None:
            _flash(status, result[1], "success" if result[0] else "error")
    _button(app, row, definition["button_text"], export).pack(side="left", padx=(12, 0))
    _register(app, body, reload)
    return CustomControl(body, choice.get, choice.set)


def _import_dialog(app, definition, path, status):
    width = 440
    window = _modal(app, definition["title"])
    palette = app.palette
    tk.Label(window, text=definition["title"], bg=palette["surface"], fg=palette["text"],
             font=("Poppins", -18, "bold"), anchor="w").pack(fill="x", pady=(0, 12))
    _modal_label(app, window, "{} {}".format(definition["file_label"], os.path.basename(path)), width, dim=True)
    _modal_label(app, window, definition["input_label"], width, dim=True)
    entry = _entry(app, window, width=40)
    entry.insert(0, definition["default_name"])
    entry.pack(fill="x", ipady=5)

    def confirm():
        if not entry.get().strip():
            messagebox.showwarning(TITLE, "Please enter a profile name", parent=window)
            entry.focus_set()
            return
        try:
            ok, message = import_profile(app, path, entry.get())
        except Exception as error:
            _flash(status, "Error: {}".format(error), "error")
            return
        _flash(status, message, "success" if ok else "error")
        if ok:
            window.destroy()
            _reload_profiles(app)
    entry.bind("<Return>", lambda event: confirm())
    _modal_buttons(app, window, definition["cancel_text"], definition["save_text"], confirm)
    _present(app, window, width)
    entry.focus_set()
    entry.select_range(0, "end")


def _build_import_profile(app, parent, spec):
    definition = CUSTOM_DEFINITIONS["import_profile"]
    palette = app.palette
    body = _frame(app, parent)
    body.pack(fill="x")
    row = _frame(app, body)
    row.pack(fill="x")
    status = _status_label(app, body)

    def choose():
        path = filedialog.askopenfilename(parent=app.root, title=definition["title"],
                                          filetypes=[("JSON", "*.json")])
        if path:
            _import_dialog(app, definition, path, status)
    _secondary_button(app, row, definition["button_text"], choose).pack(side="left")
    tk.Label(row, text=definition["empty_file_text"], bg=palette["surface"], fg=palette["dim"],
             font=("Poppins", -13)).pack(side="left", padx=12)
    return CustomControl(body)


_BUILDERS = {
    "current_profile": _build_current_profile,
    "switch_profile": _build_switch_profile,
    "create_profile": _build_create_profile,
    "duplicate_profile": _build_duplicate_profile,
    "export_profile": _build_export_profile,
    "import_profile": _build_import_profile,
    "model_downloads": _build_model_downloads,
    "task_priorities": _build_task_priorities,
    "hotbar": _build_hotbar,
    "quest_overrides": _build_quest_overrides,
    "petals_guide": _build_guide,
    "sprout_guide": _build_guide,
}


def build_custom(app, parent, spec):
    """Render a kind='custom' spec into parent; returns a Control-like object.

    The widget packs itself into parent. Its get()/set() carry the stored
    value for task_priority_order and nothing for the other workflows.
    """
    builder = _BUILDERS.get(spec.get("action"))
    if builder is None:
        raise ValueError("No custom configuration widget for action {!r}".format(spec.get("action")))
    return builder(app, parent, spec)


# ---------------------------------------------------------------------------
# Button and save actions
# ---------------------------------------------------------------------------

def _fallback_private_servers(app, spec, control):
    definition = CUSTOM_DEFINITIONS["fallback_private_servers"]
    width = 640
    window = _modal(app, definition["title"])
    palette = app.palette
    tk.Label(window, text=definition["title"], bg=palette["surface"], fg=palette["text"],
             font=("Poppins", -18, "bold"), anchor="w").pack(fill="x", pady=(0, 8))
    _modal_label(app, window, definition["desc"], width, dim=True)
    settings = app.manager.loadAllSettings()
    entries = []
    for field in definition["controls"]:
        _modal_label(app, window, field["title"], width)
        entry = _entry(app, window, width=60)
        entry.insert(0, settings.get(field["id"]) or "")
        entry.pack(fill="x", ipady=5, pady=(0, 8))
        entries.append((field["id"], entry))

    def save():
        for key, entry in entries:
            app.save(key, entry.get(), "general")
        window.destroy()
    _modal_buttons(app, window, definition["cancel_text"], definition["save_text"], save)
    _present(app, window, width)
    entries[0][1].focus_set()


def _export_debug(app, spec, control):
    result = app.action("exportDebugZip", app.manager.getCurrentProfile())
    if not result:
        messagebox.showerror(TITLE, "Failed to export debug folder.", parent=app.root)
    elif result[0] is not True:
        messagebox.showerror(TITLE, "Export failed: {}".format(result[1]), parent=app.root)
    else:
        path = filedialog.asksaveasfilename(parent=app.root, title=spec["title"], defaultextension=".zip",
                                            initialfile=result[2] if len(result) > 2 and result[2] else "fuzzy_debug.zip",
                                            filetypes=[("Zip archive", "*.zip")])
        if path:
            with open(path, "wb") as handle:
                handle.write(base64.b64decode(result[1]))
            app.status("Debug folder exported to {}".format(path))


def _update_from_hash(app, spec, control):
    if app.update_running:
        return
    commit = str(control.get()).strip()
    if not re.match(r"^[0-9a-fA-F]{7}$", commit):
        messagebox.showwarning(TITLE, "Please enter a valid 7-character hex commit hash.", parent=app.root)
        return
    if not messagebox.askyesno(TITLE, "Update macro from commit {}? This will backup and apply files."
                               .format(commit), parent=app.root):
        return
    # The confirmation dialog services Tk events while it is open.
    if app.update_running:
        return
    app.update_running = True
    app.status("Starting update to {}".format(commit))

    def finished(ok, result):
        app.update_running = False
        if not app.root.winfo_exists():
            return
        if not ok:
            messagebox.showerror(TITLE, "Error initiating update: {}".format(result), parent=app.root)
        elif result:
            messagebox.showinfo(TITLE, "Update started. The app may close to apply the update.",
                                parent=app.root)
        else:
            messagebox.showerror(TITLE, "Update failed or was aborted. Check logs for details.",
                                 parent=app.root)
    _run_async(app, lambda: app.actions.updateFromHash(commit), finished)


def _normalized_field(name):
    return re.sub(r"\s+", " ", str(name).lower().replace("_", " "))


def tad_alt_settings_from_field(source):
    """The values boost.js copies from a host field into the TAD Alt preset."""
    def either(value, default):
        return value if _truthy(value) else default

    def present(value, default):
        return default if value is None else value
    return {
        "tad_alt_gather_shape": either(source.get("shape"), "e_lol"),
        "tad_alt_gather_size": either(source.get("size"), "m"),
        "tad_alt_gather_width": present(source.get("width"), 5),
        "tad_alt_gather_shift_lock": _truthy(source.get("shift_lock")),
        "tad_alt_gather_drift_compensation": _truthy(source.get("field_drift_compensation")),
        "tad_alt_gather_invert_lr": _truthy(source.get("invert_lr")),
        "tad_alt_gather_invert_fb": _truthy(source.get("invert_fb")),
        "tad_alt_gather_turn": either(source.get("turn"), "none"),
        "tad_alt_gather_turn_times": present(source.get("turn_times"), 1),
        "tad_alt_gather_start_location": either(source.get("start_location"), "center"),
        "tad_alt_gather_distance": present(source.get("distance"), 1),
        "tad_alt_gather_goo": _truthy(source.get("goo")),
        "tad_alt_gather_goo_interval": present(source.get("goo_interval"), 3),
    }


def _copy_host_field_settings(app, spec, control):
    button = control.widget
    if getattr(button, "copying", False):
        return
    button.copying = True
    try:
        settings = app.manager.loadAllSettings()
        field = str(settings.get("tad_alt_default_field") or "pine tree").strip()
        wanted = _normalized_field(field)
        source = next((v for k, v in app.manager.loadFields().items()
                       if _normalized_field(str(k).strip()) == wanted), None)
        if not isinstance(source, dict):
            raise ValueError("No host settings found for {}".format(field))
        copied = tad_alt_settings_from_field(source)
        app.manager.saveDictProfileSettings(copied)
        app.settings.update(copied)
        for key, value in copied.items():
            if key in app.controls:
                app.controls[key].set(value)
        text = "Copied"
    except Exception as error:
        app.status("Could not copy host field settings to TAD Alt: {}".format(error))
        text = "Copy Failed"
    if hasattr(button, "set_text"):
        button.set_text(text)

    def restore():
        button.copying = False
        if button.winfo_exists() and hasattr(button, "set_text"):
            button.set_text(CONTROL_PRESENTATION["tad_alt_copy_field_settings"]["text"])
    button.after(900, restore)


def _sync_glitter_slot(app, spec, control):
    slot = _number(control.get())
    if not math.isfinite(slot):
        return
    slot = int(slot)
    for key in GLITTER_SLOT_IDS:
        if key in app.controls:
            app.controls[key].set(slot)
        app.save(key, slot)


def _raw(control):
    """The text typed in a field; Control.get() turns an empty numeric field into 0."""
    return control.variable.get() if control.variable is not None else control.get()


def _save_cannon_attempts(app, spec, control):
    """saveSetting() clamping for the two cannon retry limits (1-25, resync 0-25)."""
    key = spec["id"]
    resync = key == "cannon_hive_resync_attempts"
    minimum = 0 if resync else 1
    n = _parse_int(control.get())
    n = minimum if n is None else min(max(n, minimum), 25)
    if resync:
        maximum = _parse_int(_raw(app.controls["max_cannon_attempts"]))
        if maximum is not None and n >= maximum:
            n = max(0, maximum - 1)
    elif "cannon_hive_resync_attempts" in app.controls:
        other = app.controls["cannon_hive_resync_attempts"]
        attempts = _parse_int(_raw(other)) or 0
        if attempts >= n:
            attempts = max(0, n - 1)
            other.set(attempts)
            app.save("cannon_hive_resync_attempts", attempts, "general")
    control.set(n)
    app.save(key, n, "general")


# Rows toggled by the delivery mode, in page order after the always-visible mode and time format rows.
DISCORD_ROWS = (("discord_bot_token", lambda mode: mode != "webhook"),
                ("webhook_link", lambda mode: mode != "discord_bot"),
                ("discord_channel_id", lambda mode: mode == "discord_bot"))


def _row_of(widget, container):
    while widget is not None and widget.master is not container:
        widget = widget.master
    return widget


def _common_container(widgets):
    chains = []
    for widget in widgets:
        chain = []
        while widget is not None:
            chain.append(widget)
            widget = widget.master
        chains.append(chain)
    return next(w for w in chains[0][1:] if all(w in chain for chain in chains[1:]))


def _select_discord_delivery_mode(app, spec, control):
    mode = control.get()
    app.save("discord_delivery_mode", mode, "general")
    mode = mode or "both"
    ids = ["discord_delivery_mode", "webhook_time_format"] + [key for key, _ in DISCORD_ROWS]
    if not all(key in app.controls for key in ids):
        return
    container = _common_container([app.controls[key].widget for key in ids])
    rows = {key: _row_of(app.controls[key].widget, container) for key in ids}
    previous = rows["discord_delivery_mode"]
    for key, visible_when in DISCORD_ROWS:
        row = rows[key]
        if key == "webhook_link":
            previous = rows["webhook_time_format"]
        manager = row.winfo_manager()
        if not visible_when(mode):
            if manager == "grid":
                row.grid_remove()
            elif manager == "pack":
                row.pack_options = {k: v for k, v in row.pack_info().items() if k != "in"}
                row.pack_forget()
            continue
        if manager == "grid":
            row.grid()
        elif manager == "pack":
            row.pack_configure(after=previous)
        else:
            row.pack(after=previous, **getattr(row, "pack_options", {"fill": "x"}))
        previous = row


def _reset_blender(app, spec, control):
    app.action("clearBlender")
    _reset_feedback(control)


def _reset_auto_field_boost(app, spec, control):
    app.action("clearAFB")
    _reset_feedback(control)


_ACTIONS = {
    "fallback_private_servers": _fallback_private_servers,
    "export_debug": _export_debug,
    "update_from_hash": _update_from_hash,
    "copy_host_field_settings_to_tad_alt": _copy_host_field_settings,
    "select_discord_delivery_mode": _select_discord_delivery_mode,
    "sync_glitter_hotbar_slot": _sync_glitter_slot,
    "save_cannon_attempts": _save_cannon_attempts,
    "reset_blender": _reset_blender,
    "reset_auto_field_boost": _reset_auto_field_boost,
}


def handle_action(app, action, spec, control):
    """Run a configuration action; False means this module does not own it.

    sync_glitter_hotbar_slot, save_cannon_attempts and select_discord_delivery_mode
    perform the control's save themselves, as the source's trigger functions did.
    """
    handler = _ACTIONS.get(action)
    if handler is None:
        return False
    handler(app, spec, control)
    return True
