"""
rns510_firmware_viewer.py -- read-only tkinter GUI that explores the real
embedded Java application layer directly inside `FHDD6.FLI` (the firmware
image documented on the wiki's "Firmware Reversing" / "Embedded Java
Application Layer" pages): the real class-path architecture (~2,800
classes), the handful of classes that survive as standalone, individually
decompilable `.class` files, and the unit's own real embedded UI screens
(e.g. per-brand "Software update" splash screens).

Nothing here is hardcoded or pre-extracted -- every run scans whatever
firmware file you open, live, via `research/firmware_java_reader.py` (and
decompiles on demand via `research/firmware_java_decompile.py`, which
auto-installs a portable JDK + the CFR decompiler on first use if you don't
already have a JVM). This is the firmware-exploration counterpart to
`rns510_map_viewer.py` (which renders the MAP DISC's road/city/POI data) --
a separate concern, not an extension of it.

Status: a first-pass visual mockup toward the longer-term goal of a full
simulator of the real RNS-510 UI. The "Simulator" tab assembles what's
actually recoverable today -- a real recovered boot screen, a real
recovered button icon, and the real top-level `vdo/rns/app/*` package
names (nav, icdent, mda, ...) as menu entries -- into a boot -> menu ->
select flow. This is NOT real, verified menu logic: there is no recovered
navigation/dispatch bytecode behind it (the bulk of the real application
is pre-linked/"romized" into Jeode's own still-not-fully-cracked bundle
format -- see the wiki page), so clicking a menu entry only shows which
real package it came from, not what the unit actually does. Every asset
and label shown is computed live from whatever firmware file you open --
nothing is hardcoded -- so the exact screen/icon/menu entries shown can
vary firmware to firmware.

File > Open Firmware accepts either a raw `.FLI` file (read whole, as
before) or a firmware ISO directly -- for an ISO, the main apps image
(`FHDD*.FLI`) is located and read straight out of the ISO's own byte
range via `rns510_iso.py`'s existing `find_file()`/`open_file_ref()`,
the same no-extraction pattern already used elsewhere in this project
(e.g. `research/swl_5238_reader.py`): nothing is ever written to a
separate extracted file on disk.

Run with:
    py rns510_firmware_viewer.py
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "research"))
import firmware_java_reader as fjr  # noqa: E402

try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None


class FirmwareViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RNS510 Firmware Explorer (Java application layer)")
        self.root.geometry("1100x700")

        self.data = None
        self.class_paths = []
        self.classes = []
        self.images = []
        self._photo_refs = []  # keep PhotoImage objects alive

        self._build_menu()
        self._build_layout()

    # ------------------------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Firmware (ISO or .FLI)...", command=self.open_firmware)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

    def _build_layout(self):
        self.status = tk.StringVar(value="File > Open Firmware (.FLI)... to begin")
        status_bar = ttk.Label(self.root, textvariable=self.status, anchor="w", relief="sunken")
        status_bar.pack(side="bottom", fill="x")

        notebook = self.notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)

        self.tab_packages = ttk.Frame(notebook)
        self.tab_classes = ttk.Frame(notebook)
        self.tab_screens = ttk.Frame(notebook)
        self.tab_simulator = ttk.Frame(notebook)
        notebook.add(self.tab_packages, text="Package tree (names only)")
        notebook.add(self.tab_classes, text="Decompiled classes")
        notebook.add(self.tab_screens, text="Real screens / images")
        notebook.add(self.tab_simulator, text="Simulator (mockup)")

        self._build_packages_tab()
        self._build_classes_tab()
        self._build_screens_tab()
        self._build_simulator_tab()

    # ------------------------------------------------------------------
    def _build_packages_tab(self):
        top = ttk.Frame(self.tab_packages)
        top.pack(fill="x", padx=4, pady=4)
        ttk.Label(top, text="Filter:").pack(side="left")
        self.pkg_filter = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.pkg_filter)
        entry.pack(side="left", fill="x", expand=True, padx=4)
        entry.bind("<KeyRelease>", lambda e: self._refresh_package_list())

        self.pkg_count_label = ttk.Label(top, text="")
        self.pkg_count_label.pack(side="right")

        self.pkg_listbox = tk.Listbox(self.tab_packages, font=("Consolas", 10))
        self.pkg_listbox.pack(fill="both", expand=True, padx=4, pady=4)

    def _refresh_package_list(self):
        self.pkg_listbox.delete(0, tk.END)
        needle = self.pkg_filter.get().lower()
        shown = 0
        for p in self.class_paths:
            if needle in p.lower():
                self.pkg_listbox.insert(tk.END, p)
                shown += 1
        self.pkg_count_label.config(text=f"{shown} / {len(self.class_paths)}")

    # ------------------------------------------------------------------
    def _build_classes_tab(self):
        paned = ttk.PanedWindow(self.tab_classes, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned)
        self.class_listbox = tk.Listbox(left, font=("Consolas", 10), width=40)
        self.class_listbox.pack(fill="both", expand=True)
        self.class_listbox.bind("<<ListboxSelect>>", self._on_class_selected)
        paned.add(left, weight=1)

        right = ttk.Frame(paned)
        self.class_source = tk.Text(right, font=("Consolas", 10), wrap="none")
        self.class_source.pack(fill="both", expand=True)
        paned.add(right, weight=3)

    def _on_class_selected(self, _event):
        sel = self.class_listbox.curselection()
        if not sel or not self.data:
            return
        info = self.classes[sel[0]]
        self.class_source.delete("1.0", tk.END)
        self.class_source.insert(tk.END, "decompiling...\n")

        def work():
            import firmware_java_decompile as fjd
            import firmware_java_reader as fjr
            try:
                src = fjd.decompile_class(info.data)
            except Exception as exc:  # noqa: BLE001
                src = f"decompilation failed: {exc}"
            # for a partial/corrupted streamed class, the normal attempt above
            # usually fails outright -- fall back to real signatures mined
            # from its own intact constant pool (see reconstruct_class_signatures)
            if not getattr(info, "fully_valid", True) and "Can't load the class" in src:
                reconstructed = fjr.reconstruct_class_signatures(info)
                if reconstructed is not None:
                    try:
                        recon_src = fjd.decompile_class(reconstructed)
                        src = (
                            "// NOTE: this class is only partially recovered (see the\n"
                            "// wiki's Firmware-Embedded-Java-Application-Layer page).\n"
                            "// Field/method SIGNATURES below are real, mined from this\n"
                            "// class's own intact constant pool -- but there is no real\n"
                            "// bytecode, so method bodies are fabricated stand-ins, not\n"
                            "// the real implementation.\n\n" + recon_src
                        )
                    except Exception:  # noqa: BLE001
                        pass
            self.root.after(0, lambda: self._show_source(src))

        threading.Thread(target=work, daemon=True).start()

    def _show_source(self, src):
        self.class_source.delete("1.0", tk.END)
        self.class_source.insert(tk.END, src)

    # ------------------------------------------------------------------
    def _build_screens_tab(self):
        paned = ttk.PanedWindow(self.tab_screens, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned)
        self.screen_listbox = tk.Listbox(left, font=("Consolas", 10), width=30)
        self.screen_listbox.pack(fill="both", expand=True)
        self.screen_listbox.bind("<<ListboxSelect>>", self._on_screen_selected)
        paned.add(left, weight=1)

        right = ttk.Frame(paned)
        self.screen_canvas = tk.Canvas(right, bg="gray20")
        self.screen_canvas.pack(fill="both", expand=True)
        paned.add(right, weight=3)

    def _on_screen_selected(self, _event):
        sel = self.screen_listbox.curselection()
        if not sel or ImageTk is None:
            return
        info = self.images[sel[0]]
        photo = ImageTk.PhotoImage(info.image)
        self._photo_refs.append(photo)  # prevent garbage collection
        self.screen_canvas.delete("all")
        self.screen_canvas.create_image(0, 0, anchor="nw", image=photo)
        self.screen_canvas.config(scrollregion=(0, 0, info.width, info.height))

    # ------------------------------------------------------------------
    def _build_simulator_tab(self):
        note = (
            "Mockup, not verified logic: boot screen + button icon are REAL "
            "recovered assets; the menu is the REAL vdo/rns/app/* package "
            "tree from this firmware, drillable down to real class names. "
            "There is no recovered navigation bytecode behind this -- "
            "drilling down just walks the real package structure, not real "
            "unit behavior. See the wiki for what's real vs. placeholder here."
        )
        ttk.Label(self.tab_simulator, text=note, wraplength=1000, justify="left",
                  foreground="#a05a00").pack(fill="x", padx=6, pady=6)

        container = ttk.Frame(self.tab_simulator, relief="sunken", borderwidth=2)
        container.pack(padx=10, pady=10)

        self.sim_splash_frame = tk.Frame(container, bg="black", width=800, height=480)
        self.sim_splash_frame.pack_propagate(False)
        self.sim_menu_frame = tk.Frame(container, bg="#1c1c1c", width=800, height=480)
        self.sim_menu_frame.pack_propagate(False)

        self.sim_splash_label = tk.Label(self.sim_splash_frame, bg="black",
                                          fg="white", text="Open a firmware file first.")
        self.sim_splash_label.pack(fill="both", expand=True)
        ttk.Button(self.sim_splash_frame, text="Continue →",
                   command=self._sim_show_menu).place(relx=1.0, rely=1.0, anchor="se", x=-10, y=-10)
        ttk.Button(self.sim_splash_frame, text="← Prev screen",
                   command=lambda: self._sim_cycle_splash(-1)).place(
            relx=0.0, rely=1.0, anchor="sw", x=10, y=-10)
        ttk.Button(self.sim_splash_frame, text="Next screen →",
                   command=lambda: self._sim_cycle_splash(1)).place(
            relx=0.0, rely=1.0, anchor="sw", x=130, y=-10)
        self.sim_splash_caption = tk.StringVar(value="")
        tk.Label(self.sim_splash_frame, textvariable=self.sim_splash_caption,
                 bg="black", fg="#9fd89f", font=("Consolas", 9)).place(
            relx=0.5, rely=1.0, anchor="s", y=-12)
        self.sim_splash_images = []
        self.sim_splash_index = 0

        nav_bar = tk.Frame(self.sim_menu_frame, bg="#1c1c1c")
        nav_bar.pack(fill="x", padx=16, pady=(12, 0))
        self.sim_back_btn = tk.Button(nav_bar, text="← Back", command=self._sim_back,
                                       bg="#2e2e2e", fg="white", activebackground="#444")
        self.sim_back_btn.pack(side="left")
        self.sim_breadcrumb = tk.StringVar(value="")
        tk.Label(nav_bar, textvariable=self.sim_breadcrumb, bg="#1c1c1c", fg="#cfe8ff",
                 font=("Consolas", 10), anchor="w").pack(side="left", padx=12)

        self.sim_menu_grid = tk.Frame(self.sim_menu_frame, bg="#1c1c1c")
        self.sim_menu_grid.pack(fill="both", expand=True, padx=16, pady=16)
        self._sim_path = []  # real vdo/rns/app/* path segments drilled into so far

        bottom_bar = tk.Frame(self.sim_menu_frame, bg="#1c1c1c")
        bottom_bar.pack(fill="x", side="bottom", pady=8)
        self.sim_cancel_btn_holder = tk.Frame(bottom_bar, bg="#1c1c1c")
        self.sim_cancel_btn_holder.pack(side="right", padx=10)

        self.sim_status = tk.StringVar(value="")
        tk.Label(bottom_bar, textvariable=self.sim_status, bg="#1c1c1c", fg="#9fd89f",
                 anchor="w").pack(side="left", padx=10, fill="x", expand=True)

        self.sim_splash_frame.pack()
        self._sim_state = "splash"

    def _sim_show_splash(self):
        self.sim_menu_frame.pack_forget()
        self.sim_splash_frame.pack()

    def _sim_show_splash_image(self):
        if not self.sim_splash_images:
            self.sim_splash_label.config(
                image="", text="(no real screen recovered from this firmware)"
            )
            self.sim_splash_caption.set("")
            return
        im = self.sim_splash_images[self.sim_splash_index]
        if ImageTk is not None:
            photo = ImageTk.PhotoImage(im.image)
            self._photo_refs.append(photo)
            self.sim_splash_label.config(image=photo, text="")
        else:
            self.sim_splash_label.config(image="", text="(Pillow not installed)")
        flag = " [partial]" if im.partial else ""
        self.sim_splash_caption.set(
            f"real screen {self.sim_splash_index + 1}/{len(self.sim_splash_images)} "
            f"-- offset 0x{im.offset:x}, {im.width}x{im.height}{flag}"
        )

    def _sim_cycle_splash(self, direction):
        if not self.sim_splash_images:
            return
        self.sim_splash_index = (self.sim_splash_index + direction) % len(self.sim_splash_images)
        self._sim_show_splash_image()

    def _sim_show_menu(self):
        self.sim_splash_frame.pack_forget()
        self.sim_menu_frame.pack()

    def _sim_find_decompilable(self, full_class_name):
        """Return the index into self.classes/self.class_listbox of a
        class (standalone or streamed) whose own real name matches
        `full_class_name` (e.g. "vdo/rns/app/.../Foo.class"), or None."""
        want_no_suffix = full_class_name[:-len(".class")]  # standalone ClassFileInfo.name has no ".class"
        for i, info in enumerate(self.classes):
            name = getattr(info, "name", None)
            if name == full_class_name or name == want_no_suffix:
                return i
        return None

    def _sim_open_class(self, class_index):
        self.notebook.select(self.tab_classes)
        self.class_listbox.selection_clear(0, tk.END)
        self.class_listbox.selection_set(class_index)
        self.class_listbox.see(class_index)
        self._on_class_selected(None)

    def _sim_drill_into(self, name):
        self._sim_path.append(name)
        self._sim_render_menu_level()

    def _sim_back(self):
        if self._sim_path:
            self._sim_path.pop()
            self._sim_render_menu_level()

    def _sim_render_menu_level(self):
        """Render the menu grid for the real package path currently drilled
        into (`self._sim_path`, segments under `vdo/rns/app/`): real
        sub-package names become further drill-down buttons, AND any real
        classes declared directly at this same level (a package can
        legitimately have both) are shown right below them -- as a plain
        label, or as a clickable green button when that exact class also
        happens to be one of the real decompilable ones found elsewhere
        in this firmware. This is as deep as real structural information
        goes without recovered navigation bytecode."""
        for child in self.sim_menu_grid.winfo_children():
            child.destroy()

        prefix = "rns/app/" + "".join(seg + "/" for seg in self._sim_path)
        self.sim_breadcrumb.set("vdo/" + prefix.rstrip("/"))
        self.sim_back_btn.config(state="normal" if self._sim_path else "disabled")

        counts = {}
        leaf_classes = []
        for p in self.class_paths:
            idx = p.find(prefix)
            if idx == -1:
                continue
            rest = p[idx + len(prefix):]
            if "/" in rest:
                seg = rest.split("/", 1)[0]
                if seg:
                    counts[seg] = counts.get(seg, 0) + 1
            elif rest:
                leaf_classes.append(rest)

        entries = sorted(counts.items(), key=lambda kv: -kv[1])[:12]
        cols = 4
        row = 0
        for i, (name, count) in enumerate(entries):
            tk.Button(
                self.sim_menu_grid, text=f"{name}\n({count} real classes)",
                width=14, height=3, bg="#2e2e2e", fg="white", activebackground="#444",
                command=lambda n=name: self._sim_drill_into(n),
            ).grid(row=i // cols, column=i % cols, padx=8, pady=8)
        if entries:
            row = (len(entries) - 1) // cols + 1

        decompilable = 0
        if leaf_classes:
            if entries:
                tk.Frame(self.sim_menu_grid, bg="#444", height=2).grid(
                    row=row, column=0, columnspan=cols, sticky="we", pady=10)
                row += 1
            shown = sorted(leaf_classes)[:20]
            for j, name in enumerate(shown):
                full_name = f"vdo/{prefix}{name}.class"
                class_index = self._sim_find_decompilable(full_name)
                if class_index is not None:
                    decompilable += 1
                    widget = tk.Button(
                        self.sim_menu_grid, text=f"{name}  ▸ real source", anchor="w",
                        bg="#28422d", fg="#9fd89f", font=("Consolas", 10), relief="flat",
                        command=lambda ci=class_index: self._sim_open_class(ci),
                    )
                else:
                    widget = tk.Label(self.sim_menu_grid, text=name, bg="#1c1c1c", fg="#cfe8ff",
                                       anchor="w", font=("Consolas", 10))
                widget.grid(row=row + j // 2, column=(j % 2) * (cols // 2), columnspan=cols // 2,
                            sticky="we", padx=8, pady=2)

        if not entries and not leaf_classes:
            tk.Label(self.sim_menu_grid, bg="#1c1c1c", fg="white",
                     text="(no further real structure found here)").pack()
            self.sim_status.set("")
            return

        parts = []
        if entries:
            parts.append(f"{len(entries)} real sub-package(s)")
        if leaf_classes:
            extra = f" ({decompilable} with real recovered source, click to view)" if decompilable else ""
            parts.append(f"{len(leaf_classes)} real class(es) here{extra}")
        self.sim_status.set(" + ".join(parts) + f" under vdo/{prefix.rstrip('/')}")

    def _sim_populate(self):
        """(Re)build the simulator's boot screen, menu grid, and CANCEL
        button from whatever was actually found in the currently-loaded
        firmware -- nothing here is hardcoded."""
        # 1. boot screen: cycle through every real, fully-decoded 800x480
        # screen found (falls back to whatever was found, partial included,
        # if there's no full-size one)
        self.sim_splash_images = [im for im in self.images if not im.partial and im.width == 800]
        if not self.sim_splash_images:
            self.sim_splash_images = list(self.images)
        self.sim_splash_index = 0
        self._sim_show_splash_image()

        # 2. CANCEL-style button icon: the real recovered UI widget icons are
        # the 100x50 hits (see find_embedded_images docstring item 3)
        for child in self.sim_cancel_btn_holder.winfo_children():
            child.destroy()
        icon = next((im for im in self.images if im.width == 100 and im.height == 50), None)
        if icon is not None and ImageTk is not None:
            photo = ImageTk.PhotoImage(icon.image)
            self._photo_refs.append(photo)
            tk.Button(self.sim_cancel_btn_holder, image=photo, borderwidth=0,
                      command=self._sim_show_splash).pack()
        else:
            ttk.Button(self.sim_cancel_btn_holder, text="CANCEL",
                       command=self._sim_show_splash).pack()

        # 3. menu entries: real vdo/rns/app/* package structure, drillable --
        # see _sim_render_menu_level()
        self._sim_path = []
        self._sim_render_menu_level()

    # ------------------------------------------------------------------
    def open_firmware(self):
        path = filedialog.askopenfilename(
            title="Open firmware ISO (preferred) or a raw .FLI file",
            filetypes=[
                ("Firmware ISO", "*.iso *.ISO"),
                ("Raw firmware image (.FLI)", "*.FLI *.fli"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.status.set(f"Loading {os.path.basename(path)}...")

        def work():
            try:
                if path.lower().endswith(".iso"):
                    data, source_label = self._read_fli_from_iso(path)
                else:
                    with open(path, "rb") as f:
                        data = f.read()
                    source_label = os.path.basename(path)
            except Exception as exc:  # noqa: BLE001
                self.root.after(0, lambda: self._on_load_error(exc))
                return
            class_paths = sorted(fjr.find_java_class_paths(data))
            classes = fjr.find_class_files(data)
            streamed = fjr.find_streamed_zip_classes(data)
            try:
                images = fjr.find_embedded_images(data)
            except ImportError:
                images = []
            self.root.after(0, lambda: self._on_loaded(
                data, class_paths, classes, streamed, images, source_label))

        threading.Thread(target=work, daemon=True).start()

    def _read_fli_from_iso(self, iso_path):
        """Locate this disc family's main apps firmware image (a
        `FHDD*.FLI`, see rns510_iso.find_file()'s own docstring for why
        that pattern, not a hardcoded name) inside a firmware ISO and
        read just ITS OWN byte range directly out of the ISO file --
        no extraction to a separate file anywhere -- via rns510_iso.py's
        existing find_file()/open_file_ref() (the same direct-from-ISO,
        no-extraction pattern already used elsewhere in this project,
        e.g. research/swl_5238_reader.py's find_screen_resolution()).
        Returns `(data, source_label)`."""
        import rns510_iso as riso
        iso = riso.open_tolerant(iso_path)
        try:
            inner_path = riso.find_file(iso, "FHDD*.FLI")
            if inner_path is None:
                raise FileNotFoundError(
                    "no FHDD*.FLI (the main apps firmware image) found inside this ISO"
                )
            ref = riso.open_file_ref(iso, inner_path, iso_path)
        finally:
            iso.close()
        with riso.open_ref_or_path(ref) as f:
            data = f.read()
        return data, f"{os.path.basename(iso_path)} :: {inner_path}"

    def _on_load_error(self, exc):
        self.status.set(f"Failed to load firmware: {exc}")
        messagebox.showerror("Failed to load firmware", str(exc))

    def _on_loaded(self, data, class_paths, classes, streamed, images, source_label):
        self.data = data
        self.class_paths = class_paths
        # merge both real sources of decompilable classes; both expose .data,
        # so the existing decompile-on-select logic works unchanged for either
        self.classes = list(classes) + list(streamed)
        self.images = images

        self._refresh_package_list()

        self.class_listbox.delete(0, tk.END)
        for info in classes:
            label = f"0x{info.start:x}  ({info.end - info.start} bytes)"
            self.class_listbox.insert(tk.END, label)
        for info in streamed:
            if info.fully_valid:
                flag = ""
            elif info.trustworthy_prefix_estimate:
                flag = f"  [partial/corrupted, ~{info.trustworthy_prefix_estimate} bytes trustworthy]"
            else:
                flag = "  [partial/corrupted]"
            label = f"0x{info.offset:x}  {info.name}{flag}"
            self.class_listbox.insert(tk.END, label)

        self.screen_listbox.delete(0, tk.END)
        for info in images:
            flag = "  [partial]" if info.partial else ""
            self.screen_listbox.insert(tk.END, f"0x{info.offset:x}  {info.width}x{info.height}{flag}")
        if images and ImageTk is None:
            messagebox.showwarning(
                "Pillow not installed",
                "Found real embedded images, but Pillow (PIL) isn't installed "
                "so they can't be displayed. Run: py -m pip install Pillow",
            )

        self.status.set(
            f"{source_label}: {len(class_paths)} real Java class names, "
            f"{len(self.classes)} decompilable classes ({len(classes)} standalone + "
            f"{len(streamed)} from streamed ZIP entries), {len(images)} real screens/images"
        )

        self._sim_populate()
        self._sim_show_splash()


def main():
    root = tk.Tk()
    FirmwareViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
