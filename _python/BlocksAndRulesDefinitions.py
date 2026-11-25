"""
BotanicGarden voxel editor.

Edits the three voxel definition files in voxel_data/:
    voxel_colors.json      index -> R, G, B, A (0..1)
    voxel_data.json        index -> s0..s7 (0..65535)
    voxel_editor_aux.json  names, groups and type labels (editor + in-game block selector only)

Field meanings come from voxel_data/schemas/type_<id>_<name>.json (see the README there).

Run:  python _python/BlocksAndRulesDefinitions.py [data_dir]
      (data_dir defaults to <project>/voxel_data)

How it works:
  * Single-click selects a row. It never changes the editor, so you can click or arrow through
    rows to compare them: the selected row's values show in the "vs" column next to each field.
  * Double-click or Enter opens a row in the editor. Edits apply right away (undo with Ctrl+Z).
    Nothing is written to disk until Ctrl+S. Every save first copies the old files to
    _backups/autosave/<time>/ (the last 20 are kept).

Shortcuts: Ctrl+S save, Ctrl+Z / Ctrl+Y undo / redo, Ctrl+N new voxel, Ctrl+D duplicate,
Ctrl+F search, Alt+Left back. In the table: Enter edit, Del delete, F2 change index,
Ctrl+C copy, Ctrl+V paste parameters, Ctrl+Shift+V paste colour.
"""

from __future__ import annotations

import copy
import datetime
import json
import os
import re
import shutil
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import colorchooser, messagebox, simpledialog, ttk

# ==============================================================================
# CONSTANTS
# ==============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_PATH = os.path.dirname(SCRIPT_DIR)
DEFAULT_DATA_DIR = os.path.join(PROJECT_PATH, "voxel_data")
STATE_FILE = os.path.join(SCRIPT_DIR, ".editor_state.json")

TYPE_SIZE = 2048            # indices per type (type = index >> 11)
TYPE_COUNT = 32
SLOTS = 8                   # s0..s7
MAX_INDEX = 65535
MAX_VALUE = 65535           # C# reads index and s0..s7 as ushort
SIGNED_LIMIT = 32768        # the render shader samples through a signed isampler3D
STEPS_PER_SECOND = 50       # WorldRender._timePerSimulation = 0.02 s
MAX_BACKUPS = 20
MAX_UNDO = 300


