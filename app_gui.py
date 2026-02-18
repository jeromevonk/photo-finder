import os
import time
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from database import Database
from scanner import PhotoScanner
from face_engine import FaceEngine
from config import FACE_DISTANCE_THRESHOLD, RESULTS_DIR

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Estados da UI ──────────────────────────────────────────────────────
STATE_IDLE = "idle"
STATE_SCANNING = "scanning"
STATE_RESULTS = "results"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FaceVault")
        self.geometry("1100x700")
        self.minsize(900, 550)

        self.db = Database()
        self.engine = FaceEngine()
        self.scanner = PhotoScanner(self.db)
        self._state = STATE_IDLE

        self._build_ui()
        self._load_root_path()
        self._load_persons()
        self._refresh_stats()

    # ══════════════════════════════════════════════════════════════════
    #  CONSTRUÇÃO DA UI
    # ══════════════════════════════════════════════════════════════════
    def _build_ui(self):
        # ── Topbar ─────────────────────────────────────────────────────
        self.topbar = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.topbar.pack(side="top", fill="x")
        self.topbar.pack_propagate(False)

        app_label = ctk.CTkLabel(
            self.topbar,
            text="🔒 FaceVault",
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
            text="Pronto",
            font=ctk.CTkFont(size=12),
            text_color="#888888",
        )
        self.status_label.pack(side="right", padx=15)

        # ── Container principal ───────────────────────────────────────
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(side="top", expand=True, fill="both", padx=10, pady=(5, 10))

        # ── Sidebar ───────────────────────────────────────────────────
        self.sidebar = ctk.CTkFrame(container, width=260, corner_radius=10)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.sidebar.pack_propagate(False)

        # Seção: Diretório Raiz
        ctk.CTkLabel(
            self.sidebar,
            text="📂 DIRETÓRIO RAIZ",
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
            self.sidebar, text="Selecionar Pasta", command=self.select_root, height=32
        )
        self.btn_select.pack(fill="x", padx=15, pady=2)

        self.btn_rescan = ctk.CTkButton(
            self.sidebar, text="⟳  Reescanear", command=self.rescan, height=32
        )
        self.btn_rescan.pack(fill="x", padx=15, pady=2)

        self.btn_cancel = ctk.CTkButton(
            self.sidebar,
            text="✕  Cancelar",
            command=self._cancel_scan,
            height=32,
            fg_color="#8B0000",
            hover_color="#B22222",
        )
        # Não faz pack ainda — só aparece durante scan

        # Separador
        sep1 = ctk.CTkFrame(self.sidebar, height=2, fg_color="#333333")
        sep1.pack(fill="x", padx=15, pady=12)

        # Seção: Pessoas
        ctk.CTkLabel(
            self.sidebar,
            text="👤 PESSOAS",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=15, pady=(0, 5))

        self.person_var = ctk.StringVar()
        self.person_dropdown = ctk.CTkOptionMenu(
            self.sidebar, variable=self.person_var, height=32
        )
        self.person_dropdown.pack(fill="x", padx=15, pady=(0, 5))

        self.btn_search = ctk.CTkButton(
            self.sidebar,
            text="🔍  Procurar",
            command=self.search,
            height=32,
            fg_color="#1B5E20",
            hover_color="#2E7D32",
        )
        self.btn_search.pack(fill="x", padx=15, pady=2)

        self.btn_register = ctk.CTkButton(
            self.sidebar, text="＋  Cadastrar Pessoa", command=self.register_person, height=32
        )
        self.btn_register.pack(fill="x", padx=15, pady=2)

        # Separador
        sep2 = ctk.CTkFrame(self.sidebar, height=2, fg_color="#333333")
        sep2.pack(fill="x", padx=15, pady=12)

        # Info na sidebar
        self.sidebar_info = ctk.CTkLabel(
            self.sidebar,
            text="100% Offline\nPrivacidade total",
            font=ctk.CTkFont(size=11),
            text_color="#666666",
            justify="center",
        )
        self.sidebar_info.pack(side="bottom", pady=15)

        # ── Área principal ────────────────────────────────────────────
        self.main = ctk.CTkFrame(container, corner_radius=10)
        self.main.pack(side="right", expand=True, fill="both")

        # Área de progresso (visível durante scan)
        self.progress_frame = ctk.CTkFrame(self.main, fg_color="transparent")

        self.progress_title = ctk.CTkLabel(
            self.progress_frame,
            text="Escaneando fotos...",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.progress_title.pack(pady=(20, 10))

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, width=400, height=16)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=5)

        self.progress_detail = ctk.CTkLabel(
            self.progress_frame,
            text="Preparando...",
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

        # Área de output/resultados
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

        # Botão de links simbólicos (escondido por padrão)
        self.btn_symlinks = ctk.CTkButton(
            self.output_frame,
            text="📁  Criar pasta com links simbólicos",
            command=self._create_symlinks,
            height=32,
            fg_color="#1565C0",
            hover_color="#1976D2",
        )

        # Estado inicial
        self._show_welcome()

    # ══════════════════════════════════════════════════════════════════
    #  HELPERS DE UI (thread-safe)
    # ══════════════════════════════════════════════════════════════════
    def _ui(self, fn):
        """Agenda execução de fn na main thread. Seguro para chamar de qualquer thread."""
        self.after(0, fn)

    def _set_status(self, text):
        self._ui(lambda: self.status_label.configure(text=text))

    def _refresh_stats(self):
        photos = self.db.get_photo_count()
        persons = self.db.get_person_count()
        self.stats_label.configure(text=f"📷 {photos:,} fotos  •  👤 {persons} pessoas")

    def _show_welcome(self):
        """Mostra tela inicial quando nenhuma ação está em andamento."""
        root = self.root_path_var.get()
        self.output_header.configure(text="")
        self.output_box.delete("1.0", "end")

        if not root:
            self.output_box.insert("end", "  Bem-vindo ao FaceVault!\n\n")
            self.output_box.insert("end", "  ← Selecione um diretório raiz para começar.\n")
        else:
            self.output_box.insert("end", f"  Diretório raiz: {root}\n\n")
            self.output_box.insert("end", "  Use os botões à esquerda para:\n")
            self.output_box.insert("end", "    • Reescanear fotos novas\n")
            self.output_box.insert("end", "    • Cadastrar uma pessoa\n")
            self.output_box.insert("end", "    • Procurar uma pessoa nas fotos\n")

    def _set_state(self, state):
        """Gerencia habilitação/desabilitação de botões conforme o estado."""
        self._state = state

        if state == STATE_SCANNING:
            self.btn_select.configure(state="disabled")
            self.btn_rescan.configure(state="disabled")
            self.btn_search.configure(state="disabled")
            self.btn_register.configure(state="disabled")
            self.person_dropdown.configure(state="disabled")
            # Mostrar botão cancelar
            self.btn_rescan.pack_forget()
            self.btn_cancel.pack(fill="x", padx=15, pady=2, after=self.btn_select)
            # Mostrar progresso, esconder output
            self.output_frame.pack_forget()
            self.progress_frame.pack(expand=True, fill="both", padx=10, pady=10)
        else:
            self.btn_select.configure(state="normal")
            self.btn_rescan.configure(state="normal")
            self.btn_search.configure(state="normal")
            self.btn_register.configure(state="normal")
            self.person_dropdown.configure(state="normal")
            # Esconder cancelar, mostrar rescan
            self.btn_cancel.pack_forget()
            self.btn_rescan.pack(fill="x", padx=15, pady=2, after=self.btn_select)
            # Esconder progresso, mostrar output
            self.progress_frame.pack_forget()
            self.output_frame.pack(expand=True, fill="both", padx=10, pady=10)

    # ══════════════════════════════════════════════════════════════════
    #  AÇÕES
    # ══════════════════════════════════════════════════════════════════
    def _load_root_path(self):
        path = self.db.get_setting("root_path")
        if path:
            self.root_path_var.set(path)

    def _load_persons(self):
        persons = self.db.get_persons()
        self.person_map = {name: pid for pid, name in persons}
        names = list(self.person_map.keys())
        self.person_dropdown.configure(values=names)
        if names:
            self.person_var.set(names[0])
        else:
            self.person_var.set("")

    def select_root(self):
        path = filedialog.askdirectory()
        if path:
            self.db.set_setting("root_path", path)
            self.root_path_var.set(path)
            self._show_welcome()
            self._set_status("Diretório selecionado")

    # ── Reescaneamento ────────────────────────────────────────────────
    def rescan(self):
        root_path = self.root_path_var.get()

        if not root_path:
            messagebox.showwarning("Aviso", "Selecione um diretório raiz primeiro.")
            return

        if not os.path.exists(root_path):
            messagebox.showerror(
                "HD não encontrado",
                f"O diretório não está acessível:\n\n{root_path}\n\n"
                "Verifique se o HD externo está conectado.",
            )
            return

        self._set_state(STATE_SCANNING)
        self._set_status("Escaneando...")
        self.progress_bar.set(0)
        self.progress_detail.configure(text="Listando arquivos...")
        self.progress_file.configure(text="")
        self._scan_start_time = time.time()
        self._scan_timestamps = []  # timestamps para média móvel do ETA

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
        """Atualiza a barra de progresso e detalhes. Chamado na main thread."""
        if total == 0:
            return

        pct = processed / total
        self.progress_bar.set(pct)

        now = time.time()
        self._scan_timestamps.append(now)

        # ETA com média móvel (últimas 100 fotos)
        window = 100
        if len(self._scan_timestamps) >= 2:
            ts = self._scan_timestamps[-window:]
            window_elapsed = ts[-1] - ts[0]
            window_count = len(ts) - 1
            per_item = window_elapsed / window_count
            remaining = per_item * (total - processed)
            eta = self._format_time(remaining)
        else:
            eta = "calculando..."

        err_text = f"  •  ⚠ {errors} erros" if errors else ""
        self.progress_detail.configure(
            text=f"{processed:,}/{total:,} fotos  ({pct:.0%}){err_text}  •  Tempo restante: {eta}"
        )

        # Mostrar nome curto do arquivo atual
        short = os.path.basename(current_file) if current_file else ""
        self.progress_file.configure(text=short)

        self.progress_title.configure(text="Escaneando fotos...")
        self._set_status(f"Escaneando {processed:,}/{total:,}")

    def _show_scan_summary(self, stats):
        """Mostra resumo do scan na área principal."""
        elapsed = time.time() - self._scan_start_time
        time_str = self._format_time(elapsed)

        self.output_header.configure(text="Resultado do escaneamento")
        self.output_box.delete("1.0", "end")

        if stats.get("cancelled"):
            self.output_box.insert("end", "  ⚠ Escaneamento cancelado pelo usuário.\n\n")
            self._set_status("Cancelado")
        else:
            self._set_status("Pronto")

        self.output_box.insert("end", f"  Tempo total: {time_str}\n\n")
        self.output_box.insert("end", f"  📷 Fotos novas processadas:  {stats.get('new', 0)}\n")
        self.output_box.insert("end", f"  😀 Faces encontradas:        {stats.get('faces_found', 0)} (em {stats.get('photos_with_faces', 0)} fotos)\n")
        self.output_box.insert("end", f"  📦 Fotos movidas detectadas: {stats.get('moved', 0)}\n")
        self.output_box.insert("end", f"  🗑  Fotos removidas:          {stats.get('removed', 0)}\n")

        if stats.get("errors", 0) > 0:
            self.output_box.insert("end", f"  ⚠  Erros (fotos ignoradas):  {stats['errors']}\n")

    def _cancel_scan(self):
        self.scanner.cancel()
        self.progress_title.configure(text="Cancelando...")
        self.progress_detail.configure(text="Aguardando tarefas em andamento finalizarem...")
        self.btn_cancel.configure(state="disabled")

    @staticmethod
    def _format_time(seconds):
        """Formata segundos em string legível (ex: '1h 23m 45s')."""
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}s"
        minutes, secs = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}m {secs:02d}s"
        hours, mins = divmod(minutes, 60)
        return f"{hours}h {mins:02d}m {secs:02d}s"

    # ── Cadastro de Pessoa ────────────────────────────────────────────
    def register_person(self):
        name = ctk.CTkInputDialog(text="Nome da pessoa:", title="Cadastrar Pessoa").get_input()
        if not name or not name.strip():
            return

        name = name.strip()

        image_path = filedialog.askopenfilename(
            title="Selecione uma foto com o rosto da pessoa",
            filetypes=[("Imagens", "*.jpg *.jpeg *.png")],
        )
        if not image_path:
            return

        self._set_status("Detectando rosto...")

        embeddings = self.engine.extract_embeddings(image_path)
        if len(embeddings) == 0:
            messagebox.showerror("Erro", "Nenhum rosto detectado na imagem.")
            self._set_status("Pronto")
            return
        if len(embeddings) > 1:
            messagebox.showerror(
                "Erro",
                f"Detectados {len(embeddings)} rostos.\n"
                "A imagem deve conter exatamente 1 rosto.",
            )
            self._set_status("Pronto")
            return

        try:
            self.db.add_person(name, embeddings[0])
        except Exception as e:
            if "UNIQUE" in str(e):
                messagebox.showerror("Erro", f"Já existe uma pessoa com o nome '{name}'.")
            else:
                messagebox.showerror("Erro", f"Erro ao cadastrar: {e}")
            self._set_status("Pronto")
            return

        self._load_persons()
        self._refresh_stats()
        messagebox.showinfo("Sucesso", f"Pessoa '{name}' cadastrada com sucesso!")
        self._set_status("Pronto")

    # ── Busca ─────────────────────────────────────────────────────────
    def search(self):
        name = self.person_var.get()
        if not name or name not in self.person_map:
            messagebox.showwarning("Aviso", "Selecione uma pessoa no dropdown.")
            return

        self._set_status("Buscando...")

        person_id = self.person_map[name]
        query_embedding = self.db.get_person_embedding(person_id)

        if query_embedding is None:
            messagebox.showerror("Erro", "Embedding da pessoa não encontrado.")
            self._set_status("Pronto")
            return

        db_embeddings, paths = self.db.get_all_face_embeddings()

        if len(db_embeddings) == 0:
            messagebox.showinfo("Info", "Nenhuma foto indexada. Faça um escaneamento primeiro.")
            self._set_status("Pronto")
            return

        distances = self.engine.compare(query_embedding, db_embeddings)

        # Coletar resultados únicos, guardando a menor distância por foto
        photo_best_dist = {}
        for i, d in enumerate(distances):
            if d < FACE_DISTANCE_THRESHOLD:
                path = paths[i]
                if path not in photo_best_dist or d < photo_best_dist[path]:
                    photo_best_dist[path] = d

        # Ordenar por proximidade (menor distância = mais parecido)
        self._search_results = sorted(photo_best_dist.keys(), key=lambda p: photo_best_dist[p])

        self._search_person = name
        self._set_state(STATE_RESULTS)

        self.output_header.configure(
            text=f"Resultados para '{name}' — {len(self._search_results)} fotos encontradas"
        )
        self.output_box.delete("1.0", "end")

        if self._search_results:
            for path in self._search_results:
                self.output_box.insert("end", path + "\n")
            self.btn_symlinks.pack(fill="x", pady=(10, 0))
        else:
            self.output_box.insert("end", "  Nenhuma foto encontrada para esta pessoa.\n")
            self.btn_symlinks.pack_forget()

        self._set_status(f"Encontradas {len(self._search_results)} fotos")

    def _create_symlinks(self):
        """Cria pasta com links simbólicos para os resultados da busca."""
        if not hasattr(self, "_search_results") or not self._search_results:
            return

        name = self._search_person
        os.makedirs(RESULTS_DIR, exist_ok=True)
        target_dir = os.path.join(RESULTS_DIR, name)
        os.makedirs(target_dir, exist_ok=True)

        created = 0
        for path in self._search_results:
            link_path = os.path.join(target_dir, os.path.basename(path))
            if not os.path.exists(link_path):
                try:
                    os.symlink(path, link_path)
                    created += 1
                except OSError:
                    pass

        messagebox.showinfo(
            "Pronto",
            f"Criados {created} links em:\n{os.path.abspath(target_dir)}",
        )


if __name__ == "__main__":
    app = App()
    app.mainloop()
