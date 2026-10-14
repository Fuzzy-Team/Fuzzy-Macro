"""Native Planters, Tools, and token-ranking editors.

Builders use the host's cards and controls. Tool actions only run on an
explicit button click; status polling never starts automation.
"""

import json
import tkinter as tk
from tkinter import ttk
import uuid

from . import calculators as calc
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


def build_planters(app, parent):
    page = _frame(app, parent)
    page.pack(fill="both", expand=True)
    mode_body = app.card(page, "Planters")
    content = _frame(app, page)
    content.pack(fill="both", expand=True)
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
            app.label(hotbar[0], "No planters selected.", dim=True).pack(anchor="w")
        for planter in selected:
            _control(app, hotbar[0], "planter_hotbar_{}_slot".format(planter),
                     planter.replace("_", " ").title(), "dropdown", numeric="int",
                     choices=[dict(label="0 - Inventory" if slot == 0 else str(slot), value=slot) for slot in range(8)])

    def changed_planter(key, value, auto):
        app.save(key, value)
        render_hotbar(auto)

    def harvest_controls(body, auto):
        prefix = "auto" if auto else "manual"
        _control(app, body, prefix + "_planters_collect_every", "Harvest Every X Hours", "textbox",
                 "Maximum grow time before harvest. 2-3 hours is recommended." if auto else "How often to collect each cycle. 2-3 hours is recommended.",
                 numeric="float", limit=4)
        full = prefix + "_planters_collect_full"
        if auto:
            automatic = "auto_planters_collect_auto"
            mutually_exclusive = {}

            def change(key, other, value):
                if value:
                    app.save(other, False)
                    mutually_exclusive[other].set(False)
                app.save(key, bool(value))

            mutually_exclusive[full] = _control(app, body, full, "Harvest When Full",
                desc="Overrides Harvest Every X Hours.", onchange=lambda value: change(full, automatic, value))
        else:
            _control(app, body, full, "Harvest When Full", desc="Overrides Harvest Every X Hours.")
        _control(app, body, "planters_collect_loot", "Collect Planter Loot",
                 desc="Collect tokens dropped after harvesting planters.")
        _control(app, body, prefix + "_planters_check", "Planter Check",
                 desc="Check inventory after looting to confirm the planter was collected.")
        if auto:
            mutually_exclusive[automatic] = _control(app, body, automatic, "Auto Harvest",
                desc="Let the macro decide when to harvest for nectar maintenance.",
                onchange=lambda value: change(automatic, full, value))
            _control(app, body, "auto_max_planters", "Max Planters", "textbox", numeric="int", limit=1)
        _buttons(app, body, [("Clear Planter Timers", lambda: _timer_reset(app, auto))])

    def manual():
        body = app.card(content, "Manual Planters")
        harvest_controls(body, False)
        for cycle in range(1, 6):
            body = app.card(content, "Cycle {}".format(cycle),
                            "Up to 3 planters per cycle. A field or planter set to None disables that slot.")
            row = _frame(app, body, True)
            row.pack(fill="x")
            for slot in range(1, 4):
                column = _frame(app, row, True)
                column.grid(row=0, column=slot - 1, sticky="nsew", padx=6)
                row.columnconfigure(slot - 1, weight=1, uniform="slots")
                app.label(column, "Slot {}".format(slot)).pack(anchor="w")
                key = "cycle{}_{}_planter".format(cycle, slot)
                _control(app, column, key, "Planter", "dropdown", choices=_choices(PLANTER_ICONS),
                         onchange=lambda value, key=key: changed_planter(key, value, False))
                _control(app, column, "cycle{}_{}_field".format(cycle, slot), "Field", "dropdown", choices=_choices(FIELD_NECTAR_ICONS))
                _control(app, column, "cycle{}_{}_gather".format(cycle, slot), "Gather in Planter Field", desc="Uses this field's Gather settings.")
                _control(app, column, "cycle{}_{}_glitter".format(cycle, slot), "Glitter", desc="Use on placement to speed growth by 25%.")
        hotbar[0] = app.card(content, "Selected Planters", "Map selected planters to hotbar slots. Slot 0 uses inventory search.")
        render_hotbar(False)

    def auto():
        body = app.card(content, "Auto Planters / Planter+")
        harvest_controls(body, True)

        def change_preset(value):
            app.save("auto_preset", value)
            for key, setting in planter_preset(value).items():
                app.save(key, setting)
            app.refresh()

        _control(app, body, "auto_preset", "Presets", "dropdown", choices=[dict(label=name.title(), value=name) for name in ("blue", "red", "white", "custom")],
                 onchange=change_preset)
        def save_gather(value):
            if app.action("setAutoPlanterGather", bool(value)) is False:
                app.status("Could not save Auto Planter gather flag.")

        data = app.action("getAutoPlanterData")
        _control(app, body, "auto_planters_gather", "Gather in Planter Fields",
            desc="Gather immediately after placement while the planter grows.", scope="local",
            value=bool(data.get("gather", False)) if isinstance(data, dict) else False,
            onchange=save_gather)
        body = app.card(content, "Nectar Priority", "Higher entries have greater priority. Maintain each nectar above its minimum percentage.")
        for index in range(5):
            _control(app, body, "auto_priority_{}_nectar".format(index), "Priority {}".format(index + 1), "dropdown", choices=_choices({nectar: nectar for nectar in NECTARS}))
            _control(app, body, "auto_priority_{}_min".format(index), "Minimum %", "textbox", numeric="int", limit=3)
        _buttons(app, body, [("Nectar Guide", lambda: app.open_image("../../webapp/assets/cheatsheet/nectar.png"))])
        restrictions = app.card(content, "Planters Allowed & Restrictions", "Restrict which fields each enabled planter can use.")
        for planter in PLANTER_ICONS:
            if planter == "none":
                continue
            section = _frame(app, restrictions, True)
            section.pack(fill="x", pady=6)
            _control(app, section, "auto_planter_" + planter, planter.replace("_", " ").title(),
                     onchange=lambda value, key="auto_planter_" + planter: changed_planter(key, bool(value), True))
            fields = _frame(app, section, True)
            controls = []
            for field in FIELD_NECTAR_ICONS:
                if field == "none":
                    continue
                key = "auto_planter_{}_field_{}".format(planter, field)
                if key not in app.settings:
                    app.save(key, True)
                controls.append((key, field))
            summary = app.label(section, "", dim=True)
            summary.pack(anchor="w")

            def update_summary(summary=summary, controls=controls):
                count = sum(bool(app.settings.get(key)) for key, _ in controls)
                summary.configure(text="Allowed fields: {}".format(count))

            def change_field(key, value, update_summary=update_summary):
                app.save(key, bool(value))
                update_summary()

            for key, field in controls:
                _control(app, fields, key, field.replace("_", " ").title(),
                         onchange=lambda value, key=key, change_field=change_field: change_field(key, value))

            def toggle(fields=fields):
                if fields.winfo_manager():
                    fields.pack_forget()
                else:
                    fields.pack(fill="x", pady=6)

            app.button(section, "Show / Hide Allowed Fields", toggle).pack(anchor="w")
            summaries.append(update_summary)
            update_summary()
        body = app.card(content, "Allowed Fields", "Fields the macro can plant in.")
        for field in FIELD_NECTAR_ICONS:
            if field != "none":
                _control(app, body, "auto_field_" + field, field.replace("_", " ").title())
        hotbar[0] = app.card(content, "Selected Planters", "Map enabled planters to hotbar slots. Slot 0 uses inventory search.")
        render_hotbar(True)
        body = app.card(content, "Wax from Planters", "Reference guide for wax drops from different planters.")
        _buttons(app, body, [("Wax Guide", lambda: app.open_image("../../webapp/assets/cheatsheet/planters.png"))])

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
            app.card(content, "Planters are Off", "The macro will not harvest or plant any planters. Select Manual or Auto to enable planter management.")

    def change_mode(value):
        app.save("planters_mode", calc.parse_int(value))
        render(value)

    _control(app, mode_body, "planters_mode", "Mode", "dropdown", numeric="int",
             choices=[dict(label=label, value=value) for value, label in enumerate(("Off", "Manual", "Auto"))], onchange=change_mode)
    render(app.settings["planters_mode"])
    app.refresh_planters = lambda: render(app.settings["planters_mode"])
    _buttons(app, page, [("Export Settings", lambda: _export_planters(app)),
                         ("Import Settings", lambda: _import_planters(app))])
    return page


