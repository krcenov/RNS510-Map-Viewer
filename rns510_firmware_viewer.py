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

Status: an early step toward the longer-term goal of a full visual
simulator of the real RNS-510 UI (menus, screens, everything). What's
recoverable TODAY is real structural/architectural information (the real
class/package tree, a `MenuManagerService`/`MenuManagerStateMachine`, a
VW-branded custom widget toolkit) and a handful of real screens/classes --
not yet a working menu simulation, since the bulk of the real application
is pre-linked/"romized" into Jeode's own (currently undocumented) bundle
format. See the wiki page for the full picture and what's still open.

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
        file_menu.add_command(label="Open Firmware (.FLI)...", command=self.open_firmware)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

    def _build_layout(self):
        self.status = tk.StringVar(value="File > Open Firmware (.FLI)... to begin")
        status_bar = ttk.Label(self.root, textvariable=self.status, anchor="w", relief="sunken")
        status_bar.pack(side="bottom", fill="x")

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)

        self.tab_packages = ttk.Frame(notebook)
        self.tab_classes = ttk.Frame(notebook)
        self.tab_screens = ttk.Frame(notebook)
        notebook.add(self.tab_packages, text="Package tree (names only)")
        notebook.add(self.tab_classes, text="Decompiled classes")
        notebook.add(self.tab_screens, text="Real screens / images")

        self._build_packages_tab()
        self._build_classes_tab()
        self._build_screens_tab()

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
            try:
                src = fjd.decompile_class(info.data)
            except Exception as exc:  # noqa: BLE001
                src = f"decompilation failed: {exc}"
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
    def open_firmware(self):
        path = filedialog.askopenfilename(
            title="Open firmware (e.g. FHDD6.FLI)",
            filetypes=[("Firmware image", "*.FLI *.fli"), ("All files", "*.*")],
        )
        if not path:
            return
        self.status.set(f"Loading {os.path.basename(path)}...")

        def work():
            with open(path, "rb") as f:
                data = f.read()
            class_paths = sorted(fjr.find_java_class_paths(data))
            classes = fjr.find_class_files(data)
            streamed = fjr.find_streamed_zip_classes(data)
            try:
                images = fjr.find_embedded_images(data)
            except ImportError:
                images = []
            self.root.after(0, lambda: self._on_loaded(data, class_paths, classes, streamed, images, path))

        threading.Thread(target=work, daemon=True).start()

    def _on_loaded(self, data, class_paths, classes, streamed, images, path):
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
            f"{os.path.basename(path)}: {len(class_paths)} real Java class names, "
            f"{len(self.classes)} decompilable classes ({len(classes)} standalone + "
            f"{len(streamed)} from streamed ZIP entries), {len(images)} real screens/images"
        )


def main():
    root = tk.Tk()
    FirmwareViewerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
