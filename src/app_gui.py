import os
import time
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from database import Database
from scanner import PhotoScanner
from face_engine import FaceEngine
from config import FACE_DISTANCE_THRESHOLD, RESULTS_DIR

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# -- UI States --
STATE_IDLE = "idle"
STATE_SCANNING = "scanning"
STATE_SEARCHING = "searching"
STATE_RESULTS = "results"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Photo Finder")
        self.geometry("1100x700")
        self.minsize(900, 550)

        # Window icon (look in project root)
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(root_dir, "icon.png")
        if os.path.exists(icon_path):
            icon_image = Image.open(icon_path).resize((64, 64))
            self._icon = ImageTk.PhotoImage(icon_image)
            self.iconphoto(False, self._icon)

        self.db = Database()
        self.engine = FaceEngine()
        self.scanner = PhotoScanner(self.db)
        self._state = STATE_IDLE

        self._build_ui()
        self._load_root_path()
        self._load_persons()
        self._refresh_stats()

    # ==================================================================
    #  UI CONSTRUCTION
    # ==================================================================
    def _build_ui(self):
        # -- Topbar --
        self.topbar = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.topbar.pack(side="top", fill="x")
        self.topbar.pack_propagate(False)

        app_label = ctk.CTkLabel(
            self.topbar,
            text="📷 Photo Finder",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        app_label.pack(side="left", padx=15)

        self.stats_label = ctk.CTkLabel(
            self.topbar,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#aaaaaa",
        )
        self.stats_label.pack(side="right", padx=15)

        self.status_label = ctk.CTkLabel(
            self.topbar,
            text="Ready",
            font=ctk.CTkFont(size=12),
            text_color="#888888",
        )
        self.status_label.pack(side="right", padx=15)

        # -- Main container --
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(side="top", expand=True, fill="both", padx=10, pady=(5, 10))

        # -- Sidebar --
        self.sidebar = ctk.CTkFrame(container, width=260, corner_radius=10)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.sidebar.pack_propagate(False)

        # Section: Root Directory
        ctk.CTkLabel(
            self.sidebar,
            text="📂 ROOT DIRECTORY",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=15, pady=(15, 5))

        self.root_path_var = ctk.StringVar()
        self.root_entry = ctk.CTkEntry(
            self.sidebar,
            textvariable=self.root_path_var,
            state="readonly",
            height=30,
            font=ctk.CTkFont(size=11),
        )
        self.root_entry.pack(fill="x", padx=15, pady=(0, 5))

        self.btn_select = ctk.CTkButton(
            self.sidebar, text="Select Folder", command=self.select_root, height=32
        )
        self.btn_select.pack(fill="x", padx=15, pady=2)

        self.btn_rescan = ctk.CTkButton(
            self.sidebar, text="⟳  Rescan", command=self.rescan, height=32
        )
        self.btn_rescan.pack(fill="x", padx=15, pady=2)

        self.btn_cancel = ctk.CTkButton(
            self.sidebar,
            text="✕  Cancel",
            command=self._cancel_scan,
            height=32,
            fg_color="#8B0000",
            hover_color="#B22222",
        )
        # Not packed yet — only visible during scan

        # Separator
        sep1 = ctk.CTkFrame(self.sidebar, height=2, fg_color="#333333")
        sep1.pack(fill="x", padx=15, pady=12)

        # Section: Persons
        ctk.CTkLabel(
            self.sidebar,
            text="👤 PERSONS (select one or more)",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=15, pady=(0, 5))

        # Scrollable frame with checkboxes for multi-person selection
        self.person_scroll = ctk.CTkScrollableFrame(
            self.sidebar, height=120, corner_radius=6,
            fg_color=("#2b2b2b", "#2b2b2b"),
        )
        self.person_scroll.pack(fill="x", padx=15, pady=(0, 5))

        # Will hold {name: ctk.BooleanVar}
        self.person_check_vars = {}
        self.person_checkboxes = []

        self.btn_search = ctk.CTkButton(
            self.sidebar,
            text="🔍  Search",
            command=self.search,
            height=32,
            fg_color="#1B5E20",
            hover_color="#2E7D32",
        )
        self.btn_search.pack(fill="x", padx=15, pady=2)

        self.btn_register = ctk.CTkButton(
            self.sidebar, text="＋  Register Person", command=self.register_person, height=32
        )
        self.btn_register.pack(fill="x", padx=15, pady=2)

        # Separator
        sep2 = ctk.CTkFrame(self.sidebar, height=2, fg_color="#333333")
        sep2.pack(fill="x", padx=15, pady=12)

        # Sidebar info
        self.sidebar_info = ctk.CTkLabel(
            self.sidebar,
            text="100% Offline\nFull privacy",
            font=ctk.CTkFont(size=11),
            text_color="#666666",
            justify="center",
        )
        self.sidebar_info.pack(side="bottom", pady=15)

        # -- Main area --
        self.main = ctk.CTkFrame(container, corner_radius=10)
        self.main.pack(side="right", expand=True, fill="both")

        # Progress area (visible during scan)
        self.progress_frame = ctk.CTkFrame(self.main, fg_color="transparent")

        self.progress_title = ctk.CTkLabel(
            self.progress_frame,
            text="Scanning photos...",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.progress_title.pack(pady=(20, 10))

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, width=400, height=16)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=5)

        self.progress_detail = ctk.CTkLabel(
            self.progress_frame,
            text="Preparing...",
            font=ctk.CTkFont(size=12),
            text_color="#aaaaaa",
        )
        self.progress_detail.pack(pady=5)

        self.progress_file = ctk.CTkLabel(
            self.progress_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#666666",
            wraplength=500,
        )
        self.progress_file.pack(pady=2)

        # Output/results area
        self.output_frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self.output_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.output_header = ctk.CTkLabel(
            self.output_frame,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        self.output_header.pack(fill="x", pady=(0, 5))

        self.output_box = ctk.CTkTextbox(
            self.output_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="none",
        )
        self.output_box.pack(expand=True, fill="both")

        # Symlinks button (hidden by default)
        self.btn_symlinks = ctk.CTkButton(
            self.output_frame,
            text="📁  Create folder with symlinks",
            command=self._create_symlinks,
            height=32,
            fg_color="#1565C0",
            hover_color="#1976D2",
        )

        # Initial state
        self._show_welcome()

    # ==================================================================
    #  UI HELPERS (thread-safe)
    # ==================================================================
    def _ui(self, fn):
        """Schedule fn to run on the main thread. Safe to call from any thread."""
        self.after(0, fn)

    def _set_status(self, text):
        self._ui(lambda: self.status_label.configure(text=text))

    def _refresh_stats(self):
        photos = self.db.get_photo_count()
        persons = self.db.get_person_count()
        self.stats_label.configure(text=f"📷 {photos:,} photos  •  👤 {persons} persons")

    def _show_welcome(self):
        """Show the welcome screen when no action is in progress."""
        root = self.root_path_var.get()
        self.output_header.configure(text="")
        self.output_box.delete("1.0", "end")

        if not root:
            self.output_box.insert("end", "  Welcome to Photo Finder!\n\n")
            self.output_box.insert("end", "  ← Select a root directory to get started.\n")
        else:
            self.output_box.insert("end", f"  Root directory: {root}\n\n")
            self.output_box.insert("end", "  Use the buttons on the left to:\n")
            self.output_box.insert("end", "    • Rescan for new photos\n")
            self.output_box.insert("end", "    • Register a person\n")
            self.output_box.insert("end", "    • Search for a person in your photos\n")

    def _set_state(self, state):
        """Manage button enable/disable based on the current state."""
        self._state = state

        if state == STATE_SCANNING:
            self.btn_select.configure(state="disabled")
            self.btn_rescan.configure(state="disabled")
            self.btn_search.configure(state="disabled")
            self.btn_register.configure(state="disabled")
            self._set_checkboxes_state("disabled")
            # Show cancel button
            self.btn_rescan.pack_forget()
            self.btn_cancel.pack(fill="x", padx=15, pady=2, after=self.btn_select)
            # Show progress, hide output
            self.output_frame.pack_forget()
            self.progress_frame.pack(expand=True, fill="both", padx=10, pady=10)
        elif state == STATE_SEARCHING:
            self.btn_select.configure(state="disabled")
            self.btn_rescan.configure(state="disabled")
            self.btn_search.configure(state="disabled")
            self.btn_register.configure(state="disabled")
            self._set_checkboxes_state("disabled")
            # Clear output for new search
            self.output_header.configure(text="Searching...")
            self.output_box.delete("1.0", "end")
            self.btn_symlinks.pack_forget()
        else:
            self.btn_select.configure(state="normal")
            self.btn_rescan.configure(state="normal")
            self.btn_search.configure(state="normal")
            self.btn_register.configure(state="normal")
            self._set_checkboxes_state("normal")
            # Hide cancel, show rescan
            self.btn_cancel.pack_forget()
            self.btn_rescan.pack(fill="x", padx=15, pady=2, after=self.btn_select)
            # Hide progress, show output
            self.progress_frame.pack_forget()
            self.output_frame.pack(expand=True, fill="both", padx=10, pady=10)

    # ==================================================================
    #  ACTIONS
    # ==================================================================
    def _load_root_path(self):
        path = self.db.get_setting("root_path")
        if path:
            self.root_path_var.set(path)

    def _load_persons(self):
        persons = self.db.get_persons()
        self.person_map = {name: pid for pid, name in persons}
        names = list(self.person_map.keys())

        # Clear existing checkboxes
        for cb in self.person_checkboxes:
            cb.destroy()
        self.person_checkboxes.clear()
        self.person_check_vars.clear()

        # Create a checkbox for each person
        for name in names:
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(
                self.person_scroll,
                text=name,
                variable=var,
                font=ctk.CTkFont(size=12),
                height=28,
                corner_radius=4,
            )
            cb.pack(fill="x", padx=5, pady=2)
            self.person_check_vars[name] = var
            self.person_checkboxes.append(cb)

    def _set_checkboxes_state(self, state):
        """Enable or disable all person checkboxes."""
        for cb in self.person_checkboxes:
            cb.configure(state=state)

    def _get_selected_persons(self):
        """Return list of (name, person_id) for all checked persons."""
        selected = []
        for name, var in self.person_check_vars.items():
            if var.get():
                selected.append((name, self.person_map[name]))
        return selected

    def select_root(self):
        path = filedialog.askdirectory()
        if path:
            self.db.set_setting("root_path", path)
            self.root_path_var.set(path)
            self._show_welcome()
            self._set_status("Directory selected")

    # -- Rescan --
    def rescan(self):
        root_path = self.root_path_var.get()

        if not root_path:
            messagebox.showwarning("Warning", "Please select a root directory first.")
            return

        if not os.path.exists(root_path):
            messagebox.showerror(
                "Drive not found",
                f"The directory is not accessible:\n\n{root_path}\n\n"
                "Please check if the external drive is connected.",
            )
            return

        self._set_state(STATE_SCANNING)
        self._set_status("Scanning...")
        self.progress_bar.set(0)
        self.progress_detail.configure(text="Listing files...")
        self.progress_file.configure(text="")
        self._scan_start_time = time.time()
        self._scan_timestamps = []  # timestamps for ETA moving average

        def task():
            def progress(processed, total, errors, current_file):
                self._ui(lambda p=processed, t=total, e=errors, f=current_file:
                         self._update_progress(p, t, e, f))

            stats = self.scanner.scan(root_path, progress)

            def on_done():
                self._set_state(STATE_IDLE)
                self._refresh_stats()
                self._show_scan_summary(stats)

            self._ui(on_done)

        threading.Thread(target=task, daemon=True).start()

    def _update_progress(self, processed, total, errors, current_file):
        """Update the progress bar and details. Called on the main thread."""
        if total == 0:
            return

        pct = processed / total
        self.progress_bar.set(pct)

        now = time.time()
        self._scan_timestamps.append(now)

        # ETA with moving average (last 100 photos)
        window = 100
        if len(self._scan_timestamps) >= 2:
            ts = self._scan_timestamps[-window:]
            window_elapsed = ts[-1] - ts[0]
            window_count = len(ts) - 1
            per_item = window_elapsed / window_count
            remaining = per_item * (total - processed)
            eta = self._format_time(remaining)
        else:
            eta = "calculating..."

        err_text = f"  •  ⚠ {errors} errors" if errors else ""
        self.progress_detail.configure(
            text=f"{processed:,}/{total:,} photos  ({pct:.0%}){err_text}  •  Time remaining: {eta}"
        )

        # Show short name of current file
        short = os.path.basename(current_file) if current_file else ""
        self.progress_file.configure(text=short)

        self.progress_title.configure(text="Scanning photos...")
        self._set_status(f"Scanning {processed:,}/{total:,}")

    def _show_scan_summary(self, stats):
        """Show scan summary in the main area."""
        elapsed = time.time() - self._scan_start_time
        time_str = self._format_time(elapsed)

        self.output_header.configure(text="Scan Results")
        self.output_box.delete("1.0", "end")

        if stats.get("cancelled"):
            self.output_box.insert("end", "  ⚠ Scan cancelled by user.\n\n")
            self._set_status("Cancelled")
        else:
            self._set_status("Ready")

        self.output_box.insert("end", f"  Total time: {time_str}\n\n")
        self.output_box.insert("end", f"  📷 New photos processed:  {stats.get('new', 0)}\n")
        self.output_box.insert("end", f"  😀 Faces found:           {stats.get('faces_found', 0)} (in {stats.get('photos_with_faces', 0)} photos)\n")
        self.output_box.insert("end", f"  📦 Moved photos detected: {stats.get('moved', 0)}\n")
        self.output_box.insert("end", f"  🗑  Photos removed:        {stats.get('removed', 0)}\n")

        if stats.get("errors", 0) > 0:
            self.output_box.insert("end", f"  ⚠  Errors (photos skipped): {stats['errors']}\n")

    def _cancel_scan(self):
        self.scanner.cancel()
        self.progress_title.configure(text="Cancelling...")
        self.progress_detail.configure(text="Waiting for in-progress tasks to finish...")
        self.btn_cancel.configure(state="disabled")

    @staticmethod
    def _format_time(seconds):
        """Format seconds into a readable string (e.g. '1h 23m 45s')."""
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}s"
        minutes, secs = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}m {secs:02d}s"
        hours, mins = divmod(minutes, 60)
        return f"{hours}h {mins:02d}m {secs:02d}s"

    # -- Person Registration --
    def register_person(self):
        name = ctk.CTkInputDialog(text="Person's name:", title="Register Person").get_input()
        if not name or not name.strip():
            return

        name = name.strip()

        image_path = filedialog.askopenfilename(
            title="Select a photo with the person's face",
            filetypes=[("Images", "*.jpg *.jpeg *.png")],
        )
        if not image_path:
            return

        self._set_status("Detecting face...")

        embeddings = self.engine.extract_embeddings(image_path)
        if len(embeddings) == 0:
            messagebox.showerror("Error", "No face detected in the image.")
            self._set_status("Ready")
            return
        if len(embeddings) > 1:
            messagebox.showerror(
                "Error",
                f"{len(embeddings)} faces detected.\n"
                "The image must contain exactly 1 face.",
            )
            self._set_status("Ready")
            return

        try:
            self.db.add_person(name, embeddings[0])
        except Exception as e:
            if "UNIQUE" in str(e):
                messagebox.showerror("Error", f"A person named '{name}' already exists.")
            else:
                messagebox.showerror("Error", f"Registration error: {e}")
            self._set_status("Ready")
            return

        self._load_persons()
        self._refresh_stats()
        messagebox.showinfo("Success", f"Person '{name}' registered successfully!")
        self._set_status("Ready")

    # -- Search --
    def search(self):
        selected = self._get_selected_persons()
        if not selected:
            messagebox.showwarning("Warning", "Please select at least one person.")
            return

        self._set_state(STATE_SEARCHING)
        self._set_status("Searching...")

        # Build list of (name, person_id)
        search_persons = selected  # [(name, pid), ...]

        def task():
            # Load all embeddings once — shared across all person queries
            db_embeddings, paths = self.db.get_all_face_embeddings()

            if len(db_embeddings) == 0:
                def on_empty():
                    messagebox.showinfo("Info", "No photos indexed. Please run a scan first.")
                    self._set_state(STATE_IDLE)
                    self._set_status("Ready")
                self._ui(on_empty)
                return

            # For each person, find the set of matching photos
            per_person_photos = {}  # name -> {path: best_dist}

            for person_name, person_id in search_persons:
                query_embedding = self.db.get_person_embedding(person_id)

                if query_embedding is None:
                    def on_error(n=person_name):
                        messagebox.showerror("Error", f"Embedding not found for '{n}'.")
                        self._set_state(STATE_IDLE)
                        self._set_status("Ready")
                    self._ui(on_error)
                    return

                distances = self.engine.compare(query_embedding, db_embeddings)

                photo_best_dist = {}
                for i, d in enumerate(distances):
                    if d < FACE_DISTANCE_THRESHOLD:
                        path = paths[i]
                        if path not in photo_best_dist or d < photo_best_dist[path]:
                            photo_best_dist[path] = d

                per_person_photos[person_name] = photo_best_dist

            # Intersection: photos that match ALL selected persons
            photo_sets = [set(ppd.keys()) for ppd in per_person_photos.values()]
            common_photos = photo_sets[0]
            for s in photo_sets[1:]:
                common_photos &= s

            # For ranking, use the maximum (worst) best-distance across persons
            # so the "best" results are photos where every person is very close.
            combined_dist = {}
            for path in common_photos:
                worst = max(ppd[path] for ppd in per_person_photos.values())
                combined_dist[path] = worst

            results = sorted(common_photos, key=lambda p: combined_dist[p])

            # Build per-person distances for display
            per_person_result_dist = {}
            for person_name in per_person_photos:
                per_person_result_dist[person_name] = {
                    p: per_person_photos[person_name][p] for p in common_photos
                }

            names_label = " + ".join(n for n, _ in search_persons)

            def on_done():
                self._search_results = results
                self._search_distances = combined_dist
                self._search_person = names_label
                self._set_state(STATE_RESULTS)

                self.output_header.configure(
                    text=f"Results for '{names_label}' — {len(results)} photos found"
                )
                self.output_box.delete("1.0", "end")

                if results:
                    # Column header with person names
                    person_names = [n for n, _ in search_persons]
                    if len(person_names) > 1:
                        header_parts = [f"  {'  '.join(f'[{n[:8]:^8s}]' for n in person_names)}  Path"]
                        self.output_box.insert("end", header_parts[0] + "\n")
                        self.output_box.insert("end", "  " + "-" * 60 + "\n")

                    for path in results:
                        if len(person_names) > 1:
                            dists = "  ".join(
                                f"[{per_person_result_dist[n][path]:.3f}  ]"
                                for n in person_names
                            )
                            self.output_box.insert("end", f"  {dists}  {path}\n")
                        else:
                            dist = combined_dist[path]
                            self.output_box.insert("end", f"  [{dist:.3f}]  {path}\n")
                    self.btn_symlinks.pack(fill="x", pady=(10, 0))
                else:
                    if len(search_persons) > 1:
                        self.output_box.insert("end", "  No photos found with all selected persons together.\n")
                    else:
                        self.output_box.insert("end", "  No photos found for this person.\n")
                    self.btn_symlinks.pack_forget()

                self._set_status(f"Found {len(results)} photos")

            self._ui(on_done)

        threading.Thread(target=task, daemon=True).start()

    def _create_symlinks(self):
        """Create a folder with symbolic links for the search results."""
        if not hasattr(self, "_search_results") or not self._search_results:
            return

        name = self._search_person
        os.makedirs(RESULTS_DIR, exist_ok=True)
        target_dir = os.path.join(RESULTS_DIR, name)
        os.makedirs(target_dir, exist_ok=True)

        created = 0
        failed_count = 0
        for path in self._search_results:
            dist = self._search_distances.get(path, 0)
            base = os.path.basename(path)
            stem, ext = os.path.splitext(base)
            link_name = f"{dist:.3f}_{stem}{ext}"
            link_path = os.path.join(target_dir, link_name)

            # Resolve name collisions
            counter = 2
            while os.path.exists(link_path):
                link_name = f"{dist:.3f}_{stem}_{counter}{ext}"
                link_path = os.path.join(target_dir, link_name)
                counter += 1

            try:
                os.symlink(path, link_path)
                created += 1
            except OSError as e:
                failed_count += 1
                # If this is Windows and error 1314 (Privilege not held)
                if hasattr(e, "winerror") and e.winerror == 1314:
                    messagebox.showerror(
                        "Permission Error",
                        "Windows requires Developer Mode or Administrator privileges to create symbolic links.\n\n"
                        "Please enable Developer Mode in Windows Settings to use this feature."
                    )
                    return

        if created > 0:
            messagebox.showinfo(
                "Done",
                f"Created {created} links in:\n{os.path.abspath(target_dir)}",
            )
        elif failed_count > 0:
            messagebox.showwarning("Warning", f"Failed to create {failed_count} links. Check permissions.")


if __name__ == "__main__":
    app = App()
    app.mainloop()