def _tool_hotkeys(app, body, start_key, default_start="Not set"):
    app.label(body, "Start hotkey: {}. Stop hotkey: {}. Change these in Config.".format(
        app.settings.get(start_key) or default_start,
        app.settings.get("stop_keybind") or "F3"), dim=True).pack(anchor="w", pady=8)


def _tool_status(app, body, getter, start_action, stop_action, rows):
    """Poll an existing runner; cancel the Tk callback when its page is destroyed."""
    labels = [(app.label(body, ""), formatter) for formatter in rows]
    for label, _ in labels:
        label.pack(anchor="w", pady=3)
    buttons = _buttons(app, body, [])

    def invoke(action):
        result = action()
        if isinstance(result, dict) and result.get("message"):
            app.status(result["message"])
        refresh()

    start = app.button(buttons, "Start", lambda: invoke(start_action))
    stop = app.button(buttons, "Stop", lambda: invoke(stop_action))
    timer = [None]
    running = [False]
    texts = [None] * len(labels)

    def refresh():
        status = app.action(getter)
        if not isinstance(status, dict):
            return
        for index, (label, formatter) in enumerate(labels):
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


def _build_autoclicker(app, parent):
    body = app.card(parent, "Auto Clicker", "Repeatedly left-clicks at a configurable interval.")
    interval = _control(app, body, "autoclicker_interval_ms", "Click Interval (ms)", "textbox",
                        "Lower values click faster.", scope="local", numeric="int", limit=4, value=100,
                        onchange=lambda value: interval.set(max(10, calc.parse_int(value, 100))))
    delay = _control(app, body, "autoclicker_start_delay_seconds", "Start Delay (seconds)", "textbox",
                     "Wait before clicking begins.", scope="local", numeric="int", limit=2, value=3,
                     onchange=lambda value: delay.set(min(10, max(0, calc.parse_int(value, 3)))))

    def start():
        milliseconds = max(10, calc.parse_int(interval.get(), 100))
        seconds = min(10, max(0, calc.parse_int(delay.get(), 3)))
        interval.set(milliseconds)
        delay.set(seconds)
        return app.action("startAutoClickerTool", milliseconds, seconds)

    _tool_hotkeys(app, body, "autoclicker_keybind")
    _tool_status(app, body, "getAutoClickerStatus", start,
                 lambda: app.action("stopAutoClickerTool"),
                 [lambda status: status.get("message") or "Ready"])


