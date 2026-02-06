"""Simple Tkinter GUI to edit parameters and run the model."""

from __future__ import annotations

import json
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, Optional

from .bottleneck import detect_bottleneck
from .model import Config
from .optimizer import constraint_checks, optimize
from .simulate import simulate

TRADUCCIONES = {
    # Modos
    "minimize_time": "Minimización de tiempo",
    "maximize_Q": "Maximización de producción",
    
    # Estados
    "feasible": "factible",
    "infeasible": "inviable",
    
    # Cuellos de botella
    "materia prima": "materia prima",
    "pesado": "pesado (balanzas)",
    "mezcla": "mezcla (bowls)",
    "moldes": "moldes",
    "personal": "personal",
    "acoplamiento": "acoplamiento",
    
    # Restricciones
    "material": "Material",
    "time_pesado": "Tiempo pesado",
    "time_mezcla": "Tiempo mezcla",
    "time_moldes": "Tiempo moldes",
    "personal": "Personal",
    "acoplamiento": "Acoplamiento",
    "gelificacion": "Gelificacion (mezcla->molde)",

}


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Macetas Biodegradables - Optimizador")
        self.geometry("980x720")
        self.minsize(980, 720)
        self.resizable(True, True)
        self.state("zoomed")
        self.colors = {
            "bg": "#E8EDF2",  # Fondo principal
            "panel": "#F5F7FA",  # Paneles
            "accent": "#3D5A80",  # Header azul oscuro
            "accent_2": "#5B8FB9",  # Azul medio
            "text": "#2C3E50",  # Texto principal
            "muted": "#7F8C8D",  # Texto secundario
            "chart_bg": "#FFFFFF",  # Fondo de gráficos
            "chart_bar": "#5B8FB9",  # Barras azules
            "chart_bar_2": "#E07A5F",  # Barras naranjas
            "border": "#BDC3C7",  # Bordes
            "red_border": "#95A5A6",  # Borde sutil
            "label_bg": "#FFFFFF",  # Fondo de etiquetas
            "button_alt": "#5B8FB9",  # Botón secundario
            "hover_green": "#81B29A",  # Hover verde
            "status_bg": "#34495E",  # Barra de estado
        }
        
        self.fonts = {
            "title": ("Segoe UI", 20, "bold"),      # Título principal
            "subtitle": ("Segoe UI", 13, "bold"),   # Subtítulos
            "body": ("Segoe UI", 11),               # Texto normal
            "mono": ("Consolas", 10),               # Texto monoespaciado
            "caption": ("Segoe UI", 10),            # Texto pequeño
        }
        
        self.configure(bg=self.colors["bg"])
        self._apply_theme()
        self._font_cache = {
            "body": tkfont.Font(font=self.fonts["body"]),
            "subtitle": tkfont.Font(font=self.fonts["subtitle"]),
            "mono": tkfont.Font(font=self.fonts["mono"]),
        }

        # Header
        header = tk.Frame(self, bg=self.colors["accent"], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title = tk.Label(
            header,
            text="🌱 Macetas Biodegradables - Optimizador",
            bg=self.colors["accent"],
            fg="#FFFFFF",
            font=self.fonts["title"],
            padx=20,
            pady=12,
        )
        title.pack(anchor=tk.W, side=tk.LEFT)
        
        subtitle = tk.Label(
            header,
            text="Dimensionamiento de equipos y simulación de flujo",
            bg=self.colors["accent"],
            fg="#ECF0F1",
            font=self.fonts["caption"],
            padx=20,
        )
        subtitle.pack(anchor=tk.E, side=tk.RIGHT)

        # Contenedor principal
        container = tk.Frame(self, bg=self.colors["bg"], padx=12, pady=12)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=3)
        container.columnconfigure(1, weight=2)
        container.rowconfigure(0, weight=1)

        self.left = tk.Frame(container, bg=self.colors["bg"])
        self.right = tk.Frame(container, bg=self.colors["bg"])
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.right.grid(row=0, column=1, sticky="nsew")
        self.left.columnconfigure(0, weight=1)
        self.right.columnconfigure(0, weight=1)

        self.left_paned = tk.PanedWindow(
            self.left,
            orient=tk.VERTICAL,
            bg=self.colors["border"],
            sashwidth=6,
            sashrelief=tk.RAISED,
            bd=1,
            sashpad=1,
            showhandle=True,
            handlesize=10,
            handlepad=20,
        )
        self.left_paned.pack(fill=tk.BOTH, expand=True)
        
        # Frame para parámetros
        self.form_container = tk.Frame(self.left_paned, bg=self.colors["bg"])
        self._auto_updating_m = False
        self.material_slack = 0.10
        self._auto_min_values: Dict[str, int] = {}
        self._build_form(self.form_container)
        self._setup_material_binding()
        self._setup_min_suggestions()
        
        # Frame para resultados
        self.output_container = tk.Frame(self.left_paned, bg=self.colors["bg"])
        self._build_output(self.output_container)
        
        # Agregar ambos frames al PanedWindow
        self.left_paned.add(self.form_container, stretch="always", minsize=70)
        self.left_paned.add(self.output_container, stretch="always", minsize=150)
        
        # Configurar la posición inicial del separador (aproximadamente 350px para parámetros)
        self._sash_update_pending = False
        self._schedule_sash_update()
        self.left_paned.bind("<Configure>", lambda _e: self._schedule_sash_update())
        
        self._build_simulation(self.right)
        self._last_charts = {}
        self._anim_data = None
        self._anim_after_id = None
        self._anim_start = None
        self.anim_duration = 12.0
        self.anim_flow_seconds = 10.0
        self.anim_pause = 3.0
        self._anim_paused = False
        self._anim_pause_started = None
        self._anim_current = None
        self._tooltip_items = None
        self._tooltip_visible = False
        self._tooltip_pos = (0, 0)
        self._anim_clock = 0.0
        self._hover_pot = None
        self._pot_map: Dict[int, Dict[str, Any]] = {}
        self._queue_ids = [[], [], []]
        self._tooltip_after_id = None
        self._tooltip_window = None
        self._tooltip_label = None
        self._pause_text_id = None
        self._note_tip_window = None
        self._note_tip_label = None
        self._note_tip_after_id = None
        self._note_tip_active = False
        self._note_tip_pos = (0, 0)
        self._last_config: Optional[Config] = None
        self._last_sim = None

        # Barra de estado
        self.status = tk.Label(
            self,
            text="✓ Listo",
            bg=self.colors["status_bg"],
            fg="#FFFFFF",
            font=self.fonts["caption"],
            anchor="w",
            padx=10,
            pady=5,
            relief="flat",
        )
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

        self.bind("<Return>", lambda _e: self.run_model())

    def _apply_theme(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "TLabel",
            background=self.colors["bg"],
            foreground=self.colors["text"],
            font=self.fonts["body"],
            padding=(0, 2),
        )
        style.configure(
            "TFrame",
            background=self.colors["bg"],
        )
        style.configure(
            "Row.TFrame",
            background=self.colors["panel"],
        )
        style.configure(
            "Card.TFrame",
            background=self.colors["panel"],
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "TEntry",
            fieldbackground=self.colors["label_bg"],
            background=self.colors["label_bg"],
            bordercolor=self.colors["border"],
            foreground=self.colors["text"],
            padding=3,
        )
        style.configure(
            "Accent.TButton",
            background=self.colors["button_alt"],
            foreground="#FFFFFF",
            padding=(10, 6),
            font=self.fonts["subtitle"],
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", self.colors["hover_green"])],
        )
        style.configure(
            "Ghost.TButton",
            background=self.colors["button_alt"],
            foreground="#FFFFFF",
            padding=(8, 5),
            font=self.fonts["subtitle"],
        )
        style.map(
            "Ghost.TButton",
            background=[("active", self.colors["hover_green"])],
        )

    def _schedule_sash_update(self) -> None:
        if self._sash_update_pending:
            return
        self._sash_update_pending = True
        self.after_idle(self._position_left_sash)

    def _position_left_sash(self) -> None:
        self._sash_update_pending = False
        self.update_idletasks()
        if not hasattr(self, "form_header") or not hasattr(self, "form_body"):
            return
        header_h = self.form_header.winfo_reqheight()
        body_h = self.form_body.winfo_reqheight()
        padding = 24
        required = header_h + body_h + padding
        if required <= 1:
            self.after(50, self._schedule_sash_update)
            return
        total = self.left_paned.winfo_height()
        output_min = 150
        if total <= 0:
            self.after(50, self._schedule_sash_update)
            return
        available = max(0, total - output_min)
        sash_y = min(required, available)
        self.left_paned.sash_place(0, 0, sash_y)

    def _build_form(self, parent: tk.Frame) -> None:
        """Construir el formulario de parámetros."""
        
        # ====================================================================
        # HEADER CON TÍTULO Y BOTONES EN LÍNEA (ARRIBA)
        # ====================================================================
        header_frame = tk.Frame(parent, bg=self.colors["bg"])
        header_frame.pack(fill=tk.X, pady=(0, 10))
        self.form_header = header_frame
        
        # Título de sección a la izquierda
        lbl = tk.Label(
            header_frame,
            text="⚙️ Parámetros del Modelo",
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=self.fonts["subtitle"],
        )
        lbl.pack(side=tk.LEFT)
        
        # Frame para botones en línea a la derecha
        button_frame = tk.Frame(header_frame, bg=self.colors["bg"])
        button_frame.pack(side=tk.RIGHT)
        
        # Botón "Cargar JSON"
        btn_load = tk.Button(
            button_frame,
            text="📁 Cargar JSON",
            command=self.load_json,
            bg=self.colors["button_alt"],
            fg="#FFFFFF",
            font=self.fonts["subtitle"],
            relief="solid",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=6,
        )
        btn_load.pack(side=tk.LEFT, padx=2)
        self._bind_button_hover(btn_load, self.colors["button_alt"], self.colors["hover_green"])
        
        # Botón "Calcular"
        btn_calc = tk.Button(
            button_frame,
            text="🚀 Calcular",
            command=self.run_model,
            bg=self.colors["accent_2"],
            fg="#FFFFFF",
            font=self.fonts["subtitle"],
            relief="solid",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=6,
        )
        btn_calc.pack(side=tk.LEFT, padx=2)
        self._bind_button_hover(btn_calc, self.colors["accent_2"], self.colors["hover_green"])
        
        # ====================================================================
        # FORMULARIO DE PARÁMETROS
        # ====================================================================
        frame = tk.Frame(
            parent,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            padx=12,
            pady=12,
        )
        frame.pack(fill=tk.X)
        self.form_body = frame

        self.vars: Dict[str, tk.StringVar] = {}
        self.min_sug_labels: Dict[str, tk.Label] = {}

        self.params_notebook = ttk.Notebook(frame)
        self.params_notebook.pack(fill=tk.BOTH, expand=True)

        params_tab = tk.Frame(self.params_notebook, bg=self.colors["panel"])
        times_tab = tk.Frame(self.params_notebook, bg=self.colors["panel"])
        self.params_notebook.add(params_tab, text="Parámetros")
        self.params_notebook.add(times_tab, text="Constantes de ciclo")
        self.times_tab = times_tab

        def add_row(parent_tab: tk.Frame, label: str, key: str, default: str = "") -> None:
            row = ttk.Frame(parent_tab, style="Row.TFrame")
            row.pack(fill=tk.X, pady=3)
            self._boxed_label(row, text=label, width=26).pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            self.vars[key] = var
            self._boxed_entry(row, textvariable=var, width=18).pack(side=tk.LEFT, padx=(4, 0))

        def add_min_max_row(
            parent_tab: tk.Frame, label: str, key_min: str, key_max: str
        ) -> None:
            row = ttk.Frame(parent_tab, style="Row.TFrame")
            row.pack(fill=tk.X, pady=3)
            self._boxed_label(row, text=label, width=26).pack(side=tk.LEFT)

            self._boxed_label(row, text="min", width=4).pack(side=tk.LEFT, padx=(0, 4))
            var_min = tk.StringVar(value="")
            self.vars[key_min] = var_min
            self._boxed_entry(row, textvariable=var_min, width=6).pack(side=tk.LEFT, padx=(2, 0))
            sug = tk.Label(
                row,
                text="sug: -",
                bg=self.colors["panel"],
                fg=self.colors["muted"],
                font=self.fonts["caption"],
                padx=6,
            )
            sug.pack(side=tk.LEFT, padx=(6, 8))
            self.min_sug_labels[key_min] = sug

            self._boxed_label(row, text="max", width=4).pack(side=tk.LEFT, padx=(12, 4))
            var_max = tk.StringVar(value="")
            self.vars[key_max] = var_max
            self._boxed_entry(row, textvariable=var_max, width=6).pack(side=tk.LEFT, padx=(2, 0))

        # Mode (fixed)
        mode_row = ttk.Frame(params_tab, style="Row.TFrame")
        mode_row.pack(fill=tk.X, pady=2)
        self._boxed_label(mode_row, text="Modo", width=26).pack(side=tk.LEFT)
        self._boxed_label(
            mode_row, text="minimize_time", width=18, fg=self.colors["muted"]
        ).pack(side=tk.LEFT)

        add_row(params_tab, "Producción objetivo", "Q_obj", "100")
        add_row(params_tab, "Tiempo disponible (min)", "T_max", "120")
        add_row(params_tab, "Personal disponible", "P", "10")
        add_row(params_tab, "Material disponible (g)", "M", "4000")
        # a (material por maceta) se mueve a la pestaña de constantes
        add_min_max_row(params_tab, "Balanzas", "L_p_min", "L_p_max")
        add_min_max_row(params_tab, "Bowls", "L_m_min", "L_m_max")
        add_min_max_row(params_tab, "Moldes", "L_o_min", "L_o_max")

        # Nota de sugerencias y botón para aplicarlas
        sugg_row = tk.Frame(params_tab, bg=self.colors["panel"])
        sugg_row.pack(fill=tk.X, pady=(6, 0))
        self.sugg_note = tk.Label(
            sugg_row,
            text="Sugerencia mínima para cumplir tiempo máximo (no óptimo).",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=self.fonts["caption"],
        )
        self.sugg_note.pack(side=tk.LEFT, padx=(2, 6))
        self.apply_sugg_btn = tk.Button(
            sugg_row,
            text="Aplicar sugerencias",
            command=self._apply_suggestions,
            bg=self.colors["button_alt"],
            fg="#FFFFFF",
            font=self.fonts["caption"],
            relief="solid",
            bd=1,
            padx=8,
            pady=3,
        )
        self.apply_sugg_btn.pack(side=tk.LEFT)
        self._bind_button_hover(self.apply_sugg_btn, self.colors["button_alt"], self.colors["hover_green"])
        self.apply_sugg_btn.bind("<Enter>", self._show_note_tooltip)
        self.apply_sugg_btn.bind("<Leave>", self._hide_note_tooltip)
        self.clear_limits_btn = tk.Button(
            sugg_row,
            text="Limpiar restricciones",
            command=self._clear_equipment_limits,
            bg=self.colors["button_alt"],
            fg="#FFFFFF",
            font=self.fonts["caption"],
            relief="solid",
            bd=1,
            padx=8,
            pady=3,
        )
        self.clear_limits_btn.pack(side=tk.LEFT, padx=(6, 0))
        self._bind_button_hover(self.clear_limits_btn, self.colors["button_alt"], self.colors["hover_green"])


        add_row(times_tab, "Material por maceta (g)", "a", "155")
        add_row(times_tab, "Tiempo pesado (min)", "t_p", "")
        add_row(times_tab, "Tiempo mezcla (min)", "t_m", "")
        add_row(times_tab, "Tiempo molde (min)", "t_c", "")
        add_row(times_tab, "Tiempo max mezcla->molde (min)", "t_gel_max", "3.2")

        self.params_notebook.bind("<<NotebookTabChanged>>", self._on_params_tab_changed)

    def _setup_material_binding(self) -> None:
        if not hasattr(self, "vars"):
            return
        for key in ("Q_obj", "a"):
            if key in self.vars:
                self.vars[key].trace_add("write", lambda *_: self._update_material())
        # Ajuste inicial
        self._update_material()

    def _setup_min_suggestions(self) -> None:
        if not hasattr(self, "vars"):
            return
        for key in ("Q_obj", "T_max", "P", "t_p", "t_m", "t_c"):
            if key in self.vars:
                self.vars[key].trace_add("write", lambda *_: self._update_min_suggestions())
        self._update_min_suggestions()

    def _update_material(self) -> None:
        if self._auto_updating_m:
            return
        if "M" not in self.vars or "Q_obj" not in self.vars or "a" not in self.vars:
            return
        raw_q = self.vars["Q_obj"].get().strip()
        raw_a = self.vars["a"].get().strip()
        if raw_q == "" or raw_a == "":
            return
        try:
            q_val = float(raw_q)
            a_val = float(raw_a)
        except ValueError:
            return
        if q_val < 0 or a_val <= 0:
            return
        m_val = q_val * a_val * (1 + self.material_slack)
        self._auto_updating_m = True
        self.vars["M"].set(f"{m_val:.2f}")
        self._auto_updating_m = False

    def _update_min_suggestions(self) -> None:
        if not {"Q_obj", "T_max", "P", "L_p_min", "L_m_min", "L_o_min"}.issubset(self.vars):
            return
        try:
            q_val = float(self.vars["Q_obj"].get().strip() or 0)
            t_max = float(self.vars["T_max"].get().strip() or 0)
            p_val = int(float(self.vars["P"].get().strip() or 0))
        except ValueError:
            return
        if q_val <= 0 or t_max <= 0 or p_val <= 0:
            return

        def get_time(key: str, default: float) -> float:
            raw = self.vars.get(key)
            if raw is None:
                return default
            txt = raw.get().strip()
            if txt == "":
                return default
            try:
                return float(txt)
            except ValueError:
                return default

        t_p = get_time("t_p", 1.25)
        t_m = get_time("t_m", 2.4)
        t_c = get_time("t_c", 8.5)

        def ceil_div(a: float, b: float) -> int:
            return int(-(-a // b)) if b > 0 else 0

        req_p = max(1, ceil_div(q_val * t_p, t_max))
        req_m = max(1, ceil_div(q_val * t_m, t_max))
        req_o = max(1, ceil_div(q_val * t_c, t_max))

        total_people = req_p + req_m + 2 * req_o
        feasible = True
        if p_val < 4:
            # No hay personal suficiente para una configuración mínima 1-1-1
            sug_p, sug_m, sug_o = 1, 1, 1
            feasible = False
            self._set_status("⚠️ Personal insuficiente para mínimos 1-1-1 (balanza/bowl/molde)")
        elif total_people > p_val:
            factor = p_val / total_people
            sug_p = max(1, int(req_p * factor))
            sug_m = max(1, int(req_m * factor))
            sug_o = max(1, int(req_o * factor))
            # Ajuste fino si aún excede personal
            def total(pp, mm, oo) -> int:
                return pp + mm + 2 * oo
            while total(sug_p, sug_m, sug_o) > p_val:
                if sug_o > 1:
                    sug_o -= 1
                elif sug_m > 1:
                    sug_m -= 1
                elif sug_p > 1:
                    sug_p -= 1
                else:
                    break
            feasible = False
            self._set_status("⚠️ Recomendación ajustada por personal disponible")
        else:
            sug_p, sug_m, sug_o = req_p, req_m, req_o
            self._set_status("✓ Mínimos sugeridos actualizados")

        suggestions = {
            "L_p_min": sug_p,
            "L_m_min": sug_m,
            "L_o_min": sug_o,
        }

        # Solo actualizar etiquetas de sugerencia fuera del input
        self._update_suggestion_labels(suggestions, feasible)

    def _update_suggestion_labels(self, suggestions: Dict[str, int], feasible: bool) -> None:
        for key, val in suggestions.items():
            lbl = self.min_sug_labels.get(key)
            if not lbl:
                continue
            lbl.config(text=f"sug: {val}")
            if feasible:
                lbl.config(fg=self.colors["muted"])
            else:
                lbl.config(fg="#E74C3C")

        # actualizar nota
        if hasattr(self, "sugg_note"):
            if feasible:
                self.sugg_note.config(fg=self.colors["muted"])
            else:
                self.sugg_note.config(fg="#E74C3C")

        # guardar sugerencias actuales para aplicar con botón
        self._last_suggestions = suggestions

    def _apply_suggestions(self) -> None:
        if not hasattr(self, "_last_suggestions"):
            return
        for key, val in self._last_suggestions.items():
            if key in self.vars:
                self.vars[key].set(str(val))

    def _clear_equipment_limits(self) -> None:
        for key in ("L_p_min", "L_p_max", "L_m_min", "L_m_max", "L_o_min", "L_o_max"):
            if key in self.vars:
                self.vars[key].set("")

    def _on_params_tab_changed(self, _event: Optional[tk.Event] = None) -> None:
        if not hasattr(self, "params_notebook"):
            return
        selected = self.params_notebook.select()
        if selected == str(self.times_tab):
            self._ensure_time_defaults()
        self._schedule_sash_update()

    def _ensure_time_defaults(self) -> None:
        if self.vars["t_p"].get().strip() == "":
            self.vars["t_p"].set("1.25")
        if self.vars["t_m"].get().strip() == "":
            self.vars["t_m"].set("2.4")
        if self.vars["t_c"].get().strip() == "":
            self.vars["t_c"].set("8.5")
        if self.vars["t_gel_max"].get().strip() == "":
            try:
                t_m_val = float(self.vars["t_m"].get())
            except ValueError:
                t_m_val = 2.4
            self.vars["t_gel_max"].set(f"{t_m_val / 2 + 2:.2f}")

    def _build_output(self, parent: tk.Frame) -> None:
        """Construir el área de resultados."""
        frame = tk.Frame(
            parent,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            padx=12,
            pady=12,
        )
        frame.pack(fill=tk.BOTH, expand=True)
        
        self._boxed_label(frame, text="📊 Resultados", width=12, font=self.fonts["subtitle"]).pack(
            anchor=tk.W
        )
        
        output_frame = tk.Frame(frame, bg=self.colors["panel"])
        output_frame.pack(fill=tk.BOTH, expand=True)
        
        self.output = tk.Text(
            output_frame,
            height=20,
            wrap="word",
            bg=self.colors["chart_bg"],
            fg=self.colors["text"],
            font=self.fonts["body"],  # Usa la fuente body que puedes ajustar
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=self.colors["red_border"],
            padx=10,
            pady=10,
        )
        self.output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scroll = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.output.configure(yscrollcommand=scroll.set)
        self.output.configure(state="disabled")

    def _build_simulation(self, parent: tk.Frame) -> None:
        """Construir el área de simulación con gráficos."""
        frame = tk.Frame(
            parent,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            padx=12,
            pady=12,
        )
        frame.pack(fill=tk.BOTH, expand=True)

        # Scrollable area for charts
        canvas = tk.Canvas(
            frame,
            bg=self.colors["panel"],
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        charts = tk.Frame(canvas, bg=self.colors["panel"])
        window_id = canvas.create_window((0, 0), window=charts, anchor=tk.NW)

        def on_configure(_event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        charts.bind("<Configure>", on_configure)
        self._bind_mousewheel(canvas)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))

        # Título de simulación
        self._boxed_label(
            charts,
            text="🔬 Simulación (ocupación de recursos)",
            width=36,
            font=self.fonts["subtitle"],
        ).pack(anchor=tk.CENTER)
        
        self.sim_info = self._boxed_label(
            charts, text="Sin datos", width=22, fg=self.colors["muted"]
        )
        self.sim_info.pack(anchor=tk.CENTER, pady=(0, 8))

        # Gráfico de Utilización
        self._boxed_label(
            charts, text="📊 Utilización", width=14, font=self.fonts["subtitle"]
        ).pack(anchor=tk.CENTER)
        self.util_canvas = tk.Canvas(
            charts,
            height=240,
            bg=self.colors["chart_bg"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
        )
        self.util_canvas.pack(fill=tk.X, padx=16, pady=(2, 8))
        self.util_canvas.bind("<Configure>", lambda _e: self._redraw_charts())

        # Gráfico de Espera Promedio
        self._boxed_label(
            charts, text="⏳ Espera promedio (min)", width=20, font=self.fonts["subtitle"]
        ).pack(anchor=tk.CENTER)
        self.wait_canvas = tk.Canvas(
            charts,
            height=240,
            bg=self.colors["chart_bg"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
        )
        self.wait_canvas.pack(fill=tk.X, padx=16, pady=(2, 8))
        self.wait_canvas.bind("<Configure>", lambda _e: self._redraw_charts())

        # WIP stats
        self.sim_wip = self._boxed_label(
            charts, text="WIP promedio: - | WIP max: -", width=32, fg=self.colors["muted"]
        )
        self.sim_wip.pack(anchor=tk.CENTER, pady=(4, 0))

        # Gráfico de WIP por etapa
        self._boxed_label(
            charts, text="📦 WIP por etapa (promedio)", width=24, font=self.fonts["subtitle"]
        ).pack(anchor=tk.CENTER, pady=(6, 0))
        self.wip_stage_canvas = tk.Canvas(
            charts,
            height=180,
            bg=self.colors["chart_bg"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
        )
        self.wip_stage_canvas.pack(fill=tk.X, padx=16, pady=(2, 8))
        self.wip_stage_canvas.bind("<Configure>", lambda _e: self._redraw_charts())

        # Gráfico de WIP total en el tiempo
        self._boxed_label(
            charts, text="📈 WIP total (tiempo)", width=18, font=self.fonts["subtitle"]
        ).pack(anchor=tk.CENTER, pady=(6, 0))
        self.wip_time_canvas = tk.Canvas(
            charts,
            height=140,
            bg=self.colors["chart_bg"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
        )
        self.wip_time_canvas.pack(fill=tk.X, padx=16, pady=(2, 8))
        self.wip_time_canvas.bind("<Configure>", lambda _e: self._redraw_charts())

        # Animacion de flujo
        self._boxed_label(
            charts, text="Animacion (flujo)", width=18, font=self.fonts["subtitle"]
        ).pack(anchor=tk.CENTER, pady=(6, 0))
        anim_ctrl = tk.Frame(charts, bg=self.colors["panel"])
        anim_ctrl.pack(anchor=tk.CENTER, pady=(2, 6))
        tk.Label(
            anim_ctrl,
            text="Macetas animación",
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=self.fonts["caption"],
        ).pack(side=tk.LEFT, padx=(0, 6))
        self.anim_count_var = tk.StringVar(value="4")
        anim_combo = ttk.Combobox(
            anim_ctrl,
            textvariable=self.anim_count_var,
            values=[str(i) for i in range(1, 21)],
            width=4,
            state="readonly",
        )
        anim_combo.pack(side=tk.LEFT)
        anim_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_anim_count_change())
        self.anim_pause_btn = tk.Button(
            anim_ctrl,
            text="Pausar",
            command=self._toggle_anim_pause,
            bg=self.colors["button_alt"],
            fg="#FFFFFF",
            font=self.fonts["caption"],
            relief="solid",
            bd=1,
            padx=8,
            pady=3,
        )
        self.anim_pause_btn.pack(side=tk.LEFT, padx=(8, 0))
        self._bind_button_hover(self.anim_pause_btn, self.colors["button_alt"], self.colors["hover_green"])
        self.anim_canvas = tk.Canvas(
            charts,
            height=160,
            bg=self.colors["chart_bg"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
        )
        self.anim_canvas.pack(fill=tk.X, padx=16, pady=(2, 8))
        self.anim_canvas.bind("<Configure>", lambda _e: self._redraw_animation())
        self.anim_canvas.tag_bind("pot", "<Enter>", self._on_pot_enter)
        self.anim_canvas.tag_bind("pot", "<Leave>", self._on_pot_leave)
        self.anim_canvas.tag_bind("pot", "<Motion>", self._on_pot_motion)

        legend = tk.Frame(charts, bg=self.colors["panel"])
        legend.pack(anchor=tk.CENTER, pady=(2, 8))
        self._legend_swatch(legend, self.colors["chart_bar"], "Pesado").pack(side=tk.LEFT, padx=8)
        self._legend_swatch(legend, self.colors["chart_bar_2"], "Mezclado").pack(
            side=tk.LEFT, padx=8
        )
        self._legend_swatch(legend, self.colors["hover_green"], "Secado").pack(
            side=tk.LEFT, padx=8
        )
        self._legend_swatch(legend, "#C0C7CF", "En espera").pack(side=tk.LEFT, padx=8)

    def _boxed_label(
        self,
        parent: tk.Widget,
        text: str,
        width: int = 10,
        fg: str | None = None,
        font=None,
    ) -> tk.Canvas:
        fnt = tkfont.Font(font=font or self.fonts["body"])
        pad_x, pad_y, radius = 6, 4, 4
        min_w = fnt.measure("0" * width)
        text_w = fnt.measure(text)
        text_h = fnt.metrics("linespace")
        w = max(min_w, text_w) + pad_x * 2
        h = text_h + pad_y * 2
        canvas = tk.Canvas(
            parent,
            width=w,
            height=h,
            bg=self.colors["panel"],
            highlightthickness=0,
        )
        canvas._box_conf = {
            "pad_x": pad_x,
            "pad_y": pad_y,
            "radius": radius,
            "min_chars": width,
            "fill": self.colors["label_bg"],
            "outline": self.colors["red_border"],
            "fg": fg or self.colors["text"],
            "font": fnt,
        }
        self._redraw_boxed_label(canvas, text)
        return canvas

    def _boxed_entry(
        self,
        parent: tk.Widget,
        textvariable: tk.StringVar,
        width: int = 10,
    ) -> tk.Canvas:
        fnt = self._font_cache["body"]
        pad_x, pad_y, radius = 6, 4, 4
        text_w = fnt.measure("0" * width)
        text_h = fnt.metrics("linespace")
        w = text_w + pad_x * 2
        h = text_h + pad_y * 2
        canvas = tk.Canvas(
            parent,
            width=w,
            height=h,
            bg=self.colors["panel"],
            highlightthickness=0,
        )
        self._round_rect(
            canvas,
            1,
            1,
            w - 1,
            h - 1,
            radius,
            fill=self.colors["label_bg"],
            outline=self.colors["red_border"],
        )
        entry = tk.Entry(
            canvas,
            textvariable=textvariable,
            width=width,
            bg=self.colors["label_bg"],
            fg=self.colors["text"],
            font=self.fonts["body"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            insertbackground=self.colors["text"],
        )
        canvas.create_window(pad_x, pad_y, anchor=tk.NW, window=entry)
        return canvas

    def _legend_swatch(self, parent: tk.Widget, color: str, label: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=self.colors["panel"])
        swatch = tk.Canvas(
            frame,
            width=14,
            height=14,
            bg=self.colors["panel"],
            highlightthickness=0,
        )
        swatch.create_oval(2, 2, 12, 12, fill=color, outline=color)
        swatch.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(
            frame,
            text=label,
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            font=self.fonts["caption"],
        ).pack(side=tk.LEFT)
        return frame

    def _show_note_tooltip(self, event: tk.Event) -> None:
        self._note_tip_active = True
        self._note_tip_pos = (event.x_root, event.y_root)
        if self._note_tip_after_id is not None:
            try:
                self.after_cancel(self._note_tip_after_id)
            except Exception:
                pass
            self._note_tip_after_id = None
        self._note_tip_after_id = self.after(1000, self._show_note_tooltip_delayed)

    def _show_note_tooltip_delayed(self) -> None:
        self._note_tip_after_id = None
        if not self._note_tip_active:
            return
        text = "Sugerencia mínima para cumplir tiempo máximo (no óptimo)."
        if self._note_tip_window is None or self._note_tip_label is None:
            win = tk.Toplevel(self)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=self.colors["label_bg"])
            label = tk.Label(
                win,
                text=text,
                bg=self.colors["label_bg"],
                fg=self.colors["text"],
                font=self.fonts["caption"],
                justify=tk.LEFT,
                relief="solid",
                bd=1,
                padx=6,
                pady=4,
            )
            label.pack()
            self._note_tip_window = win
            self._note_tip_label = label
        else:
            self._note_tip_label.config(text=text)
        try:
            x_root, y_root = self._note_tip_pos
            x = x_root + 12
            y = y_root - 28
            self._note_tip_window.geometry(f"+{x}+{y}")
            self._note_tip_window.deiconify()
        except Exception:
            pass

    def _hide_note_tooltip(self, _event: tk.Event) -> None:
        self._note_tip_active = False
        if self._note_tip_after_id is not None:
            try:
                self.after_cancel(self._note_tip_after_id)
            except Exception:
                pass
            self._note_tip_after_id = None
        try:
            if self._note_tip_window is not None:
                self._note_tip_window.withdraw()
        except Exception:
            pass

    def _set_boxed_text(self, widget: tk.Widget, text: str) -> None:
        if isinstance(widget, tk.Canvas) and hasattr(widget, "_text_id"):
            self._redraw_boxed_label(widget, text)
        elif isinstance(widget, tk.Label):
            widget.config(text=text)

    def _redraw_boxed_label(self, canvas: tk.Canvas, text: str) -> None:
        conf = getattr(canvas, "_box_conf", None)
        if conf is None:
            return
        fnt = conf["font"]
        pad_x = conf["pad_x"]
        pad_y = conf["pad_y"]
        radius = conf["radius"]
        min_w = fnt.measure("0" * conf["min_chars"])
        text_w = fnt.measure(text)
        text_h = fnt.metrics("linespace")
        w = max(min_w, text_w) + pad_x * 2
        h = text_h + pad_y * 2
        canvas.config(width=w, height=h)
        canvas.delete("all")
        self._round_rect(
            canvas,
            1,
            1,
            w - 1,
            h - 1,
            radius,
            fill=conf["fill"],
            outline=conf["outline"],
        )
        text_id = canvas.create_text(
            pad_x,
            h / 2,
            text=text,
            anchor=tk.W,
            fill=conf["fg"],
            font=fnt,
        )
        canvas._text_id = text_id

    def _round_rect(
        self,
        canvas: tk.Canvas,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        r: int,
        fill: str,
        outline: str,
    ) -> None:
        r = max(1, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
        points = [
            x1 + r,
            y1,
            x2 - r,
            y1,
            x2,
            y1,
            x2,
            y1 + r,
            x2,
            y2 - r,
            x2,
            y2,
            x2 - r,
            y2,
            x1 + r,
            y2,
            x1,
            y2,
            x1,
            y2 - r,
            x1,
            y1 + r,
            x1,
            y1,
        ]
        canvas.create_polygon(
            points, smooth=True, splinesteps=24, fill=fill, outline=outline
        )

    def load_json(self) -> None:
        """Cargar parámetros desde archivo JSON."""
        path = filedialog.askopenfilename(
            title="Selecciona un archivo JSON",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo leer el JSON:\n{exc}")
            return

        self._set_if_present("Q_obj", data.get("Q_obj"))
        if data.get("T_max") is None and data.get("T") is not None:
            self._set_if_present("T_max", data.get("T"))
        else:
            self._set_if_present("T_max", data.get("T_max"))
        self._set_if_present("P", data.get("P"))
        self._set_if_present("M", data.get("M"))
        self._set_if_present("a", data.get("a"))
        self._set_if_present("t_p", data.get("t_p"))
        self._set_if_present("t_m", data.get("t_m"))
        self._set_if_present("t_c", data.get("t_c"))
        self._set_if_present("t_gel_max", data.get("t_gel_max", data.get("t_gel")))
        self._set_if_present("L_p_min", data.get("L_p_min"))
        self._set_if_present("L_p_max", data.get("L_p_max", data.get("L_p")))
        self._set_if_present("L_m_min", data.get("L_m_min"))
        self._set_if_present("L_m_max", data.get("L_m_max", data.get("L_m")))
        self._set_if_present("L_o_min", data.get("L_o_min"))
        self._set_if_present("L_o_max", data.get("L_o_max", data.get("L_o")))
        
        # Si se cargan tiempos, mostrar la pestaña correspondiente
        if any(data.get(k) is not None for k in ("t_p", "t_m", "t_c", "t_gel_max", "t_gel")):
            self.params_notebook.select(self.times_tab)
            self._ensure_time_defaults()
        self._schedule_sash_update()
        
        self._set_status("✓ JSON cargado correctamente")

    def _set_if_present(self, key: str, value: Any) -> None:
        if value is None:
            self.vars[key].set("")
        else:
            self.vars[key].set(str(value))

    def run_model(self) -> None:
        """Ejecutar el modelo de optimización."""
        try:
            self._set_status("⏳ Calculando...")
            data = self._collect_config()
            config = Config.from_dict(data)
            config.validate()
            result = optimize(config)
            bottleneck = detect_bottleneck(config, result)
            checks = constraint_checks(config, result)
            t_max = config.T_max if config.T_max is not None else config.T

            # ================================================================
            # FORMATEAR RESULTADOS EN ESPAÑOL
            # ================================================================
            self.output.configure(state="normal")
            self.output.delete("1.0", tk.END)
            
            # Modo y estado
            mode_es = TRADUCCIONES.get(result.mode, result.mode)
            
            # Determinar el estado y su formato
            if result.status == "ok":
                status_text = "Solución exitosa ✔️"
                status_tag = "status_viable"
            else:
                status_text = "Inviable ❌"
                status_tag = "status_inviable"
            
            self.output.insert(tk.END, f"Modo: {mode_es}\n", "bold")
            self.output.insert(tk.END, "Estado: ", "bold")
            self.output.insert(tk.END, f"{status_text}\n\n", status_tag)
            
            # Equipos
            self.output.insert(tk.END, "Equipos:\n", "bold")
            self.output.insert(tk.END, f"  • Balanzas = {result.x_p}\n")
            self.output.insert(tk.END, f"  • Bowls = {result.x_m}\n")
            self.output.insert(tk.END, f"  • Moldes = {result.x_o}\n\n")
            
            # Producción
            self.output.insert(tk.END, "Producción Q: ", "bold")
            self.output.insert(tk.END, f"{result.Q}\n")
            if hasattr(result, 'Q_continuous') and result.Q_continuous is not None:
                self.output.insert(tk.END, f"  (Q continuo: {result.Q_continuous:.2f})\n")
            self.output.insert(tk.END, "\n")
            
            # Tiempo
            if result.T_req is not None:
                self.output.insert(tk.END, "Tiempo requerido: ", "bold")
                self.output.insert(tk.END, f"{result.T_req:.2f} min\n")
            self.output.insert(tk.END, "Tiempo máximo: ", "bold")
            self.output.insert(tk.END, f"{t_max:.2f} min\n\n")
            
            # Cuello de botella
            if bottleneck:
                bottleneck_es = TRADUCCIONES.get(bottleneck, bottleneck)
                self.output.insert(tk.END, "Cuello de botella: ", "bold")
                self.output.insert(tk.END, f"⚠️ Presente en {bottleneck_es}\n\n", "warning")
            
            # Restricciones
            self.output.insert(tk.END, "Restricciones:\n", "bold")
            check_labels = {
                "material": "Material",
                "time_pesado": "Tiempo pesado",
                "time_mezcla": "Tiempo mezcla",
                "time_moldes": "Tiempo moldes",
                "personal": "Personal",
                "acoplamiento": "Acoplamiento",
                "gelificacion": "Gelificacion (mezcla->molde)",
            }
            
            for key, label in check_labels.items():
                if key in checks:
                    icon = "✔️" if checks[key] else "❌"
                    tag = "success" if checks[key] else "danger"
                    self.output.insert(tk.END, f"  • {label}: {icon}\n", tag)
            
            self.output.insert(tk.END, "\n")
            
            # Notas
            if result.notes:
                self.output.insert(tk.END, "Notas:\n", "bold")
                self.output.insert(tk.END, f"{result.notes}\n")
            elif result.status == "infeasible":
                self.output.insert(tk.END, "Notas:\n", "bold")
                self.output.insert(tk.END, "No es posible cumplir el objetivo dentro del tiempo máximo, ")
                self.output.insert(tk.END, "se devuelve la mejor configuración de tiempo posible.\n")
            
            # Configurar tags para colores
            self.output.tag_configure("bold", font=(self.fonts["body"][0], self.fonts["body"][1], "bold"))
            self.output.tag_configure("status_viable", foreground="#27AE60")
            self.output.tag_configure("status_inviable", foreground="#E74C3C")
            self.output.tag_configure("success", foreground="#27AE60")
            self.output.tag_configure("danger", foreground="#E74C3C")
            self.output.tag_configure("warning", foreground="#F39C12")
            
            self.output.configure(state="disabled")

            # ================================================================
            # ACTUALIZAR SIMULACIÓN Y GRÁFICOS
            # ================================================================
            self._update_simulation(config, result)
            self._set_status("✓ Cálculo completado")
            
        except Exception as exc:
            self._set_status("❌ Error")
            messagebox.showerror("Error", str(exc))

    def _collect_config(self) -> Dict[str, Any]:
        """Recolectar configuración desde el formulario."""
        data: Dict[str, Any] = {
            "mode": "minimize_time",
        }

        def parse_optional_int(key: str) -> Optional[int]:
            raw = self.vars[key].get().strip()
            if raw == "" or raw.lower() == "null":
                return None
            return int(raw)

        def parse_optional_float(key: str) -> Optional[float]:
            raw = self.vars[key].get().strip()
            if raw == "" or raw.lower() == "null":
                return None
            return float(raw)

        # Required or defaulted
        data["T_max"] = float(self.vars["T_max"].get())
        data["P"] = int(self.vars["P"].get())
        data["M"] = float(self.vars["M"].get())
        data["a"] = float(self.vars["a"].get())

        # Optional
        data["Q_obj"] = parse_optional_int("Q_obj")
        data["L_p_min"] = parse_optional_int("L_p_min")
        data["L_p_max"] = parse_optional_int("L_p_max")
        data["L_m_min"] = parse_optional_int("L_m_min")
        data["L_m_max"] = parse_optional_int("L_m_max")
        data["L_o_min"] = parse_optional_int("L_o_min")
        data["L_o_max"] = parse_optional_int("L_o_max")
        t_p = parse_optional_float("t_p")
        t_m = parse_optional_float("t_m")
        t_c = parse_optional_float("t_c")
        t_gel_max = parse_optional_float("t_gel_max")
        if t_p is not None:
            data["t_p"] = t_p
        if t_m is not None:
            data["t_m"] = t_m
        if t_c is not None:
            data["t_c"] = t_c
        if t_gel_max is not None:
            data["t_gel_max"] = t_gel_max

        return data

    def _update_simulation(self, config: Config, result) -> None:
        """Actualizar simulación y gráficos."""
        if result.Q <= 0:
            self._set_boxed_text(self.sim_info, "Sin datos (Q=0)")
            self._set_boxed_text(self.sim_wip, "WIP promedio: - | WIP max: -")
            self._clear_canvas(self.util_canvas)
            self._clear_canvas(self.wait_canvas)
            self._clear_canvas(self.wip_stage_canvas)
            self._clear_canvas(self.wip_time_canvas)
            self._clear_canvas(self.anim_canvas)
            self._last_charts = {}
            self._anim_data = None
            self._stop_animation()
            return

        sim = simulate(config, result.x_p, result.x_m, result.x_o, result.Q)
        self._last_config = config
        self._last_sim = sim
        self._set_boxed_text(self.sim_info, f"Makespan: {sim.makespan:.2f} min")
        
        labels = ["Pesado", "Mezcla", "Moldes"]
        util_values = [
            sim.utilization.get("pesado", 0.0),
            sim.utilization.get("mezcla", 0.0),
            sim.utilization.get("moldes", 0.0),
        ]
        wait_values = [
            sim.queue_stats.get("pesado", {"avg": 0.0})["avg"],
            sim.queue_stats.get("mezcla", {"avg": 0.0})["avg"],
            sim.queue_stats.get("moldes", {"avg": 0.0})["avg"],
        ]
        max_wait = max(wait_values) if wait_values else 0.0
        
        self._last_charts = {
            "util": {
                "labels": labels,
                "values": util_values,
                "max": 1.0,
                "suffix": "",
                "color": self.colors["chart_bar"],
            },
            "wait": {
                "labels": labels,
                "values": wait_values,
                "max": max_wait or 1.0,
                "suffix": " min",
                "color": self.colors["chart_bar_2"],
            },
            "wip_stage": None,
            "wip_series": None,
        }
        
        self._redraw_charts()
        
        if sim.wip_stats:
            wip_avg = sim.wip_stats["system"]["avg"]
            wip_max = sim.wip_stats["system"]["max"]
            self._set_boxed_text(
                self.sim_wip,
                f"WIP promedio: {wip_avg:.2f} | WIP max: {wip_max}",
            )
            stage_labels = ["Pesado", "Mezcla", "Moldes"]
            stage_wip_avg = [
                sim.wip_stats["pesado"]["avg"],
                sim.wip_stats["mezcla"]["avg"],
                sim.wip_stats["moldes"]["avg"],
            ]
            max_stage = max(stage_wip_avg) if stage_wip_avg else 1.0
            self._last_charts["wip_stage"] = {
                "labels": stage_labels,
                "values": stage_wip_avg,
                "max": max_stage or 1.0,
                "suffix": "",
                "color": self.colors["chart_bar"],
            }
            self._draw_bar_chart(
                self.wip_stage_canvas,
                stage_labels,
                stage_wip_avg,
                max_stage or 1.0,
                suffix="",
                bar_color=self.colors["chart_bar"],
            )
        
        if sim.wip_series:
            self._last_charts["wip_series"] = sim.wip_series
            self._draw_line_chart(self.wip_time_canvas, sim.wip_series)

        self._update_animation(config, sim)

    def _set_status(self, text: str) -> None:
        if hasattr(self, "status"):
            self.status.config(text=text)

    def _clear_canvas(self, canvas: tk.Canvas) -> None:
        canvas.delete("all")

    def _redraw_charts(self) -> None:
        """Redibujar todos los gráficos."""
        if not self._last_charts:
            return
        util = self._last_charts.get("util")
        if util:
            self._draw_bar_chart(
                self.util_canvas,
                util["labels"],
                util["values"],
                util["max"],
                suffix=util["suffix"],
                bar_color=util["color"],
            )
        wait = self._last_charts.get("wait")
        if wait:
            self._draw_bar_chart(
                self.wait_canvas,
                wait["labels"],
                wait["values"],
                wait["max"],
                suffix=wait["suffix"],
                bar_color=wait["color"],
            )
        wip_stage = self._last_charts.get("wip_stage")
        if wip_stage:
            self._draw_bar_chart(
                self.wip_stage_canvas,
                wip_stage["labels"],
                wip_stage["values"],
                wip_stage["max"],
                suffix=wip_stage["suffix"],
                bar_color=wip_stage["color"],
            )
        wip_series = self._last_charts.get("wip_series")
        if wip_series:
            self._draw_line_chart(self.wip_time_canvas, wip_series)

    def _update_animation(self, config: Config, sim) -> None:
        max_items = min(self._anim_count(), len(sim.items))
        items = []
        for item in sim.items[:max_items]:
            if item.pesado is None or item.mezcla is None or item.moldes is None:
                continue
            items.append(
                {
                    "id": item.item_id,
                    "p_start": item.pesado.start,
                    "p_end": item.pesado.end,
                    "m_start": item.mezcla.start,
                    "m_end": item.mezcla.end,
                    "o_start": item.moldes.start,
                    "o_end": item.moldes.end,
                }
            )
        span = max((item["o_end"] for item in items), default=0.0)
        flow_times = []
        for it in sim.items:
            if it.pesado and it.moldes:
                flow_times.append(it.moldes.end - it.pesado.start)
        base_flow = sum(flow_times) / len(flow_times) if flow_times else span
        min_flow = min(flow_times) if flow_times else span
        if not items or span <= 0:
            self._anim_data = None
            self._stop_animation()
            self._clear_canvas(self.anim_canvas)
            self.anim_canvas.create_text(
                self.anim_canvas.winfo_width() / 2,
                self.anim_canvas.winfo_height() / 2,
                text="Sin datos",
                fill=self.colors["muted"],
                font=self.fonts["body"],
            )
            return
        rows = len(items)
        r = 8
        row_gap = 6
        lane_h = rows * (2 * r) + max(rows - 1, 0) * row_gap
        desired_h = max(160, int(lane_h + 60))
        try:
            current_h = int(self.anim_canvas.cget("height"))
        except Exception:
            current_h = desired_h
        if current_h != desired_h:
            self.anim_canvas.config(height=desired_h)

        self._anim_data = {
            "labels": ["Pesado", "Mezcla", "Moldes"],
            "items": items,
            "span": span,
            "base_flow": base_flow,
            "min_flow": min_flow,
            "total_items": len(sim.items),
        }
        self._redraw_animation()

    def _redraw_animation(self) -> None:
        if not hasattr(self, "anim_canvas"):
            return
        self._clear_canvas(self.anim_canvas)
        self._pot_map = {}
        self._queue_ids = [[], [], []]
        self._tooltip_visible = False
        self._hover_pot = None
        self._cancel_tooltip_update()
        self._hide_tooltip()
        self._pause_text_id = None
        if not self._anim_data:
            self._stop_animation()
            self.anim_canvas.create_text(
                self.anim_canvas.winfo_width() / 2,
                self.anim_canvas.winfo_height() / 2,
                text="Sin datos",
                fill=self.colors["muted"],
                font=self.fonts["body"],
            )
            return
        self._anim_layout = self._draw_animation_static(self._anim_data)
        self._start_animation()

    def _draw_animation_static(self, data: Dict[str, Any]) -> Dict[str, Any]:
        canvas = self.anim_canvas
        w = max(canvas.winfo_width(), 1)
        h = max(canvas.winfo_height(), 1)
        margin_x = 18
        gap = 12
        items = data.get("items", [])
        rows = max(len(items), 1)
        row_gap = 6
        available_h = max(h - 50, 40)
        r = int(max(5, min(10, (available_h - (rows - 1) * row_gap) / (2 * rows))))
        box_h = min(available_h, max(50, 2 * r * rows + row_gap * (rows - 1)))
        y0 = (h - box_h) / 2
        y1 = y0 + box_h
        box_w = max((w - 2 * margin_x - 2 * gap) / 3, 10)

        labels = data["labels"]
        stage_boxes = []
        for idx, label in enumerate(labels):
            x0 = margin_x + idx * (box_w + gap)
            x1 = x0 + box_w
            canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                outline=self.colors["border"],
                fill=self.colors["label_bg"],
                width=1,
            )
            canvas.create_text(
                (x0 + x1) / 2,
                y0 - 10,
                text=label,
                fill=self.colors["text"],
                font=self.fonts["caption"],
            )
            stage_boxes.append((x0, x1, y0, y1))

        lane_y = []
        for idx in range(rows):
            lane_y.append(y0 + r + idx * (2 * r + row_gap))

        lefts = []
        rights = []
        for x0, x1, _y0, _y1 in stage_boxes:
            lefts.append(x0 + r + 4)
            rights.append(x1 - r - 4)

        for idx, item in enumerate(items):
            cy = lane_y[idx]
            start_x = lefts[0]
            pot_id = canvas.create_oval(
                start_x - r,
                cy - r,
                start_x + r,
                cy + r,
                fill=self.colors["chart_bar"],
                outline=self.colors["chart_bar"],
                tags=("pot", f"pot_{item['id']}"),
            )
            item["lane"] = idx
            self._pot_map[pot_id] = item

        if items:
            self._init_queue_visuals(len(items), lefts, stage_boxes, r)

        # Pause indicator (hidden by default)
        pause_y = min(h - 12, y1 + 18)
        self._pause_text_id = canvas.create_text(
            w / 2,
            pause_y,
            text="Tiempo de gracia (reiniciando modelo)",
            fill=self.colors["muted"],
            font=self.fonts["caption"],
            state="hidden",
        )
        return {
            "stage_boxes": stage_boxes,
            "radius": r,
            "lane_y": lane_y,
            "lefts": lefts,
            "rights": rights,
        }

    def _init_queue_visuals(
        self, count: int, lefts: list[float], stage_boxes: list[tuple], r: int
    ) -> None:
        if count <= 0:
            return
        canvas = self.anim_canvas
        wait_color = "#C0C7CF"
        block_w = max(6, r + 2)
        block_h = max(4, r)
        for stage_idx in range(3):
            self._queue_ids[stage_idx] = []
            for _ in range(count):
                dot = canvas.create_rectangle(
                    0,
                    0,
                    block_w,
                    block_h,
                    fill=wait_color,
                    outline=wait_color,
                    state="hidden",
                )
                self._queue_ids[stage_idx].append(dot)

    def _update_queue_visuals(self, waiting_by_stage: list[list[int]]) -> None:
        if not hasattr(self, "_anim_layout"):
            return
        lefts = self._anim_layout["lefts"]
        lane_y = self._anim_layout["lane_y"]
        r = self._anim_layout["radius"]
        for stage_idx in range(3):
            dots = self._queue_ids[stage_idx] if stage_idx < len(self._queue_ids) else []
            block_w = max(6, r + 2)
            block_h = max(4, r)
            x = lefts[stage_idx] - (r * 2.5)
            for dot in dots:
                self.anim_canvas.itemconfigure(dot, state="hidden")
            for lane in waiting_by_stage[stage_idx]:
                if lane < 0 or lane >= len(dots) or lane >= len(lane_y):
                    continue
                y = lane_y[lane] - block_h / 2
                self.anim_canvas.coords(dot := dots[lane], x - block_w / 2, y, x + block_w / 2, y + block_h)
                self.anim_canvas.itemconfigure(dot, state="normal")

    def _set_pause_indicator(self, active: bool) -> None:
        if self._pause_text_id is None:
            return
        try:
            self.anim_canvas.itemconfigure(
                self._pause_text_id, state=("normal" if active else "hidden")
            )
        except Exception:
            return

    def _start_animation(self) -> None:
        self._stop_animation()
        self._anim_start = time.perf_counter()
        self._tick_animation()

    def _stop_animation(self) -> None:
        if self._anim_after_id is not None:
            self.after_cancel(self._anim_after_id)
            self._anim_after_id = None

    def _tick_animation(self) -> None:
        if not self._anim_data or not hasattr(self, "anim_canvas"):
            return
        if not hasattr(self, "_anim_layout"):
            return
        if self._anim_start is None:
            return
        if self._anim_paused:
            return

        target_seconds = self.anim_flow_seconds
        pause_seconds = max(self.anim_pause, 0.0)
        span = self._anim_data.get("span", 0.0)
        min_flow = self._anim_data.get("min_flow")
        if min_flow is None:
            min_flow = self._anim_data.get("base_flow", span)
        if target_seconds <= 0 or span <= 0:
            return

        elapsed = time.perf_counter() - self._anim_start
        seconds_per_min = target_seconds / max(min_flow, 1e-6)
        cycle = span * seconds_per_min + pause_seconds
        t_cycle = elapsed % cycle
        pause_active = t_cycle >= (span * seconds_per_min)
        if pause_active:
            t_real = span
        else:
            t_real = t_cycle / seconds_per_min
        self._anim_clock = t_real

        lefts = self._anim_layout["lefts"]
        rights = self._anim_layout["rights"]
        lane_y = self._anim_layout["lane_y"]
        r = self._anim_layout["radius"]

        colors = [self.colors["chart_bar"], self.colors["chart_bar_2"], self.colors["hover_green"]]
        wait_color = "#C0C7CF"

        waiting_by_stage: list[list[int]] = [[], [], []]
        for pot_id, item in list(self._pot_map.items()):
            try:
                idx = item.get("lane", 0)
                stage_idx, phase, progress, _elapsed = self._item_state(item, t_real)
            except Exception:
                continue
            left = lefts[stage_idx]
            right = rights[stage_idx]
            if right <= left:
                right = left + 1
            if phase.startswith("espera") or phase == "completado":
                x = left if phase.startswith("espera") else right
                color = wait_color if phase.startswith("espera") else colors[stage_idx % len(colors)]
            else:
                x = left + (right - left) * progress
                color = colors[stage_idx % len(colors)]

            cy = lane_y[min(idx, len(lane_y) - 1)]
            try:
                self.anim_canvas.coords(pot_id, x - r, cy - r, x + r, cy + r)
                self.anim_canvas.itemconfig(pot_id, fill=color, outline=color)
            except Exception:
                continue
            if phase.startswith("espera"):
                waiting_by_stage[stage_idx].append(idx)

        self._update_queue_visuals(waiting_by_stage)
        self._set_pause_indicator(pause_active)

        self._anim_after_id = self.after(33, self._tick_animation)

    def _item_state(
        self, item: Dict[str, Any], t_real: float
    ) -> tuple[int, str, float, float]:
        try:
            p_start = item.get("p_start", 0.0)
            p_end = item.get("p_end", 0.0)
            m_start = item.get("m_start", 0.0)
            m_end = item.get("m_end", 0.0)
            o_start = item.get("o_start", 0.0)
            o_end = item.get("o_end", 0.0)

            if t_real < p_start:
                return (0, "espera_pesado", 0.0, t_real)
            if t_real < p_end:
                progress = (t_real - p_start) / max(p_end - p_start, 1e-6)
                return (0, "pesado", progress, t_real)
            if t_real < m_start:
                return (1, "espera_mezcla", 0.0, t_real)
            if t_real < m_end:
                progress = (t_real - m_start) / max(m_end - m_start, 1e-6)
                return (1, "mezcla", progress, t_real)
            if t_real < o_start:
                return (2, "espera_moldes", 0.0, t_real)
            if t_real < o_end:
                progress = (t_real - o_start) / max(o_end - o_start, 1e-6)
                return (2, "moldes", progress, t_real)
            return (2, "completado", 1.0, o_end)
        except Exception:
            return (0, "espera_pesado", 0.0, t_real)

    def _anim_count(self) -> int:
        raw = getattr(self, "anim_count_var", None)
        if raw is None:
            return 4
        try:
            val = int(float(raw.get().strip() or 4))
        except ValueError:
            return 4
        return max(1, min(val, 20))

    def _on_anim_count_change(self) -> None:
        if self._last_sim is None or self._last_config is None:
            return
        self._update_animation(self._last_config, self._last_sim)

    def _toggle_anim_pause(self) -> None:
        if self._anim_paused:
            self._anim_paused = False
            if self._anim_pause_started is not None and self._anim_start is not None:
                self._anim_start += time.perf_counter() - self._anim_pause_started
            self._anim_pause_started = None
            if hasattr(self, "anim_pause_btn"):
                self.anim_pause_btn.config(text="Pausar")
            self._tick_animation()
        else:
            self._anim_paused = True
            self._anim_pause_started = time.perf_counter()
            if hasattr(self, "anim_pause_btn"):
                self.anim_pause_btn.config(text="Reanudar")
            self._stop_animation()

    def _tooltip_allowed(self, item: Dict[str, Any]) -> bool:
        try:
            stage_idx, phase, progress, _elapsed = self._item_state(item, self._anim_clock)
        except Exception:
            return False
        return True

    def _current_pot_id(self, event: tk.Event) -> Optional[int]:
        current = event.widget.find_withtag("current")
        if not current:
            return None
        item_id = current[0]
        try:
            tags = event.widget.gettags(item_id)
        except Exception:
            return None
        if "pot" not in tags:
            return None
        return item_id

    def _schedule_tooltip_update(self) -> None:
        if not self._tooltip_visible:
            return
        if self._tooltip_after_id is None:
            self._tooltip_after_id = self.after(120, self._tooltip_tick)

    def _cancel_tooltip_update(self) -> None:
        if self._tooltip_after_id is not None:
            try:
                self.after_cancel(self._tooltip_after_id)
            except Exception:
                pass
            self._tooltip_after_id = None

    def _tooltip_tick(self) -> None:
        self._tooltip_after_id = None
        if not self._tooltip_visible:
            return
        if self._hover_pot is None or self._hover_pot not in self._pot_map:
            self._tooltip_visible = False
            self._hover_pot = None
            self._hide_tooltip()
            return
        item = self._pot_map.get(self._hover_pot)
        if item and not self._tooltip_allowed(item):
            self._tooltip_visible = False
            self._hover_pot = None
            self._hide_tooltip()
            return
        self._refresh_tooltip()
        self._schedule_tooltip_update()

    def _ensure_tooltip_window(self) -> None:
        if self._tooltip_window is not None and self._tooltip_label is not None:
            return
        win = tk.Toplevel(self)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=self.colors["label_bg"])
        label = tk.Label(
            win,
            text="",
            bg=self.colors["label_bg"],
            fg=self.colors["text"],
            font=self.fonts["caption"],
            justify=tk.LEFT,
            relief="solid",
            bd=1,
            padx=6,
            pady=4,
        )
        label.pack()
        self._tooltip_window = win
        self._tooltip_label = label

    def _tooltip_text(self) -> str:
        try:
            if not self._anim_data or self._hover_pot is None:
                return "Tiempo: -"
            item = self._pot_map.get(self._hover_pot)
            if not item:
                return "Tiempo: -"
            try:
                stage_idx, phase, _progress, elapsed = self._item_state(item, self._anim_clock)
            except Exception:
                return "Tiempo: -"
            if not self._tooltip_allowed(item):
                return "Tiempo: -"
            labels = self._anim_data["labels"]
            if phase == "completado":
                return f"Maceta {item['id']}\nFinalizado\nFin: {elapsed:.2f} min"
            if phase.startswith("espera"):
                phase_label = "espera"
            else:
                phase_label = "proceso"
            return f"Maceta {item['id']}\n{labels[stage_idx]} ({phase_label})\nTiempo: {elapsed:.2f} min"
        except Exception:
            return "Tiempo: -"

    def _refresh_tooltip(self) -> None:
        if not self._tooltip_visible:
            return
        if self._hover_pot is None:
            return
        if self._hover_pot not in self._pot_map:
            self._tooltip_visible = False
            self._hover_pot = None
            self._hide_tooltip()
            return
        item = self._pot_map.get(self._hover_pot)
        if item and not self._tooltip_allowed(item):
            self._tooltip_visible = False
            self._hover_pot = None
            self._hide_tooltip()
            return
        try:
            self._ensure_tooltip_window()
            text = self._tooltip_text()
            x, y = self._tooltip_pos
            if self._tooltip_label is not None:
                self._tooltip_label.config(text=text)
            if self._tooltip_window is not None:
                self._tooltip_window.geometry(f"+{x+12}+{y-28}")
                self._tooltip_window.deiconify()
        except Exception:
            self._tooltip_visible = False
            self._hover_pot = None
            self._hide_tooltip()

    def _hide_tooltip(self) -> None:
        try:
            if self._tooltip_window is not None:
                self._tooltip_window.withdraw()
        except Exception:
            pass

    def _on_pot_enter(self, event: tk.Event) -> None:
        try:
            self._hover_pot = self._current_pot_id(event)
            if self._hover_pot is None or self._hover_pot not in self._pot_map:
                return
            item = self._pot_map.get(self._hover_pot)
            if item and not self._tooltip_allowed(item):
                self._tooltip_visible = False
                self._hover_pot = None
                self._hide_tooltip()
                return
            self._tooltip_visible = True
            self._tooltip_pos = (event.x_root, event.y_root)
            self._refresh_tooltip()
            self._schedule_tooltip_update()
        except Exception:
            self._tooltip_visible = False
            self._hover_pot = None

    def _on_pot_motion(self, event: tk.Event) -> None:
        try:
            pot_id = self._current_pot_id(event)
            if pot_id is not None:
                self._hover_pot = pot_id
            self._tooltip_pos = (event.x_root, event.y_root)
            if self._tooltip_visible and self._hover_pot is not None and self._hover_pot in self._pot_map:
                item = self._pot_map.get(self._hover_pot)
                if item and not self._tooltip_allowed(item):
                    self._tooltip_visible = False
                    self._hover_pot = None
                    self._hide_tooltip()
                    return
                self._refresh_tooltip()
                self._schedule_tooltip_update()
        except Exception:
            self._tooltip_visible = False
            self._hover_pot = None

    def _on_pot_leave(self, _event: tk.Event) -> None:
        try:
            self._tooltip_visible = False
            self._hover_pot = None
            self._hide_tooltip()
            self._cancel_tooltip_update()
        except Exception:
            self._tooltip_visible = False
            self._hover_pot = None

    def _draw_bar_chart(
        self,
        canvas: tk.Canvas,
        labels,
        values,
        max_value: float,
        suffix: str = "",
        bar_color: str = "",
    ) -> None:
        """Dibujar gráfico de barras con animación."""
        steps = 14
        duration_ms = 280
        step_ms = max(int(duration_ms / steps), 1)
        target = list(values)

        if hasattr(canvas, "_anim_id"):
            canvas.after_cancel(canvas._anim_id)

        def render(step: int) -> None:
            factor = (step + 1) / steps
            eased = 1 - (1 - factor) * (1 - factor)
            current = [v * eased for v in target]
            color = bar_color or self.colors["chart_bar"]
            self._render_bars(canvas, labels, current, max_value, suffix, color)
            if step < steps - 1:
                canvas._anim_id = canvas.after(step_ms, render, step + 1)

        render(0)

    def _render_bars(
        self,
        canvas: tk.Canvas,
        labels,
        values,
        max_value: float,
        suffix: str,
        bar_color: str,
    ) -> None:
        """Renderizar barras en el canvas."""
        self._clear_canvas(canvas)
        w = int(canvas.winfo_width() or canvas["width"])
        h = int(canvas.winfo_height() or canvas["height"])
        padding = 28
        
        # Líneas de cuadrícula
        for i in range(1, 4):
            y = padding + i * (h - 2 * padding) / 4
            canvas.create_line(
                padding,
                y,
                w - padding,
                y,
                fill=self.colors["border"],
                width=1,
                stipple="gray50",
            )
        
        bar_width = (w - 2 * padding) // max(len(values), 1)
        for i, (label, val) in enumerate(zip(labels, values)):
            x0 = padding + i * bar_width + 10
            x1 = padding + (i + 1) * bar_width - 10
            ratio = 0.0 if max_value <= 0 else min(val / max_value, 1.0)
            y1 = h - padding
            y0 = y1 - int((h - 2 * padding) * ratio)
            canvas.create_rectangle(
                x0, y0, x1, y1, fill=bar_color, outline=""
            )
            canvas.create_text(
                (x0 + x1) / 2,
                y1 + 8,
                text=label,
                anchor=tk.N,
                font=self.fonts["body"],
                fill=self.colors["muted"],
            )
            canvas.create_text(
                (x0 + x1) / 2,
                y0 - 8,
                text=f"{val:.2f}{suffix}",
                anchor=tk.S,
                font=self.fonts["body"],
                fill=self.colors["text"],
            )

    def _bind_mousewheel(self, canvas: tk.Canvas) -> None:
        """Vincular evento de rueda del mouse SOLO al canvas específico."""
        def on_mousewheel(event) -> None:
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        # Usar bind en lugar de bind_all para que solo afecte este canvas
        canvas.bind("<MouseWheel>", on_mousewheel)
        canvas.bind("<Button-4>", on_mousewheel)
        canvas.bind("<Button-5>", on_mousewheel)
        
        # También vincular al frame de charts para mejor UX
        def bind_to_widget(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Button-4>", on_mousewheel)
            widget.bind("<Button-5>", on_mousewheel)
            for child in widget.winfo_children():
                bind_to_widget(child)
        
        # Esto permite scroll cuando el mouse está sobre los gráficos
        canvas.bind("<Enter>", lambda e: bind_to_widget(canvas))
        canvas.bind("<Leave>", lambda e: None)

    def _draw_line_chart(self, canvas: tk.Canvas, series: list[tuple[float, int]]) -> None:
        """Dibujar gráfico de líneas."""
        self._clear_canvas(canvas)
        if not series:
            return
        w = int(canvas.winfo_width() or canvas["width"])
        h = int(canvas.winfo_height() or canvas["height"])
        padding = 24
        times = [t for t, _ in series]
        values = [v for _, v in series]
        t_min, t_max = min(times), max(times)
        v_min, v_max = 0, max(values) if values else 1
        if t_max - t_min <= 0:
            t_max = t_min + 1
        if v_max <= 0:
            v_max = 1

        canvas._wip_series = series
        canvas._wip_scale = (t_min, t_max, v_min, v_max, padding, w, h)
        if not hasattr(canvas, "_tooltip_bound"):
            self._bind_line_tooltip(canvas)
            canvas._tooltip_bound = True

        # Cuadrícula
        for i in range(1, 3):
            y = padding + i * (h - 2 * padding) / 3
            canvas.create_line(
                padding,
                y,
                w - padding,
                y,
                fill=self.colors["border"],
                width=1,
                stipple="gray50",
            )

        def to_x(t: float) -> float:
            return padding + (t - t_min) / (t_max - t_min) * (w - 2 * padding)

        def to_y(v: float) -> float:
            return h - padding - (v - v_min) / (v_max - v_min) * (h - 2 * padding)

        points = []
        for t, v in series:
            points.extend([to_x(t), to_y(v)])
        if len(points) >= 4:
            canvas.create_line(*points, fill=self.colors["chart_bar_2"], width=2, smooth=False)
        
        # Etiquetas
        canvas.create_text(
            padding, padding - 6, text=f"{v_max}", anchor=tk.SW,
            font=self.fonts["body"], fill=self.colors["text"]
        )
        canvas.create_text(
            w - padding, h - padding + 6, text=f"{t_max:.0f} min", anchor=tk.NE,
            font=self.fonts["body"], fill=self.colors["muted"]
        )

    def _bind_line_tooltip(self, canvas: tk.Canvas) -> None:
        """Vincular tooltip al gráfico de líneas."""
        def on_move(event) -> None:
            if not hasattr(canvas, "_wip_series") or not hasattr(canvas, "_wip_scale"):
                return
            series = canvas._wip_series
            t_min, t_max, _v_min, _v_max, padding, w, h = canvas._wip_scale
            x = min(max(event.x, padding), w - padding)
            t = t_min + (x - padding) / (w - 2 * padding) * (t_max - t_min)
            idx = min(range(len(series)), key=lambda i: abs(series[i][0] - t))
            t_val, wip_val = series[idx]
            self._show_canvas_tooltip(
                canvas,
                event.x,
                event.y,
                f"{wip_val} macetas\n{t_val:.0f} min",
            )

        def on_leave(_event) -> None:
            canvas.delete("tooltip")

        canvas.bind("<Motion>", on_move)
        canvas.bind("<Leave>", on_leave)

    def _show_canvas_tooltip(self, canvas: tk.Canvas, x: int, y: int, text: str) -> None:
        """Mostrar tooltip en el canvas."""
        canvas.delete("tooltip")
        fnt = self._font_cache["body"]
        lines = text.split("\n")
        text_w = max(fnt.measure(line) for line in lines) if lines else 0
        text_h = fnt.metrics("linespace") * max(len(lines), 1)
        pad = 4
        w = int(canvas.winfo_width() or canvas["width"])
        h = int(canvas.winfo_height() or canvas["height"])
        x0 = min(max(x + 10, 5), w - text_w - pad * 2 - 5)
        y0 = min(max(y - text_h - 10, 5), h - text_h - pad * 2 - 5)
        canvas.create_rectangle(
            x0,
            y0,
            x0 + text_w + pad * 2,
            y0 + text_h + pad * 2,
            fill=self.colors["label_bg"],
            outline=self.colors["border"],
            tags="tooltip",
        )
        canvas.create_text(
            x0 + pad,
            y0 + pad,
            text=text,
            anchor=tk.NW,
            font=self.fonts["body"],
            fill=self.colors["text"],
            tags="tooltip",
        )

    def _bind_button_hover(self, button: tk.Button, base: str, hover: str) -> None:
        """Vincular efecto hover al botón."""
        def on_enter(_event) -> None:
            self._animate_button(button, base, hover)

        def on_leave(_event) -> None:
            self._animate_button(button, hover, base)

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)

    def _animate_button(
        self,
        button: tk.Button,
        start_hex: str,
        end_hex: str,
        steps: int = 10,
        delay_ms: int = 20,
    ) -> None:
        """Animar transición de color del botón."""
        if hasattr(button, "_anim_id"):
            button.after_cancel(button._anim_id)

        start = self._hex_to_rgb(start_hex)
        end = self._hex_to_rgb(end_hex)

        def step(i: int) -> None:
            t = i / max(steps, 1)
            eased = 1 - (1 - t) * (1 - t)
            r = int(start[0] + (end[0] - start[0]) * eased)
            g = int(start[1] + (end[1] - start[1]) * eased)
            b = int(start[2] + (end[2] - start[2]) * eased)
            color = self._rgb_to_hex((r, g, b))
            button.configure(bg=color, activebackground=color)
            if i < steps:
                button._anim_id = button.after(delay_ms, step, i + 1)

        step(0)

    @staticmethod
    def _hex_to_rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))

    @staticmethod
    def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
        return "#{:02X}{:02X}{:02X}".format(rgb[0], rgb[1], rgb[2])


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
