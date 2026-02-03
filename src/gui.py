"""Simple Tkinter GUI to edit parameters and run the model."""

from __future__ import annotations

import json
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, Optional

from .bottleneck import detect_bottleneck
from .model import Config
from .optimizer import constraint_checks, optimize
from .simulate import simulate


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Macetas Biodegradables - Optimizador")
        self.geometry("980x720")
        self.minsize(980, 720)
        self.resizable(True, True)

        self.colors = {
            "bg": "#B1B7D1",
            "panel": "#9B9FB5",
            "accent": "#8C7284",
            "accent_2": "#9B9FB5",
            "text": "#000000",
            "muted": "#000000",
            "chart_bg": "#B1B7D1",
            "chart_bar": "#8C7284",
            "chart_bar_2": "#9B9FB5",
            "border": "#000000",
            "red_border": "#000000",
            "label_bg": "#C7CDDD",
            "button_alt": "#C8A4B4",
            "hover_green": "#BFE3C0",
            "status_bg": "#9B9FB5",
        }
        self.fonts = {
            "title": ("Trebuchet MS", 20, "bold"),
            "subtitle": ("Trebuchet MS", 13, "bold"),
            "body": ("Verdana", 12),
            "mono": ("Consolas", 11),
            "caption": ("Verdana", 10),
        }
        self.configure(bg=self.colors["bg"])
        self._apply_theme()
        self._font_cache = {
            "body": tkfont.Font(font=self.fonts["body"]),
            "subtitle": tkfont.Font(font=self.fonts["subtitle"]),
            "mono": tkfont.Font(font=self.fonts["mono"]),
        }

        header = tk.Frame(self, bg=self.colors["accent"], height=54)
        header.pack(fill=tk.X)
        title = tk.Label(
            header,
            text="Macetas Biodegradables - Optimizador",
            bg=self.colors["accent"],
            fg=self.colors["text"],
            font=self.fonts["title"],
            padx=16,
            pady=12,
        )
        title.pack(anchor=tk.W)
        subtitle = tk.Label(
            header,
            text="Dimensionamiento de equipos y simulacion de flujo",
            bg=self.colors["accent"],
            fg=self.colors["text"],
            font=self.fonts["caption"],
            padx=16,
        )
        subtitle.place(relx=1.0, rely=0.5, anchor="e", x=-12)

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

        self._build_form(self.left)
        ttk.Separator(self.left, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(8, 8))
        self._build_output(self.left)
        self._build_simulation(self.right)
        self._last_charts = {}

        self.status = tk.Label(
            self,
            text="Listo",
            bg=self.colors["status_bg"],
            fg=self.colors["text"],
            font=self.fonts["caption"],
            anchor="w",
            padx=8,
            pady=4,
            relief="sunken",
            bd=1,
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
            fieldbackground=self.colors["panel"],
            background=self.colors["panel"],
            bordercolor=self.colors["border"],
            foreground=self.colors["text"],
            padding=3,
        )
        style.configure(
            "Accent.TButton",
            background=self.colors["button_alt"],
            foreground=self.colors["text"],
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
            foreground=self.colors["text"],
            padding=(8, 5),
            font=self.fonts["subtitle"],
        )
        style.map(
            "Ghost.TButton",
            background=[("active", self.colors["hover_green"])],
        )

    def _build_form(self, parent: tk.Frame) -> None:
        frame = tk.Frame(
            parent,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            padx=12,
            pady=12,
        )
        frame.pack(fill=tk.X)

        self.vars: Dict[str, tk.StringVar] = {}

        def add_row(label: str, key: str, default: str = "") -> None:
            row = ttk.Frame(frame, style="Row.TFrame")
            row.pack(fill=tk.X, pady=3)
            self._boxed_label(row, text=label, width=26).pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            self.vars[key] = var
            self._boxed_entry(row, textvariable=var, width=18).pack(side=tk.LEFT, padx=(4, 0))

        def add_min_max_row(label: str, key_min: str, key_max: str) -> None:
            row = ttk.Frame(frame, style="Row.TFrame")
            row.pack(fill=tk.X, pady=3)
            self._boxed_label(row, text=label, width=26).pack(side=tk.LEFT)

            self._boxed_label(row, text="min", width=4).pack(side=tk.LEFT, padx=(0, 4))
            var_min = tk.StringVar(value="")
            self.vars[key_min] = var_min
            self._boxed_entry(row, textvariable=var_min, width=6).pack(side=tk.LEFT, padx=(2, 0))

            self._boxed_label(row, text="max", width=4).pack(side=tk.LEFT, padx=(12, 4))
            var_max = tk.StringVar(value="")
            self.vars[key_max] = var_max
            self._boxed_entry(row, textvariable=var_max, width=6).pack(side=tk.LEFT, padx=(2, 0))

        # Mode (fixed)
        mode_row = ttk.Frame(frame, style="Row.TFrame")
        mode_row.pack(fill=tk.X, pady=2)
        self._boxed_label(mode_row, text="Modo", width=26).pack(side=tk.LEFT)
        self._boxed_label(
            mode_row, text="minimize_time", width=18, fg=self.colors["muted"]
        ).pack(side=tk.LEFT)

        add_row("Cantidad de macetas objetivo", "Q_obj", "")
        add_row("Tiempo Maximo del ciclo (min)", "T_max", "120")
        add_row("Personal disponible", "P", "10")
        add_row("Materia Prima (g)", "M", "4000")
        add_row("Gramos de cascara por maceta", "a", "155")
        add_min_max_row("Balanzas", "L_p_min", "L_p_max")
        add_min_max_row("Bowls", "L_m_min", "L_m_max")
        add_min_max_row("Moldes", "L_o_min", "L_o_max")

        self.times_frame = ttk.Frame(frame, style="Row.TFrame")
        self.times_visible = False
        btn_times = tk.Button(
            frame,
            text="Tiempos de produccion",
            command=self.toggle_times,
            bg=self.colors["button_alt"],
            fg=self.colors["text"],
            font=self.fonts["subtitle"],
            relief="solid",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=6,
        )
        btn_times.pack(pady=6, anchor=tk.W)
        self._bind_button_hover(btn_times, self.colors["button_alt"], self.colors["hover_green"])
        self._build_times(self.times_frame)

        buttons = tk.Frame(frame, bg=self.colors["panel"])
        buttons.pack(fill=tk.X, pady=8)
        btn_load = tk.Button(
            buttons,
            text="Cargar JSON",
            command=self.load_json,
            bg=self.colors["button_alt"],
            fg=self.colors["text"],
            font=self.fonts["subtitle"],
            relief="solid",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=6,
        )
        btn_load.pack(side=tk.LEFT, padx=4)
        btn_calc = tk.Button(
            buttons,
            text="Calcular",
            command=self.run_model,
            bg=self.colors["button_alt"],
            fg=self.colors["text"],
            font=self.fonts["subtitle"],
            relief="solid",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=6,
        )
        btn_calc.pack(side=tk.LEFT, padx=4)
        self._bind_button_hover(btn_load, self.colors["button_alt"], self.colors["hover_green"])
        self._bind_button_hover(btn_calc, self.colors["button_alt"], self.colors["hover_green"])

    def _build_output(self, parent: tk.Frame) -> None:
        frame = tk.Frame(
            parent,
            bg=self.colors["panel"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            padx=12,
            pady=12,
        )
        frame.pack(fill=tk.BOTH, expand=True)
        self._boxed_label(frame, text="Resultado", width=12, font=self.fonts["subtitle"]).pack(
            anchor=tk.W
        )
        output_frame = tk.Frame(frame, bg=self.colors["panel"])
        output_frame.pack(fill=tk.BOTH, expand=True)
        self.output = tk.Text(
            output_frame,
            height=20,
            wrap="word",
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=self.fonts["mono"],
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=self.colors["red_border"],
        )
        self.output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.output.configure(yscrollcommand=scroll.set)
        self.output.configure(state="disabled")

    def _build_simulation(self, parent: tk.Frame) -> None:
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

        self._boxed_label(
            charts,
            text="Simulacion (ocupacion de recursos)",
            width=36,
            font=self.fonts["subtitle"],
        ).pack(anchor=tk.CENTER)
        self.sim_info = self._boxed_label(
            charts, text="Sin datos", width=22, fg=self.colors["muted"]
        )
        self.sim_info.pack(anchor=tk.CENTER, pady=(0, 8))

        self._boxed_label(
            charts, text="Utilizacion", width=14, font=self.fonts["subtitle"]
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

        self._boxed_label(
            charts, text="Espera promedio (min)", width=20, font=self.fonts["subtitle"]
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

        self.sim_wip = self._boxed_label(
            charts, text="WIP promedio: - | WIP max: -", width=32, fg=self.colors["muted"]
        )
        self.sim_wip.pack(anchor=tk.CENTER, pady=(4, 0))

        self._boxed_label(
            charts, text="WIP por etapa (promedio)", width=24, font=self.fonts["subtitle"]
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

        self._boxed_label(
            charts, text="WIP total (tiempo)", width=18, font=self.fonts["subtitle"]
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
            fill=self.colors["bg"],
            outline=self.colors["red_border"],
        )
        entry = tk.Entry(
            canvas,
            textvariable=textvariable,
            width=width,
            bg=self.colors["bg"],
            fg=self.colors["text"],
            font=self.fonts["body"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            insertbackground=self.colors["text"],
        )
        canvas.create_window(pad_x, pad_y, anchor=tk.NW, window=entry)
        return canvas

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

    def _build_times(self, frame: ttk.Frame) -> None:
        def add_time_row(label: str, key: str, default: str) -> None:
            row = ttk.Frame(frame, style="Row.TFrame")
            row.pack(fill=tk.X, pady=2)
            self._boxed_label(row, text=label, width=28).pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            self.vars[key] = var
            self._boxed_entry(row, textvariable=var, width=10).pack(side=tk.LEFT)

        add_time_row("t_p (pesado, min)", "t_p", "")
        add_time_row("t_m (mezcla, min)", "t_m", "")
        add_time_row("t_c (moldes, min)", "t_c", "")

    def toggle_times(self) -> None:
        if self.times_visible:
            self.times_frame.pack_forget()
            self.times_visible = False
            return

        if self.vars["t_p"].get().strip() == "":
            self.vars["t_p"].set("1.25")
        if self.vars["t_m"].get().strip() == "":
            self.vars["t_m"].set("2.4")
        if self.vars["t_c"].get().strip() == "":
            self.vars["t_c"].set("8.5")
        self.times_frame.pack(fill=tk.X, pady=2)
        self.times_visible = True

    def load_json(self) -> None:
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
        self._set_if_present("L_p_min", data.get("L_p_min"))
        self._set_if_present("L_p_max", data.get("L_p_max", data.get("L_p")))
        self._set_if_present("L_m_min", data.get("L_m_min"))
        self._set_if_present("L_m_max", data.get("L_m_max", data.get("L_m")))
        self._set_if_present("L_o_min", data.get("L_o_min"))
        self._set_if_present("L_o_max", data.get("L_o_max", data.get("L_o")))
        if any(k in data for k in ("t_p", "t_m", "t_c")):
            if not self.times_visible:
                self.toggle_times()

    def _set_if_present(self, key: str, value: Any) -> None:
        if value is None:
            self.vars[key].set("")
        else:
            self.vars[key].set(str(value))

    def run_model(self) -> None:
        try:
            self._set_status("Calculando...")
            data = self._collect_config()
            config = Config.from_dict(data)
            config.validate()
            result = optimize(config)
            bottleneck = detect_bottleneck(config, result)
            checks = constraint_checks(config, result)
            t_max = config.T_max if config.T_max is not None else config.T

            lines = []
            lines.append("=== RESULTADO ===")
            lines.append(f"Modo: {result.mode} (status: {result.status})")
            lines.append(
                f"Equipos: balanzas={result.x_p}, bowls={result.x_m}, moldes={result.x_o}"
            )
            lines.append(
                f"Produccion Q: {result.Q} (Q continuo: {result.Q_continuous:.2f})"
            )
            if result.T_req is not None:
                lines.append(f"Tiempo requerido: {result.T_req:.2f} min")
            lines.append(f"T_max: {t_max:.2f} min")
            lines.append(f"Cuello de botella: {bottleneck}")
            lines.append(f"Restricciones: {checks}")
            if result.notes:
                lines.append(f"Notas: {result.notes}")

            self.output.configure(state="normal")
            self.output.delete("1.0", tk.END)
            self.output.insert(tk.END, "\n".join(lines))
            self.output.configure(state="disabled")

            self._update_simulation(config, result)
            self._set_status("Listo")
        except Exception as exc:
            self._set_status("Error")
            messagebox.showerror("Error", str(exc))

    def _collect_config(self) -> Dict[str, Any]:
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
        if t_p is not None:
            data["t_p"] = t_p
        if t_m is not None:
            data["t_m"] = t_m
        if t_c is not None:
            data["t_c"] = t_c

        return data

    def _update_simulation(self, config: Config, result) -> None:
        if result.Q <= 0:
            self._set_boxed_text(self.sim_info, "Sin datos (Q=0)")
            self._set_boxed_text(self.sim_wip, "WIP promedio: - | WIP max: -")
            self._clear_canvas(self.util_canvas)
            self._clear_canvas(self.wait_canvas)
            self._clear_canvas(self.wip_stage_canvas)
            self._clear_canvas(self.wip_time_canvas)
            self._last_charts = {}
            return

        sim = simulate(config, result.x_p, result.x_m, result.x_o, result.Q)
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

    def _set_status(self, text: str) -> None:
        if hasattr(self, "status"):
            self.status.config(text=text)

    def _clear_canvas(self, canvas: tk.Canvas) -> None:
        canvas.delete("all")

    def _redraw_charts(self) -> None:
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

    def _draw_bar_chart(
        self,
        canvas: tk.Canvas,
        labels,
        values,
        max_value: float,
        suffix: str = "",
        bar_color: str = "",
    ) -> None:
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
        self._clear_canvas(canvas)
        w = int(canvas.winfo_width() or canvas["width"])
        h = int(canvas.winfo_height() or canvas["height"])
        padding = 28
        # subtle grid lines for readability
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
        def on_mousewheel(event) -> None:
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", on_mousewheel)
        canvas.bind_all("<Button-5>", on_mousewheel)

    def _draw_line_chart(self, canvas: tk.Canvas, series: list[tuple[float, int]]) -> None:
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

        # grid
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
        # labels
        canvas.create_text(padding, padding - 6, text=f"{v_max}", anchor=tk.SW, font=self.fonts["body"], fill=self.colors["text"])
        canvas.create_text(w - padding, h - padding + 6, text=f"{t_max:.0f} min", anchor=tk.NE, font=self.fonts["body"], fill=self.colors["muted"])

    def _bind_line_tooltip(self, canvas: tk.Canvas) -> None:
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