def _build_hotbar_buff(app, parent):
    body = app.card(parent, "Hotbar Buff", "Runs this tool's hotbar timers while you play.")
    _tool_hotkeys(app, body, "hotbar_buff_start_keybind", "F4")
    _tool_status(app, body, "getHotbarBuffStatus", lambda: app.action("startHotbarBuffTool"),
                 lambda: app.action("stopHotbarBuffTool"), [
                     lambda status: "Status: {}".format(status.get("state") or "idle"),
                     lambda status: "Last Slot: {}".format("Slot {}".format(status["last_slot"]) if status.get("last_slot") else "None"),
                     lambda status: status.get("message") or "Ready"])

    def slot_builder(slot, parent):
        body = app.card(parent, "Slot {}".format(slot), "Enable this slot and set how often it should be pressed.")
        prefix = "hotbar_buff_tool_slot{}_".format(slot)
        _control(app, body, prefix + "enabled", "Enabled")
        _control(app, body, prefix + "use_every_value", "Use Every", "textbox", numeric="float")
        _control(app, body, prefix + "use_every_format", "Units", "dropdown",
                 choices=[dict(label="Secs", value="secs"), dict(label="Mins", value="mins")])

    app.subtabs(body, [("slot{}".format(slot), "[{}]".format(slot),
                        lambda parent, slot=slot: slot_builder(slot, parent)) for slot in range(1, 8)],
                "activeHotbarBuffToolSlot")


