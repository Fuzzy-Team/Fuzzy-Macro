"""Native Planters, Tools, and token-ranking editors.

Builders use the host's cards and controls. Tool actions only run on an
explicit button click; status polling never starts automation.
"""

import json
import re
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from types import SimpleNamespace
import uuid

from . import calculators as calc
from . import widgets
from .token_data import sprout_preset, token_model, token_ranking, token_state


# Order, icons, and stored dropdown values follow emojis.js and ui-builder.js.
PLANTER_ICONS = {
    "none": None, "paper": "paper_planter", "ticket": "ticket_planter",
    "festive": "festive_planter", "sticker": "sticker_planter",
    "plastic": "plastic_planter", "candy": "candy_planter",
    "red_clay": "red_clay_planter", "blue_clay": "blue_clay_planter",
    "tacky": "tacky_planter", "pesticide": "pesticide_planter",
    "heat-treated": "heat-treated_planter", "hydroponic": "hydroponic_planter",
    "petal": "petal_planter", "planter_of_plenty": "planter_of_plenty_planter",
}
FIELD_NECTAR_ICONS = {
    "none": None, "sunflower": "satisfying", "dandelion": "comforting",
    "mushroom": "motivating", "blue_flower": "refreshing",
    "clover": "invigorating", "strawberry": "refreshing", "spider": "motivating",
    "bamboo": "comforting", "pineapple": "satisfying", "stump": "motivating",
    "cactus": "invigorating", "pumpkin": "satisfying", "pine_tree": "comforting",
    "rose": "motivating", "mountain_top": "invigorating", "pepper": "invigorating",
    "coconut": "refreshing",
}
NECTARS = ("comforting", "motivating", "satisfying", "refreshing", "invigorating")
WEB_DIM = "#adb4bc"  # the web's hard-coded planter description color


def planter_preset(name):
    """The exact changePreset mapping; selecting Custom changes no other keys."""
    order = {
        "blue": ("comforting", "motivating", "satisfying", "refreshing", "invigorating"),
        "red": ("invigorating", "refreshing", "motivating", "satisfying", "comforting"),
        "white": ("satisfying", "motivating", "refreshing", "comforting", "invigorating"),
    }
    if name not in order:
        return {}
    data = {}
    for index, nectar in enumerate(order[name]):
        data["auto_priority_{}_nectar".format(index)] = nectar
    for index, minimum in enumerate((70, 80, 80, 80, 40)):
        data["auto_priority_{}_min".format(index)] = minimum
    disallowed = {"mushroom", "stump", "mountain_top", "coconut"}
    if name != "red":
        disallowed.add("pumpkin")
    if name == "blue":
        disallowed.add("bamboo")
    for field in FIELD_NECTAR_ICONS:
        if field != "none":
            data["auto_field_" + field] = field not in disallowed
    return data


def selected_planters(settings, auto=False):
    if auto:
        return [name for name in PLANTER_ICONS if name != "none" and settings.get("auto_planter_" + name)]
    selected = []
    for cycle in range(1, 6):
        for slot in range(1, 4):
            name = str(settings.get("cycle{}_{}_planter".format(cycle, slot)) or "").replace(" ", "_")
            if name and name != "none" and name not in selected:
                selected.append(name)
    return selected


def _frame(app, parent, surface=False):
    return tk.Frame(parent, bg=app.palette["surface" if surface else "bg"])


def _control(app, parent, key, title, kind="checkbox", desc="", **kwargs):
    value = kwargs.pop("value", None)
    onchange = kwargs.pop("onchange", None)
    spec = dict(id=key, title=title, desc=desc, kind=kind, scope="profile")
    spec.update(kwargs)
    if value is not None:
        return app.add_control(parent, spec, value=value, onchange=onchange)
    return app.add_control(parent, spec, onchange=onchange)


def _choices(icons):
    return [dict(label=name.replace("_", " ").title(), value=name.replace("_", " "),
                 image="../../webapp/assets/icons/{}.png".format(icon) if icon else None)
            for name, icon in icons.items()]


def _buttons(app, parent, buttons):
    row = _frame(app, parent, True)
    row.pack(fill="x", pady=8)
    for text, command in buttons:
        app.button(row, text, command).pack(side="left", padx=(0, 8))
    return row


