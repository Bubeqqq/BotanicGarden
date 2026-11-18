import json
import os
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox, simpledialog

# ==============================================================================
# TWARDO ZAKODOWANE ŚCIEŻKI I DANE STARTOWE JSON (JAKO STRINGI)
# ==============================================================================

PROJECT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLORS_FILE_PATH  = os.path.join(PROJECT_PATH, "voxel_data/voxel_colors.json")
STRUCTS_FILE_PATH = os.path.join(PROJECT_PATH, "voxel_data/voxel_data.json")
AUX_FILE_PATH     = os.path.join(PROJECT_PATH, "voxel_data/voxel_editor_aux.json")

# Domyślny JSON dla kolorów (dodano wartość A)
DEFAULT_COLORS_JSON_STRING = """
[
  { "Index":    0, "R": 0.0 , "G": 0.0 , "B": 0.0 , "A": 0.0 },
  { "Index": 2048, "R": 0.45, "G": 0.45, "B": 0.48, "A": 1.0 },
  { "Index": 2049, "R": 0.35, "G": 0.22, "B": 0.12, "A": 1.0 },
  { "Index": 2050, "R": 0.20, "G": 0.65, "B": 0.25, "A": 1.0 },
  { "Index": 4096, "R": 0.90, "G": 0.15, "B": 0.20, "A": 1.0 },
  { "Index": 4097, "R": 0.95, "G": 0.85, "B": 0.10, "A": 1.0 }
]
"""

# Domyślny JSON dla struktur (używany, gdy plik jeszcze nie istnieje na dysku)
DEFAULT_STRUCTS_JSON_STRING = """
[
  { "index":    0, "s0":   0, "s1":   0, "s2":   0, "s3":   0, "s4":   0, "s5":   0, "s6":   0, "s7":   0 },
  { "index": 2048, "s0":   1, "s1": 100, "s2":   0, "s3":   0, "s4":   0, "s5":   0, "s6":   0, "s7":   0 },
  { "index": 2049, "s0":   1, "s1":  50, "s2":   0, "s3":   0, "s4":   0, "s5":   0, "s6":   0, "s7":   0 },
  { "index": 2050, "s0":   1, "s1":  40, "s2":   1, "s3":   0, "s4":   0, "s5":   0, "s6":   0, "s7":   0 },
  { "index": 4096, "s0":   2, "s1":   5, "s2":  10, "s3":   0, "s4":   0, "s5":   0, "s6":   0, "s7":   0 },
  { "index": 4097, "s0":   2, "s1":   5, "s2":  12, "s3":   0, "s4":   0, "s5":   0, "s6":   0, "s7":   0 }
]
"""

DEFAULT_AUX_JSON_STRING = """
{
  "voxel_names": {
    "0"   : "Powietrze (Air)",
    "2048": "Kamień",
    "2049": "Ziemia",
    "2050": "Trawa",
    "4096": "Czerwona Róża",
    "4097": "Mlecz"
  },
  "groups": {
    "Podstawowe bloki terenu": [2048, 2049, 2050],
    "Kwiaty wiosenne": [4096, 4097]
  },
  "type_names": {
    "0": "Special voxels (air, ...)",
    "1": "Static blocks",
    "2": "Flowers"
  }
}
"""

# ==============================================================================
# FUNKCJE POMOCNICZE
# ==============================================================================

def rgb_float_to_hex(r: float, g: float, b: float) -> str:
    ri = max(0, min(255, int(round(r * 255))))
    gi = max(0, min(255, int(round(g * 255))))
    bi = max(0, min(255, int(round(b * 255))))
    return f"#{ri:02X}{gi:02X}{bi:02X}"

def hex_to_rgb_float(hex_str: str):
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) != 6:
        raise ValueError("Nieprawidłowy format HEX")
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return round(r, 4), round(g, 4), round(b, 4)

def get_contrast_text_color(r: float, g: float, b: float) -> str:
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if luminance > 0.52 else "#FFFFFF"