def _build_auto_gifted(app, parent):
    body = app.card(parent, "Auto Gifted Basic Bee Tool (BETA)",
                    "Focuses Roblox, waits for the capture delay, captures your mouse position as the bee slot, "
                    "then alternates Basic Egg and Royal Jelly until a Gifted Basic Bee or a paused result.")
    app.label(body, "Stop the main macro first, keep Auto-Jelly disabled in-game, and keep Roblox visible. "
                   "Watch this beta tool while it runs. OCR may misread results.", dim=True).pack(anchor="w", pady=8)
    _tool_hotkeys(app, body, "auto_gifted_basic_bee_start_keybind")
    delay = _control(app, body, "auto-gifted-basic-bee-delay", "Capture Delay (seconds)", "textbox",
                     scope="local", numeric="int", value=3,
                     onchange=lambda value: delay.set(min(10, max(1, calc.parse_int(value, 3)))))
    pause = {}
    for name, title, default in (("gifted_other", "Gifted Non-Basic", True),
                                 ("legendary", "Legendary", False), ("mythic", "Mythic", True)):
        pause[name] = _control(app, body, "auto-gifted-basic-bee-pause-" + name.replace("_", "-"),
                               "Pause On " + title, scope="local", value=default)

    def start():
        seconds = min(10, max(1, calc.parse_int(delay.get(), 3)))
        delay.set(seconds)
        settings = dict(pause_on_gifted_basic=True, pause_on_basic=False, pause_on_other=False)
        settings.update({"pause_on_" + name: bool(control.get()) for name, control in pause.items()})
        return app.action("startAutoGiftedBasicBeeTool", seconds, settings)

    _tool_status(app, body, "getAutoGiftedBasicBeeStatus", start,
                 lambda: app.action("stopAutoGiftedBasicBeeTool"), [
                     lambda status: "Status: {}".format(status.get("state") or "idle"),
                     lambda status: "Bee Slot: {}".format("{}, {}".format(status["bee_slot_x"], status["bee_slot_y"])
                         if status.get("bee_slot_x") is not None and status.get("bee_slot_y") is not None else "Not captured"),
                     lambda status: "Basic Eggs: {}".format(status.get("basic_eggs_used", 0)),
                     lambda status: "Royal Jellies: {}".format(status.get("royal_jellies_used", 0)),
                     lambda status: "Total Rolls: {}".format(status.get("rolls", 0)),
                     lambda status: "Message: {}".format(status.get("message") or "Ready"),
                     lambda status: "Last OCR Read: {}".format(status.get("last_detected_text") or "None")])


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