def _dialog(app, title, width=680, height=560):
    window = tk.Toplevel(app.root)
    window.title(title)
    window.transient(app.root)
    window.configure(bg=app.palette["bg"])
    x = app.root.winfo_rootx() + max(0, (app.root.winfo_width() - width) // 2)
    y = app.root.winfo_rooty() + max(0, (app.root.winfo_height() - height) // 2)
    window.geometry("{}x{}+{}+{}".format(width, height, x, y))
    window.minsize(420, 320)
    window.resizable(True, True)
    window.protocol("WM_DELETE_WINDOW", window.destroy)
    window.wait_visibility()
    window.grab_set()
    window.focus_set()
    return window


def _tree(app, parent, columns, height=12):
    container = _frame(app, parent, True)
    container.pack(fill="both", expand=True, pady=8)
    style = ttk.Style(app.root)
    style.configure("Editor.Treeview", background=app.palette["input"],
                    fieldbackground=app.palette["input"], foreground=app.palette["text"],
                    bordercolor=app.palette["border"], lightcolor=app.palette["border"], darkcolor=app.palette["border"], rowheight=28)
    style.configure("Editor.Treeview.Heading", background=app.palette["surface"],
                    foreground=app.palette["text"], bordercolor=app.palette["border"], lightcolor=app.palette["border"], darkcolor=app.palette["border"])
    style.map("Editor.Treeview", background=[("selected", app.palette["accent"])],
              foreground=[("selected", app.palette["text"])])
    tree = ttk.Treeview(container, columns=[key for key, _ in columns],
                        show="headings", selectmode="browse", height=height,
                        style="Editor.Treeview")
    for key, title in columns:
        tree.heading(key, text=title)
        tree.column(key, width=130, minwidth=70, stretch=True)
    vertical = ttk.Scrollbar(container, orient="vertical", command=tree.yview, style="Native.Vertical.TScrollbar")
    horizontal = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    container.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)
    return tree


def open_token_ranking(app, field_name, model="standard", sprouts=False):
    """Edit a working copy; only Save writes rankings through the source APIs."""
    existing = getattr(app, "_token_ranking_window", None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        existing.focus_set()
        return existing
    model = token_model(model, sprouts)
    if sprouts:
        ranking = dict(preferred_tokens=app.settings.get("sprouts_preferred_tokens", ""),
                       ignored_tokens=app.settings.get("sprouts_ignored_tokens", ""))
    else:
        if not field_name:
            app.status("Select a gather field first.")
            return
        try:
            ranking = app.manager.loadFuzzyAITokenRanking(field_name, model)
        except Exception as error:
            app.status("Could not load token ranking: {}".format(error))
            return
    state = token_state(ranking, model, sprouts)
    window = _dialog(app, "Sprout token ranking" if sprouts else "Gather token ranking")
    app._token_ranking_window = window

    def clear_window(event=None):
        if event is not None and event.widget is not window:
            return
        if getattr(app, "_token_ranking_window", None) is window:
            app._token_ranking_window = None

    def close():
        window.destroy()
        clear_window()

    window.bind("<Destroy>", clear_window, add="+")
    window.protocol("WM_DELETE_WINDOW", close)
    footer = _frame(app, window)
    footer.pack(side="bottom", fill="x", padx=16, pady=(0, 16))
    body = _frame(app, window)
    body.pack(fill="both", expand=True, padx=16, pady=16)
    app.label(body, "Field: {}. Selected model: {}.".format(field_name, model.title())).pack(anchor="w")
    app.label(body, "Drag rows or use Up/Down to set priority.", dim=True).pack(anchor="w")
    app.label(body, "Click the Collect column or press Space to enable a token.", dim=True).pack(anchor="w")
    tree = _tree(app, body, [("enabled", "Collect"), ("rank", "Priority"), ("token", "Token")])
    tree.column("enabled", width=75, stretch=False)
    tree.column("rank", width=75, stretch=False)
    tree.column("token", width=360)

    def render(select=None):
        tree.delete(*tree.get_children())
        for index, (token, enabled) in enumerate(state):
            tree.insert("", "end", iid=token, values=("Yes" if enabled else "No", index + 1, token))
        if select:
            tree.selection_set(select)
            tree.see(select)

    def move(delta):
        selection = tree.selection()
        if not selection:
            return
        token = selection[0]
        index = next(i for i, row in enumerate(state) if row[0] == token)
        target = index + delta
        if 0 <= target < len(state):
            state.insert(target, state.pop(index))
            render(token)

    def toggle(event=None):
        selection = tree.selection()
        if selection:
            token = selection[0]
            index = next(i for i, row in enumerate(state) if row[0] == token)
            state[index] = (token, not state[index][1])
            render(token)
        return "break"

    drag = [None]

    def press(event):
        token = tree.identify_row(event.y)
        drag[0] = token or None
        if token:
            tree.selection_set(token)
            if tree.identify_column(event.x) == "#1":
                drag[0] = None
                return toggle()

    def drag_to(event):
        token = drag[0]
        target = tree.identify_row(event.y)
        if token and target and token != target:
            old = next(i for i, row in enumerate(state) if row[0] == token)
            new = next(i for i, row in enumerate(state) if row[0] == target)
            state.insert(new, state.pop(old))
            render(token)
        if token and event.y < 20:
            tree.yview_scroll(-1, "units")
        elif token and event.y > tree.winfo_height() - 20:
            tree.yview_scroll(1, "units")
        return "break"

    def save():
        result = token_ranking(state, model, sprouts)
        try:
            if sprouts:
                app.save("sprouts_preferred_tokens", result["preferred_tokens"])
                app.save("sprouts_ignored_tokens", result["ignored_tokens"])
            else:
                app.manager.saveFuzzyAITokenRanking(field_name, result, model)
        except Exception as error:
            app.status("Could not save token ranking: {}".format(error))
            return
        close()
        app.status("Token ranking saved.")

    def preset(name):
        state[:] = token_state(sprout_preset(name, field_name, model), model, True)
        render()

    tree.bind("<Button-1>", press)
    tree.bind("<B1-Motion>", drag_to)
    tree.bind("<ButtonRelease-1>", lambda event: drag.__setitem__(0, None))
    tree.bind("<space>", toggle)
    tree.bind("<Alt-Up>", lambda event: move(-1))
    tree.bind("<Alt-Down>", lambda event: move(1))
    render()
    _buttons(app, body, [("Up", lambda: move(-1)), ("Down", lambda: move(1))])
    if sprouts:
        _buttons(app, body, [("Field Drops", lambda: preset("field")),
                            ("All Sprout Drops", lambda: preset("all")),
                            ("Clear", lambda: preset("clear"))])
    app.button(footer, "Save", save).pack(side="right")
    app.button(footer, "Cancel", close).pack(side="right", padx=(0, 8))
    return window


def _export_planters(app):
    try:
        payload = app.manager.exportPlanterSettings()
        if not payload:
            raise ValueError("No planter settings returned.")
        app.root.clipboard_clear()
        app.root.clipboard_append(payload)
        metadata = json.loads(payload).get("metadata", {})
        message = "Planter settings exported and copied to clipboard!"
        if metadata.get("macro_version"):
            message += " Macro version: {}.".format(metadata["macro_version"])
        if metadata.get("export_date"):
            message += " Exported: {}.".format(metadata["export_date"])
        app.status(message)
    except Exception as error:
        app.status("Could not export planter settings: {}".format(error))


def _import_planters(app):
    window = _dialog(app, "Import Planter Settings", 640, 420)
    body = _frame(app, window)
    body.pack(fill="both", expand=True, padx=16, pady=16)
    app.label(body, "Paste your JSON settings below:").pack(anchor="w")
    container = _frame(app, body)
    container.pack(fill="both", expand=True, pady=8)
    text = tk.Text(container, wrap="word", bg=app.palette["input"], fg=app.palette["text"],
                   insertbackground=app.palette["text"], relief="flat", undo=True)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)
    feedback = app.label(body, "", dim=True)
    feedback.pack(anchor="w")

    def import_settings():
        payload = text.get("1.0", "end").strip()
        if not payload:
            feedback.configure(text="Please paste JSON settings to import.")
            return
        try:
            result = app.manager.importPlanterSettings(payload)
            if not isinstance(result, dict) or not result.get("success"):
                raise ValueError("Please check your JSON format.")
        except Exception as error:
            feedback.configure(text="Could not import planter settings: {}".format(error))
            return
        message = "Successfully imported planter settings!"
        if result.get("macro_version") and result["macro_version"] != "unknown":
            message += " Macro version: {}.".format(result["macro_version"])
        if "imported_settings_count" in result:
            message += " Imported settings: {}.".format(result["imported_settings_count"])
        window.destroy()
        app.refresh()
        app.status(message)

    _buttons(app, body, [("Cancel", window.destroy), ("Import", import_settings)])
    return window


def _timer_reset(app, auto=False):
    result = app.action("resetAutoPlanterTimer", "all") if auto else app.action("clearManualPlanters")
    if result is False:
        app.status("Planter timers could not be reset.")
    elif result is True:
        app.status("Planter timers reset.")


def _inline_control(app, parent, key, kind="checkbox", choices=(), width=184, onchange=None):
    """A bare checkbox or dropdown for the planter grids, saved like add_control."""
    value = app.settings.get(key, "none" if kind == "dropdown" else False)

    def changed():
        if onchange:
            onchange(control.get())
        else:
            app.save(key, control.get())

    if kind == "checkbox":
        widget = widgets.Checkbox(parent, value, changed, app.palette)
    else:
        widget = widgets.Choice(parent, list(choices), value, changed, app.palette, width=width, image_loader=app.image)
    control = widgets.Control(widget, widget.variable)
    app.controls[key] = control
    app.control_groups.setdefault(key, []).append(control)
    return control


def _mode_slider(app, parent, command):
    """The web Off / Manual / Auto range input; command receives the new mode."""
    canvas = tk.Canvas(parent, width=178, height=40, bg=app.palette["bg"], highlightthickness=0, bd=0, cursor="hand2")
    stops = (11, 90, 169)
    value = [calc.parse_int(app.settings["planters_mode"])]

    def draw():
        canvas.delete("all")
        x = stops[min(2, max(0, value[0]))]
        canvas.create_line(4, 9, 176, 9, width=5, capstyle="round", fill=app.palette["text"])
        canvas.create_line(4, 9, x, 9, width=5, capstyle="round", fill=app.palette["accent"])
        canvas.create_oval(x - 8, 1, x + 8, 17, fill=app.palette["accent"], outline="")
        for left, anchor, text in ((1, "w", "Off"), (82, "center", "Manual"), (177, "e", "Auto")):
            canvas.create_text(left, 30, text=text, anchor=anchor, font=("Helvetica", -16), fill=app.palette["text"])

    def set_value(mode):
        value[0] = calc.parse_int(mode)
        draw()

    def drag(event):
        mode = min(range(3), key=lambda index: abs(stops[index] - event.x))
        if mode != value[0]:
            set_value(mode)
            command(mode)

    canvas.bind("<Button-1>", drag)
    canvas.bind("<B1-Motion>", drag)
    draw()
    return widgets.Control(canvas, SimpleNamespace(get=lambda: value[0], set=set_value))


def _planter_card(app, parent, title, desc=""):
    # Planter cards use the web's inline 1rem description instead of the card default.
    body = app.card(parent, title)
    if desc:
        label = app.label(body, desc, dim=True)
        label.configure(font=("Helvetica", -16))
        label.pack(fill="x", pady=(0, 16))
        label.bind("<Configure>", lambda event: label.configure(wraplength=max(1, event.width)))
    return body


def _icon(name):
    return "../../webapp/assets/icons/{}.png".format(name)


def build_planters(app, parent):
    page = _frame(app, parent)
    page.pack(fill="both", expand=True)
    hotbar = [None]
    hotbar_selection = [None]
    summaries = []

    def render_hotbar(auto):
        if hotbar[0] is None:
            return
        selected = selected_planters(app.settings, auto)
        if selected == hotbar_selection[0]:
            return
        hotbar_selection[0] = selected
        for child in hotbar[0].winfo_children():
            child.destroy()
        if not selected:
            empty = app.label(hotbar[0], "No planters selected.", dim=True)
            empty.configure(font=("Helvetica", -14))
            empty.pack(anchor="w", pady=(8, 0))
        for index, planter in enumerate(selected):
            card = widgets.Card(hotbar[0], app.palette, radius=8, padding=12)
            card.configure(width=136)
            card.grid(row=index // 6, column=index % 6, sticky="nsew", padx=(0, 12), pady=(0, 12))
            tile = card.body
            if PLANTER_ICONS.get(planter):
                icon = app.label(tile, "")
                icon.configure(image=app.image(_icon(PLANTER_ICONS[planter]), (42, 42)))
                icon.pack()
            name = app.label(tile, planter.replace("_", " ").title())
            name.configure(font=("Helvetica", -14), anchor="center")
            name.pack(fill="x", pady=(6, 9))
            _inline_control(app, tile, "planter_hotbar_{}_slot".format(planter), "dropdown", width=110,
                            choices=[dict(label="0 - Inventory" if slot == 0 else str(slot), value=slot) for slot in range(8)]).widget.pack()

    def changed_planter(key, value, auto):
        app.save(key, value)
        render_hotbar(auto)

    def reset_row(body, auto):
        row = _frame(app, body, True)
        row.pack(fill="x", pady=(0, 16))
        button = app.button(row, "Reset", lambda: _timer_reset(app, auto))
        button.configure(width=90, height=26)
        button.pack(side="right", anchor="n", pady=6)
        row.bind("<Configure>", lambda event: button.pack_configure(padx=(0, round(event.width * .05))))
        text = _frame(app, row, True)
        text.pack(side="left", fill="x", expand=True)
        title = app.label(text, "Clear Planter Timers")
        title.configure(font=("Helvetica", -15))
        title.pack(anchor="w")
        desc = app.label(text, "Resets the macro's tracking data for the planters", dim=True)
        desc.configure(font=("Helvetica", -13))
        desc.pack(anchor="w")

    def harvest_controls(body, auto):
        prefix = "auto" if auto else "manual"
        _control(app, body, prefix + "_planters_collect_every", "Harvest Every X Hours", "textbox",
                 "The maximum amount of time for planters to grow before being harvested. 2-3 is recommended" if auto
                 else "How often the macro should collect each cycle of planters. 2-3 is recommended",
                 numeric="float", limit=4)
        full = prefix + "_planters_collect_full"
        full_desc = "Collect the planters when they are fully grown. Overrides the 'Harvest Every X Hours' setting"
        if auto:
            automatic = "auto_planters_collect_auto"
            mutually_exclusive = {}

            def change(key, other, value):
                if value:
                    app.save(other, False)
                    mutually_exclusive[other].set(False)
                app.save(key, bool(value))

            mutually_exclusive[full] = _control(app, body, full, "Harvest When Full",
                desc=full_desc, onchange=lambda value: change(full, automatic, value))
        else:
            _control(app, body, full, "Harvest When Full", desc=full_desc)
        _control(app, body, "planters_collect_loot", "Collect Planter Loot",
                 desc="Collect tokens dropped after harvesting planters. Disable this to harvest planters without sweeping up loot.")
        _control(app, body, prefix + "_planters_check", "Planter check",
                 desc="Check inventory after looting planters and make sure that the planter was in fact collected.")
        if auto:
            mutually_exclusive[automatic] = _control(app, body, automatic, "Auto Harvest",
                desc="Let the macro decide when to harvest planters for optimal nectar maintenance. Overrides the 'Harvest Every X Hours' setting",
                onchange=lambda value: change(automatic, full, value))
            _control(app, body, "auto_max_planters", "Max Planters", "textbox",
                     "Maximum number of planters that can be placed at any time", numeric="int", limit=1)
        reset_row(body, auto)

    def guide(body, name, width):
        path = "../../webapp/assets/cheatsheet/" + name
        image = app.label(body, "")
        image.configure(image=app.image(path, (width, 2000)), cursor="hand2", anchor="center")
        image.pack(pady=(16, 0))
        image.bind("<Button-1>", lambda event: app.open_image(path))

    def off():
        body = app.card(content, "")
        title = _frame(app, body, True)
        title.pack(pady=(8, 16))
        heading = app.label(title, "Planters are Off")
        heading.configure(font=("Helvetica", -18, "bold"))
        heading.pack()
        rule = _frame(app, title, True)
        rule.configure(bg=app.palette["border"], height=1)
        rule.pack(fill="x", pady=(6, 0))
        line = app.label(body, "The macro will not harvest or plant any planters.")
        line.configure(font=("Helvetica", -17), fg=WEB_DIM)
        line.pack()
        line = _frame(app, body, True)
        line.pack()
        for text, bold in (("Move the slider above to ", False), ("Manual", True), (" or ", False),
                           ("Auto", True), (" to enable planter management.", False)):
            part = app.label(line, text)
            part.configure(font=("Helvetica", -17, "bold") if bold else ("Helvetica", -17), fg=WEB_DIM)
            part.pack(side="left")
        # The web pause-circle icon: 64px, stroke 2/24, text color at 50% opacity.
        icon = tk.Canvas(body, width=64, height=64, bg=app.palette["surface"], highlightthickness=0, bd=0)
        icon.pack(pady=(32, 6))
        icon.create_oval(5.3, 5.3, 58.7, 58.7, outline="#7f7f7f", width=5.3)
        for x in (26.7, 37.3):
            icon.create_line(x, 24, x, 40, fill="#7f7f7f", width=5.3, capstyle="round")

    def manual():
        body = app.card(content, "Manual Planters")
        harvest_controls(body, False)
        body = _planter_card(app, content, "Planter Cycles",
                             "The macro can place and collect up to 3 planters at once each cycle. "
                             "Setting a field or planter as 'none' will make the macro ignore that slot")
        labels = (("Planters:", ""), ("Fields:", ""),
                  ("Gather in Planter Field:", "The field's gather settings match\nthose in the gather tab"),
                  ("Glitter:", "Use Glitter when the placing a planter.\nSpeeds up planter growth by 25%"))
        for cycle in range(1, 6):
            heading = app.label(body, "Cycle {}".format(cycle))
            heading.configure(font=("Helvetica", -16))
            heading.pack(anchor="w", pady=(20 if cycle > 1 else 8, 28))
            grid = _frame(app, body, True)
            grid.pack(fill="x")
            grid.columnconfigure(0, minsize=284)
            for row, (title, desc) in enumerate(labels):
                cell = _frame(app, grid, True)
                cell.grid(row=row, column=0, sticky="nw", padx=(3, 0))
                label = app.label(cell, title)
                label.configure(font=("Helvetica", -14))
                label.pack(anchor="w", pady=(6, 0) if row < 2 else 0)
                if desc:
                    label = app.label(cell, desc)
                    label.configure(font=("Helvetica", -14), fg=WEB_DIM)
                    label.pack(anchor="w")
            for slot in range(1, 4):
                key = "cycle{}_{}_".format(cycle, slot)
                controls = (
                    _inline_control(app, grid, key + "planter", "dropdown", _choices(PLANTER_ICONS),
                                    onchange=lambda value, key=key + "planter": changed_planter(key, value, False)),
                    _inline_control(app, grid, key + "field", "dropdown", _choices(FIELD_NECTAR_ICONS)),
                    _inline_control(app, grid, key + "gather"),
                    _inline_control(app, grid, key + "glitter"))
                for row, control in enumerate(controls):
                    control.widget.grid(row=row, column=slot, sticky="nw", padx=(0, 30), pady=(0, 13 if row < 2 else 6))
        body = _planter_card(app, content, "Selected Planters", "Map selected planters to hotbar slots. Slot 0 uses inventory search.")
        hotbar[0] = _frame(app, body, True)
        hotbar[0].pack(fill="x")
        render_hotbar(False)

    def auto():
        body = app.card(content, "Auto Planters/Planter+")
        harvest_controls(body, True)

        def change_preset(value):
            app.save("auto_preset", value)
            for key, setting in planter_preset(value).items():
                app.save(key, setting)
            app.refresh()

        _control(app, body, "auto_preset", "Presets", "dropdown", "Recommended nectar priority and field settings based on hive color",
                 choices=[dict(label=name.title(), value=name) for name in ("blue", "red", "white", "custom")], onchange=change_preset)

        def save_gather(value):
            if app.action("setAutoPlanterGather", bool(value)) is False:
                app.status("Could not save Auto Planter gather flag.")

        data = app.action("getAutoPlanterData")
        _control(app, body, "auto_planters_gather", "Gather in Planter Fields",
            desc="When enabled, the macro will gather the planter's field immediately after placement so it collects while the planter grows.",
            scope="local", value=bool(data.get("gather", False)) if isinstance(data, dict) else False,
            onchange=save_gather)

        body = _planter_card(app, content, "Nectar Priority",
                             "The macro will aim to maintain nectars above the min%. The higher up a nectar is, the greater its priority")
        for index in range(5):
            # The web row is a flex row with 5% right padding and the min% box flush right.
            line = _frame(app, body, True)
            line.pack(fill="x", pady=(30 if index else 18, 21 if index == 4 else 0))
            _inline_control(app, line, "auto_priority_{}_nectar".format(index), "dropdown",
                            _choices({nectar: nectar for nectar in NECTARS})).widget.pack(side="left", anchor="n")
            row = _bare(_control(app, line, "auto_priority_{}_min".format(index), "", "textbox", numeric="int", limit=3))
            row.pack_configure(side="right", fill="none", anchor="n")
            line.bind("<Configure>", lambda event, row=row: row.pack_configure(padx=(0, round(event.width * .05))))
        guide(body, "nectar.png", 500)

        restrictions = _planter_card(app, content, "Planters Allowed & Restrictions",
                                     "Restrict which fields each planter can be placed in when using Auto Planters.")
        for planter, icon in PLANTER_ICONS.items():
            if planter == "none":
                continue
            enable_key = "auto_planter_" + planter
            outline = widgets.Card(restrictions, app.palette, radius=6, padding=3)
            outline.pack(fill="x", pady=(0, 4))
            section = outline.body
            header = _frame(app, section, True)
            header.configure(cursor="hand2")
            header.pack(fill="x")
            fields = _frame(app, section, True)
            keys = []
            for field in FIELD_NECTAR_ICONS:
                if field == "none":
                    continue
                key = "auto_planter_{}_field_{}".format(planter, field)
                if key not in app.settings:
                    app.save(key, True)
                keys.append((key, field))
            summary = app.label(header, "", dim=True)
            summary.configure(font=("Helvetica", -14), fg="#6b7280")
            summary.pack(side="right")

            def update_summary(outline=outline, summary=summary, keys=keys, enable_key=enable_key):
                count = sum(bool(app.settings.get(key)) for key, _ in keys)
                summary.configure(text="Allowed fields: {}".format(count))
                # The web outlines enabled planters in rgba(96,165,250,.25).
                outline.set_border("#2f4055" if app.settings.get(enable_key) else app.palette["surface"])

            def change_planter(value, key=enable_key, update_summary=update_summary):
                changed_planter(key, bool(value), True)
                update_summary()

            def change_field(key, value, update_summary=update_summary):
                app.save(key, bool(value))
                update_summary()

            _inline_control(app, header, enable_key, onchange=change_planter).widget.pack(side="left")
            name = app.label(header, " " + planter.replace("_", " ").title())
            name.configure(font=("Helvetica", -15), image=app.image(_icon(icon), (18, 18)), compound="left", padx=0)
            name.pack(side="left", padx=(8, 0))
            for column in range(4):
                fields.columnconfigure(column, minsize=220)
            for index, (key, field) in enumerate(keys):
                cell = _frame(app, fields, True)
                cell.grid(row=index // 4, column=index % 4, sticky="ew", padx=(0, 10), pady=(0, 10))
                _inline_control(app, cell, key, onchange=lambda value, key=key, change_field=change_field: change_field(key, value)).widget.pack(side="right")
                label = app.label(cell, field.replace("_", " ").title())
                label.configure(font=("Helvetica", -15), image=app.image(_icon(FIELD_NECTAR_ICONS[field]), (18, 18)), compound="right")
                label.pack(side="left")

            def toggle(event=None, fields=fields):
                if fields.winfo_manager():
                    fields.pack_forget()
                else:
                    fields.pack(fill="x", pady=(12, 0))

            for widget in (header, name, summary):
                widget.bind("<Button-1>", toggle)
            summaries.append(update_summary)
            update_summary()

        body = _planter_card(app, content, "Allowed Fields", "Fields the macro can plant in")
        for field, nectar in FIELD_NECTAR_ICONS.items():
            if field == "none":
                continue
            row = _frame(app, body, True)
            row.pack(fill="x", pady=(0, 24))
            checkbox = _inline_control(app, row, "auto_field_" + field).widget
            checkbox.pack(side="right", anchor="n", pady=(10, 0))
            row.bind("<Configure>", lambda event, checkbox=checkbox: checkbox.pack_configure(padx=(0, round(event.width * .10))))
            label = app.label(row, field.replace("_", " ").title())
            label.configure(font=("Helvetica", -15), image=app.image(_icon(nectar), (18, 18)), compound="right")
            label.pack(side="left", anchor="n")

        body = _planter_card(app, content, "Selected Planters", "Map enabled planters to hotbar slots. Slot 0 uses inventory search.")
        hotbar[0] = _frame(app, body, True)
        hotbar[0].pack(fill="x")
        render_hotbar(True)
        body = _planter_card(app, content, "Wax from Planters", "Reference guide for wax drops from different planters")
        guide(body, "planters.png", 600)

    rendered_mode = [None]
    def render(value):
        mode = calc.parse_int(value)
        if mode == rendered_mode[0]:
            if mode == 2:
                app.controls['auto_planters_gather'].set(bool(app.action('getAutoPlanterData')['gather']))
                render_hotbar(True)
                for update_summary in summaries:
                    update_summary()
            return
        summaries[:] = []
        rendered_mode[0] = mode
        hotbar[0] = None
        hotbar_selection[0] = None
        for child in content.winfo_children():
            child.destroy()
        if mode == 1:
            manual()
        elif mode == 2:
            auto()
        else:
            off()

    def change_mode(value):
        app.save("planters_mode", calc.parse_int(value))
        render(value)

    mode = _mode_slider(app, page, change_mode)
    mode.widget.pack(anchor="e", padx=(0, 14), pady=(25, 65))
    app.controls["planters_mode"] = mode
    app.control_groups.setdefault("planters_mode", []).append(mode)
    content = _frame(app, page)
    content.pack(fill="both", expand=True)
    render(app.settings["planters_mode"])
    app.refresh_planters = lambda: render(app.settings["planters_mode"])
    actions = _frame(app, page)
    actions.pack(pady=(5, 20))
    for text, command in (("Export Settings", lambda: _export_planters(app)), ("Import Settings", lambda: _import_planters(app))):
        # The web .import-export-button: tinted accent fill, main text color, radius 8.
        button = app.button(actions, text, command)
        button.fill, button.foreground, button.radius = app.palette["selected"], app.palette["text"], 8
        button.configure(height=32)
        button.pack(side="left", padx=5)
    return page


# The web tools draw these boxes with translucent white over the surface color.
TOOL_BOX = dict(surface="#272727", border="#2e2e2e")
WARNING_BOX = dict(surface="#332424", border="#a94545")


def _box(app, parent, colors, radius=10, padding=16):
    """A rounded bordered box; its children go in .body."""
    return widgets.Card(parent, dict(app.palette, **colors), radius=radius, padding=padding)


def _text(app, parent, text, size=-15, dim=True, pady=0, **options):
    label = app.label(parent, text, dim)
    label.configure(font=("Helvetica", size), **options)
    label.pack(fill="x", pady=pady)
    label.bind("<Configure>", lambda event: label.configure(wraplength=max(1, event.width)))
    return label


def _rich(app, parent, parts, size=-15, dim=True, pady=0):
    """Wrapped text whose odd-indexed parts are bold, like the web's hotkey spans."""
    flow = tk.Frame(parent, bg=parent.cget("bg"), height=1)
    flow.pack(fill="x", pady=pady)
    tokens, space = [], False
    for index, part in enumerate(parts):
        for match in re.finditer(r"(\s*)(\S+)", part):
            spaced = space or bool(match.group(1))
            space = False
            if tokens and not spaced:
                # Punctuation joins the word before it, so no gap opens between labels.
                tokens[-1][0] += match.group(2)
            else:
                tokens.append([match.group(2), index % 2, spaced])
        space = space or part[-1:].isspace()
    words = []
    for text, bold, spaced in tokens:
        label = app.label(flow, text, dim)
        label.configure(font=("Helvetica", size, "bold") if bold else ("Helvetica", size))
        words.append((label, spaced))

    def arrange(event):
        gap = tkfont.Font(font=("Helvetica", size)).measure(" ")
        line = max(label.winfo_reqheight() for label, _ in words)
        x = y = 0
        for label, spaced in words:
            width = label.winfo_reqwidth()
            if spaced and x and x + gap + width > event.width:
                x, y = 0, y + line
            elif spaced and x:
                x += gap
            label.place(x=x, y=y)
            x += width
        if int(flow.cget("height")) != y + line:
            flow.configure(height=y + line)

    flow.bind("<Configure>", arrange)
    return flow


def _bare(control):
    """Drop an add_control row's title column and right alignment, keeping the control."""
    right = control.widget.master
    row = right.master
    row.unbind("<Configure>")
    for widget in row.grid_slaves(column=0):
        widget.grid_remove()
    row.grid_columnconfigure(0, weight=0)
    row.grid_columnconfigure(1, weight=1)
    right.grid_configure(sticky="ew", padx=0, pady=0)
    row.pack_configure(pady=0)
    return row


def _grid(app, parent, weights, pady=0, bg=None):
    """Grid columns with the web's 0.75rem gap; cells go in even columns."""
    grid = tk.Frame(parent, bg=bg or parent.cget("bg"))
    grid.pack(fill="x", pady=pady)
    for index, weight in enumerate(weights):
        grid.grid_columnconfigure(index * 2, weight=weight, uniform="cells")
        if index:
            grid.grid_columnconfigure(index * 2 - 1, minsize=12)
    return grid


def _group(app, grid, column, title):
    """A web .bond-calc-input-group: a label above a control that fills the column."""
    cell = _frame(app, grid, True)
    cell.grid(row=0, column=column * 2, sticky="ew")
    label = app.label(cell, title)
    label.configure(font=("Helvetica", -15))
    label.pack(anchor="w", pady=(0, 6))
    return cell


def _filled(control):
    _bare(control)
    control.widget.pack_configure(fill="x", expand=True)
    return control


def _summary(app, grid, column, title):
    box = _box(app, grid, dict(surface=app.palette["hover"]), 8, 11)
    box.grid(row=0, column=column * 2, sticky="nsew")
    name = app.label(box.body, title, dim=True)
    name.configure(font=("Helvetica", -13))
    name.pack(anchor="w")
    value = app.label(box.body, "")
    value.configure(font=("Helvetica", -16, "bold"))
    value.pack(anchor="w", pady=(4, 0))
    return name, value


def _table(app, parent, headings):
    """The web .bond-calc-table: a shaded header and a rule under every row."""
    table = _frame(app, parent, True)
    table.pack(fill="x", pady=(16, 0))
    body = _frame(app, table, True)

    def cell(row, column, text, header=False):
        label = tk.Label(body, text=text, anchor="w", padx=8, pady=8, bd=0,
                         font=("Helvetica", -14, "bold") if header else ("Helvetica", -14),
                         bg=app.palette["hover" if header else "surface"],
                         fg=app.palette["text" if header else "dim"])
        label.grid(row=row * 2, column=column, sticky="nsew")
        return label

    def render(rows):
        for widget in body.winfo_children():
            if widget not in labels:
                widget.destroy()
        for index, values in enumerate(rows, 1):
            for column, text in enumerate(values):
                cell(index, column, text)
        for index in range(len(rows) + 1):
            tk.Frame(body, bg=app.palette["border"], height=1).grid(
                row=index * 2 + 1, column=0, columnspan=len(headings), sticky="ew")
        # Like an auto-layout HTML table, spare width follows each column's widest text.
        for column in range(len(headings)):
            body.grid_columnconfigure(column, weight=max(len(str(values[column])) for values in [headings, *rows]) + 2)

    labels = [cell(0, column, title, True) for column, title in enumerate(headings)]
    body.pack(fill="x")
    return table, labels, render


def _tool_panel(app, parent, title, desc=""):
    """The outer tool panel holding its titled section card, like the web nesting."""
    panel = app.card(parent, "")
    return panel, app.card(panel, title, desc)


def _action_row(app, parent, title, desc):
    """A settings row whose right side holds tool buttons, aligned like textbox rows."""
    row = _frame(app, parent, True)
    row.pack(fill="x", pady=(0, 16))
    right = _frame(app, row, True)
    right.pack(side="right", anchor="n", pady=6)
    copy = _frame(app, row, True)
    copy.pack(side="left", fill="x", expand=True)
    _text(app, copy, title, dim=False)
    _text(app, copy, desc, -13)
    row.bind("<Configure>", lambda event: right.pack_configure(padx=(24, round(event.width * .05))))
    return right


def _form_row(app, parent, title, desc, pady):
    """A web .boost-hotbar-form-row: copy on the left, its control flush right."""
    row = tk.Frame(parent, bg=parent.cget("bg"))
    row.pack(fill="x", pady=pady)
    right = tk.Frame(row, bg=parent.cget("bg"))
    right.pack(side="right", anchor="n")
    copy = tk.Frame(row, bg=parent.cget("bg"))
    copy.pack(side="left", fill="x", expand=True)
    _text(app, copy, title, dim=False)
    _text(app, copy, desc, -13, pady=(4, 0))
    return right


def _tool_status(app, body, getter, start_action, stop_action, rows, start_parent, stop_parent=None):
    """Poll an existing runner; cancel the Tk callback when its page is destroyed.

    rows pairs each status label with the formatter that fills it.
    """
    def invoke(action):
        result = action()
        if isinstance(result, dict) and result.get("message"):
            app.status(result["message"])
        refresh()

    start = app.button(start_parent, "Start", lambda: invoke(start_action))
    stop = app.button(stop_parent or start_parent, "Stop", lambda: invoke(stop_action))
    timer = [None]
    running = [False]
    texts = [None] * len(rows)

    def refresh():
        status = app.action(getter)
        if not isinstance(status, dict):
            return
        for index, (label, formatter) in enumerate(rows):
            text = formatter(status)
            if text != texts[index]:
                label.configure(text=text)
                texts[index] = text
        active = bool(status.get("running"))
        if active != running[0]:
            running[0] = active
            if active:
                start.pack_forget()
                stop.pack(side="left", padx=(0, 8))
            else:
                stop.pack_forget()
                start.pack(side="left", padx=(0, 8))

    def poll():
        timer[0] = None
        refresh()
        timer[0] = body.after(1000, poll)

    def destroy(event):
        if event.widget is body and timer[0] is not None:
            body.after_cancel(timer[0])
            timer[0] = None

    body.bind("<Destroy>", destroy, add="+")
    start.pack(side="left", padx=(0, 8))
    poll()


def _hotkey(app, key, default="Not set"):
    return app.settings.get(key) or default


def _build_autoclicker(app, parent):
    panel, body = _tool_panel(app, parent, "Auto Clicker", "Repeatedly left-clicks at a configurable interval")
    interval = _control(app, body, "autoclicker_interval_ms", "Click Interval (ms)", "textbox",
                        "Time between clicks in milliseconds. Lower values click faster.",
                        scope="local", numeric="int", limit=4, value=100,
                        onchange=lambda value: interval.set(max(10, calc.parse_int(value, 100))))
    delay = _control(app, body, "autoclicker_start_delay_seconds", "Start Delay (seconds)", "textbox",
                     "Wait time before the auto clicker begins. Default is 3 seconds.",
                     scope="local", numeric="int", limit=2, value=3,
                     onchange=lambda value: delay.set(min(10, max(0, calc.parse_int(value, 3)))))

    def start():
        milliseconds = max(10, calc.parse_int(interval.get(), 100))
        seconds = min(10, max(0, calc.parse_int(delay.get(), 3)))
        interval.set(milliseconds)
        delay.set(seconds)
        return app.action("startAutoClickerTool", milliseconds, seconds)

    start_row = _action_row(app, body, "Start Auto Clicker", "Begins clicking after the configured start delay.")
    stop_row = _action_row(app, body, "Stop Auto Clicker", "Stops all automatic clicking.")
    _tool_status(app, body, "getAutoClickerStatus", start,
                 lambda: app.action("stopAutoClickerTool"), [], start_row, stop_row)
    box = _box(app, panel, TOOL_BOX)
    box.pack(fill="x")
    box = box.body
    title = app.label(box, "Hotkeys")
    title.configure(bg=box.cget("bg"), font=("Helvetica", -14, "bold"))
    title.pack(anchor="w", pady=(0, 5))
    _rich(app, box, ["Start hotkey: ", _hotkey(app, "autoclicker_keybind"),
                     ". This tool stops with the macro stop hotkey: ", _hotkey(app, "stop_keybind", "F3"),
                     ". You can change this in Config."], -14, dim=False)


def _build_hotbar_buff(app, parent):
    palette = app.palette
    panel, body = _tool_panel(app, parent, "Hotbar Buff")
    _text(app, body, "Runs this tool's hotbar timers while you play.")
    _rich(app, body, ["Start hotkey: ", _hotkey(app, "hotbar_buff_start_keybind", "F4"),
                      ". Stop hotkey: ", _hotkey(app, "stop_keybind", "F3"), "."], pady=(12, 0))
    buttons = _frame(app, body, True)
    buttons.pack(fill="x", pady=(16, 0))
    grid = _grid(app, body, (1, 1), pady=(16, 0))
    state = _summary(app, grid, 0, "Status")[1]
    last = _summary(app, grid, 1, "Last Slot")[1]
    message = _text(app, body, "", pady=(16, 0))
    _tool_status(app, body, "getHotbarBuffStatus", lambda: app.action("startHotbarBuffTool"),
                 lambda: app.action("stopHotbarBuffTool"), [
                     (state, lambda status: status.get("state") or "idle"),
                     (last, lambda status: "Slot {}".format(status["last_slot"]) if status.get("last_slot") else "None"),
                     (message, lambda status: status.get("message") or "Ready")], buttons)

    strip = _frame(app, body, True)
    strip.pack(anchor="w", pady=(12, 14))
    holder = _frame(app, body, True)
    holder.pack(fill="x")
    # The web panel is white at 3% over the card.
    fill = widgets.mix("#ffffff", palette["surface"], .03)
    tiles, panels = [], []

    def show(slot):
        app.subtab_selection["activeHotbarBuffToolSlot"] = "slot{}".format(slot)
        for index, (number, canvas) in enumerate(tiles, 1):
            number.configure(fg=palette["accent"] if index == slot else palette["dim"])
            widgets.draw_hotbar_slot(canvas, palette, index == slot)
            panels[index - 1].pack_forget()
        panels[slot - 1].pack(fill="x")

    for slot in range(1, 8):
        column = _frame(app, strip, True)
        column.pack(side="left")
        number = tk.Label(column, text="[{}]".format(slot), bg=palette["surface"], font=("Helvetica", -13, "bold"))
        number.pack()
        canvas = tk.Canvas(column, width=80, height=82, bg=palette["surface"], highlightthickness=0,
                           bd=0, cursor="hand2")
        canvas.pack()
        canvas.bind("<ButtonRelease-1>", lambda event, slot=slot: show(slot))
        tiles.append((number, canvas))

        slot_panel = widgets.Card(holder, dict(palette, surface=fill), radius=18, padding=20)
        head = tk.Frame(slot_panel.body, bg=fill)
        head.pack(fill="x", pady=(0, 16))
        icon = tk.Canvas(head, width=52, height=52, bg=fill, highlightthickness=0, bd=0)
        widgets.draw_hotbar_icon(icon, fill)
        icon.pack(side="left", padx=(0, 16))
        copy = tk.Frame(head, bg=fill)
        copy.pack(side="left", fill="x", expand=True)
        _text(app, copy, "Slot {}".format(slot), dim=False).configure(font=("Helvetica", -15, "bold"))
        _text(app, copy, "Enable this slot and set how often it should be pressed.", -14, pady=(4, 0))
        prefix = "hotbar_buff_tool_slot{}_".format(slot)
        _bare(_control(app, _form_row(app, slot_panel.body, "Enabled", "Allow the tool to press this hotbar slot.", 0),
                       prefix + "enabled", ""))
        every = _control(app, _form_row(app, slot_panel.body, "Use Every", "Set the cooldown for repeated use of this slot.",
                                        (16, 0)), prefix + "use_every_value", "", "textbox", numeric="float")
        _bare(every)
        every.widget.configure(width=16)
        units = _control(app, every.widget.master, prefix + "use_every_format", "", "dropdown",
                         choices=[dict(label="Secs", value="secs"), dict(label="Mins", value="mins")])
        _bare(units).pack_configure(side="left", fill="none", padx=(8, 0))
        units.widget.button.configure(width=96)
        panels.append(slot_panel)
    selected = str(app.subtab_selection.get("activeHotbarBuffToolSlot", "slot1"))[4:]
    show(int(selected) if selected in [str(slot) for slot in range(1, 8)] else 1)


def _build_auto_gifted(app, parent):
    palette = app.palette
    panel, body = _tool_panel(app, parent, "Auto Gifted Basic Bee Tool (BETA)")
    _text(app, body, "This tool is in early beta and may be buggy. It is recommended to watch the tool run to make sure "
                     "it doesn't do anything unexpected. If you encounter any issues, please report them on the discord server.")
    _text(app, body, "When you press start, the tool focuses Roblox, waits a short countdown (set below, default of 3 seconds), "
                     "captures your current mouse position as the bee slot, then alternates Basic Egg, Royal Jelly, Basic Egg, "
                     "and repeats until it finds a Gifted Basic Bee or a paused result.", pady=(28, 0))
    _rich(app, body, ["Start this tool with its configured hotkey: ", _hotkey(app, "auto_gifted_basic_bee_start_keybind"),
                      ". To stop this tool, use the macro stop hotkey: ", _hotkey(app, "stop_keybind", "F3"),
                      ". You can change this in Config."], pady=(8, 0))
    grid = _grid(app, body, (1, 1), pady=(16, 0))
    cell = _frame(app, grid, True)
    cell.grid(row=0, column=0, sticky="w")
    label = app.label(cell, "Capture Delay (seconds)")
    label.configure(font=("Helvetica", -15))
    label.pack(side="left", padx=(0, 4))
    delay = _control(app, cell, "auto-gifted-basic-bee-delay", "", "textbox",
                     scope="local", numeric="int", value=3,
                     onchange=lambda value: delay.set(min(10, max(1, calc.parse_int(value, 3)))))
    _bare(delay).pack_configure(side="left", fill="none")
    delay.widget.configure(width=16)
    buttons = _frame(app, grid, True)
    buttons.grid(row=0, column=2, sticky="w")

    _text(app, body, "Pause On Result", dim=False, pady=(16, 8))
    choices = _grid(app, body, (1, 1, 1))
    pause = {}
    for column, (name, title, default) in enumerate((("gifted_other", "Gifted Non-Basic", True),
                                                     ("legendary", "Legendary", False), ("mythic", "Mythic", True))):
        cell = _frame(app, choices, True)
        cell.grid(row=0, column=column * 2, sticky="w")
        pause[name] = _control(app, cell, "auto-gifted-basic-bee-pause-" + name.replace("_", "-"),
                               "", scope="local", value=default)
        _bare(pause[name]).pack_configure(side="left", fill="none")
        label = app.label(cell, title)
        label.configure(font=("Helvetica", -15))
        label.pack(side="left")

    def start():
        seconds = min(10, max(1, calc.parse_int(delay.get(), 3)))
        delay.set(seconds)
        settings = dict(pause_on_gifted_basic=True, pause_on_basic=False, pause_on_other=False)
        settings.update({"pause_on_" + name: bool(control.get()) for name, control in pause.items()})
        return app.action("startAutoGiftedBasicBeeTool", seconds, settings)

    box = _box(app, body, TOOL_BOX)
    box.pack(fill="x", pady=(16, 0))
    box = box.body
    stats = _grid(app, box, (1, 1, 1, 1), bg=box.cget("bg"))
    values = []
    for index, title in enumerate(("Status", "Bee Slot", "Basic Eggs", "Royal Jellies", "Total Rolls",
                                   "Message", "Last OCR Read")):
        cell = tk.Frame(stats if index < 5 else box, bg=box.cget("bg"))
        if index < 5:
            cell.grid(row=index // 4 * 2, column=index % 4 * 2, sticky="nw")
            stats.grid_rowconfigure(1, minsize=12)
        else:
            cell.pack(fill="x", pady=(16, 0))
        _text(app, cell, title, dim=False).configure(bg=box.cget("bg"))
        value = _text(app, cell, "", -14, dim=index == 6, pady=(4, 0), bg=box.cget("bg"))
        if index == 0:
            value.configure(font=("Helvetica", -14, "bold"))
        values.append(value)
    _tool_status(app, body, "getAutoGiftedBasicBeeStatus", start,
                 lambda: app.action("stopAutoGiftedBasicBeeTool"), list(zip(values, [
                     lambda status: status.get("state") or "idle",
                     lambda status: "{}, {}".format(status["bee_slot_x"], status["bee_slot_y"])
                         if status.get("bee_slot_x") is not None and status.get("bee_slot_y") is not None else "Not captured",
                     lambda status: str(status.get("basic_eggs_used", 0)),
                     lambda status: str(status.get("royal_jellies_used", 0)),
                     lambda status: str(status.get("rolls", 0)),
                     lambda status: status.get("message") or "Ready",
                     lambda status: status.get("last_detected_text") or "None"])), buttons)
    _text(app, body, "Requirements: stop the main macro first, keep Auto-Jelly disabled in-game, and make sure "
                     "Roblox is visible before starting.", -14, pady=(16, 0))
    _text(app, body, "Please note: this is beta, it may mess up, it is not garunteed to work, please watch it run and "
                     "report any issues you see on the discord. The tool relies on OCR to read the result of each roll, "
                     "so it may misread sometimes, especially if your game resolution is low or if you have a lot of "
                     "screen clutter. If it misreads a result, it may do extra rolls or stop when it shouldn't, so it's "
                     "important to keep an eye on it while it's running.", -14, pady=(16, 0), fg="#c75b74")


def _watch_calculator(body, controls, update):
    updating = [False]

    def changed(*args):
        if updating[0]:
            return
        updating[0] = True
        try:
            update()
        finally:
            updating[0] = False

    traces = [(control.variable, control.variable.trace_add("write", changed)) for control in controls]

    def destroy(event):
        if event.widget is body:
            for variable, trace in traces:
                variable.trace_remove("write", trace)

    body.bind("<Destroy>", destroy, add="+")
    changed()


def _calculator_warning(app, body, before):
    box = _box(app, body, WARNING_BOX, 8, 8)
    warning = tk.Label(box.body, font=("Helvetica", -14), anchor="w", justify="left", padx=4, pady=0,
                       bg=WARNING_BOX["surface"], fg="#ffb3b3")
    warning.pack(fill="x")

    def show(text):
        warning.configure(text=text)
        if text:
            box.pack(fill="x", pady=(13, 0), before=before)
        else:
            box.pack_forget()
    return show


def _build_bond_calculator(app, parent):
    panel, body = _tool_panel(app, parent, "Bond/Treat Calculator")
    _text(app, body, "Calculate treat count and honey cost between bond levels using your Bond from Treats stat.", -16, dim=False)
    _text(app, body, "You can find your Bond from Treats % in your character stats in BSS.", pady=(8, 0))
    grid = _grid(app, body, (1, 1, 1, 1), pady=(16, 0))
    start = _filled(_control(app, _group(app, grid, 0, "Initial Level"), "bond-calc-start-level", "", "dropdown",
                             scope="local", value=1, numeric="int",
                             choices=[dict(label=str(level), value=level) for level in range(1, 25)]))
    end = _filled(_control(app, _group(app, grid, 1, "Final Level"), "bond-calc-end-level", "", "dropdown",
                           scope="local", value=25, numeric="int",
                           choices=[dict(label=str(level), value=level) for level in range(2, 26)]))
    bonus = _filled(_control(app, _group(app, grid, 2, "Bond from Treats (%)"), "bond-calc-bonus", "", "textbox",
                             scope="local", value=20, numeric="float"))
    bees = _filled(_control(app, _group(app, grid, 3, "# of Bees"), "bond-calc-bee-count", "", "textbox",
                            scope="local", value=50, numeric="int"))
    summary = _grid(app, body, (1, 1, 1, 1), pady=(16, 0))
    totals = [_summary(app, summary, column, "") for column in range(4)]
    warning = _calculator_warning(app, body, summary)
    _, headings, render = _table(app, body, ("Level", "Bond Required", "Treats Needed", "Cost per Bee", "Cost for 50 Bees"))

    def update():
        result = calc.calculate_bond(start.get(), end.get(), bonus.get(), bees.get())
        value = result["bonus_percent"]
        # JavaScript writes whole numbers back without a decimal point.
        bonus.set(int(value) if value == int(value) else value)
        bees.set(result["bee_count"])
        count = result["bee_count"]
        bee_label = "{} Bee{}".format(count, "" if count == 1 else "s")
        warning(result["warning"])
        labels = ("Total Bond", "Treats Needed ({})".format(bee_label), "Cost (1 Bee)", "Cost ({})".format(bee_label))
        for (name, total), title, key in zip(totals, labels, ("total_bond", "total_treats", "cost_one", "cost_bees")):
            name.configure(text=title)
            total.configure(text=calc.format_compact_honey(result[key]))
        headings[-1].configure(text="Cost for " + bee_label)
        render([(row["label"], calc.format_whole_number(row["bond"]), calc.format_whole_number(row["treats"]),
                 calc.format_compact_honey(row["costPerBee"]), calc.format_compact_honey(row["costForBees"]))
                for row in result["rows"]])

    _watch_calculator(body, [start, end, bonus, bees], update)


def _build_ticket_calculator(app, parent):
    panel, body = _tool_panel(app, parent, "Ticket Price Calculator")
    _text(app, body, "Calculate the honey cost of buying tickets from the Bee Swarm Simulator ticket shop.", -16, dim=False)
    _text(app, body, "Enter the current price of your next ticket to see the cost for common ticket bundles.", pady=(8, 0))
    units = [dict(label=label, value=unit) for unit, label in calc.HONEY_UNITS]
    # The web grid settles at 284/220/284px; its number inputs keep their 168px default width.
    grid = _grid(app, body, (284, 220, 284), pady=(16, 0))

    def priced(column, title, key, value, unit_key):
        line = _frame(app, _group(app, grid, column, title), True)
        line.pack(fill="x")
        amount = _control(app, line, key, "", "textbox", scope="local", value=value, numeric="float")
        _bare(amount).pack_configure(side="left", fill="none")
        amount.widget.configure(width=19)
        unit = _control(app, line, unit_key, "", "dropdown", scope="local", value=1000000, numeric="int", choices=units)
        _bare(unit).pack_configure(side="left", fill="none", padx=(8, 0))
        unit.widget.button.configure(width=88)
        return amount, unit

    price, price_unit = priced(0, "Price of Next Ticket", "ticket-calc-next-price", 100, "ticket-calc-next-price-unit")
    custom = _filled(_control(app, _group(app, grid, 1, "Custom Amount"), "ticket-calc-custom-amount", "", "textbox",
                              scope="local", value=1, numeric="int"))
    budget, budget_unit = priced(2, "Budget", "ticket-calc-budget", 0, "ticket-calc-budget-unit")
    table, _, render = _table(app, body, ("Tickets", "Cost"))
    warning = _calculator_warning(app, body, table)

    def update():
        result = calc.calculate_tickets(price.get(), price_unit.get(), custom.get(), budget.get(), budget_unit.get())
        custom.set(result["custom_amount"])
        warning(result["warning"])
        rows = []
        for amount, purchase in result["rows"]:
            label = "{} Tickets".format(calc.format_whole_number(amount))
            if amount == result["custom_amount"] and amount not in calc.TICKET_CALC_PRESETS:
                label += " (Custom)"
            rows.append((label, calc.format_compact_honey(purchase["totalCost"])))
        rows.append(("Max ({} Tickets)".format(calc.format_whole_number(result["budget"]["tickets"])),
                     calc.format_compact_honey(result["budget"]["totalCost"])))
        render(rows)

    _watch_calculator(body, [price, price_unit, custom, budget, budget_unit], update)


def build_tools(app, parent):
    page = _frame(app, parent)
    page.pack(fill="both", expand=True)
    # Session synchronization belongs to the window lifetime, not tab reloads.
    if not getattr(app, "_tools_session_id", None):
        app._tools_session_id = str(uuid.uuid4())
        app.action("syncToolSession", app._tools_session_id)
    app.subtabs(page, [
        ("tools-autoclicker", "Auto Clicker", lambda parent: _build_autoclicker(app, parent)),
        ("tools-hotbar-buff", "Hotbar Buff", lambda parent: _build_hotbar_buff(app, parent)),
        ("tools-bond-calculator", "Bond Calculator", lambda parent: _build_bond_calculator(app, parent)),
        ("tools-ticket-calculator", "Ticket Price Calculator", lambda parent: _build_ticket_calculator(app, parent)),
        ("tools-auto-gifted-basic-bee", "Auto Gifted Basic Bee", lambda parent: _build_auto_gifted(app, parent)),
    ], "activeToolsSubtab")
    return page
