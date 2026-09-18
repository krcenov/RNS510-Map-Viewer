"""
rns510_gui.py -- tkinter GUI for editing db/eeu.rd / db/eeu.il / db/eeu.iof
inside a VW RNS510 navigation map ISO.

All actual file-format logic lives in rns510_core.py (no GUI code there);
this module is a thin, testable-by-inspection widget layer that calls into
rns510_core.MapProject. Long-running operations (load, save) run on a
background thread so the UI does not freeze; progress is relayed back to
the main thread through a thread-safe queue polled via Tk's `after()`.

Run with:
    py rns510_gui.py

After saving a new ISO, use the separate "maps-tool" application to convert
it into the MAPS/MAPSDVD SD card folder structure the head unit needs --
this tool only produces the edited ISO.
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import rns510_core as core

APP_TITLE = "RNS510 Map Editor"

EXPERIMENTAL_ADD_WARNING = (
    "EXPERIMENTAL: adding a brand-new road only updates eeu.rd / eeu.il / "
    "eeu.iof. The road-name search tree, city/county tables and map "
    "rendering tiles are NOT updated. A new road may show up in this "
    "tool's search and in the head unit's raw record data, but it may NOT "
    "render on the map display or be routable. Editing the name or "
    "coordinates of an EXISTING road is much more reliable -- prefer that "
    "whenever possible."
)


class BackgroundTask:
    """Runs `fn` on a worker thread, forwarding progress strings and the
    final (result, error) back to the Tk main thread via a queue that the
    caller polls with `root.after`."""

    def __init__(self, root, fn, on_progress, on_done):
        self.root = root
        self.q = queue.Queue()
        self.on_progress = on_progress
        self.on_done = on_done

        def worker():
            try:
                result = fn(progress=lambda msg: self.q.put(("progress", msg)))
                self.q.put(("done", result))
            except Exception as exc:  # noqa: BLE001 - surface any error to the UI
                self.q.put(("error", exc))

        self._thread = threading.Thread(target=worker, daemon=True)

    def start(self):
        self._thread.start()
        self._poll()

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "progress":
                    self.on_progress(payload)
                elif kind == "done":
                    self.on_done(payload, None)
                    return
                elif kind == "error":
                    self.on_done(None, payload)
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll)


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("900x600")

        self.project = None  # core.MapProject once an ISO is loaded
        self.results = []  # last search results: list[core.RoadRecord]
        self.busy = False

        self._build_menu()
        self._build_widgets()
        self._set_status("No ISO loaded. Use File > Open Map ISO...")
        self._set_controls_enabled(False)

    # ------------------------------------------------------------- layout

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open Map ISO...", command=self.on_open_iso)
        filemenu.add_command(label="Save As New ISO...", command=self.on_save_as)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

    def _build_widgets(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        self.iso_label = ttk.Label(top, text="(no ISO loaded)", anchor="w")
        self.iso_label.pack(fill="x")

        # --- search --------------------------------------------------
        search_frame = ttk.LabelFrame(self.root, text="Search roads (by name, via eeu.il index)", padding=8)
        search_frame.pack(fill="x", padx=8, pady=4)

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True)
        search_entry.bind("<Return>", lambda e: self.on_search())
        ttk.Button(search_frame, text="Search", command=self.on_search).pack(side="left", padx=4)

        # --- results ---------------------------------------------------
        results_frame = ttk.LabelFrame(self.root, text="Results", padding=8)
        results_frame.pack(fill="both", expand=True, padx=8, pady=4)

        columns = ("index", "name", "lon", "lat")
        self.tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=12)
        for col, width in (("index", 90), ("name", 300), ("lon", 100), ("lat", 100)):
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select_result)

        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="left", fill="y")

        self.results_note = ttk.Label(self.root, text="", anchor="w")
        self.results_note.pack(fill="x", padx=8)

        # --- edit existing ------------------------------------------------
        edit_frame = ttk.LabelFrame(self.root, text="Edit selected road (reliable -- preserves unknown bytes)", padding=8)
        edit_frame.pack(fill="x", padx=8, pady=4)

        self.edit_index_var = tk.StringVar(value="(select a result above)")
        ttk.Label(edit_frame, textvariable=self.edit_index_var).grid(row=0, column=0, columnspan=4, sticky="w")

        ttk.Label(edit_frame, text="Name:").grid(row=1, column=0, sticky="w")
        self.edit_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.edit_name_var, width=40).grid(row=1, column=1, sticky="w")

        ttk.Label(edit_frame, text="Lon:").grid(row=1, column=2, sticky="w")
        self.edit_lon_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.edit_lon_var, width=14).grid(row=1, column=3, sticky="w")

        ttk.Label(edit_frame, text="Lat:").grid(row=1, column=4, sticky="w")
        self.edit_lat_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.edit_lat_var, width=14).grid(row=1, column=5, sticky="w")

        self.apply_edit_btn = ttk.Button(edit_frame, text="Apply Edit", command=self.on_apply_edit)
        self.apply_edit_btn.grid(row=1, column=6, padx=6)

        # --- add new (experimental) -----------------------------------
        add_frame = ttk.LabelFrame(self.root, text="Add new road", padding=8)
        add_frame.pack(fill="x", padx=8, pady=4)

        warn = ttk.Label(add_frame, text="EXPERIMENTAL - see tooltip / hover for details", foreground="#b30000")
        warn.grid(row=0, column=0, columnspan=6, sticky="w")
        self._add_tooltip(warn, EXPERIMENTAL_ADD_WARNING)

        ttk.Label(add_frame, text="Name:").grid(row=1, column=0, sticky="w")
        self.new_name_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.new_name_var, width=40).grid(row=1, column=1, sticky="w")

        ttk.Label(add_frame, text="Lon:").grid(row=1, column=2, sticky="w")
        self.new_lon_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.new_lon_var, width=14).grid(row=1, column=3, sticky="w")

        ttk.Label(add_frame, text="Lat:").grid(row=1, column=4, sticky="w")
        self.new_lat_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.new_lat_var, width=14).grid(row=1, column=5, sticky="w")

        self.add_btn = ttk.Button(add_frame, text="Add Road (experimental)", command=self.on_add_road)
        self.add_btn.grid(row=1, column=6, padx=6)

        # --- status bar --------------------------------------------------
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", side="bottom")

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", side="bottom")

        self._controls = [search_entry, self.tree, self.apply_edit_btn, self.add_btn]

    @staticmethod
    def _add_tooltip(widget, text):
        tip = tk.Toplevel(widget)
        tip.withdraw()
        tip.overrideredirect(True)
        label = ttk.Label(tip, text=text, wraplength=420, background="#ffffe0",
                           relief="solid", borderwidth=1, padding=6)
        label.pack()

        def show(event):
            x = widget.winfo_rootx() + 10
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            tip.geometry("+%d+%d" % (x, y))
            tip.deiconify()

        def hide(event):
            tip.withdraw()

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    # -------------------------------------------------------------- state

    def _set_status(self, text):
        self.status_var.set(text)

    def _set_controls_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for w in getattr(self, "_controls", []):
            try:
                w.configure(state=state)
            except tk.TclError:
                pass

    def _begin_busy(self, msg):
        self.busy = True
        self._set_controls_enabled(False)
        self._set_status(msg)
        self.progress.start(12)

    def _end_busy(self):
        self.busy = False
        self.progress.stop()
        self._set_controls_enabled(self.project is not None)

    # ------------------------------------------------------------- actions

    def on_open_iso(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(
            title="Open Map ISO",
            filetypes=[("ISO images", "*.iso *.ISO"), ("All files", "*.*")],
        )
        if not path:
            return

        self.project = core.MapProject(path)
        self._begin_busy("Loading %s ..." % path)

        def do_load(progress):
            self.project.load(progress=progress)
            return path

        def done(result, error):
            self._end_busy()
            if error:
                messagebox.showerror("Open failed", str(error))
                self._set_status("Failed to open ISO: %s" % error)
                self.project = None
                return
            self.iso_label.config(text="Loaded: %s  (%d road records)" % (result, self.project.record_count()))
            self._set_status("Ready. %d road records loaded." % self.project.record_count())
            self._set_controls_enabled(True)

        BackgroundTask(self.root, do_load, self._set_status, done).start()

    def on_search(self):
        if self.busy or self.project is None:
            return
        query = self.search_var.get().strip()
        if not query:
            return
        self._begin_busy("Searching for %r ..." % query)

        def do_search(progress):
            return self.project.search(query, limit=300)

        def done(result, error):
            self._end_busy()
            if error:
                messagebox.showerror("Search failed", str(error))
                return
            results, total = result
            self.results = results
            for row in self.tree.get_children():
                self.tree.delete(row)
            # eeu.il can contain multiple entries pointing at the same
            # eeu.rd record index (observed on the real disc), so the row
            # iid must be the row position, not the record index.
            for row_id, r in enumerate(results):
                self.tree.insert("", "end", iid=str(row_id), values=(r.index, r.name, r.lon, r.lat))
            if total > len(results):
                note = "Showing first %d of %d matches -- refine your search for more precise results." % (
                    len(results), total)
            else:
                note = "%d match(es)." % total
            self.results_note.config(text=note)
            self._set_status("Search complete: %s" % note)

        BackgroundTask(self.root, do_search, self._set_status, done).start()

    def on_select_result(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        row_id = int(sel[0])
        if not (0 <= row_id < len(self.results)):
            return
        record = self.results[row_id]
        self.edit_index_var.set("Editing record #%d" % record.index)
        self.edit_name_var.set(record.name)
        self.edit_lon_var.set(str(record.lon))
        self.edit_lat_var.set(str(record.lat))

    def on_apply_edit(self):
        if self.busy or self.project is None:
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a result row to edit first.")
            return
        row_id = int(sel[0])
        if not (0 <= row_id < len(self.results)):
            return
        index = self.results[row_id].index
        try:
            new_lon = float(self.edit_lon_var.get())
            new_lat = float(self.edit_lat_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Longitude/Latitude must be numbers.")
            return
        new_name = self.edit_name_var.get()
        if len(new_name.encode("latin-1", errors="replace")) > core.RD_NAME_SIZE:
            messagebox.showerror("Name too long", "Name must fit in %d bytes." % core.RD_NAME_SIZE)
            return

        self._begin_busy("Applying edit to record #%d ..." % index)

        def do_edit(progress):
            return self.project.edit_record(index, new_name=new_name, new_lon=new_lon, new_lat=new_lat)

        def done(result, error):
            self._end_busy()
            if error:
                messagebox.showerror("Edit failed", str(error))
                return
            self.tree.item(str(row_id), values=(result.index, result.name, result.lon, result.lat))
            self.results[row_id] = result
            self._set_status("Edit applied to record #%d (working copy only -- use Save As to write an ISO)." % index)

        BackgroundTask(self.root, do_edit, self._set_status, done).start()

    def on_add_road(self):
        if self.busy or self.project is None:
            return
        name = self.new_name_var.get().strip()
        if not name:
            messagebox.showinfo("Name required", "Enter a name for the new road.")
            return
        if len(name.encode("latin-1", errors="replace")) > core.RD_NAME_SIZE:
            messagebox.showerror("Name too long", "Name must fit in %d bytes." % core.RD_NAME_SIZE)
            return
        try:
            lon = float(self.new_lon_var.get())
            lat = float(self.new_lat_var.get())
        except ValueError:
            messagebox.showerror("Invalid input", "Longitude/Latitude must be numbers.")
            return

        proceed = messagebox.askyesno(
            "Confirm experimental add",
            EXPERIMENTAL_ADD_WARNING + "\n\nAdd this road anyway?",
        )
        if not proceed:
            return

        self._begin_busy("Appending new road %r ..." % name)

        def do_add(progress):
            return self.project.append_record(name, lon, lat)

        def done(result, error):
            self._end_busy()
            if error:
                messagebox.showerror("Add failed", str(error))
                return
            self._set_status(
                "Added new road %r as record #%d (working copy only -- use Save As to write an ISO). "
                "Remember: experimental, may not render/route on real hardware." % (name, result))
            self.new_name_var.set("")
            self.new_lon_var.set("")
            self.new_lat_var.set("")

        BackgroundTask(self.root, do_add, self._set_status, done).start()

    def on_save_as(self):
        if self.busy or self.project is None:
            messagebox.showinfo("No ISO loaded", "Open a Map ISO first.")
            return
        out_path = filedialog.asksaveasfilename(
            title="Save As New ISO",
            defaultextension=".iso",
            filetypes=[("ISO images", "*.iso")],
        )
        if not out_path:
            return
        if os.path.abspath(out_path) == os.path.abspath(self.project.iso_path):
            messagebox.showerror("Invalid path", "Cannot overwrite the original ISO. Choose a different filename.")
            return

        self._begin_busy("Writing new ISO to %s ..." % out_path)

        def do_save(progress):
            self.project.build_output_iso(out_path, progress=progress)
            progress("Verifying round-trip...")
            checks = {r.index: (r.name, r.lon, r.lat) for r in self.results[:5]}
            ok, details = self.project.verify_output(out_path, checks, progress=progress) if checks else (True, [])
            return out_path, ok, details

        def done(result, error):
            self._end_busy()
            if error:
                messagebox.showerror("Save failed", str(error))
                self._set_status("Save failed: %s" % error)
                return
            saved_path, ok, details = result
            msg = "Saved: %s\n\nRound-trip verification: %s" % (saved_path, "PASSED" if ok else "FAILED")
            if details:
                msg += "\n\n" + "\n".join(details)
            msg += ("\n\nNext step: run maps-tool (separate application) on this ISO "
                    "to produce the MAPS/MAPSDVD SD card folder structure.")
            if ok:
                messagebox.showinfo("Save complete", msg)
            else:
                messagebox.showwarning("Save complete, verification FAILED", msg)
            self._set_status("Saved to %s -- verification %s." % (saved_path, "PASSED" if ok else "FAILED"))

        BackgroundTask(self.root, do_save, self._set_status, done).start()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