def _build_bond_calculator(app, parent):
    body = app.card(parent, "Bond/Treat Calculator", "Calculate treat count and honey cost between bond levels. "
                    "Find your Bond from Treats % in your character stats in BSS.")
    start = _control(app, body, "bond-calc-start-level", "Initial Level", "dropdown", scope="local", value=1,
                     choices=[dict(label=str(level), value=level) for level in range(1, 25)], numeric="int")
    end = _control(app, body, "bond-calc-end-level", "Final Level", "dropdown", scope="local", value=25,
                   choices=[dict(label=str(level), value=level) for level in range(2, 26)], numeric="int")
    bonus = _control(app, body, "bond-calc-bonus", "Bond from Treats (%)", "textbox", scope="local", value=20, numeric="float")
    bees = _control(app, body, "bond-calc-bee-count", "# of Bees", "textbox", scope="local", value=50, numeric="int")
    warning = app.label(body, "")
    warning.pack(anchor="w")
    totals = [app.label(body, "") for _ in range(4)]
    for label in totals:
        label.pack(anchor="w", pady=3)
    tree = _tree(app, body, [("level", "Level"), ("bond", "Bond Required"), ("treats", "Treats Needed"),
                            ("one", "Cost per Bee"), ("bees", "Cost for 50 Bees")])

    def update():
        result = calc.calculate_bond(start.get(), end.get(), bonus.get(), bees.get())
        bonus.set(result["bonus_percent"])
        bees.set(result["bee_count"])
        count = result["bee_count"]
        bee_label = "{} Bee{}".format(count, "" if count == 1 else "s")
        warning.configure(text=result["warning"])
        labels = ("Total Bond", "Treats Needed ({})".format(bee_label), "Cost (1 Bee)", "Cost ({})".format(bee_label))
        for label, title, key in zip(totals, labels, ("total_bond", "total_treats", "cost_one", "cost_bees")):
            label.configure(text="{}: {}".format(title, calc.format_compact_honey(result[key])))
        tree.heading("bees", text="Cost for " + bee_label)
        tree.delete(*tree.get_children())
        for row in result["rows"]:
            tree.insert("", "end", values=(row["label"], calc.format_whole_number(row["bond"]),
                calc.format_whole_number(row["treats"]), calc.format_compact_honey(row["costPerBee"]),
                calc.format_compact_honey(row["costForBees"])))

    _watch_calculator(body, [start, end, bonus, bees], update)


def _build_ticket_calculator(app, parent):
    body = app.card(parent, "Ticket Price Calculator", "Calculate honey costs for the Bee Swarm Simulator ticket shop. "
                    "Enter the price of your next ticket to see common bundles.")
    units = [dict(label=label, value=unit) for unit, label in calc.HONEY_UNITS]
    price = _control(app, body, "ticket-calc-next-price", "Price of Next Ticket", "textbox", scope="local", value=100, numeric="float")
    price_unit = _control(app, body, "ticket-calc-next-price-unit", "Price Units", "dropdown", scope="local", value=1000000, numeric="int", choices=units)
    custom = _control(app, body, "ticket-calc-custom-amount", "Custom Amount", "textbox", scope="local", value=1, numeric="int")
    budget = _control(app, body, "ticket-calc-budget", "Budget", "textbox", scope="local", value=0, numeric="float")
    budget_unit = _control(app, body, "ticket-calc-budget-unit", "Budget Units", "dropdown", scope="local", value=1000000, numeric="int", choices=units)
    warning = app.label(body, "")
    warning.pack(anchor="w")
    tree = _tree(app, body, [("tickets", "Tickets"), ("cost", "Cost")], height=6)

    def update():
        result = calc.calculate_tickets(price.get(), price_unit.get(), custom.get(), budget.get(), budget_unit.get())
        custom.set(result["custom_amount"])
        warning.configure(text=result["warning"])
        tree.delete(*tree.get_children())
        for amount, purchase in result["rows"]:
            label = "{} Tickets".format(calc.format_whole_number(amount))
            if amount == result["custom_amount"] and amount not in calc.TICKET_CALC_PRESETS:
                label += " (Custom)"
            tree.insert("", "end", values=(label, calc.format_compact_honey(purchase["totalCost"])))
        tree.insert("", "end", values=("Max ({} Tickets)".format(calc.format_whole_number(result["budget"]["tickets"])),
                                       calc.format_compact_honey(result["budget"]["totalCost"])))

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
