"""Tk/ttk + Matplotlib desktop observer. No server and no alternate solver.

draw_field is also used with Agg by the validator; an Agg export is NOT a GUI
screenshot. Tk widgets are created only by App/main, not at module import.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import time

from matplotlib.figure import Figure
from matplotlib.colors import Normalize
from matplotlib import colormaps
import numpy as np

from control import Controller, DEFAULTS
from display import reconstruct


def draw_field(figure, field, upper, message="待更新 / No current field", display=None):
    figure.clear()
    axes = figure.subplots(1, 2)
    if field is None:
        for ax, vertical in zip(axes, ["y", "z"]):
            ax.set(xlabel="x (m)", ylabel=f"{vertical} (m)", xlim=(0, 5), ylim=(0, 4 if vertical == "y" else 3))
            ax.text(.5, .5, "NO CURRENT FIELD\nPress Update calculation", ha="center", va="center", transform=ax.transAxes)
        figure.suptitle("Echo v0.1.0 | No valid current pressure field")
        return {"axes": axes, "images": [], "norm": None, "markers": [], "colorbar": None}
    p = field.parameters
    display = reconstruct(field) if display is None else display
    norm = Normalize(vmin=0.0, vmax=upper, clip=False)
    cmap = colormaps["viridis"].copy()
    sat = display.saturation(upper)
    raw_sat = field.saturation(upper)
    images, markers = [], []
    for ax, label, vertical, data, cut, normal_axis in [
        (axes[0], "XY", display.y, display.xy, p.xy_z, 2),
        (axes[1], "XZ", display.z, display.xz, p.xz_y, 1),
    ]:
        image = ax.imshow(np.abs(data).T, extent=display.extent(label.lower()), origin="lower",
                          interpolation="nearest", interpolation_stage="data", resample=False,
                          norm=norm, cmap=cmap, aspect="equal")
        images.append(image)
        ax.set(xlabel="x (m)", ylabel=f"{label[1].lower()} (m)", xlim=(0, 5), ylim=(0, display.extent(label.lower())[3]),
               title=f"{label}: |P| (Pa), {['x','y','z'][normal_axis]}={cut!r} m")
        ax.set_aspect("equal")
        notes = []
        for name, point, shape, color, active in [
            ("Source 1", p.source, "x", "red", True),
            ("Source 2", p.source2, "s", "cyan", p.gain2 > 0),
            ("Observer", p.observer, "o", "white", True),
        ]:
            distance = abs(point[normal_axis] - cut)
            on_plane = distance <= 1e-9
            drawn = active and on_plane
            if not active:
                notes.append(f"{name}: inactive (g=0), not drawn")
            elif on_plane:
                ordinate = point[1] if label == "XY" else point[2]
                ax.plot(point[0], ordinate, marker=shape, color=color, markeredgecolor="black" if shape == "o" else color,
                        markerfacecolor="none" if name == "Source 2" else color,
                        markersize=10 if name == "Source 2" else 7, linestyle="none", label=name)
                notes.append(f"{name}: on-plane marker")
            else:
                notes.append(f"{name}: off-plane by {distance:.6g} m (not drawn)")
            markers.append({"panel": label, "name": name, "active": active, "on_plane": on_plane,
                            "drawn": drawn, "normal_distance_m": distance})
        ax.set_xlabel("x (m)\n" + "\n".join(notes), fontsize=8)
    # One Figure legend from actually drawn markers; keep the fixed semantic order.
    handles_by_label = {}
    for ax in axes:
        handles, labels = ax.get_legend_handles_labels()
        for handle, label in zip(handles, labels):
            handles_by_label.setdefault(label, handle)
    labels = [label for label in ("Source 1", "Source 2", "Observer") if label in handles_by_label]
    if labels:
        legend = figure.legend([handles_by_label[label] for label in labels], labels,
                               loc="upper left", ncols=3, fontsize=7)
        # Use the existing top-left whitespace without changing constrained Axes layout.
        legend.set_in_layout(False)
    colorbar = figure.colorbar(images[0], ax=list(axes), label="Pressure amplitude |P| (Pa)",
                              extend="max" if sat["xy_count"] or sat["xz_count"] or raw_sat["xy_count"] or raw_sat["xz_count"] else "neither", shrink=.83)
    saturated = f" | SATURATED: XY={sat['xy_count']}, XZ={sat['xz_count']} samples; raw data unchanged" if sat["xy_count"] or sat["xz_count"] else ""
    figure.suptitle(
        f"Echo v0.1.0 | {p.frequency_hz!r} Hz | coherent complex pressure sum\n"
        f"S1={p.source} m; S2={p.source2} m; g={p.gain2!r}; phi={p.phase2_deg!r} deg"
        f"{' (S2 inactive)' if p.gain2 == 0 else ''}\n"
        f"Q1=1e-5; Q2=g Q1 exp(+i phi) m^3/s; sigma=0.25 m; cutoff=1200 Hz ({field.diagnostics['mode_count']} modes)\n"
        f"Shared MANUAL linear color range 0–{upper:g} Pa | complex cosine cell centers, h={display.cell_width_m:g} m{saturated}", fontsize=9)
    return {"axes": axes, "images": images, "norm": norm, "markers": markers, "colorbar": colorbar,
            "display": display, "raw_saturation": raw_sat, "display_saturation": sat}


def observation_text(field):
    """Shared, testable text used verbatim by the real Tk observer readout."""
    if field is None:
        return "当前无有效结果 / No current result. Re P: — Pa | Im P: — Pa | |P|: — Pa | phase: — deg"
    f = field
    value = f.observer_pressure
    phase = f.diagnostics["observer_phase"]
    if phase["status"] == "ZERO_UNDEFINED":
        phase_text = "— (零声压 / undefined at zero)"
    elif phase["status"] == "NEAR_ZERO_UNRESOLVED":
        phase_text = f"— (数值近零 / unresolved; |P| <= {phase['roundoff_threshold_pa']:.3g} Pa)"
    else:
        phase_text = f"{phase['degrees']:.9g} deg"
    return (
        f"当前总声压 / Current total: {f.parameters.frequency_hz!r} Hz; observer={f.parameters.observer} m\n"
        f"Re P={value.real:.12g} Pa | Im P={value.imag:.12g} Pa | |P|={abs(value):.12g} Pa | phase: {phase_text}\n"
        f"Numerical compute {f.elapsed_seconds:.4f} s; slices XY {len(f.x)}×{len(f.y)}, XZ {len(f.x)}×{len(f.z)}. Amplitude is peak phasor magnitude, not RMS.")


class App:
    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        self.root = root
        self.controller = Controller()
        self.display = None
        self.display_source = None
        self.last_refresh_timing = {}
        self.last_update_timing = {}
        self.root.title("回声 Echo v0.1.0 · 同频双声源")
        self.root.geometry("1400x960")
        self.root.minsize(1280, 900)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)
        self.entries = []
        self.busy = False
        panel = ttk.Frame(root, padding=8)
        panel.grid(row=0, column=0, sticky="ew")
        self.variables = {key: tk.StringVar(value=value) for key, value in DEFAULTS.items()}
        groups = [("第一声源 Source 1 (m)", ["source_x", "source_y", "source_z"]),
                  ("第二声源 Source 2", ["source2_x", "source2_y", "source2_z", "gain2", "phase2_deg"]),
                  ("观察点 Observer (m)", ["observer_x", "observer_y", "observer_z"]),
                  ("频率及切片", ["frequency_hz", "xy_z", "xz_y"])]
        for column, (title, keys) in enumerate(groups):
            frame = ttk.LabelFrame(panel, text=title, padding=6)
            frame.grid(row=0, column=column, padx=3, sticky="nsew")
            for row, key in enumerate(keys):
                label = {"frequency_hz": "f [25–120] Hz", "xy_z": "XY z [0–3] m", "xz_y": "XZ y [0–4] m",
                         "gain2": "g [0–1]; 0=未激活", "phase2_deg": "φ [−180–180] deg"}.get(
                             key, key[-1] + " [0–" + {"x":"5", "y":"4", "z":"3"}.get(key[-1], "") + "] m")
                ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w")
                entry = ttk.Entry(frame, textvariable=self.variables[key], width=12)
                entry.grid(row=row, column=1, padx=3, pady=2)
                self.entries.append(entry)
        actions = ttk.LabelFrame(panel, text="绝对声压色标 / Absolute Pa", padding=6)
        actions.grid(row=0, column=4, sticky="nsew", padx=3)
        ttk.Label(actions, text="最小值 0 Pa；上限 >0 Pa").grid(row=0, column=0)
        entry = ttk.Entry(actions, textvariable=self.variables["vmax_pa"], width=14)
        entry.grid(row=1, column=0)
        self.entries.append(entry)
        self.color_button = ttk.Button(actions, text="应用色标 / Apply color", command=self.on_color)
        self.color_button.grid(row=2, column=0, pady=3)
        self.update_button = ttk.Button(panel, text="更新计算 / Update calculation", command=self.on_update)
        self.update_button.grid(row=0, column=5, padx=8, sticky="ns")
        panel.columnconfigure(5, weight=1)
        self.status_var = tk.StringVar()
        ttk.Label(root, textvariable=self.status_var, wraplength=1200, justify="left", foreground="#7a3100", padding=8).grid(row=1, column=0, sticky="ew")
        self.figure = Figure(figsize=(12, 5.5), dpi=100, layout="constrained")
        self.canvas = FigureCanvasTkAgg(self.figure, master=root)
        self.canvas.get_tk_widget().grid(row=2, column=0, sticky="nsew")
        self.readout_var = tk.StringVar()
        ttk.Label(root, textvariable=self.readout_var, wraplength=1200, justify="left", padding=8).grid(row=3, column=0, sticky="ew")
        ttk.Label(root, text="3-D | room 5×4×3 m | c=343 m/s | rho=1.2 kg/m³ | sigma=0.25 m | Q1=1e-5; Q2=g Q1 exp(+iφ) m³/s | exp(+iωt) | rigid, lossless | no normalization", padding=5, wraplength=1200).grid(row=4, column=0, sticky="ew")
        for key, variable in self.variables.items():
            variable.trace_add("write", lambda *_args, key=key: self.on_edit(key))
        self.refresh()

    def on_edit(self, key):
        self.controller.edit(key, self.variables[key].get())
        # COLOR_PENDING retains the last visibly labeled color scale; no solve.
        self.refresh(redraw=key != "vmax_pa" or self.controller.result is None)

    def refresh(self, redraw=True):
        started = time.perf_counter()
        c = self.controller
        fit_seconds = query_seconds = 0.0
        if c.result is None:
            self.display = self.display_source = None
        elif self.display_source is not c.result:
            try:
                self.display = reconstruct(c.result)
                self.display_source = c.result
                fit_seconds, query_seconds = self.display.fit_seconds, self.display.query_seconds
            except Exception as exc:
                c.clear_error("DISPLAY_ERROR", f"显示重建失败 / {type(exc).__name__}: {exc}. No current field.")
                self.display = self.display_source = None
        note = ""
        if self.display is not None:
            sat = self.display.saturation(c.applied_upper_pa)
            note = (f"\n显示 / Display: complex cosine, 0.25 m training → {self.display.cell_width_m:g} m cell centers; observer remains direct. "
                    f"Display saturation XY={sat['xy_count']}, XZ={sat['xz_count']}; raw Pa unchanged.")
        self.status_var.set(f"[{c.status}] {c.message}{note}")
        self.readout_var.set(observation_text(c.result))
        graph_seconds = draw_seconds = 0.0
        if redraw:
            t = time.perf_counter()
            self.plot_objects = draw_field(self.figure, c.result, c.applied_upper_pa, display=self.display)
            graph_seconds = time.perf_counter() - t
            t = time.perf_counter()
            self.canvas.draw()
            draw_seconds = time.perf_counter() - t
        self.last_refresh_timing = {"cosine_fit_seconds": fit_seconds, "cosine_query_seconds": query_seconds,
                                   "graph_construction_seconds": graph_seconds, "tkagg_canvas_draw_seconds": draw_seconds,
                                   "refresh_seconds": time.perf_counter() - started}

    def on_update(self):
        if self.busy:
            return
        started = time.perf_counter()
        self.busy = True
        for entry in self.entries:
            entry.state(["disabled"])
        self.update_button.state(["disabled"])
        self.color_button.state(["disabled"])
        self.status_var.set("[CALCULATING] 正在计算 / Calculating the unchanged 3-D model…")
        self.root.update_idletasks()
        try:
            t = time.perf_counter()
            self.controller.update()
            physics_wall = time.perf_counter() - t
            self.refresh()
        finally:
            for entry in self.entries:
                entry.state(["!disabled"])
            self.update_button.state(["!disabled"])
            self.color_button.state(["!disabled"])
            self.busy = False
            self.root.update_idletasks()
            self.last_update_timing = {**self.last_refresh_timing, "physical_controller_wall_seconds": physics_wall,
                "raw_engine_compute_seconds": self.controller.result.elapsed_seconds if self.controller.result is not None else None,
                "button_to_draw_and_idle_complete_seconds": time.perf_counter() - started}

    def on_color(self):
        self.controller.apply_color()
        self.refresh()


def smoke(root, app, screenshot=None):
    """Only executed with a REAL Tk window, never a Tk mock or Agg substitute."""
    root.update()
    app.update_button.invoke()
    root.update()
    assert app.controller.result is not None
    app.variables["source_x"].set("1.35")
    assert app.controller.status == "NEEDS_UPDATE" and app.controller.result is None
    app.update_button.invoke()
    root.update()
    result = app.controller.result
    calls = app.controller.engine.call_count
    app.variables["vmax_pa"].set("0.00001")
    app.color_button.invoke()
    assert app.controller.result is result and app.controller.engine.call_count == calls
    app.variables["frequency_hz"].set("34.3")
    app.update_button.invoke()
    assert app.controller.status == "RESONANCE" and app.controller.result is None
    app.variables["frequency_hz"].set("34.30001")
    app.update_button.invoke()
    assert app.controller.status == "NEAR_RESONANCE"
    app.variables["source_x"].set("NaN")
    app.update_button.invoke()
    assert app.controller.status == "INPUT_ERROR" and app.controller.result is None
    for key, value in DEFAULTS.items():
        app.variables[key].set(value)
    app.update_button.invoke()
    root.update()
    screenshot_result = None
    if screenshot:
        from PIL import ImageGrab
        x,y = root.winfo_rootx(),root.winfo_rooty()
        ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save(screenshot)
        screenshot_result = str(screenshot)
    return {"status":"GUI_STARTED_SMOKE_PASSED", "screenshot":screenshot_result, "real_widget_workflow_verified":True}


def destroy_window(root):
    """Normal WM close already destroys Tk; do not destroy it a second time."""
    if root is None:
        return
    from tkinter import TclError
    try:
        exists = root.winfo_exists()
    except TclError as exc:
        if "application has been destroyed" in str(exc):
            return
        raise
    if exists:
        root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    if args.screenshot and not args.smoke:
        parser.error("--screenshot requires --smoke")
    if args.screenshot and args.screenshot.exists():
        parser.error("Screenshot already exists; choose a new path; nothing overwritten")
    root = None
    try:
        import tkinter as tk
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        root = tk.Tk()
        app = App(root)
        if args.smoke:
            result = smoke(root, app, args.screenshot)
            print(json.dumps(result, ensure_ascii=False))
        else:
            root.mainloop()
        return 0
    except Exception as exc:
        # Missing display is reported explicitly, not disguised as GUI success.
        is_display = type(exc).__name__ == "TclError" and ("display" in str(exc).lower() or "screen" in str(exc).lower())
        result = {"status":"GUI_UNVERIFIED_DISPLAY_UNAVAILABLE" if is_display else "GUI_STARTUP_OR_SMOKE_FAILED",
                  "error_type":type(exc).__name__, "reason":str(exc), "real_widget_workflow_verified":False, "screenshot":None}
        print(json.dumps(result, ensure_ascii=False))
        if not args.smoke:
            print("A desktop display with Tcl/Tk is required. No current field was produced.", file=sys.stderr)
        return 2 if is_display else 1
    finally:
        destroy_window(root)


if __name__ == "__main__":
    sys.exit(main())