def get_voxel_type_id(index: int) -> int:
    return max(0, min(31, index // 2048))

# ==============================================================================
# GŁÓWNA KLASA APLIKACJI OKIENKOWEJ
# ==============================================================================

class VoxelEditorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BotanicGarden - Wizualny Edytor Voxeli (Kolory + Struktury + Grupy)")
        self.root.geometry("1380x820")
        self.root.minsize(1150, 700)

        # Dane w pamięci:
        # self.colors: dict[int, tuple[float, float, float, float]] (R, G, B, A)
        self.colors = {}
        self.structs = {}
        self.voxel_names = {}
        self.groups = {}
        self.type_names = {}

        self._updating_ui = False

        self.load_all_data()
        self.build_ui()
        self.refresh_group_list()
        self.refresh_table()

        self.root.bind("<Control-s>", lambda e: self.save_all_data())

    # --------------------------------------------------------------------------
    # WCZYTYWANIE I ZAPISYWANIE DANYCH
    # --------------------------------------------------------------------------

    def load_all_data(self):
        self.colors.clear()
        self.structs.clear()

        # 1. Wczytanie kolorów
        if os.path.exists(COLORS_FILE_PATH):
            with open(COLORS_FILE_PATH, "r", encoding="utf-8") as f:
                raw_colors = json.load(f)
        else:
            raw_colors = json.loads(DEFAULT_COLORS_JSON_STRING)

        for item in raw_colors:
            norm = {k.lower(): v for k, v in item.items()}
            idx = int(norm.get("index", 0))
            r = float(norm.get("r", 0.0))
            g = float(norm.get("g", 0.0))
            b = float(norm.get("b", 0.0))
            a = float(norm.get("a", 1.0)) # Domyślnie 1.0, jeśli brak wpisu w starych danych
            self.colors[idx] = (r, g, b, a)

        # 2. Wczytanie struktur s0..s7
        if os.path.exists(STRUCTS_FILE_PATH):
            with open(STRUCTS_FILE_PATH, "r", encoding="utf-8") as f:
                raw_structs = json.load(f)
        else:
            raw_structs = json.loads(DEFAULT_STRUCTS_JSON_STRING)

        for item in raw_structs:
            norm = {k.lower(): v for k, v in item.items()}
            idx = int(norm.get("index", 0))
            s_vals = [int(norm.get(f"s{i}", 0)) for i in range(8)]
            self.structs[idx] = s_vals

        # 3. Wczytanie pliku pomocniczego
        if os.path.exists(AUX_FILE_PATH):
            try:
                with open(AUX_FILE_PATH, "r", encoding="utf-8") as f:
                    aux = json.load(f)
            except Exception:
                aux = json.loads(DEFAULT_AUX_JSON_STRING)
        else:
            aux = json.loads(DEFAULT_AUX_JSON_STRING)

        self.voxel_names = aux.get("voxel_names", {})
        self.groups = {k: sorted(list(set(int(x) for x in v))) for k, v in aux.get("groups", {}).items()}
        self.type_names = aux.get("type_names", {})
        for t in range(32):
            if str(t) not in self.type_names:
                self.type_names[str(t)] = ""

    def save_all_data(self):
        try:
            for path in (COLORS_FILE_PATH, STRUCTS_FILE_PATH, AUX_FILE_PATH):
                folder = os.path.dirname(path)
                if folder and not os.path.exists(folder):
                    os.makedirs(folder, exist_ok=True)

            # Zapis VoxelColors.json (dodano A)
            colors_out = [
                {
                    "Index": idx,
                    "R": round(rgba[0], 4),
                    "G": round(rgba[1], 4),
                    "B": round(rgba[2], 4),
                    "A": round(rgba[3], 4)
                }
                for idx, rgba in sorted(self.colors.items())
            ]
            with open(COLORS_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(colors_out, f, indent=2, ensure_ascii=False)

            # Zapis VoxelDataStruct.json
            structs_out = [
                {
                    "index": idx,
                    "s0": vals[0],
                    "s1": vals[1],
                    "s2": vals[2],
                    "s3": vals[3],
                    "s4": vals[4],
                    "s5": vals[5],
                    "s6": vals[6],
                    "s7": vals[7],
                }
                for idx, vals in sorted(self.structs.items())
            ]
            with open(STRUCTS_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(structs_out, f, indent=2, ensure_ascii=False)

            # Zapis pliku pomocniczego
            aux_out = {
                "voxel_names": self.voxel_names,
                "groups": self.groups,
                "type_names": self.type_names
            }
            with open(AUX_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(aux_out, f, indent=2, ensure_ascii=False)

            self.status_var.set(f"Zapisano pomyślnie do katalogu: {os.path.dirname(COLORS_FILE_PATH)}")
            messagebox.showinfo("Zapisano pliki", "Zmiany zostały pomyślnie zapisane na dysku.")
        except Exception as e:
            messagebox.showerror("Błąd zapisu", f"Nie udało się zapisać plików:\n{e}")

    # --------------------------------------------------------------------------
    # BUDOWANIE INTERFEJSU GRAFICZNEGO
    # --------------------------------------------------------------------------

    def build_ui(self):
        top_bar = ttk.Frame(self.root, padding=(10, 6))
        top_bar.pack(fill=tk.X)
        ttk.Label(top_bar, text="", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        ttk.Button(top_bar, text="💾 Zapisz wszystko (Ctrl+S)", command=self.save_all_data).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top_bar, text="🔄 Wczytaj ponownie z dysku", command=self.reload_from_disk).pack(side=tk.RIGHT, padx=4)

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        left_frame = ttk.Frame(paned, padding=6)
        paned.add(left_frame, weight=1)
        self.build_left_panel(left_frame)

        center_frame = ttk.Frame(paned, padding=6)
        paned.add(center_frame, weight=3)
        self.build_center_panel(center_frame)

        right_frame = ttk.Frame(paned, padding=6)
        paned.add(right_frame, weight=2)
        self.build_right_panel(right_frame)

        self.status_var = tk.StringVar(value="Gotowy. Kliknij voxel na liście lub utwórz nowy.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=(6, 3))
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def build_left_panel(self, parent):
        search_box = ttk.LabelFrame(parent, text="Filtruj voxele", padding=6)
        search_box.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(search_box, text="Szukaj (indeks lub nazwa):").pack(anchor=tk.W)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_table())
        ttk.Entry(search_box, textvariable=self.search_var).pack(fill=tk.X, pady=(2, 6))

        ttk.Label(search_box, text="Filtr typu (wg zakresów 2048):").pack(anchor=tk.W)
        self.type_filter_var = tk.StringVar(value="Wszystkie typy")
        self.type_combo = ttk.Combobox(search_box, textvariable=self.type_filter_var, state="readonly")
        self.populate_type_combo()
        self.type_combo.pack(fill=tk.X, pady=(2, 4))
        self.type_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())

        ttk.Button(search_box, text="✏️ Zmień opis wybranego Typu (0-31)", command=self.rename_selected_type).pack(fill=tk.X, pady=(2, 0))

        group_box = ttk.LabelFrame(parent, text="Własne Grupy Indeksów", padding=6)
        group_box.pack(fill=tk.BOTH, expand=True)
        ttk.Label(group_box, text="Wybierz grupę do podglądu:").pack(anchor=tk.W)

        list_frame = ttk.Frame(group_box)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=4)
        self.group_listbox = tk.Listbox(list_frame, exportselection=False, height=12)
        sc = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.group_listbox.yview)
        self.group_listbox.configure(yscrollcommand=sc.set)
        self.group_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sc.pack(side=tk.RIGHT, fill=tk.Y)
        self.group_listbox.bind("<<ListboxSelect>>", lambda e: self.refresh_table())

        btn_grid = ttk.Frame(group_box)
        btn_grid.pack(fill=tk.X, pady=2)
        ttk.Button(btn_grid, text="➕ Nowa grupa", command=self.create_group).pack(fill=tk.X, pady=1)
        ttk.Button(btn_grid, text="✏️ Zmień nazwę grupy", command=self.rename_group).pack(fill=tk.X, pady=1)
        ttk.Button(btn_grid, text="🗑️ Usuń grupę", command=self.delete_group).pack(fill=tk.X, pady=1)

        ttk.Separator(group_box, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)
        ttk.Label(group_box, text="Przypisywanie indeksów do grupy:").pack(anchor=tk.W, pady=(0, 2))
        ttk.Button(group_box, text="📥 Dodaj zaznaczone w tabeli do grupy", command=self.add_selected_voxels_to_group).pack(fill=tk.X, pady=1)
        ttk.Button(group_box, text="🔢 Dodaj zakres/listę (np. 2048-2055)", command=self.add_range_to_group).pack(fill=tk.X, pady=1)
        ttk.Button(group_box, text="📤 Usuń zaznaczone w tabeli z grupy", command=self.remove_selected_voxels_from_group).pack(fill=tk.X, pady=1)

    def build_center_panel(self, parent):
        header = ttk.Frame(parent)
        header.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(header, text="Lista Voxeli (możesz zaznaczyć wiele wierszy z Ctrl / Shift)", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

        columns = ("index", "name", "type", "groups", "hex", "rgba", "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7")
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        headings = {
            "index": ("Index", 65),
            "name": ("Nazwa (Aux)", 140),
            "type": ("Typ (0-31)", 120),
            "groups": ("Grupy", 130),
            "hex": ("Kolor", 75),
            "rgba": ("R, G, B, A (0..1)", 140),
            "s0": ("s0", 45), "s1": ("s1", 45), "s2": ("s2", 45), "s3": ("s3", 45),
            "s4": ("s4", 45), "s5": ("s5", 45), "s6": ("s6", 45), "s7": ("s7", 45),
        }
        for col, (text, width) in headings.items():
            self.tree.heading(col, text=text)
            anchor = tk.CENTER if col not in ("name", "type", "groups") else tk.W
            self.tree.column(col, width=width, minwidth=40, anchor=anchor)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

    def build_right_panel(self, parent):
        meta_box = ttk.LabelFrame(parent, text="1. Identyfikacja Voxela", padding=8)
        meta_box.pack(fill=tk.X, pady=(0, 8))

        row1 = ttk.Frame(meta_box)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="Index (0 - 65535):").pack(side=tk.LEFT)
        self.idx_var = tk.IntVar(value=2048)
        self.idx_spin = ttk.Spinbox(row1, from_=0, to=65535, textvariable=self.idx_var, width=10)
        self.idx_spin.pack(side=tk.LEFT, padx=6)
        self.idx_var.trace_add("write", lambda *_: self.update_type_info_label())

        self.type_info_var = tk.StringVar(value="Type 1 (2048-4095)")
        ttk.Label(row1, textvariable=self.type_info_var, foreground="#2b579a").pack(side=tk.LEFT, padx=4)

        row2 = ttk.Frame(meta_box)
        row2.pack(fill=tk.X, pady=4)
        ttk.Label(row2, text="Nazwa robocza:").pack(side=tk.LEFT)
        self.name_var = tk.StringVar(value="")
        ttk.Entry(row2, textvariable=self.name_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        row3 = ttk.Frame(meta_box)
        row3.pack(fill=tk.X, pady=2)
        self.in_colors_var = tk.BooleanVar(value=True)
        self.in_structs_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row3, text="Zapisz w VoxelColors.json", variable=self.in_colors_var).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(row3, text="Zapisz w VoxelDataStruct.json", variable=self.in_structs_var).pack(side=tk.LEFT)

        color_box = ttk.LabelFrame(parent, text="2. Kolor Voxela (RGBA 0.0 - 1.0)", padding=8)
        color_box.pack(fill=tk.X, pady=(0, 8))

        preview_row = ttk.Frame(color_box)
        preview_row.pack(fill=tk.X, pady=(0, 8))

        self.color_canvas = tk.Canvas(preview_row, width=110, height=55, bg="#73737A", highlightthickness=1, highlightbackground="#444444", cursor="hand2")
        self.color_canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.color_canvas.bind("<Button-1>", lambda e: self.open_color_picker())

        right_color_controls = ttk.Frame(preview_row)
        right_color_controls.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Button(right_color_controls, text="🎨 Wybierz z palety kolorów...", command=self.open_color_picker).pack(fill=tk.X, pady=(0, 4))

        hex_row = ttk.Frame(right_color_controls)
        hex_row.pack(fill=tk.X)
        ttk.Label(hex_row, text="Kod HEX:").pack(side=tk.LEFT)
        self.hex_var = tk.StringVar(value="#73737A")
        hex_entry = ttk.Entry(hex_row, textvariable=self.hex_var, width=10)
        hex_entry.pack(side=tk.LEFT, padx=4)
        ttk.Button(hex_row, text="Ustaw z HEX", command=self.apply_hex_input).pack(side=tk.LEFT)

        self.r_var = tk.DoubleVar(value=0.45)
        self.g_var = tk.DoubleVar(value=0.45)
        self.b_var = tk.DoubleVar(value=0.48)
        self.a_var = tk.DoubleVar(value=1.0) # NOWE POLE - ALPHA

        for label_txt, var, col_hex in (
            ("R (Czerwony):", self.r_var, "#C0392B"),
            ("G (Zielony):", self.g_var, "#27AE60"),
            ("B (Niebieski):", self.b_var, "#2980B9"),
            ("A (Przeźroczystość):", self.a_var, "#555555")
        ):
            r_frame = ttk.Frame(color_box)
            r_frame.pack(fill=tk.X, pady=2)
            ttk.Label(r_frame, text=label_txt, width=17, foreground=col_hex).pack(side=tk.LEFT)
            scale = ttk.Scale(r_frame, from_=0.0, to=1.0, variable=var, command=lambda _val, v=var: self.on_rgb_slider_move(v))
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
            entry = ttk.Spinbox(r_frame, from_=0.0, to=1.0, increment=0.01, textvariable=var, width=7, format="%.3f", command=self.update_color_preview_from_vars)
            entry.pack(side=tk.LEFT)
            entry.bind("<Return>", lambda e: self.update_color_preview_from_vars())
            entry.bind("<FocusOut>", lambda e: self.update_color_preview_from_vars())

        # Sekcja 3: 8 wartości specjalnych (s0 - s7)
        struct_box = ttk.LabelFrame(parent, text="3. Wartości specjalne (s0 - s7, typ ushort: 0 do 65535)", padding=8)
        struct_box.pack(fill=tk.X, pady=(0, 8))

        grid_f = ttk.Frame(struct_box)
        grid_f.pack(fill=tk.X)

        self.s_vars = [tk.IntVar(value=0) for _ in range(8)]
        for i in range(8):
            r_idx = i // 2
            c_idx = (i % 2) * 2
            ttk.Label(grid_f, text=f"s{i}:", width=4, anchor=tk.E).grid(row=r_idx, column=c_idx, padx=(4, 2), pady=3, sticky="e")
            sp = ttk.Spinbox(grid_f, from_=0, to=65535, textvariable=self.s_vars[i], width=10)
            sp.grid(row=r_idx, column=c_idx + 1, padx=(0, 12), pady=3, sticky="we")
            grid_f.columnconfigure(c_idx + 1, weight=1)

        actions_box = ttk.LabelFrame(parent, text="4. Operacje na Voxelach", padding=8)
        actions_box.pack(fill=tk.X)
        ttk.Button(actions_box, text="✅ Zapisz / Zaktualizuj ten Voxel (wg pola Index)", command=self.save_single_voxel).pack(fill=tk.X, pady=2)
        ttk.Button(actions_box, text="➕ Znajdź pierwszy wolny Index w bieżącym Typie", command=self.find_next_free_index).pack(fill=tk.X, pady=2)
        ttk.Separator(actions_box, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)
        ttk.Button(actions_box, text="🎨 Zastosuj powyższy KOLOR (RGBA) do zaznaczonych", command=self.batch_apply_color).pack(fill=tk.X, pady=2)
        ttk.Button(actions_box, text="⚙️ Zastosuj powyższe s0-s7 do wszystkich zaznaczonych", command=self.batch_apply_structs).pack(fill=tk.X, pady=2)
        ttk.Separator(actions_box, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)
        ttk.Button(actions_box, text="🗑️ Usuń zaznaczone Voxele", command=self.delete_selected_voxels).pack(fill=tk.X, pady=2)

        self.update_color_preview_from_vars()
        self.update_type_info_label()

    # --------------------------------------------------------------------------
    # LOGIKA KOLORÓW I FORMULARZA
    # --------------------------------------------------------------------------

    def on_rgb_slider_move(self, var: tk.DoubleVar):
        if self._updating_ui: return
        var.set(round(float(var.get()), 3))
        self.update_color_preview_from_vars()

    def update_color_preview_from_vars(self):
        if self._updating_ui: return
        try:
            r = max(0.0, min(1.0, float(self.r_var.get())))
            g = max(0.0, min(1.0, float(self.g_var.get())))
            b = max(0.0, min(1.0, float(self.b_var.get())))
            # Weryfikacja dla przeźroczystości
            _a = max(0.0, min(1.0, float(self.a_var.get())))
        except (ValueError, tk.TclError):
            return

        hex_code = rgb_float_to_hex(r, g, b)
        self._updating_ui = True
        self.hex_var.set(hex_code)
        self.color_canvas.configure(bg=hex_code) # Canvas nie używa wartości A
        self._updating_ui = False

    def open_color_picker(self):
        current_hex = self.hex_var.get()
        rgb_255, hex_code = colorchooser.askcolor(color=current_hex, title="Wybierz kolor voxela")
        if hex_code:
            r, g, b = hex_to_rgb_float(hex_code)
            self._updating_ui = True
            self.r_var.set(round(r, 3))
            self.g_var.set(round(g, 3))
            self.b_var.set(round(b, 3))
            self.hex_var.set(hex_code.upper())
            self.color_canvas.configure(bg=hex_code.upper())
            self._updating_ui = False

    def apply_hex_input(self):
        try:
            r, g, b = hex_to_rgb_float(self.hex_var.get())
            self._updating_ui = True
            self.r_var.set(round(r, 3))
            self.g_var.set(round(g, 3))
            self.b_var.set(round(b, 3))
            self.color_canvas.configure(bg=rgb_float_to_hex(r, g, b))
            self._updating_ui = False
        except ValueError as e:
            messagebox.showwarning("Błędny HEX", str(e))

    def update_type_info_label(self):
        try:
            idx = int(self.idx_var.get())
        except (ValueError, tk.TclError):
            self.type_info_var.set("Nieprawidłowy indeks")
            return
        t_id = get_voxel_type_id(idx)
        t_desc = self.type_names.get(str(t_id), "")
        suffix = f" - {t_desc}" if t_desc else ""
        warn = " [UWAGA: >32766 dla short!]" if idx >= 32767 else ""
        self.type_info_var.set(f"Type {t_id} ({t_id*2048}-{t_id*2048+2047}){suffix}{warn}")

    # --------------------------------------------------------------------------
    # ODŚWIEŻANIE TABELI I FILTROWANIE
    # --------------------------------------------------------------------------

    def populate_type_combo(self):
        values = ["Wszystkie typy"]
        for t in range(32):
            start = t * 2048
            end = start + 2047
            desc = self.type_names.get(str(t), "").strip()
            label = f"Type {t}: {start}-{end}" + (f" ({desc})" if desc else "")
            values.append(label)
        self.type_combo["values"] = values

    def refresh_group_list(self):
        sel = self.get_selected_group_name()
        self.group_listbox.delete(0, tk.END)
        all_count = len(set(self.colors.keys()) | set(self.structs.keys()))
        self.group_listbox.insert(tk.END, f"[Wszystkie voxele] ({all_count})")

        selected_idx = 0
        for i, (g_name, members) in enumerate(sorted(self.groups.items()), start=1):
            self.group_listbox.insert(tk.END, f"{g_name} ({len(members)})")
            if g_name == sel:
                selected_idx = i
        self.group_listbox.selection_set(selected_idx)

    def get_selected_group_name(self):
        sel = self.group_listbox.curselection()
        if not sel or sel[0] == 0: return None
        sorted_names = sorted(self.groups.keys())
        idx = sel[0] - 1
        if 0 <= idx < len(sorted_names): return sorted_names[idx]
        return None

    def get_groups_for_index(self, idx: int):
        return [g_name for g_name, members in self.groups.items() if idx in members]

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        all_indices = sorted(set(self.colors.keys()) | set(self.structs.keys()))

        active_group = self.get_selected_group_name()
        if active_group is not None:
            group_set = set(self.groups.get(active_group, []))
            all_indices = [i for i in all_indices if i in group_set]

        type_filter = self.type_filter_var.get()
        if type_filter.startswith("Type "):
            try:
                t_num = int(type_filter.split(":")[0].replace("Type ", "").strip())
                all_indices = [i for i in all_indices if get_voxel_type_id(i) == t_num]
            except ValueError: pass

        query = self.search_var.get().strip().lower()

        for idx in all_indices:
            name = self.voxel_names.get(str(idx), "")
            if query and (query not in str(idx) and query not in name.lower()): continue

            t_id = get_voxel_type_id(idx)
            t_desc = self.type_names.get(str(t_id), "")
            type_str = f"T{t_id}" + (f": {t_desc}" if t_desc else "")

            grp_list = self.get_groups_for_index(idx)
            grp_str = ", ".join(grp_list)

            if idx in self.colors:
                r, g, b, a = self.colors[idx]
                hex_col = rgb_float_to_hex(r, g, b)
                rgba_str = f"{r:.2f}, {g:.2f}, {b:.2f}, {a:.2f}"
                fg_col = get_contrast_text_color(r, g, b)
            else:
                hex_col = "Brak"
                rgba_str = "-"
                fg_col = "#000000"

            s_vals = self.structs.get(idx, ["-"] * 8)
            tag_name = f"voxel_{idx}"
            self.tree.insert("", tk.END, iid=str(idx), values=(idx, name, type_str, grp_str, hex_col, rgba_str, *s_vals), tags=(tag_name,))
            if idx in self.colors:
                self.tree.tag_configure(tag_name, background=hex_col, foreground=fg_col)

    # --------------------------------------------------------------------------
    # OBSŁUGA WYBORU I EDYCJI VOXELI
    # --------------------------------------------------------------------------

    def on_tree_select(self, _event):
        selected = self.tree.selection()
        if not selected: return

        idx = int(selected[0])
        self._updating_ui = True

        self.idx_var.set(idx)
        self.name_var.set(self.voxel_names.get(str(idx), ""))

        has_color = idx in self.colors
        has_struct = idx in self.structs
        self.in_colors_var.set(has_color)
        self.in_structs_var.set(has_struct)

        if has_color:
            r, g, b, a = self.colors[idx]
            self.r_var.set(round(r, 3))
            self.g_var.set(round(g, 3))
            self.b_var.set(round(b, 3))
            self.a_var.set(round(a, 3))
            hex_c = rgb_float_to_hex(r, g, b)
            self.hex_var.set(hex_c)
            self.color_canvas.configure(bg=hex_c)

        if has_struct:
            for i, val in enumerate(self.structs[idx]):
                self.s_vars[i].set(val)
        else:
            for i in range(8):
                self.s_vars[i].set(0)

        self._updating_ui = False
        self.update_type_info_label()

    def validate_and_read_form(self):
        try:
            idx = int(self.idx_var.get())
            if not (0 <= idx <= 65535):
                raise ValueError("Index musi mieścić się w przedziale od 0 do 65535 (ushort).")
        except ValueError as e:
            messagebox.showerror("Błąd walidacji", f"Nieprawidłowy Index:\n{e}")
            return None

        try:
            r = max(0.0, min(1.0, float(self.r_var.get())))
            g = max(0.0, min(1.0, float(self.g_var.get())))
            b = max(0.0, min(1.0, float(self.b_var.get())))
            a = max(0.0, min(1.0, float(self.a_var.get())))
        except ValueError:
            messagebox.showerror("Błąd walidacji", "Wartości R, G, B, A muszą być liczbami zmiennoprzecinkowymi (0.0 - 1.0).")
            return None

        s_vals = []
        try:
            for i in range(8):
                val = int(self.s_vars[i].get())
                if not (0 <= val <= 65535):
                    raise ValueError(f"Wartość s{i} ({val}) przekracza zakres ushort (0 do 65535).")
                s_vals.append(val)
        except ValueError as e:
            messagebox.showerror("Błąd walidacji s0-s7", str(e))
            return None

        return idx, (r, g, b, a), s_vals

    def save_single_voxel(self):
        res = self.validate_and_read_form()
        if not res: return
        idx, rgba, s_vals = res

        if self.in_colors_var.get():
            self.colors[idx] = rgba
        elif idx in self.colors:
            del self.colors[idx]

        if self.in_structs_var.get():
            self.structs[idx] = s_vals
        elif idx in self.structs:
            del self.structs[idx]

        name_clean = self.name_var.get().strip()
        if name_clean:
            self.voxel_names[str(idx)] = name_clean
        elif str(idx) in self.voxel_names:
            del self.voxel_names[str(idx)]

        active_group = self.get_selected_group_name()
        if active_group and idx not in self.groups[active_group]:
            self.groups[active_group].append(idx)
            self.groups[active_group].sort()

        self.refresh_group_list()
        self.refresh_table()
        if self.tree.exists(str(idx)):
            self.tree.selection_set(str(idx))
            self.tree.see(str(idx))
        self.status_var.set(f"Zaktualizowano voxel o indeksie {idx}.")

    def find_next_free_index(self):
        try:
            curr = int(self.idx_var.get())
        except ValueError:
            curr = 0
        t_id = get_voxel_type_id(curr)
        start = t_id * 2048
        end = start + 2047
        used = set(self.colors.keys()) | set(self.structs.keys())
        for candidate in range(start, end + 1):
            if candidate not in used:
                self.idx_var.set(candidate)
                self.name_var.set("")
                self.status_var.set(f"Wskazano pierwszy wolny indeks w Type {t_id}: {candidate}")
                return
        messagebox.showinfo("Brak wolnych indeksów", f"Wszystkie indeksy w Type {t_id} ({start}-{end}) są zajęte.")

    def batch_apply_color(self):
        selected = [int(x) for x in self.tree.selection()]
        if not selected:
            messagebox.showwarning("Brak zaznaczenia", "Zaznacz w tabeli przynajmniej jeden voxel.")
            return
        res = self.validate_and_read_form()
        if not res: return
        _, rgba, _ = res
        for idx in selected:
            self.colors[idx] = rgba
        self.refresh_table()
        self.status_var.set(f"Zastosowano nowy kolor RGBA dla {len(selected)} zaznaczonych voxeli.")

    def batch_apply_structs(self):
        selected = [int(x) for x in self.tree.selection()]
        if not selected:
            messagebox.showwarning("Brak zaznaczenia", "Zaznacz w tabeli przynajmniej jeden voxel.")
            return
        res = self.validate_and_read_form()
        if not res: return
        _, _, s_vals = res
        for idx in selected:
            self.structs[idx] = list(s_vals)
        self.refresh_table()
        self.status_var.set(f"Zastosowano wartości s0-s7 dla {len(selected)} zaznaczonych voxeli.")

    def delete_selected_voxels(self):
        selected = [int(x) for x in self.tree.selection()]
        if not selected: return
        if not messagebox.askyesno("Potwierdzenie", f"Czy na pewno usunąć zaznaczone voxele ({len(selected)} szt.) z obu plików?"):
            return
        for idx in selected:
            self.colors.pop(idx, None)
            self.structs.pop(idx, None)
            self.voxel_names.pop(str(idx), None)
            for grp in self.groups.values():
                if idx in grp: grp.remove(idx)
        self.refresh_group_list()
        self.refresh_table()
        self.status_var.set(f"Usunięto {len(selected)} voxeli.")

    # --------------------------------------------------------------------------
    # ZARZĄDZANIE GRUPAMI I NAZWAMI TYPÓW
    # --------------------------------------------------------------------------

    def create_group(self):
        name = simpledialog.askstring("Nowa grupa", "Podaj nazwę nowej grupy voxeli:")
        if not name: return
        name = name.strip()
        if name in self.groups:
            messagebox.showwarning("Grupa istnieje", "Grupa o takiej nazwie już istnieje.")
            return
        selected = [int(x) for x in self.tree.selection()]
        self.groups[name] = sorted(selected)
        self.refresh_group_list()
        self.refresh_table()
        self.status_var.set(f"Utworzono grupę '{name}' ({len(selected)} indeksów).")

    def rename_group(self):
        old_name = self.get_selected_group_name()
        if not old_name:
            messagebox.showinfo("Wybierz grupę", "Najpierw wybierz własną grupę na liście po lewej stronie.")
            return
        new_name = simpledialog.askstring("Zmień nazwę grupy", "Nowa nazwa grupy:", initialvalue=old_name)
        if not new_name or new_name.strip() == old_name: return
        new_name = new_name.strip()
        self.groups[new_name] = self.groups.pop(old_name)
        self.refresh_group_list()
        self.refresh_table()

    def delete_group(self):
        name = self.get_selected_group_name()
        if not name:
            messagebox.showinfo("Wybierz grupę", "Wybierz grupę do usunięcia (nie usuwa samych voxeli).")
            return
        if messagebox.askyesno("Usuń grupę", f"Czy usunąć grupę '{name}'?\n(Voxele należące do grupy NIE zostaną usunięte)."):
            del self.groups[name]
            self.refresh_group_list()
            self.refresh_table()

    def add_selected_voxels_to_group(self):
        selected = [int(x) for x in self.tree.selection()]
        if not selected:
            messagebox.showinfo("Brak zaznaczenia", "Zaznacz w tabeli voxele, które chcesz dodać do grupy.")
            return
        if not self.groups:
            messagebox.showinfo("Brak grup", "Najpierw utwórz przynajmniej jedną grupę.")
            return
        target_group = self.ask_group_choice("Wybierz grupę docelową")
        if not target_group: return
        current_set = set(self.groups[target_group])
        current_set.update(selected)
        self.groups[target_group] = sorted(current_set)
        self.refresh_group_list()
        self.refresh_table()
        self.status_var.set(f"Dodano {len(selected)} voxeli do grupy '{target_group}'.")

    def add_range_to_group(self):
        target_group = self.get_selected_group_name() or self.ask_group_choice("Wybierz grupę docelową")
        if not target_group: return
        expr = simpledialog.askstring("Dodaj zakres indeksów", f"Podaj indeksy lub zakresy do dodania do grupy '{target_group}'\n(np. 2048-2055, 2060):")
        if not expr: return
        added = set()
        try:
            for part in expr.split(","):
                part = part.strip()
                if not part: continue
                if "-" in part:
                    a, b = part.split("-", 1)
                    start, end = int(a.strip()), int(b.strip())
                    if start > end: start, end = end, start
                    for idx in range(start, end + 1):
                        if 0 <= idx <= 65535: added.add(idx)
                else:
                    idx = int(part)
                    if 0 <= idx <= 65535: added.add(idx)
        except ValueError:
            messagebox.showerror("Błąd formatu", "Użyj formatu liczb oddzielonych przecinkami lub myślnikiem, np.: 2048-2052, 2060")
            return

        missing = [i for i in added if i not in self.colors and i not in self.structs]
        if missing and messagebox.askyesno("Nowe indeksy", f"{len(missing)} z podanych indeksów nie istnieje jeszcze w plikach JSON.\nCzy utworzyć dla nich domyślne wpisy?"):
            for idx in missing:
                self.colors[idx] = (0.5, 0.5, 0.5, 1.0)
                self.structs[idx] = [0] * 8

        self.groups[target_group] = sorted(set(self.groups[target_group]) | added)
        self.refresh_group_list()
        self.refresh_table()
        self.status_var.set(f"Dodano {len(added)} indeksów do grupy '{target_group}'.")

    def remove_selected_voxels_from_group(self):
        active_group = self.get_selected_group_name()
        if not active_group:
            messagebox.showinfo("Wybierz grupę", "Wybierz konkretną grupę na liście po lewej stronie, aby usunąć z niej zaznaczone voxele.")
            return
        selected = set(int(x) for x in self.tree.selection())
        if not selected: return
        self.groups[active_group] = [i for i in self.groups[active_group] if i not in selected]
        self.refresh_group_list()
        self.refresh_table()

    def ask_group_choice(self, title: str):
        names = sorted(self.groups.keys())
        if not names: return None
        if len(names) == 1: return names[0]
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("320x150")
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text="Wybierz grupę:", padding=8).pack(anchor=tk.W)
        var = tk.StringVar(value=names[0])
        cb = ttk.Combobox(win, textvariable=var, values=names, state="readonly")
        cb.pack(fill=tk.X, padx=8, pady=4)
        result = {"val": None}
        def confirm():
            result["val"] = var.get()
            win.destroy()
        ttk.Button(win, text="OK", command=confirm).pack(pady=10)
        self.root.wait_window(win)
        return result["val"]

    def rename_selected_type(self):
        val = self.type_filter_var.get()
        if not val.startswith("Type "):
            messagebox.showinfo("Wybierz typ", "Najpierw wybierz konkretny Typ (np. Type 3) z listy rozwijanej powyżej.")
            return
        t_id = int(val.split(":")[0].replace("Type ", "").strip())
        current_desc = self.type_names.get(str(t_id), "")
        new_desc = simpledialog.askstring(f"Opis dla Type {t_id}", f"Podaj nazwę kategorii dla Type {t_id} (zakres {t_id*2048}-{t_id*2048+2047}):", initialvalue=current_desc)
        if new_desc is not None:
            self.type_names[str(t_id)] = new_desc.strip()
            self.populate_type_combo()
            self.type_combo.current(t_id + 1)
            self.refresh_table()
            self.update_type_info_label()

    def reload_from_disk(self):
        if messagebox.askyesno("Wczytaj ponownie", "Odrzucić niezapisane zmiany i wczytać pliki ponownie?"):
            self.load_all_data()
            self.populate_type_combo()
            self.refresh_group_list()
            self.refresh_table()
            self.status_var.set("Ponownie wczytano dane.")

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    app = VoxelEditorApp(root)
    root.mainloop()