def type_of(index: int) -> int:
    return max(0, min(TYPE_COUNT - 1, index // TYPE_SIZE))


def type_range(t: int) -> tuple[int, int]:
    return t * TYPE_SIZE, t * TYPE_SIZE + TYPE_SIZE - 1


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(int(round(clamp01(c) * 255)) for c in (r, g, b)))


def hex_to_rgb(text: str) -> tuple[float, float, float] | None:
    m = re.fullmatch(r"\s*#?([0-9a-fA-F]{6})\s*", text)
    if not m:
        return None
    h = m.group(1)
    return tuple(round(int(h[i:i + 2], 16) / 255.0, 4) for i in (0, 2, 4))


def fmt_seconds(s: float) -> str:
    if s < 120:
        return f"{s:.2g} s" if s < 1 else f"{s:.3g} s"
    if s < 7200:
        return f"{s / 60:.3g} min"
    return f"{s / 3600:.3g} h"


def trailing_number(text: str) -> str | None:
    m = re.search(r"(\d+)$", text)
    return m.group(1) if m else None


def increment_name(name: str, taken: set[str]) -> str:
    """seed_3 -> seed_4 (or the next free number); names without a number get ' copy'."""
    m = re.match(r"^(.*?)(\d+)$", name)
    if m:
        base, n = m.group(1), int(m.group(2))
        k = n + 1
        while f"{base}{k}" in taken:
            k += 1
        return f"{base}{k}"
    cand = f"{name} copy"
    k = 2
    while cand in taken:
        cand = f"{name} copy {k}"
        k += 1
    return cand


# ==============================================================================
# SCHEMAS (voxel_data/schemas/*.json)
# ==============================================================================

class FieldSpec:
    def __init__(self, slot: int, d: dict):
        self.slot = slot
        self.label = d.get("label", f"s{slot}")
        self.short = d.get("short", self.label)
        self.kind = d.get("kind", "number")
        self.description = d.get("description", "")
        self.default = d.get("default")
        self.zero = d.get("zero")
        self.scale = d.get("scale")
        self.target = d.get("target") or {}
        self.read = d.get("read", True)
        self.max = d.get("max")  # largest value the shaders can handle, if below 65535

    def target_type(self):
        return self.target.get("type")

    def target_variants(self):
        v = self.target.get("variant")
        if v is None:
            return None
        return set(v) if isinstance(v, list) else {v}


def _slot(key: str) -> int:
    if not re.fullmatch(r"s[0-7]", key):
        raise ValueError(f"unknown field '{key}' (expected s0..s7)")
    return int(key[1:])


class TypeSchema:
    def __init__(self, d: dict, path: str):
        self.path = path
        self.type = int(d["type"])
        self.name = d.get("name", f"Type {self.type}")
        self.description = d.get("description", "")
        self.shader = d.get("shader", "")
        vf = d.get("variant_field")
        self.variant_slot = _slot(vf) if vf else None
        self.fields = {_slot(k): FieldSpec(_slot(k), v) for k, v in d.get("fields", {}).items()}
        self.variants = {}
        for k, v in d.get("variants", {}).items():
            self.variants[int(k)] = {
                "name": v.get("name", f"Variant {k}"),
                "description": v.get("description", ""),
                "fields": {_slot(fk): FieldSpec(_slot(fk), fv) for fk, fv in v.get("fields", {}).items()},
            }

    def variant_of(self, values):
        return values[self.variant_slot] if self.variant_slot is not None else None

    def variant_name(self, v) -> str:
        if v in self.variants:
            return self.variants[v]["name"]
        return f"unknown ({v})"

    def specs(self, values) -> list:
        out = [None] * SLOTS
        for s, f in self.fields.items():
            out[s] = f
        v = self.variant_of(values)
        if v in self.variants:
            for s, f in self.variants[v]["fields"].items():
                out[s] = f
        return out

    def describe(self, values) -> str:
        v = self.variant_of(values)
        if v in self.variants and self.variants[v]["description"]:
            return self.variants[v]["description"]
        return self.description


def load_schemas(folder: str):
    schemas, errors = {}, []
    if not os.path.isdir(folder):
        return schemas, [f"No schema folder at {folder}; fields are shown as plain s0..s7."]
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(folder, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                sch = TypeSchema(json.load(f), path)
            schemas[sch.type] = sch
        except Exception as e:  # keep going with the other files
            errors.append(f"{fn}: {e}")
    return schemas, errors


# ==============================================================================
# DATA MODEL (the three JSON files)
# ==============================================================================

class DataPaths:
    def __init__(self, data_dir: str):
        self.data_dir = os.path.abspath(data_dir)
        self.colors = os.path.join(self.data_dir, "voxel_colors.json")
        self.structs = os.path.join(self.data_dir, "voxel_data.json")
        self.aux = os.path.join(self.data_dir, "voxel_editor_aux.json")
        self.schemas = os.path.join(self.data_dir, "schemas")
        self.backups = os.path.join(os.path.dirname(self.data_dir), "_backups", "autosave")

    def files(self):
        return (self.colors, self.structs, self.aux)

    def mtimes(self):
        return {p: (os.path.getmtime(p) if os.path.exists(p) else None) for p in self.files()}


def _read_json(path, default):
    if not os.path.exists(path):
        return default, f"{os.path.basename(path)} not found, starting empty"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f), None


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


class Model:
    def __init__(self):
        self.colors: dict[int, list[float]] = {}    # index -> [r, g, b, a]
        self.structs: dict[int, list[int]] = {}     # index -> [s0..s7]
        self.names: dict[int, str] = {}
        self.groups: dict[str, list[int]] = {}      # insertion order = display order
        self.type_names: dict[int, str] = {}
        self.aux_extra: dict = {}                   # unknown aux keys, written back untouched

    # ---- files ----
    def load(self, paths: DataPaths) -> list[str]:
        msgs = []
        self.__init__()
        raw, msg = _read_json(paths.colors, [])
        if msg:
            msgs.append(msg)
        for item in raw:
            n = {k.lower(): v for k, v in item.items()}
            self.colors[int(n.get("index", 0))] = [float(n.get("r", 0)), float(n.get("g", 0)),
                                                   float(n.get("b", 0)), float(n.get("a", 1))]
        raw, msg = _read_json(paths.structs, [])
        if msg:
            msgs.append(msg)
        for item in raw:
            n = {k.lower(): v for k, v in item.items()}
            self.structs[int(n.get("index", 0))] = [int(n.get(f"s{i}", 0)) for i in range(SLOTS)]
        raw, msg = _read_json(paths.aux, {})
        if msg:
            msgs.append(msg)
        self.names = {int(k): v for k, v in raw.get("voxel_names", {}).items() if str(v).strip()}
        for g, members in raw.get("groups", {}).items():
            self.groups[g] = sorted({int(x) for x in members})
        self.type_names = {int(k): v for k, v in raw.get("type_names", {}).items()}
        self.aux_extra = {k: v for k, v in raw.items() if k not in ("voxel_names", "groups", "type_names")}
        return msgs

    def save(self, paths: DataPaths):
        os.makedirs(paths.data_dir, exist_ok=True)
        _write_json(paths.colors, [
            {"Index": i, "R": round(c[0], 4), "G": round(c[1], 4), "B": round(c[2], 4), "A": round(c[3], 4)}
            for i, c in sorted(self.colors.items())])
        _write_json(paths.structs, [
            dict({"index": i}, **{f"s{k}": v[k] for k in range(SLOTS)}) for i, v in sorted(self.structs.items())])
        aux = {
            "voxel_names": {str(i): n for i, n in sorted(self.names.items())},
            "groups": {g: sorted(m) for g, m in self.groups.items()},
            "type_names": {str(t): self.type_names.get(t, "") for t in range(TYPE_COUNT)},
        }
        aux.update(self.aux_extra)
        _write_json(paths.aux, aux)

    # ---- undo snapshots ----
    def state(self):
        return copy.deepcopy((self.colors, self.structs, self.names, self.groups, self.type_names))

    def restore(self, st):
        self.colors, self.structs, self.names, self.groups, self.type_names = copy.deepcopy(st)

    # ---- queries ----
    def indices(self) -> list[int]:
        return sorted(set(self.colors) | set(self.structs) | set(self.names))

    def exists(self, idx) -> bool:
        return idx in self.colors or idx in self.structs or idx in self.names

    def values(self, idx) -> list[int]:
        return list(self.structs.get(idx, [0] * SLOTS))

    def name(self, idx) -> str:
        return self.names.get(idx, "")

    def groups_of(self, idx) -> list[str]:
        return [g for g, m in self.groups.items() if idx in m]

    def free_index(self, t, start=None, taken=None):
        lo, hi = type_range(t)
        if t == 0:
            lo = 2  # 0 = air, 1 = also treated as empty by the renderer
        taken = set(self.indices()) if taken is None else taken
        start = lo if start is None else min(max(start, lo), hi)
        for c in list(range(start, hi + 1)) + list(range(lo, start)):
            if c not in taken:
                return c
        return None

    def free_block(self, t, n, start, taken):
        lo, hi = type_range(t)
        lo = max(lo, 2)
        for s in list(range(max(start, lo), hi - n + 2)) + list(range(lo, hi - n + 2)):
            if all(s + k not in taken for k in range(n)):
                return s
        return None

    def remove(self, idx):
        self.colors.pop(idx, None)
        self.structs.pop(idx, None)
        self.names.pop(idx, None)
        for m in self.groups.values():
            if idx in m:
                m.remove(idx)


def backup_files(paths: DataPaths):
    existing = [p for p in paths.files() if os.path.exists(p)]
    if not existing:
        return None
    dest = os.path.join(paths.backups, datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    os.makedirs(dest, exist_ok=True)
    for p in existing:
        shutil.copy2(p, dest)
    dirs = sorted(d for d in os.listdir(paths.backups) if os.path.isdir(os.path.join(paths.backups, d)))
    for d in dirs[:-MAX_BACKUPS]:
        shutil.rmtree(os.path.join(paths.backups, d), ignore_errors=True)
    return dest


# ==============================================================================
# SMALL WIDGET HELPERS
# ==============================================================================

class TipWindow:
    """One floating tooltip shared by the whole app."""

    def __init__(self, root):
        self.root = root
        self.win = None

    def show(self, x, y, text):
        self.hide()
        if not text:
            return
        w = tk.Toplevel(self.root)
        w.wm_overrideredirect(True)
        w.wm_geometry(f"+{x + 14}+{y + 18}")
        tk.Label(w, text=text, justify="left", background="#FFFDE7", foreground="#222",
                 relief="solid", borderwidth=1, wraplength=440, padx=7, pady=5).pack()
        self.win = w

    def hide(self):
        if self.win is not None:
            self.win.destroy()
            self.win = None


class Tooltip:
    def __init__(self, tip: TipWindow, widget, text):
        self.tip, self.widget, self.text, self.job = tip, widget, text, None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, e):
        self._cancel()
        self.job = self.widget.after(450, lambda: self.tip.show(
            e.x_root, e.y_root, self.text() if callable(self.text) else self.text))

    def _leave(self, _e):
        self._cancel()
        self.tip.hide()

    def _cancel(self):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.inner = ttk.Frame(self.canvas)
        win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(win, width=e.width))
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.bind_all("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        if w is None or not str(w).startswith(str(self)) or w.winfo_class() in ("Listbox", "Text"):
            return
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")


class ParamRow:
    def __init__(self, slot, spec, var, widget, hint, compare, jump):
        self.slot, self.spec, self.var, self.widget = slot, spec, var, widget
        self.hint, self.compare, self.jump = hint, compare, jump


# ==============================================================================
# NEW VOXEL DIALOG
# ==============================================================================

class NewVoxelDialog(simpledialog.Dialog):
    def __init__(self, app: "App", type_id: int, group: str | None):
        self.app, self.init_type, self.init_group = app, type_id, group
        self.result = None
        super().__init__(app.root, "New voxel")

    def body(self, master):
        app = self.app
        master.columnconfigure(1, weight=1)
        self.type_var = tk.StringVar(value=self._type_text(self.init_type))
        self.part_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.group_var = tk.StringVar(value=self.init_group or "(none)")
        self.index_var = tk.StringVar()

        rows = [("Type", None), ("Part", None), ("Name", None), ("Group", None), ("Index", None)]
        for r, (lbl, _) in enumerate(rows):
            ttk.Label(master, text=lbl).grid(row=r, column=0, sticky="w", padx=(4, 8), pady=3)
        self.type_cb = ttk.Combobox(master, textvariable=self.type_var, state="readonly", width=34,
                                    values=[self._type_text(t) for t in range(TYPE_COUNT)])
        self.type_cb.grid(row=0, column=1, sticky="ew", pady=3)
        self.type_cb.bind("<<ComboboxSelected>>", lambda e: self._type_changed())
        self.part_cb = ttk.Combobox(master, textvariable=self.part_var, state="readonly", width=34)
        self.part_cb.grid(row=1, column=1, sticky="ew", pady=3)
        name_entry = ttk.Entry(master, textvariable=self.name_var)
        name_entry.grid(row=2, column=1, sticky="ew", pady=3)
        group_cb = ttk.Combobox(master, textvariable=self.group_var,
                                values=["(none)"] + list(app.model.groups))
        group_cb.grid(row=3, column=1, sticky="ew", pady=3)
        group_cb.bind("<<ComboboxSelected>>", lambda e: self._suggest_index())
        ttk.Spinbox(master, textvariable=self.index_var, from_=0, to=MAX_INDEX, width=10).grid(
            row=4, column=1, sticky="w", pady=3)
        ttk.Label(master, text="Type a new name in Group to create it. Empty links are filled in\n"
                               "from the group when there is exactly one matching part.",
                  style="Hint.TLabel").grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self._type_changed()
        return name_entry

    def _type_text(self, t):
        lo, hi = type_range(t)
        return f"{t} · {self.app.type_label(t)}  ({lo}-{hi})"

    def _type(self):
        return int(self.type_var.get().split("·")[0])

    def _type_changed(self):
        sch = self.app.schemas.get(self._type())
        if sch and sch.variants:
            vals = [f"{k} · {v['name']}" for k, v in sorted(sch.variants.items())]
            self.part_cb.configure(values=vals, state="readonly")
            self.part_var.set(vals[0])
        else:
            self.part_cb.configure(values=[], state="disabled")
            self.part_var.set("")
        self._suggest_index()

    def _suggest_index(self):
        t = self._type()
        members = [i for i in self.app.model.groups.get(self.group_var.get(), []) if type_of(i) == t]
        start = max(members) + 1 if members else None
        idx = self.app.model.free_index(t, start)
        self.index_var.set("" if idx is None else str(idx))

    def validate(self):
        try:
            idx = int(self.index_var.get())
        except ValueError:
            messagebox.showerror("New voxel", "Index must be a number.", parent=self)
            return False
        if not 0 <= idx <= MAX_INDEX:
            messagebox.showerror("New voxel", "Index must be 0..65535.", parent=self)
            return False
        if self.app.model.exists(idx):
            messagebox.showerror("New voxel", f"Index {idx} is already used by {self.app.nice(idx)}.", parent=self)
            return False
        return True

    def apply(self):
        part = self.part_var.get()
        group = self.group_var.get().strip()
        self.result = {
            "index": int(self.index_var.get()),
            "variant": int(part.split("·")[0]) if part else None,
            "name": self.name_var.get().strip(),
            "group": None if group in ("", "(none)") else group,
        }


# ==============================================================================
# MAIN APP
# ==============================================================================

S_COLS = [f"s{i}" for i in range(SLOTS)]
TABLE_COLS = ["name", "part", "groups"] + S_COLS + ["issues"]


class App:
    def __init__(self, root: tk.Tk, data_dir: str):
        self.root = root
        self.paths = DataPaths(data_dir)
        self.schemas, schema_errors = load_schemas(self.paths.schemas)
        self.model = Model()
        load_msgs = self.model.load(self.paths)
        self.saved_state = self.model.state()
        self.file_mtimes = self.paths.mtimes()

        self.undo_stack: list = []
        self.redo_stack: list = []
        self._coalesce = None
        self.open_idx: int | None = None
        self.compare_idx: int | None = None
        self.history: list[int] = []
        self.clipboard = None
        self.sort_col, self.sort_rev = "#0", False
        self._loading = False
        self._param_sig = None
        self.param_rows: list[ParamRow] = []
        self._swatches: dict = {}
        self._cell_tip = (None, None, None)
        self._last_focus_check = 0.0

        self.tip = TipWindow(root)
        self._setup_style()
        self._build_ui()
        self._bind_keys()
        self.refresh_all()
        self._restore_ui_state()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        msgs = load_msgs + schema_errors
        self.status(" · ".join(msgs) if msgs else
                    f"Loaded {len(self.model.indices())} voxels and {len(self.schemas)} schemas. "
                    "Double-click a row to edit it; single-click only selects (for comparing).")

    # ------------------------------------------------------------------ style
    def _setup_style(self):
        st = ttk.Style(self.root)
        if "clam" in st.theme_names():
            st.theme_use("clam")
        base = tkfont.nametofont("TkDefaultFont")
        self.font_bold = base.copy()
        self.font_bold.configure(weight="bold")
        self.font_title = base.copy()
        self.font_title.configure(size=base.cget("size") + 5, weight="bold")
        self.font_section = base.copy()
        self.font_section.configure(size=base.cget("size") + 1, weight="bold")
        st.configure("Title.TLabel", font=self.font_title)
        st.configure("Section.TLabel", font=self.font_section, foreground="#1F4E79")
        st.configure("Hint.TLabel", foreground="#666666")
        st.configure("Dim.TLabel", foreground="#999999")
        st.configure("Problem.TLabel", foreground="#B3261E")
        st.configure("Diff.TLabel", foreground="#C25E00", font=self.font_bold)
        st.configure("Field.TLabel", font=self.font_bold)
        st.configure("Unused.TLabel", foreground="#9A9A9A")
        for cls in ("TEntry", "TCombobox", "TSpinbox"):
            st.configure(f"Bad.{cls}", fieldbackground="#FFD7D7")
        st.configure("Treeview", rowheight=22)
        # Don't let the mouse wheel change combobox / spinbox values by accident: it scrolls instead.
        for cls in ("TCombobox", "TSpinbox"):
            self.root.bind_class(cls, "<MouseWheel>", lambda e: None)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = self.root
        root.geometry("1560x900")
        root.minsize(1100, 640)

        # toolbar
        bar = ttk.Frame(root, padding=(8, 6))
        bar.pack(fill="x")
        def btn(text, cmd, tip):
            b = ttk.Button(bar, text=text, command=cmd)
            b.pack(side="left", padx=2)
            Tooltip(self.tip, b, tip)
            return b
        btn("＋ New", self.new_voxel, "Create a voxel at the first free index of a type (Ctrl+N)")
        btn("⧉ Duplicate", self.duplicate_selection,
            "Copy the selected voxels to free indices (Ctrl+D). Links between the copied voxels are "
            "pointed at the copies. To copy a whole species, use Duplicate on the group.")
        btn("🗑 Delete", self.delete_selection, "Delete the selected voxels (Del)")
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        self.undo_btn = btn("↶ Undo", self.undo, "Ctrl+Z")
        self.redo_btn = btn("↷ Redo", self.redo, "Ctrl+Y")
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        btn("💾 Save", self.save, "Write the three JSON files (Ctrl+S). The old files are backed up first.")
        btn("⟳ Reload", self.reload, "Re-read the JSON files and the schemas from disk")

        ttk.Label(bar, text="Search").pack(side="left", padx=(18, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_table())
        self.search_entry = ttk.Entry(bar, textvariable=self.search_var, width=30)
        self.search_entry.pack(side="left")
        self.search_entry.bind("<Escape>", lambda e: self.search_var.set(""))
        Tooltip(self.tip, self.search_entry,
                "Matches index, name, part and group. A range like 4096-4120 also works. (Ctrl+F, Esc clears)")
        self.count_lbl = ttk.Label(bar, style="Hint.TLabel")
        self.count_lbl.pack(side="right", padx=6)

        self.status_var = tk.StringVar()
        ttk.Label(root, textvariable=self.status_var, relief="sunken", anchor="w",
                  padding=(6, 3)).pack(fill="x", side="bottom")

        self.paned = ttk.PanedWindow(root, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=6, pady=(0, 4))
        left = ttk.Frame(self.paned, padding=4)
        center = ttk.Frame(self.paned, padding=4)
        right = ttk.Frame(self.paned, padding=(4, 4, 0, 4))
        self.paned.add(left, weight=1)
        self.paned.add(center, weight=3)
        self.paned.add(right, weight=2)
        self._build_nav(left)
        self._build_table(center)
        self._build_editor(right)

    # ---- navigator (types / groups)
    def _build_nav(self, parent):
        ttk.Label(parent, text="Types and groups", style="Section.TLabel").pack(anchor="w", pady=(0, 4))
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        self.nav = ttk.Treeview(frame, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.nav.yview)
        self.nav.configure(yscrollcommand=vsb.set)
        self.nav.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.nav.column("#0", width=220)
        self.nav.tag_configure("problem", foreground="#B3261E")
        self.nav.tag_configure("type", font=self.font_bold)
        self.nav.bind("<<TreeviewSelect>>", lambda e: self.refresh_table())
        self.nav.bind("<Button-3>", self._nav_menu)
        # Double-click is left to the treeview (it expands / collapses a type); rename is F2 or the button.
        self.nav.bind("<F2>", lambda e: self.rename_nav_item())
        self.nav.bind("<Motion>", self._nav_motion)
        self.nav.bind("<Leave>", lambda e: self._hide_nav_tip())
        self._nav_tip = (None, None)

        grid = ttk.Frame(parent)
        grid.pack(fill="x", pady=(6, 0))
        for i, (text, cmd, tip) in enumerate([
            ("New group", self.new_group, "New group from the selected rows"),
            ("Rename", self.rename_nav_item, "Rename the selected group or type label (F2)"),
            ("Duplicate", self.duplicate_nav_group,
             "Copy the whole group as a new species: new indices, links inside the group pointed at the "
             "copies, a new species id, names renumbered (seed_3 -> seed_4)"),
            ("Delete group", self.delete_nav_group, "Delete the group (its voxels stay)"),
        ]):
            b = ttk.Button(grid, text=text, command=cmd)
            b.grid(row=i // 2, column=i % 2, sticky="ew", padx=1, pady=1)
            Tooltip(self.tip, b, tip)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

    # ---- table
    def _build_table(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=TABLE_COLS, show="tree headings", selectmode="extended")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        widths = {"#0": 76, "name": 124, "part": 96, "groups": 70, "issues": 36}
        self.tree.heading("#0", text="Index", command=lambda: self.sort_by("#0"))
        self.tree.column("#0", width=widths["#0"], minwidth=70, stretch=False)
        for c in TABLE_COLS:
            self.tree.heading(c, text={"name": "Name", "part": "Part", "groups": "Groups",
                                       "issues": "⚠"}.get(c, c), command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=widths.get(c, 48), minwidth={"name": 90, "part": 70}.get(c, 32),
                             anchor="w" if c in ("name", "part", "groups") else "center", stretch=False)
        self.tree.tag_configure("problem", foreground="#B3261E")
        self.tree.tag_configure("open", background="#FFF1B8")

        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_table_select())
        self.tree.bind("<Double-1>", self._on_table_double)
        self.tree.bind("<Button-1>", self._on_table_click, add="+")
        self.tree.bind("<Return>", lambda e: self.open_selected())
        self.tree.bind("<Delete>", lambda e: self.delete_selection())
        self.tree.bind("<F2>", lambda e: self.change_index())
        self.tree.bind("<Button-3>", self._table_menu)
        self.tree.bind("<Motion>", self._table_motion)
        self.tree.bind("<Leave>", lambda e: self._hide_cell_tip())
        self._bind_shortcut(self.tree, ["<Control-c>", "<Control-C>"], self.copy_voxel)
        self._bind_shortcut(self.tree, ["<Control-v>"], self.paste_params)
        self._bind_shortcut(self.tree, ["<Control-V>"], self.paste_color)
        self._bind_shortcut(self.tree, ["<Control-a>", "<Control-A>"],
                            lambda: self.tree.selection_set(self.tree.get_children()))

    # ---- editor
    def _build_editor(self, parent):
        sf = ScrollableFrame(parent)
        sf.pack(fill="both", expand=True)
        host = sf.inner
        self.placeholder = ttk.Label(
            host, padding=24, justify="left", style="Hint.TLabel", wraplength=440,
            text="Double-click a row (or select it and press Enter) to edit it.\n\n"
                 "While a voxel is open, single-clicking other rows doesn't touch the editor: "
                 "their values show in the \"vs\" column so you can compare.\n\n"
                 "Edits apply immediately and can be undone (Ctrl+Z). Ctrl+S writes the files.")
        self.editor = ttk.Frame(host, padding=(10, 6, 14, 10))

        hdr = ttk.Frame(self.editor)
        hdr.pack(fill="x")
        self.back_btn = ttk.Button(hdr, text="◀", width=3, command=self.go_back)
        self.back_btn.pack(side="left", padx=(0, 6))
        Tooltip(self.tip, self.back_btn, "Back to the previously opened voxel (Alt+Left)")
        self.title_lbl = ttk.Label(hdr, style="Title.TLabel")
        self.title_lbl.pack(side="left")
        self.sub_lbl = ttk.Label(self.editor, style="Hint.TLabel")
        self.sub_lbl.pack(anchor="w", pady=(2, 0))
        self.desc_lbl = ttk.Label(self.editor, wraplength=520, justify="left")
        self.desc_lbl.pack(anchor="w", fill="x", pady=(4, 8))

        basic = ttk.Frame(self.editor)
        basic.pack(fill="x")
        basic.columnconfigure(1, weight=1)
        ttk.Label(basic, text="Name", style="Field.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=3)
        self.name_var = tk.StringVar()
        self.name_var.trace_add("write", lambda *_: self.on_name_edit())
        ttk.Entry(basic, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", pady=3)

        ttk.Label(basic, text="Colour", style="Field.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=3)
        crow = ttk.Frame(basic)
        crow.grid(row=1, column=1, sticky="ew", pady=3)
        self.swatch = tk.Canvas(crow, width=44, height=24, highlightthickness=1,
                                highlightbackground="#555", cursor="hand2")
        self.swatch.pack(side="left", padx=(0, 6))
        self.swatch.bind("<Button-1>", lambda e: self.pick_color())
        Tooltip(self.tip, self.swatch, "Click to pick a colour")
        self.hex_var = tk.StringVar()
        self.hex_var.trace_add("write", lambda *_: self.on_hex_edit())
        hex_e = ttk.Entry(crow, textvariable=self.hex_var, width=9)
        hex_e.pack(side="left", padx=(0, 8))
        self.hex_entry = hex_e
        Tooltip(self.tip, hex_e, "Hex colour, e.g. #19BE00")
        ttk.Button(crow, text="Pick…", command=self.pick_color).pack(side="left")
        rrow = ttk.Frame(basic)
        rrow.grid(row=2, column=1, sticky="w", pady=(0, 3))
        self.rgba_vars, self.rgba_widgets = [], []
        for ch in "RGBA":
            ttk.Label(rrow, text=ch).pack(side="left", padx=(0 if ch == "R" else 8, 2))
            v = tk.StringVar()
            v.trace_add("write", lambda *_: self.on_rgba_edit())
            w = ttk.Spinbox(rrow, textvariable=v, from_=0.0, to=1.0, increment=0.01, width=6)
            w.pack(side="left")
            self.rgba_vars.append(v)
            self.rgba_widgets.append(w)
        Tooltip(self.tip, self.rgba_widgets[3],
                "Alpha: 1 = opaque, 0 = invisible, in between = see-through (blended front to back). "
                "Soil is forced almost invisible when the renderer's transparent_soils is on.")

        flags = ttk.Frame(basic)
        flags.grid(row=3, column=1, sticky="w")
        self.in_colors_var = tk.BooleanVar()
        self.in_data_var = tk.BooleanVar()
        c1 = ttk.Checkbutton(flags, text="in voxel_colors.json", variable=self.in_colors_var,
                             command=self.on_in_colors_toggle)
        c1.pack(side="left", padx=(0, 12))
        c2 = ttk.Checkbutton(flags, text="in voxel_data.json", variable=self.in_data_var,
                             command=self.on_in_data_toggle)
        c2.pack(side="left")
        Tooltip(self.tip, c1, "Without a colour entry the voxel renders black.")
        Tooltip(self.tip, c2, "Without a data entry all of s0..s7 are 0. Editing a parameter adds the entry.")

        ttk.Label(basic, text="Groups", style="Field.TLabel").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=3)
        grow = ttk.Frame(basic)
        grow.grid(row=4, column=1, sticky="ew", pady=3)
        self.groups_lbl = ttk.Label(grow)
        self.groups_lbl.pack(side="left")
        self.group_rm_mb = ttk.Menubutton(grow, text="− Remove")
        self.group_rm_mb.pack(side="right", padx=(4, 0))
        self.group_add_mb = ttk.Menubutton(grow, text="+ Add to group")
        self.group_add_mb.pack(side="right")
        self.group_add_menu = tk.Menu(self.group_add_mb, tearoff=0, postcommand=self._fill_group_add_menu)
        self.group_rm_menu = tk.Menu(self.group_rm_mb, tearoff=0, postcommand=self._fill_group_rm_menu)
        self.group_add_mb["menu"] = self.group_add_menu
        self.group_rm_mb["menu"] = self.group_rm_menu

        ph = ttk.Frame(self.editor)
        ph.pack(fill="x", pady=(14, 2))
        ttk.Label(ph, text="Parameters", style="Section.TLabel").pack(side="left")
        lb = ttk.Button(ph, text="Fill empty links from group", command=self.fill_links)
        lb.pack(side="right")
        Tooltip(self.tip, lb, "For every link field that is 0, use the voxel of the right part from the "
                              "same group, when there is exactly one.")

        self.compare_bar = ttk.Frame(self.editor)
        self.compare_bar.pack(fill="x", pady=(2, 4))
        self.compare_lbl = ttk.Label(self.compare_bar, style="Hint.TLabel")
        self.compare_lbl.pack(side="left")
        self.compare_swatch = tk.Canvas(self.compare_bar, width=30, height=16, highlightthickness=1,
                                        highlightbackground="#888")
        self.compare_open_btn = ttk.Button(self.compare_bar, text="Edit it instead",
                                           command=lambda: self.open_voxel(self.compare_idx))

        self.param_frame = ttk.Frame(self.editor)
        self.param_frame.pack(fill="x")

        ttk.Label(self.editor, text="Used by", style="Section.TLabel").pack(anchor="w", pady=(14, 2))
        self.usedby = tk.Listbox(self.editor, height=4, activestyle="none", exportselection=False)
        self.usedby.pack(fill="x")
        self.usedby.bind("<Double-1>", lambda e: self._open_usedby())
        self._usedby_items: list[int] = []

        ttk.Label(self.editor, text="Problems", style="Section.TLabel").pack(anchor="w", pady=(14, 2))
        self.problems_lbl = ttk.Label(self.editor, wraplength=520, justify="left")
        self.problems_lbl.pack(anchor="w", fill="x")

        self.placeholder.pack(fill="both", expand=True)
        self._wrap = 480
        self.editor.bind("<Configure>", self._on_editor_resize)

    def _on_editor_resize(self, e):
        wrap = max(260, e.width - 40)
        if abs(wrap - self._wrap) < 4:
            return
        self._wrap = wrap
        self.desc_lbl.configure(wraplength=wrap)
        self.problems_lbl.configure(wraplength=wrap)
        self.placeholder.configure(wraplength=wrap)
        for row in self.param_rows:
            row.hint.configure(wraplength=wrap - 60)

    # ------------------------------------------------------------------ keys
    def _bind_shortcut(self, widget, seqs, fn):
        def handler(ev):
            # AltGr letters on Polish layouts (ż, ś, ć, ń...) arrive as Ctrl+Alt+letter: let them type.
            if ev.char and ev.char.isprintable():
                return None
            fn()
            return "break"
        for s in seqs:
            widget.bind(s, handler)

    def _bind_keys(self):
        r = self.root
        self._bind_shortcut(r, ["<Control-s>", "<Control-S>"], self.save)
        self._bind_shortcut(r, ["<Control-z>"], self.undo)
        self._bind_shortcut(r, ["<Control-y>", "<Control-Y>", "<Control-Z>"], self.redo)
        self._bind_shortcut(r, ["<Control-n>", "<Control-N>"], self.new_voxel)
        self._bind_shortcut(r, ["<Control-d>", "<Control-D>"], self.duplicate_selection)
        self._bind_shortcut(r, ["<Control-f>", "<Control-F>"],
                            lambda: (self.search_entry.focus_set(), self.search_entry.select_range(0, "end")))
        r.bind("<Alt-Left>", lambda e: self.go_back())
        r.bind("<F5>", lambda e: self.reload())
        r.bind("<FocusIn>", self._on_focus_in, add="+")

    # ------------------------------------------------------------------ analysis helpers
    def schema_for(self, idx):
        return self.schemas.get(type_of(idx))

    def specs_for(self, idx, values=None):
        sch = self.schema_for(idx)
        vals = self.model.values(idx) if values is None else values
        return sch.specs(vals) if sch else [None] * SLOTS

    def type_label(self, t) -> str:
        n = self.model.type_names.get(t, "").strip()
        if n:
            return n
        s = self.schemas.get(t)
        return s.name if s else f"Type {t}"

    def part_of(self, idx) -> str:
        sch = self.schema_for(idx)
        if sch is None:
            return self.type_label(type_of(idx))
        if sch.variant_slot is None:
            return sch.name
        return sch.variant_name(self.model.values(idx)[sch.variant_slot])

    def nice(self, idx) -> str:
        n = self.model.name(idx)
        return f"{idx} · {n}" if n else str(idx)

    def target_problem(self, spec: FieldSpec, target: int) -> str | None:
        if not self.model.exists(target):
            return f"{target} doesn't exist"
        tt = spec.target_type()
        if tt is not None and type_of(target) != tt:
            return f"{self.nice(target)} is type {type_of(target)}, expected type {tt}"
        tv = spec.target_variants()
        sch = self.schemas.get(type_of(target))
        if tv is not None and sch is not None and sch.variant_slot is not None:
            v = self.model.values(target)[sch.variant_slot]
            if v not in tv:
                want = " or ".join(sch.variant_name(x) for x in sorted(tv))
                return f"{self.nice(target)} is a {sch.variant_name(v)}, expected a {want}"
        return None

    def problems(self, idx) -> list[str]:
        out = []
        t = type_of(idx)
        vals = self.model.values(idx)
        if idx >= SIGNED_LIMIT:
            out.append("Index is 32768 or more: the render shader reads indices as signed numbers.")
        if t != 0 and idx not in self.model.colors:
            out.append("No colour entry: renders black.")
        for s, v in enumerate(vals):
            if not 0 <= v <= MAX_VALUE:
                out.append(f"s{s} = {v} is outside 0..65535, the game can't load it.")
        sch = self.schemas.get(t)
        if sch:
            if sch.variant_slot is not None and sch.variants and vals[sch.variant_slot] not in sch.variants:
                f = sch.fields.get(sch.variant_slot)
                out.append(f"s{sch.variant_slot} = {vals[sch.variant_slot]} is not a known "
                           f"{(f.label.lower() if f else 'variant')}.")
            for s, spec in enumerate(sch.specs(vals)):
                if spec and spec.kind == "index" and vals[s] != 0:
                    p = self.target_problem(spec, vals[s])
                    if p:
                        out.append(f"s{s} ({spec.label}): {p}.")
                if spec and spec.max is not None and vals[s] > spec.max:
                    out.append(f"s{s} ({spec.label}) = {vals[s]} is above the maximum {spec.max}.")
                if spec and spec.kind == "species":
                    out.extend(self._species_problems(idx, s, vals[s]))
        if not self.model.name(idx) and not self.model.groups_of(idx):
            out.append("No name and no group: the in-game block selector doesn't show it.")
        return out

    def _species_problems(self, idx, slot, v) -> list[str]:
        """Species id checks: Analysis.glsl groups plant counts by it."""
        if v == 0:
            return [f"s{slot} species id is 0: the analysis shader doesn't record a species for it."]
        out = []
        t = type_of(idx)
        my_groups = set(self.model.groups_of(idx))
        same_type = [i for i in self.model.indices() if type_of(i) == t and i != idx]
        if my_groups:
            mates = [i for i in same_type if my_groups & set(self.model.groups_of(i))]
            other_ids = sorted({self.model.values(i)[slot] for i in mates} - {v})
            if other_ids:
                out.append(f"s{slot} species id {v} differs from others in its group ({other_ids}).")
            strangers = [i for i in same_type if self.model.groups_of(i) and not my_groups & set(self.model.groups_of(i))
                         and self.model.values(i)[slot] == v]
            if strangers:
                gs = sorted({g for i in strangers for g in self.model.groups_of(i)})
                out.append(f"s{slot} species id {v} is also used by group(s) {', '.join(gs)}: "
                           f"the analysis would count them as one species.")
        return out

    def group_problems(self, g) -> list[str]:
        members = self.model.groups.get(g, [])
        out = []
        types = sorted({type_of(i) for i in members})
        if len(types) > 1:
            out.append(f"Mixes types {types}; the in-game block selector files the whole group under "
                       f"type {type_of(members[0])} (the type of its first index).")
        missing = [i for i in members if not self.model.exists(i)]
        if missing:
            out.append(f"Contains indices that don't exist: {missing}")
        return out

    def referrers(self, idx) -> list[tuple[int, int, FieldSpec]]:
        out = []
        for j in self.model.indices():
            vals = self.model.values(j)
            for s, spec in enumerate(self.specs_for(j, vals)):
                if spec and spec.kind == "index" and vals[s] == idx:
                    out.append((j, s, spec))
        return out

    def hint_for(self, spec: FieldSpec | None, v: int) -> tuple[str, bool]:
        """(text, is_problem) for the meaning column."""
        if spec is None:
            return ("unused, the value is ignored" if v else "", False)
        note = "" if spec.read else "  (not read by the shader)"
        if spec.kind == "index":
            if v == 0:
                return ((spec.zero or "none") + note, False)
            p = self.target_problem(spec, v)
            if p:
                return (f"⚠ {p}", True)
            return (f"→ {self.model.name(v) or '(unnamed)'} [{self.part_of(v)}]" + note, False)
        if spec.kind == "speed":
            eff = v if v else (spec.default or 0)
            scale = spec.scale or 0.0001
            p = eff * scale
            pre = f"0 → default {spec.default}: " if v == 0 and spec.default is not None else ""
            if p <= 0:
                return (pre + "never", False)
            if p >= 1:
                return (pre + "every step", False)
            return (f"{pre}{p * 100:.3g}% per step, ~{fmt_seconds(1 / (p * STEPS_PER_SECOND))}" + note, False)
        if spec.kind == "limit":
            if v == 0:
                if spec.zero:
                    return (f"0 → {spec.zero}", False)
                if spec.default is not None:
                    return (f"0 → default {spec.default}", False)
            return (note.strip(), False)
        if spec.kind == "flag":
            return (("on" if v else "off") + note, False)
        if spec.kind == "species":
            if v == 0:
                return ("0 → species not recorded" + note, True)
            if spec.max is not None and v > spec.max:
                return (f"⚠ above the maximum {spec.max}", True)
            return ("shared by all parts of a species, unique per species" + note, False)
        if spec.max is not None and v > spec.max:
            return (f"⚠ above the maximum {spec.max}", True)
        return (note.strip(), False)

    # ------------------------------------------------------------------ undo / dirty
    def checkpoint(self, label, key=None):
        """Call BEFORE changing the model. Repeated edits with the same key merge into one undo step."""
        if key is not None and key == self._coalesce:
            return
        self._coalesce = key
        self.undo_stack.append((label, self.model.state()))
        del self.undo_stack[:-MAX_UNDO]
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            self.status("Nothing to undo.")
            return
        label, st = self.undo_stack.pop()
        self.redo_stack.append((label, self.model.state()))
        self.model.restore(st)
        self._coalesce = None
        self.refresh_all()
        self.status(f"Undid: {label}")

    def redo(self):
        if not self.redo_stack:
            self.status("Nothing to redo.")
            return
        label, st = self.redo_stack.pop()
        self.undo_stack.append((label, self.model.state()))
        self.model.restore(st)
        self._coalesce = None
        self.refresh_all()
        self.status(f"Redid: {label}")

    def is_dirty(self) -> bool:
        return self.model.state() != self.saved_state

    def update_title(self):
        dirty = self.is_dirty()
        self.root.title(f"{'● ' if dirty else ''}BotanicGarden voxel editor - {self.paths.data_dir}")
        self.undo_btn.state(["!disabled"] if self.undo_stack else ["disabled"])
        self.redo_btn.state(["!disabled"] if self.redo_stack else ["disabled"])

    def status(self, text):
        self.status_var.set(text)

    # ------------------------------------------------------------------ refresh
    def refresh_all(self):
        self.refresh_nav()
        self.refresh_table()
        self.load_editor()
        self.update_title()

    def after_edit(self):
        """Light refresh after an edit made in the editor (doesn't reset the editor's fields)."""
        self.refresh_nav()
        self.refresh_table()
        self._refresh_editor_info()
        self.update_title()

    def swatch_image(self, rgba):
        key = None if rgba is None else tuple(round(c, 3) for c in rgba)
        if key in self._swatches:
            return self._swatches[key]
        w, h = 20, 14
        img = tk.PhotoImage(width=w, height=h)
        rows = []
        for y in range(h):
            row = []
            for x in range(w):
                if x in (0, w - 1) or y in (0, h - 1):
                    row.append("#555555")
                elif key is None:
                    row.append("#D33" if abs(x - y * w / h) < 1.2 else "#FFFFFF")
                else:
                    r, g, b, a = rgba
                    bg = 0.9 if (x // 4 + y // 4) % 2 == 0 else 0.62
                    row.append(rgb_to_hex(r * a + bg * (1 - a), g * a + bg * (1 - a), b * a + bg * (1 - a)))
            rows.append("{" + " ".join(row) + "}")
        img.put(" ".join(rows))
        self._swatches[key] = img
        return img

    def draw_swatch(self, canvas: tk.Canvas, rgba):
        canvas.delete("all")
        w, h = int(canvas.cget("width")), int(canvas.cget("height"))
        if rgba is None:
            canvas.create_rectangle(0, 0, w + 2, h + 2, fill="#FFFFFF", outline="")
            canvas.create_line(0, 0, w + 2, h + 2, fill="#D33", width=2)
            return
        r, g, b, a = rgba
        for x in range(0, w + 2, 6):
            for y in range(0, h + 2, 6):
                bg = 0.9 if (x // 6 + y // 6) % 2 == 0 else 0.62
                canvas.create_rectangle(x, y, x + 6, y + 6, outline="",
                                        fill=rgb_to_hex(r * a + bg * (1 - a), g * a + bg * (1 - a),
                                                        b * a + bg * (1 - a)))

    # ---- navigator
    def nav_key(self) -> str:
        sel = self.nav.selection()
        return sel[0] if sel else "all"

    def refresh_nav(self):
        key = self.nav_key()
        yview = self.nav.yview()[0]
        nav = self.nav
        nav.delete(*nav.get_children())
        all_idx = self.model.indices()
        nav.insert("", "end", "all", text=f"All voxels ({len(all_idx)})")
        n_prob = sum(1 for i in all_idx if self.problems(i))
        nav.insert("", "end", "problems", text=f"⚠ Problems ({n_prob})" if n_prob else "Problems (0)",
                   tags=("problem",) if n_prob else ())
        by_type: dict[int, list[int]] = {}
        for i in all_idx:
            by_type.setdefault(type_of(i), []).append(i)
        group_type = {g: type_of(m[0]) for g, m in self.model.groups.items() if m}
        types = sorted(set(by_type) | {t for t, n in self.model.type_names.items() if n.strip()}
                       | set(group_type.values()))
        for t in types:
            nav.insert("", "end", f"type:{t}", open=True, tags=("type",),
                       text=f"{t} · {self.type_label(t)} ({len(by_type.get(t, []))})")
            for g, members in self.model.groups.items():
                if group_type.get(g) == t:
                    bad = bool(self.group_problems(g)) or any(self.problems(i) for i in members)
                    nav.insert(f"type:{t}", "end", f"group:{g}", text=f"{g} ({len(members)})",
                               tags=("problem",) if bad else ())
            ungrouped = [i for i in by_type.get(t, []) if not self.model.groups_of(i)]
            if ungrouped:
                nav.insert(f"type:{t}", "end", f"ungrouped:{t}", text=f"(no group) ({len(ungrouped)})")
        empty = [g for g, m in self.model.groups.items() if not m]
        if empty:
            nav.insert("", "end", "empty", text="Empty groups", open=True)
            for g in empty:
                nav.insert("empty", "end", f"group:{g}", text=f"{g} (0)")
        if not nav.exists(key):
            key = "all"
        nav.selection_set(key)
        nav.see(key)
        nav.yview_moveto(yview)

    def _nav_motion(self, e):
        row = self.nav.identify_row(e.y)
        if row == self._nav_tip[0]:
            return
        self._hide_nav_tip()
        if row:
            job = self.nav.after(500, lambda: self.tip.show(e.x_root, e.y_root, self._nav_text(row)))
            self._nav_tip = (row, job)

    def _hide_nav_tip(self):
        if self._nav_tip[1]:
            self.nav.after_cancel(self._nav_tip[1])
        self._nav_tip = (None, None)
        self.tip.hide()

    def _nav_text(self, key):
        if key.startswith("group:"):
            g = key[6:]
            probs = self.group_problems(g)
            bad = [i for i in self.model.groups.get(g, []) if self.problems(i)]
            if bad:
                probs.append(f"Voxels with problems: {', '.join(self.nice(i) for i in bad)}")
            return "\n".join(probs)
        if key.startswith("type:"):
            sch = self.schemas.get(int(key[5:]))
            return sch.description if sch else "No schema for this type."
        if key == "problems":
            return "Voxels with broken links, missing colours, unknown parts and similar."
        return ""

    # ---- table
    def visible_indices(self) -> list[int]:
        key = self.nav_key()
        all_idx = self.model.indices()
        if key == "problems":
            rows = [i for i in all_idx if self.problems(i)]
        elif key.startswith("type:"):
            t = int(key[5:])
            rows = [i for i in all_idx if type_of(i) == t]
        elif key.startswith("group:"):
            rows = [i for i in self.model.groups.get(key[6:], []) if self.model.exists(i)]
        elif key.startswith("ungrouped:"):
            t = int(key[10:])
            rows = [i for i in all_idx if type_of(i) == t and not self.model.groups_of(i)]
        else:
            rows = all_idx
        q = self.search_var.get().strip().lower()
        if q:
            m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", q)
            if m:
                lo, hi = sorted((int(m.group(1)), int(m.group(2))))
                rows = [i for i in rows if lo <= i <= hi]
            else:
                rows = [i for i in rows if q in str(i) or q in self.model.name(i).lower()
                        or q in self.part_of(i).lower()
                        or any(q in g.lower() for g in self.model.groups_of(i))]
        return self._sorted(rows)

    def _sorted(self, rows):
        c = self.sort_col
        if c == "#0":
            key = lambda i: i
        elif c == "name":
            key = lambda i: (self.model.name(i).lower(), i)
        elif c == "part":
            key = lambda i: (self.part_of(i).lower(), i)
        elif c == "groups":
            key = lambda i: (", ".join(self.model.groups_of(i)).lower(), i)
        elif c == "issues":
            key = lambda i: (len(self.problems(i)), i)
        else:
            s = int(c[1:])
            key = lambda i: (self.model.values(i)[s], i)
        return sorted(rows, key=key, reverse=self.sort_rev)

    def sort_by(self, col):
        if self.sort_col == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col, self.sort_rev = col, False
        self.refresh_table()

    def refresh_table(self):
        tree = self.tree
        sel = set(tree.selection())
        yview = tree.yview()[0]
        tree.delete(*tree.get_children())
        rows = self.visible_indices()
        in_group = self.nav_key().startswith("group:")
        tree.configure(displaycolumns=[c for c in TABLE_COLS if not (in_group and c == "groups")])
        labels_per_slot = [set() for _ in range(SLOTS)]
        for i in rows:
            vals = self.model.values(i)
            specs = self.specs_for(i, vals)
            for s in range(SLOTS):
                labels_per_slot[s].add(specs[s].short if specs[s] else None)
            probs = self.problems(i)
            tags = []
            if probs:
                tags.append("problem")
            if i == self.open_idx:
                tags.append("open")
            shown = [("" if specs[s] is None and vals[s] == 0 else vals[s]) if i in self.model.structs else "–"
                     for s in range(SLOTS)]
            tree.insert("", "end", iid=str(i), text=f" {i}", image=self.swatch_image(self.model.colors.get(i)),
                        values=[self.model.name(i), self.part_of(i), ", ".join(self.model.groups_of(i)),
                                *shown, f"⚠ {len(probs)}" if probs else ""], tags=tags)
        for s in range(SLOTS):
            labels = labels_per_slot[s]
            head = f"s{s}"
            if len(labels) == 1 and None not in labels:
                head = f"s{s} {next(iter(labels))}"
            tree.heading(f"s{s}", text=head + self._sort_arrow(f"s{s}"))
        for c, t in (("#0", "Index"), ("name", "Name"), ("part", "Part"), ("groups", "Groups"), ("issues", "⚠")):
            tree.heading(c, text=t + self._sort_arrow(c))
        keep = [i for i in sel if tree.exists(i)]
        if keep:
            tree.selection_set(keep)
        tree.yview_moveto(yview)
        self.count_lbl.configure(text=f"{len(rows)} shown · {len(self.model.indices())} voxels")

    def _sort_arrow(self, col):
        return (" ▼" if self.sort_rev else " ▲") if self.sort_col == col else ""

    def selected_indices(self) -> list[int]:
        return [int(i) for i in self.tree.selection()]

    def select_rows(self, indices, focus=True):
        ids = [str(i) for i in indices if self.tree.exists(str(i))]
        if not ids:
            return
        self.tree.selection_set(ids)
        self.tree.see(ids[0])
        if focus:
            self.tree.focus(ids[0])

    def on_table_select(self):
        sel = self.selected_indices()
        if self.open_idx is None and len(sel) == 1:
            self.open_voxel(sel[0])  # nothing open yet, so nothing to lose
            return
        cmp_idx = sel[0] if len(sel) == 1 and sel[0] != self.open_idx else None
        if cmp_idx != self.compare_idx:
            self.compare_idx = cmp_idx
            self.update_compare()

    def _on_table_click(self, e):
        # A click in the empty area below the rows clears the selection (and with it the comparison).
        if self.tree.identify_region(e.x, e.y) == "nothing":
            self.tree.selection_set(())
            self.tree.focus("")
            return "break"
        return None

    def _on_table_double(self, e):
        if self.tree.identify_region(e.x, e.y) == "heading":
            return
        row = self.tree.identify_row(e.y)
        if row:
            self.open_voxel(int(row))

    def open_selected(self):
        sel = self.selected_indices()
        if sel:
            self.open_voxel(sel[0])

    # ---- cell tooltips
    def _table_motion(self, e):
        row, col = self.tree.identify_row(e.y), self.tree.identify_column(e.x)
        if (row, col) == self._cell_tip[:2]:
            return
        self._hide_cell_tip()
        if not row:
            return
        job = self.tree.after(500, lambda: self.tip.show(e.x_root, e.y_root, self._cell_text(int(row), col)))
        self._cell_tip = (row, col, job)

    def _hide_cell_tip(self):
        if self._cell_tip[2]:
            self.tree.after_cancel(self._cell_tip[2])
        self._cell_tip = (None, None, None)
        self.tip.hide()

    def _cell_text(self, idx, col):
        if col == "#0":
            return f"{self.nice(idx)}\nType {type_of(idx)} · {self.type_label(type_of(idx))}"
        try:
            name = TABLE_COLS[int(col[1:]) - 1]
        except (ValueError, IndexError):
            return ""
        if name == "issues":
            return "\n".join(self.problems(idx))
        if name in ("name", "groups"):
            groups = self.model.groups_of(idx)
            return f"{self.nice(idx)}\nGroups: {', '.join(groups) if groups else '(none)'}"
        if name == "part":
            sch = self.schema_for(idx)
            return sch.describe(self.model.values(idx)) if sch else ""
        if name in S_COLS:
            s = int(name[1:])
            vals = self.model.values(idx)
            spec = self.specs_for(idx, vals)[s]
            if spec is None:
                return f"s{s} = {vals[s]}\nNot used by a {self.part_of(idx)}."
            hint, _ = self.hint_for(spec, vals[s])
            return f"s{s} · {spec.label} = {vals[s]}\n{hint}\n\n{spec.description}".strip()
        return ""

    # ------------------------------------------------------------------ editor
    def open_voxel(self, idx, push_history=True):
        if idx is None or not self.model.exists(idx):
            return
        if push_history and self.open_idx is not None and self.open_idx != idx:
            self.history.append(self.open_idx)
            del self.history[:-50]
        self.open_idx = idx
        self._coalesce = None
        if self.compare_idx == idx:
            self.compare_idx = None
        self.load_editor()
        self.refresh_table()

    def go_back(self):
        while self.history:
            idx = self.history.pop()
            if self.model.exists(idx):
                self.open_voxel(idx, push_history=False)
                self.select_rows([idx])
                return

    def _param_signature(self, idx):
        sch = self.schema_for(idx)
        return (type_of(idx), sch.variant_of(self.model.values(idx)) if sch else None)

    def load_editor(self):
        idx = self.open_idx
        if idx is None or not self.model.exists(idx):
            self.open_idx = None
            self.editor.pack_forget()
            self.placeholder.pack(fill="both", expand=True)
            return
        self.placeholder.pack_forget()
        self.editor.pack(fill="both", expand=True)
        self._loading = True
        try:
            self.name_var.set(self.model.name(idx))
            col = self.model.colors.get(idx, [0.5, 0.5, 0.5, 1.0])
            for v, c in zip(self.rgba_vars, col):
                v.set(f"{c:.3f}".rstrip("0").rstrip(".") if c not in (0, 1) else str(int(c)))
            self.hex_var.set(rgb_to_hex(*col[:3]))
            self.in_colors_var.set(idx in self.model.colors)
            self.in_data_var.set(idx in self.model.structs)
            sig = self._param_signature(idx)
            if sig != self._param_sig:
                self._build_param_rows()
                self._param_sig = sig
            self._set_param_vars()
            for w in [self.hex_entry] + self.rgba_widgets:
                self._mark_bad(w, False)
        finally:
            self._loading = False
        self._refresh_editor_info()

    def _set_param_vars(self):
        vals = self.model.values(self.open_idx)
        sch = self.schema_for(self.open_idx)
        for row in self.param_rows:
            v = vals[row.slot]
            if row.spec and row.spec.kind == "variant" and sch and v in sch.variants:
                row.var.set(f"{v} · {sch.variants[v]['name']}")
            elif row.spec and row.spec.kind == "flag":
                row.var.set("1" if v else "0")
            else:
                row.var.set(str(v))
            if row.widget.winfo_class() in ("TEntry", "TCombobox", "TSpinbox"):
                self._mark_bad(row.widget, False)

    def _build_param_rows(self):
        for w in self.param_frame.winfo_children():
            w.destroy()
        self.param_rows = []
        idx = self.open_idx
        sch = self.schema_for(idx)
        specs = self.specs_for(idx)
        pf = self.param_frame
        pf.columnconfigure(4, weight=1)
        self.compare_head = ttk.Label(pf, text="", style="Hint.TLabel")
        self.compare_head.grid(row=0, column=4, sticky="e")
        for s in range(SLOTS):
            spec = specs[s]
            r = 2 * s + 1
            ttk.Label(pf, text=f"s{s}", style="Dim.TLabel").grid(row=r, column=0, sticky="w", padx=(0, 6), pady=(6, 0))
            lbl = ttk.Label(pf, text=spec.label if spec else "(unused)",
                            style="Field.TLabel" if spec else "Unused.TLabel")
            lbl.grid(row=r, column=1, sticky="w", padx=(0, 8), pady=(6, 0))
            var = tk.StringVar()
            jump = None
            if spec and spec.kind == "variant" and sch and sch.variants:
                w = ttk.Combobox(pf, textvariable=var, state="readonly", width=20,
                                 values=[f"{k} · {v['name']}" for k, v in sorted(sch.variants.items())])
            elif spec and spec.kind == "index":
                w = ttk.Combobox(pf, textvariable=var, width=20,
                                 postcommand=lambda s=s: self._fill_candidates(s))
                w.bind("<<ComboboxSelected>>", lambda e, v=var: v.set(re.match(r"\s*(\d+)", v.get()).group(1)))
                jump = ttk.Button(pf, text="→", width=3, command=lambda s=s: self._jump(s))
                jump.grid(row=r, column=3, padx=(2, 6), pady=(6, 0))
                Tooltip(self.tip, jump, "Open the linked voxel")
            elif spec and spec.kind == "flag":
                w = ttk.Checkbutton(pf, variable=var, onvalue="1", offvalue="0")
            else:
                w = ttk.Spinbox(pf, textvariable=var, from_=0, to=MAX_VALUE, width=20)
            w.grid(row=r, column=2, sticky="w", pady=(6, 0))
            cmp_lbl = ttk.Label(pf, style="Hint.TLabel")
            cmp_lbl.grid(row=r, column=4, sticky="e", padx=(8, 0), pady=(6, 0))
            hint = ttk.Label(pf, style="Hint.TLabel", wraplength=self._wrap - 60, justify="left")
            hint.grid(row=r + 1, column=1, columnspan=4, sticky="w")
            if spec:
                tip = f"s{s} · {spec.label}\n\n{spec.description}"
                if spec.default is not None:
                    tip += f"\n\n0 = default ({spec.default})."
                if spec.zero:
                    tip += f"\n\n0 = {spec.zero}."
                if not spec.read:
                    tip += "\n\nNot read by the shader at the moment."
            else:
                tip = f"s{s} is not used by a {self.part_of(idx)}."
            for widget in (lbl, w):
                Tooltip(self.tip, widget, tip)
            var.trace_add("write", lambda *_, s=s: self.on_param_edit(s))
            self.param_rows.append(ParamRow(s, spec, var, w, hint, cmp_lbl, jump))

    def _fill_candidates(self, slot):
        row = self.param_rows[slot]
        spec = row.spec
        mates = set()
        for g in self.model.groups_of(self.open_idx):
            mates |= set(self.model.groups[g])
        cands = [i for i in self.model.indices() if self.target_problem(spec, i) is None]
        cands.sort(key=lambda i: (i not in mates, i))
        row.widget.configure(values=["0 · none"] + [f"{i} · {self.model.name(i) or '(unnamed)'} [{self.part_of(i)}]"
                                                    for i in cands])

    def _jump(self, slot):
        v = self.model.values(self.open_idx)[slot]
        if self.model.exists(v):
            self.open_voxel(v)
            self.select_rows([v])

    def _refresh_editor_info(self):
        idx = self.open_idx
        if idx is None or not self.model.exists(idx):
            return
        t = type_of(idx)
        sch = self.schema_for(idx)
        vals = self.model.values(idx)
        self.title_lbl.configure(text=f"#{idx}  {self.model.name(idx) or '(unnamed)'}")
        sub = f"Type {t} · {self.type_label(t)}"
        if sch and sch.variant_slot is not None:
            sub += f" · {self.part_of(idx)}"
        if sch and sch.shader:
            sub += f"   ({sch.shader})"
        self.sub_lbl.configure(text=sub)
        self.desc_lbl.configure(text=sch.describe(vals) if sch else "No schema for this type: fields are plain numbers.")
        self.back_btn.state(["!disabled"] if self.history else ["disabled"])
        self.draw_swatch(self.swatch, self.model.colors.get(idx))
        groups = self.model.groups_of(idx)
        self.groups_lbl.configure(text=", ".join(groups) if groups else "(none)")
        self.group_rm_mb.state(["!disabled"] if groups else ["disabled"])

        specs = self.specs_for(idx, vals)
        for row in self.param_rows:
            text, bad = self.hint_for(specs[row.slot], vals[row.slot])
            row.hint.configure(text=text, style="Problem.TLabel" if bad else "Hint.TLabel")
            row.hint.grid() if text else row.hint.grid_remove()
            if row.jump is not None:
                row.jump.state(["!disabled"] if vals[row.slot] and self.model.exists(vals[row.slot])
                               else ["disabled"])

        self._usedby_items = []
        self.usedby.delete(0, "end")
        for j, s, spec in self.referrers(idx):
            if j == idx:
                continue
            self._usedby_items.append(j)
            self.usedby.insert("end", f"{self.nice(j)}  [{self.part_of(j)}]  via s{s} {spec.label}")
        if not self._usedby_items:
            self.usedby.insert("end", "(nothing links here)")

        probs = self.problems(idx)
        self.problems_lbl.configure(text="\n".join(f"• {p}" for p in probs) if probs else "None",
                                    style="Problem.TLabel" if probs else "Hint.TLabel")
        self.update_compare()

    def update_compare(self):
        idx, c = self.open_idx, self.compare_idx
        if idx is None or not self.param_rows:
            return
        if c is None or not self.model.exists(c):
            self.compare_lbl.configure(text="Select another row to compare it here.")
            self.compare_swatch.pack_forget()
            self.compare_open_btn.pack_forget()
            if hasattr(self, "compare_head"):
                self.compare_head.configure(text="")
            for row in self.param_rows:
                row.compare.configure(text="")
            return
        self.compare_lbl.configure(text=f"Comparing with {self.nice(c)}  [{self.part_of(c)}]")
        self.compare_swatch.pack(side="left", padx=6)
        self.draw_swatch(self.compare_swatch, self.model.colors.get(c))
        self.compare_open_btn.pack(side="right")
        self.compare_head.configure(text=f"vs #{c}")
        mine, other = self.model.values(idx), self.model.values(c)
        other_specs = self.specs_for(c, other)
        for row in self.param_rows:
            s = row.slot
            os_ = other_specs[s]
            text = str(other[s])
            if os_ is not None and row.spec is not None and os_.label != row.spec.label:
                text += f" ({os_.label})"
            row.compare.configure(text=text, style="Diff.TLabel" if other[s] != mine[s] else "Hint.TLabel")

    def _mark_bad(self, w, bad):
        cls = w.winfo_class()
        if cls in ("TEntry", "TCombobox", "TSpinbox"):
            w.configure(style=f"Bad.{cls}" if bad else cls)

    # ---- edit handlers (live)
    def on_name_edit(self):
        if self._loading or self.open_idx is None:
            return
        idx, new = self.open_idx, self.name_var.get().strip()
        if new == self.model.name(idx):
            return
        self.checkpoint(f"rename {idx}", key=("name", idx))
        if new:
            self.model.names[idx] = new
        else:
            self.model.names.pop(idx, None)
        self.after_edit()

    def _apply_color(self, rgba):
        idx = self.open_idx
        if self.model.colors.get(idx) == rgba:
            return
        self.checkpoint(f"colour of {idx}", key=("color", idx))
        self.model.colors[idx] = rgba
        self._loading = True
        self.in_colors_var.set(True)
        self._loading = False
        self.after_edit()

    def on_rgba_edit(self):
        if self._loading or self.open_idx is None:
            return
        vals = []
        for v, w in zip(self.rgba_vars, self.rgba_widgets):
            try:
                x = float(v.get().replace(",", "."))
                ok = 0.0 <= x <= 1.0
            except ValueError:
                ok = False
            self._mark_bad(w, not ok)
            if not ok:
                return
            vals.append(round(x, 4))
        self._loading = True
        self.hex_var.set(rgb_to_hex(*vals[:3]))
        self._mark_bad(self.hex_entry, False)
        self._loading = False
        self._apply_color(vals)

    def on_hex_edit(self):
        if self._loading or self.open_idx is None:
            return
        rgb = hex_to_rgb(self.hex_var.get())
        self._mark_bad(self.hex_entry, rgb is None)
        if rgb is None:
            return
        old = self.model.colors.get(self.open_idx, [0.5, 0.5, 0.5, 1.0])
        if rgb_to_hex(*old[:3]) == rgb_to_hex(*rgb):
            return  # same colour at 8-bit precision; keep the exact floats
        try:
            a = float(self.rgba_vars[3].get())
        except ValueError:
            a = old[3]
        self._loading = True
        for v, c in zip(self.rgba_vars, rgb):
            v.set(f"{c:.3f}")
        self._loading = False
        self._apply_color([*rgb, a])

    def pick_color(self):
        if self.open_idx is None:
            return
        _, hx = colorchooser.askcolor(color=self.hex_var.get() or "#808080", title="Voxel colour", parent=self.root)
        if hx:
            self.hex_var.set(hx.upper())

    def on_in_colors_toggle(self):
        idx = self.open_idx
        if idx is None:
            return
        self.checkpoint(f"colour entry of {idx}")
        if self.in_colors_var.get():
            try:
                self.model.colors[idx] = [clamp01(float(v.get())) for v in self.rgba_vars]
            except ValueError:
                self.model.colors[idx] = [0.5, 0.5, 0.5, 1.0]
        else:
            self.model.colors.pop(idx, None)
        self.after_edit()

    def on_in_data_toggle(self):
        idx = self.open_idx
        if idx is None:
            return
        self.checkpoint(f"data entry of {idx}")
        if self.in_data_var.get():
            self.model.structs[idx] = self.model.values(idx)
        else:
            self.model.structs.pop(idx, None)
        self.load_editor()
        self.after_edit()

    def on_param_edit(self, slot):
        if self._loading or self.open_idx is None or slot >= len(self.param_rows):
            return
        row = self.param_rows[slot]
        m = re.match(r"\s*(\d+)", row.var.get())
        ok = bool(m) and int(m.group(1)) <= MAX_VALUE
        self._mark_bad(row.widget, not ok)
        if not ok:
            return
        v = int(m.group(1))
        idx = self.open_idx
        vals = self.model.values(idx)
        if vals[slot] == v and idx in self.model.structs:
            return
        self.checkpoint(f"s{slot} of {idx}", key=("param", idx, slot))
        vals[slot] = v
        self.model.structs[idx] = vals
        self._loading = True
        self.in_data_var.set(True)
        self._loading = False
        if self._param_signature(idx) != self._param_sig:
            self.root.after_idle(self.load_editor)  # part changed: rebuild the field rows
        self.after_edit()

    def _open_usedby(self):
        sel = self.usedby.curselection()
        if sel and sel[0] < len(self._usedby_items):
            j = self._usedby_items[sel[0]]
            self.open_voxel(j)
            self.select_rows([j])

    def _fill_group_add_menu(self):
        m = self.group_add_menu
        m.delete(0, "end")
        idx = self.open_idx
        if idx is None:
            return
        mine = set(self.model.groups_of(idx))
        for g in self.model.groups:
            if g not in mine:
                m.add_command(label=g, command=lambda g=g: self.add_to_group([idx], g))
        if len(mine) < len(self.model.groups):
            m.add_separator()
        m.add_command(label="New group…", command=lambda: self.new_group([idx]))

    def _fill_group_rm_menu(self):
        m = self.group_rm_menu
        m.delete(0, "end")
        idx = self.open_idx
        if idx is None:
            return
        for g in self.model.groups_of(idx):
            m.add_command(label=g, command=lambda g=g: self.remove_from_group([idx], g))

    # ------------------------------------------------------------------ actions
    def _target_indices(self):
        sel = self.selected_indices()
        if sel:
            return sel
        return [self.open_idx] if self.open_idx is not None else []

    def new_voxel(self, type_id=None, group=None):
        key = self.nav_key()
        if group is None and key.startswith("group:"):
            group = key[6:]
        if type_id is None:
            if key.startswith("type:") or key.startswith("ungrouped:"):
                type_id = int(key.split(":")[1])
            elif group and self.model.groups.get(group):
                type_id = type_of(self.model.groups[group][0])
            elif self.open_idx is not None:
                type_id = type_of(self.open_idx)
            else:
                type_id = 1
        dlg = NewVoxelDialog(self, type_id, group)
        res = dlg.result
        if not res:
            return
        idx = res["index"]
        self.checkpoint(f"new voxel {idx}")
        vals = [0] * SLOTS
        sch = self.schema_for(idx)
        if sch and sch.variant_slot is not None and res["variant"] is not None:
            vals[sch.variant_slot] = res["variant"]
        g = res["group"]
        if sch and g and self.model.groups.get(g):
            for s, spec in enumerate(sch.specs(vals)):
                if spec and spec.kind == "species":
                    used = [self.model.values(i)[s] for i in self.model.groups[g] if type_of(i) == type_of(idx)]
                    if used:
                        vals[s] = max(set(used), key=used.count)
        self.model.structs[idx] = vals
        self.model.colors[idx] = [0.5, 0.5, 0.5, 1.0]
        if res["name"]:
            self.model.names[idx] = res["name"]
        if g:
            self.model.groups.setdefault(g, [])
            self.model.groups[g] = sorted(set(self.model.groups[g]) | {idx})
        filled = self._link_from_group(idx)
        self.refresh_all()
        self.open_voxel(idx)
        self.select_rows([idx])
        self.status(f"Created {self.nice(idx)}" + (f", linked {filled} field(s) from the group." if filled else "."))

    def _link_from_group(self, idx) -> int:
        vals = self.model.values(idx)
        mates = set()
        for g in self.model.groups_of(idx):
            mates |= set(self.model.groups[g])
        filled = 0
        for s, spec in enumerate(self.specs_for(idx, vals)):
            if spec and spec.kind == "index" and vals[s] == 0:
                cands = [m for m in sorted(mates) if self.model.exists(m) and self.target_problem(spec, m) is None]
                if len(cands) == 1:
                    vals[s] = cands[0]
                    filled += 1
        if filled:
            self.model.structs[idx] = vals
        return filled

    def fill_links(self):
        idx = self.open_idx
        if idx is None:
            return
        before = self.model.state()
        filled = self._link_from_group(idx)
        if not filled:
            self.status("No empty link has exactly one matching part in this voxel's groups.")
            return
        self.undo_stack.append((f"fill links of {idx}", before))
        self.redo_stack.clear()
        self._coalesce = None
        self.refresh_all()
        self.status(f"Filled {filled} link(s) from the group.")

    def _allocate(self, indices, contiguous):
        taken = set(self.model.indices())
        mapping = {}
        by_type: dict[int, list[int]] = {}
        for i in sorted(indices):
            by_type.setdefault(type_of(i), []).append(i)
        for t, items in by_type.items():
            start = None
            if contiguous:
                start = self.model.free_block(t, len(items), max(items) + 1, taken)
            for i in items:
                new = self.model.free_index(t, start if start is not None else i + 1, taken)
                if new is None:
                    return None
                taken.add(new)
                mapping[i] = new
                if start is not None:
                    start = new + 1
        return mapping

    def _copy_voxel(self, old, new, mapping):
        if old in self.model.colors:
            self.model.colors[new] = list(self.model.colors[old])
        if old in self.model.structs:
            vals = self.model.values(old)
            for s, spec in enumerate(self.specs_for(old, vals)):
                if spec and spec.kind == "index" and vals[s] in mapping:
                    vals[s] = mapping[vals[s]]
            self.model.structs[new] = vals

    def duplicate_selection(self):
        sel = self._target_indices()
        if not sel:
            self.status("Select the voxels to duplicate.")
            return
        mapping = self._allocate(sel, contiguous=False)
        if mapping is None:
            messagebox.showerror("Duplicate", "No free index left in that type.", parent=self.root)
            return
        self.checkpoint(f"duplicate {len(sel)} voxel(s)")
        taken = set(self.model.names.values())
        for old, new in mapping.items():
            self._copy_voxel(old, new, mapping)
            if self.model.name(old):
                self.model.names[new] = increment_name(self.model.name(old), taken)
                taken.add(self.model.names[new])
            for g in self.model.groups_of(old):
                self.model.groups[g] = sorted(set(self.model.groups[g]) | {new})
        self.refresh_all()
        news = list(mapping.values())
        if len(news) == 1:
            self.open_voxel(news[0])
        self.select_rows(news)
        self.status("Duplicated " + ", ".join(f"{o} → {n}" for o, n in mapping.items()))

    def delete_selection(self):
        sel = self.selected_indices()
        if not sel:
            return
        sset = set(sel)
        outside = {j for i in sel for j, _, _ in self.referrers(i) if j not in sset}
        msg = f"Delete {len(sel)} voxel(s)?\n\n" + "\n".join(self.nice(i) for i in sel[:12])
        if len(sel) > 12:
            msg += "\n…"
        if outside:
            msg += f"\n\n{len(outside)} other voxel(s) link to these; those links will break:\n" + \
                   ", ".join(self.nice(j) for j in sorted(outside)[:10])
        msg += "\n\n(Undo with Ctrl+Z.)"
        if not messagebox.askyesno("Delete", msg, parent=self.root):
            return
        self.checkpoint(f"delete {len(sel)} voxel(s)")
        for i in sel:
            self.model.remove(i)
        if self.open_idx in sset:
            self.open_idx = None
        if self.compare_idx in sset:
            self.compare_idx = None
        self.refresh_all()
        self.status(f"Deleted {len(sel)} voxel(s).")

    def change_index(self):
        sel = self._target_indices()
        if len(sel) != 1:
            self.status("Select one voxel to change its index.")
            return
        idx = sel[0]
        new = simpledialog.askinteger(
            "Change index", f"New index for {self.nice(idx)}.\nLinks from other voxels and group "
                            f"memberships are updated.", initialvalue=idx, minvalue=0, maxvalue=MAX_INDEX,
            parent=self.root)
        if new is None or new == idx:
            return
        if self.model.exists(new):
            messagebox.showerror("Change index", f"{new} is already used by {self.nice(new)}.", parent=self.root)
            return
        if type_of(new) != type_of(idx) and not messagebox.askyesno(
                "Change index", f"{new} is in type {type_of(new)} ({self.type_label(type_of(new))}), "
                                f"not type {type_of(idx)}. The voxel will change type. Continue?",
                parent=self.root):
            return
        self.checkpoint(f"change index {idx} → {new}")
        refs = self.referrers(idx)
        m = self.model
        for d in (m.colors, m.structs, m.names):
            if idx in d:
                d[new] = d.pop(idx)
        for g, members in m.groups.items():
            if idx in members:
                m.groups[g] = sorted((set(members) - {idx}) | {new})
        for j, s, _ in refs:
            j2 = new if j == idx else j
            vals = m.values(j2)
            vals[s] = new
            m.structs[j2] = vals
        if self.open_idx == idx:
            self.open_idx = new
        self.history = [new if h == idx else h for h in self.history]
        self.refresh_all()
        self.select_rows([new])
        self.status(f"Moved {idx} → {new}, updated {len(refs)} link(s).")

    def copy_voxel(self):
        sel = self._target_indices()
        if len(sel) != 1:
            self.status("Select one voxel to copy.")
            return
        idx = sel[0]
        self.clipboard = {"idx": idx, "values": self.model.values(idx), "color": self.model.colors.get(idx)}
        self.status(f"Copied {self.nice(idx)}. Ctrl+V pastes its parameters, Ctrl+Shift+V its colour "
                    f"onto the selected rows.")

    def paste_params(self):
        sel = self.selected_indices()
        if not self.clipboard or not sel:
            self.status("Copy a voxel (Ctrl+C) and select target rows first.")
            return
        self.checkpoint(f"paste parameters to {len(sel)} voxel(s)")
        for i in sel:
            self.model.structs[i] = list(self.clipboard["values"])
        self.refresh_all()
        self.status(f"Pasted the parameters of {self.clipboard['idx']} onto {len(sel)} voxel(s).")

    def paste_color(self):
        sel = self.selected_indices()
        if not self.clipboard or not sel or self.clipboard["color"] is None:
            self.status("Copy a voxel that has a colour (Ctrl+C) and select target rows first.")
            return
        self.checkpoint(f"paste colour to {len(sel)} voxel(s)")
        for i in sel:
            self.model.colors[i] = list(self.clipboard["color"])
        self.refresh_all()
        self.status(f"Pasted the colour of {self.clipboard['idx']} onto {len(sel)} voxel(s).")

    # ---- groups / types
    def _nav_group(self):
        key = self.nav_key()
        return key[6:] if key.startswith("group:") else None

    def _ask_group_name(self, title, prompt, initial=""):
        name = simpledialog.askstring(title, prompt, initialvalue=initial, parent=self.root)
        if name is None:
            return None
        name = name.strip()
        if not name:
            return None
        if name in self.model.groups:
            messagebox.showerror(title, f"A group named '{name}' already exists.", parent=self.root)
            return None
        return name

    def new_group(self, members=None):
        members = self.selected_indices() if members is None else members
        name = self._ask_group_name("New group", f"Name of the new group ({len(members)} voxel(s) selected):")
        if not name:
            return
        self.checkpoint(f"new group {name}")
        self.model.groups[name] = sorted(set(members))
        self.refresh_all()
        self.nav.selection_set(f"group:{name}")
        self.status(f"Created group '{name}'.")

    def rename_nav_item(self):
        key = self.nav_key()
        if key.startswith("type:"):
            self.rename_type(int(key[5:]))
            return
        g = self._nav_group()
        if not g:
            self.status("Select a group or a type in the list on the left.")
            return
        new = self._ask_group_name("Rename group", "New name:", g)
        if not new:
            return
        self.checkpoint(f"rename group {g}")
        self.model.groups = {(new if k == g else k): v for k, v in self.model.groups.items()}
        self.refresh_all()
        self.nav.selection_set(f"group:{new}")

    def rename_type(self, t):
        lo, hi = type_range(t)
        new = simpledialog.askstring("Type label", f"Label for type {t} ({lo}-{hi}):",
                                     initialvalue=self.model.type_names.get(t, ""), parent=self.root)
        if new is None:
            return
        self.checkpoint(f"label of type {t}")
        self.model.type_names[t] = new.strip()
        self.refresh_all()

    def delete_nav_group(self):
        g = self._nav_group()
        if not g:
            self.status("Select a group in the list on the left.")
            return
        self.checkpoint(f"delete group {g}")
        del self.model.groups[g]
        self.refresh_all()
        self.status(f"Deleted group '{g}' (its voxels are kept; Ctrl+Z to undo).")

    def duplicate_nav_group(self):
        g = self._nav_group()
        if not g:
            self.status("Select a group in the list on the left.")
            return
        members = [i for i in self.model.groups[g] if self.model.exists(i)]
        if not members:
            return
        taken_groups = set(self.model.groups)
        new_g = self._ask_group_name("Duplicate group", f"Name of the copy of '{g}' ({len(members)} voxels):",
                                     increment_name(g, taken_groups))
        if not new_g:
            return
        mapping = self._allocate(members, contiguous=True)
        if mapping is None:
            messagebox.showerror("Duplicate group", "Not enough free indices in that type.", parent=self.root)
            return
        self.checkpoint(f"duplicate group {g}")
        old_tok, new_tok = trailing_number(g), trailing_number(new_g)
        taken = set(self.model.names.values())
        for old, new in mapping.items():
            self._copy_voxel(old, new, mapping)
            name = self.model.name(old)
            if name:
                nn = name
                if old_tok and new_tok:
                    nn = re.sub(rf"(?<!\d){old_tok}(?!\d)", new_tok, name)
                if nn == name or nn in taken:
                    nn = increment_name(nn, taken)
                self.model.names[new] = nn
                taken.add(nn)
        # new species id
        for t in {type_of(i) for i in mapping.values()}:
            sch = self.schemas.get(t)
            if not sch:
                continue
            for s, spec in sch.fields.items():
                if spec.kind == "species":
                    top = max((self.model.values(i)[s] for i in self.model.indices() if type_of(i) == t), default=0)
                    for new in mapping.values():
                        if type_of(new) == t and new in self.model.structs:
                            self.model.structs[new][s] = top + 1
        self.model.groups[new_g] = sorted(mapping.values())
        self.refresh_all()
        self.nav.selection_set(f"group:{new_g}")
        lo, hi = min(mapping.values()), max(mapping.values())
        self.status(f"Copied '{g}' to '{new_g}' at {lo}-{hi}. Links inside the group point at the copies.")

    def add_to_group(self, indices, g):
        if not indices:
            return
        members = self.model.groups.get(g, [])
        types = {type_of(i) for i in indices} | ({type_of(members[0])} if members else set())
        if len(types) > 1 and not messagebox.askyesno(
                "Add to group", f"This mixes types {sorted(types)} in '{g}'. The in-game block selector "
                                f"files a group under the type of its first index. Continue?", parent=self.root):
            return
        self.checkpoint(f"add to group {g}")
        self.model.groups[g] = sorted(set(members) | set(indices))
        self.refresh_all()
        self.status(f"Added {len(indices)} voxel(s) to '{g}'.")

    def remove_from_group(self, indices, g):
        self.checkpoint(f"remove from group {g}")
        self.model.groups[g] = [i for i in self.model.groups[g] if i not in set(indices)]
        self.refresh_all()
        self.status(f"Removed {len(indices)} voxel(s) from '{g}'.")

    # ---- context menus
    def _table_menu(self, e):
        row = self.tree.identify_row(e.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
        sel = self.selected_indices()
        one = "normal" if len(sel) == 1 else "disabled"
        some = "normal" if sel else "disabled"
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Edit", state=one, command=self.open_selected)
        m.add_command(label="Duplicate    Ctrl+D", state=some, command=self.duplicate_selection)
        m.add_command(label="Change index…    F2", state=one, command=self.change_index)
        m.add_command(label="Delete    Del", state=some, command=self.delete_selection)
        m.add_separator()
        m.add_command(label="Copy    Ctrl+C", state=one, command=self.copy_voxel)
        clip = "normal" if self.clipboard and sel else "disabled"
        m.add_command(label="Paste parameters    Ctrl+V", state=clip, command=self.paste_params)
        m.add_command(label="Paste colour    Ctrl+Shift+V", state=clip, command=self.paste_color)
        m.add_separator()
        add = tk.Menu(m, tearoff=0)
        for g in self.model.groups:
            add.add_command(label=g, command=lambda g=g: self.add_to_group(sel, g))
        if self.model.groups:
            add.add_separator()
        add.add_command(label="New group…", command=lambda: self.new_group(sel))
        m.add_cascade(label="Add to group", menu=add, state=some)
        containing = [g for g in self.model.groups if any(i in self.model.groups[g] for i in sel)]
        rm = tk.Menu(m, tearoff=0)
        for g in containing:
            rm.add_command(label=g, command=lambda g=g: self.remove_from_group(sel, g))
        m.add_cascade(label="Remove from group", menu=rm, state="normal" if containing else "disabled")
        m.add_separator()
        m.add_command(label="New voxel…    Ctrl+N", command=self.new_voxel)
        m.tk_popup(e.x_root, e.y_root)

    def _nav_menu(self, e):
        row = self.nav.identify_row(e.y)
        if row:
            self.nav.selection_set(row)
        key = self.nav_key()
        m = tk.Menu(self.root, tearoff=0)
        if key.startswith("group:"):
            m.add_command(label="New voxel in this group…", command=self.new_voxel)
            m.add_command(label="Duplicate as new species…", command=self.duplicate_nav_group)
            m.add_command(label="Rename group…", command=self.rename_nav_item)
            m.add_command(label="Delete group", command=self.delete_nav_group)
        elif key.startswith("type:"):
            t = int(key[5:])
            m.add_command(label="New voxel in this type…", command=lambda: self.new_voxel(type_id=t))
            m.add_command(label="Rename type label…", command=lambda: self.rename_type(t))
        m.add_command(label="New group from selected rows…", command=self.new_group)
        m.tk_popup(e.x_root, e.y_root)

    # ------------------------------------------------------------------ files
    def save(self):
        try:
            backup = backup_files(self.paths)
            self.model.save(self.paths)
        except Exception as e:
            messagebox.showerror("Save failed", str(e), parent=self.root)
            return
        self.saved_state = self.model.state()
        self.file_mtimes = self.paths.mtimes()
        self.update_title()
        n_prob = sum(1 for i in self.model.indices() if self.problems(i))
        msg = f"Saved {len(self.model.indices())} voxels."
        if backup:
            try:
                shown = os.path.relpath(backup, os.path.dirname(self.paths.data_dir))
            except ValueError:  # different drive
                shown = backup
            msg += f" Previous files backed up to {shown}."
        if n_prob:
            msg += f" {n_prob} voxel(s) have problems (see ⚠ Problems)."
        self.status(msg)

    def reload(self, ask=True):
        if ask and self.is_dirty() and not messagebox.askyesno(
                "Reload", "Discard unsaved changes and reload the files from disk?", parent=self.root):
            return
        self.schemas, schema_errors = load_schemas(self.paths.schemas)
        msgs = self.model.load(self.paths) + schema_errors
        self.saved_state = self.model.state()
        self.file_mtimes = self.paths.mtimes()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._coalesce = None
        self._param_sig = None
        self.refresh_all()
        self.status(" · ".join(msgs) if msgs else "Reloaded the data files and schemas.")

    def _on_focus_in(self, _e):
        now = time.monotonic()
        if now - self._last_focus_check < 1.0:
            return
        self._last_focus_check = now
        if self.paths.mtimes() == self.file_mtimes:
            return
        if not self.is_dirty():
            self.reload(ask=False)
            self.status("The data files changed on disk; reloaded them.")
            return
        self.file_mtimes = self.paths.mtimes()  # ask only once
        if messagebox.askyesno("Files changed", "The data files changed on disk (git, another editor?).\n"
                                                "Reload them and lose your unsaved changes?", parent=self.root):
            self.reload(ask=False)

    def on_close(self):
        if self.is_dirty():
            ans = messagebox.askyesnocancel("Unsaved changes", "Save changes before closing?", parent=self.root)
            if ans is None:
                return
            if ans:
                self.save()
                if self.is_dirty():
                    return
        self._save_ui_state()
        self.root.destroy()

    def _save_ui_state(self):
        try:
            state = {"geometry": self.root.geometry(), "open": self.open_idx, "nav": self.nav_key()}
            w = self.paned.winfo_width()
            if w > 300:
                # Fractions of the paned width, so they still fit on a screen of another size.
                state["sash_fractions"] = [round(self.paned.sashpos(i) / w, 4) for i in range(2)]
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except Exception:
            pass

    MIN_PANE = 160  # px; a divider closer than this to an edge or to the other divider counts as broken

    def _sash_positions(self, w, fractions):
        """Divider positions for paned width w: the saved fractions if they still make sense, else defaults."""
        if isinstance(fractions, list) and len(fractions) == 2:
            try:
                a, b = (int(float(f) * w) for f in fractions)
                if self.MIN_PANE <= a and a + self.MIN_PANE <= b <= w - self.MIN_PANE:
                    return a, b
            except (TypeError, ValueError):
                pass
        a = min(195, w // 5)
        b = max(a + self.MIN_PANE, w - 535)
        return a, min(b, w - self.MIN_PANE)

    def _restore_ui_state(self):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
        if state.get("geometry"):
            self.root.geometry(state["geometry"])
        if state.get("nav") and self.nav.exists(state["nav"]):
            self.nav.selection_set(state["nav"])
            self.refresh_table()
        if state.get("open") is not None and self.model.exists(state["open"]):
            self.open_voxel(state["open"], push_history=False)

        # Place the dividers only once the window is really laid out. Setting them earlier (a fixed
        # delay was used before) can run while the paned window is still 1 px wide on a slower PC,
        # which pins both dividers to the left edge.
        fractions = state.get("sash_fractions")
        pending = {"job": None, "done": False}

        def apply():
            pending["job"] = None
            w = self.paned.winfo_width()
            if pending["done"] or w <= 300:
                return
            a, b = self._sash_positions(w, fractions)
            self.paned.sashpos(0, a)
            self.paned.sashpos(1, b)
            pending["done"] = True
            self.paned.unbind("<Configure>", bind_id)

        def on_configure(_e):
            # Configure fires several times while the window settles; act after the last one.
            if pending["job"]:
                self.paned.after_cancel(pending["job"])
            pending["job"] = self.paned.after(80, apply)

        bind_id = self.paned.bind("<Configure>", on_configure, add="+")


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATA_DIR
    root = tk.Tk()
    App(root, data_dir)
    root.mainloop()


if __name__ == "__main__":
    main()
