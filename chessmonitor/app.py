import os, tkinter as tk, threading, time
from tkinter import ttk, filedialog, simpledialog
from PIL import ImageTk, ImageDraw
import chess
from .capture import LiveCapture
from .engine import UCIEngine
from .coach import PERSONALITIES, choose_candidate, report, explain_move
from .overlay import ArrowOverlay, _exclude_from_capture
from .vision import BoardVision, SYMBOLS
from .tracker import expected_labels, board_from_scores, best_transition, guess_castling
from .maia import Maia3
from .locator import locate_chessboard

BASE = os.path.dirname(os.path.dirname(__file__))

class App:
    BG = '#090d14'; FG = '#edf3fc'; AMBER = '#f5c56b'
    SCAN_EVERY = 0.3

    def __init__(self, root):
        self.root = root; root.title('ChessMaster')
        root.geometry('430x600'); root.minsize(400, 440); root.configure(bg=self.BG)
        try: root.attributes('-topmost', True)
        except Exception: pass
        self.board = chess.Board(); self.position_confirmed = False
        self.capture = LiveCapture(interval=.2); self.preview_img = None
        self.window_items = []; self.window_choice = tk.StringVar(value='')
        self.overlay = ArrowOverlay(root); self.chosen = None; self.candidates = []
        self.personality = tk.StringVar(value='Jester')
        self.overlay_position = tk.StringVar(value='bottom')
        self.auto_coach = tk.BooleanVar(value=True)
        self.maia_model = tk.StringVar(value='maia3-5m')
        self.maia_elo = tk.IntVar(value=1500)
        self.stock_path = tk.StringVar(value=os.path.join(BASE, 'engines', 'stockfish.exe'))
        self.grid_debug = tk.BooleanVar(value=False)
        self.show_preview = tk.BooleanVar(value=False)
        self.show_settings = tk.BooleanVar(value=False)
        self.calibration = tk.BooleanVar(value=False)
        self.vision = BoardVision(os.path.join(BASE, 'vision_templates.npz'))
        self.engine = UCIEngine(self.stock_path.get()); self.maia = Maia3()
        self.board_rect = None; self.player_orientation = None; self.last_scan = 0
        self._busy = False; self._scanning = False; self._lost = 0; self._sync_n = 0; self._miss_n = 0
        self._pending_key = None; self._pending_n = 0; self._turn_unsure = False; self._analysed_fen = None
        self._vision_lock = threading.Lock(); self._calibrated_for_start = False; self._opening_gap = 0
        self._style(); self._ui(); self._start_automatic_monitor()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(500, lambda: _exclude_from_capture(root))
        root.after(250, self._tick)

    def _style(self):
        s = ttk.Style()
        try: s.theme_use('clam')
        except Exception: pass
        s.configure('.', background=self.BG, foreground=self.FG, font=('Segoe UI', 9))
        s.configure('TFrame', background=self.BG)
        s.configure('Panel.TFrame', background='#111722')
        s.configure('TLabel', background=self.BG, foreground=self.FG)
        s.configure('Muted.TLabel', background='#111722', foreground='#8492a6', font=('Segoe UI', 8))
        s.configure('Section.TLabel', background='#111722', foreground='#cbd5e1', font=('Segoe UI', 9, 'bold'))
        s.configure('TButton', background='#1b2533', foreground='#e7edf5', borderwidth=0, padding=(8, 5), font=('Segoe UI', 9))
        s.map('TButton', background=[('active', '#29374a')], foreground=[('active', '#ffffff')])
        s.configure('Accent.TButton', background='#d9e7e1', foreground='#102019', font=('Segoe UI', 9, 'bold'))
        s.map('Accent.TButton', background=[('active', '#eff8f3')])
        s.configure('TEntry', fieldbackground='#0c121c', foreground=self.FG, insertcolor=self.FG, bordercolor='#273244', padding=4)
        s.configure('TCombobox', fieldbackground='#0c121c', foreground=self.FG, background='#1b2533', arrowcolor='#dce5ef', padding=4)
        s.map('TCombobox', fieldbackground=[('readonly', '#0c121c')], foreground=[('readonly', self.FG)])
        s.configure('TCheckbutton', background='#111722', foreground='#cbd5e1')
        s.map('TCheckbutton', background=[('active', '#111722')])

    def card(self, p):
        return ttk.Frame(p, style='Panel.TFrame', padding=10)

    def _ui(self):
        P = 'Panel.TFrame'
        top = ttk.Frame(self.root, padding=(12, 10, 12, 2)); top.pack(fill='x')
        ttk.Label(top, text='CHESSMASTER', foreground='#c5e4d7', font=('Segoe UI', 10, 'bold')).pack(side='left')
        self.live_label = ttk.Label(top, text='\u25cf  MONITORING', foreground='#b6d9c8', font=('Segoe UI', 8))
        self.live_label.pack(side='right')
        bar = ttk.Frame(self.root, padding=(12, 2, 12, 2)); bar.pack(fill='x')
        self.window_combo = ttk.Combobox(bar, textvariable=self.window_choice, state='readonly', width=26)
        self.window_combo.pack(side='left', fill='x', expand=True)
        ttk.Button(bar, text='\u21bb', width=3, command=self.refresh_windows).pack(side='left', padx=(4, 0))
        ttk.Button(bar, text='Use', width=5, command=self.select_window).pack(side='left', padx=(4, 0))

        body = ttk.Frame(self.root, padding=(12, 6, 12, 10)); body.pack(fill='both', expand=True)
        self.monitor = self.card(body)
        self.preview = tk.Label(self.monitor, bg='#080c13', fg='#758397', text='Waiting for first display', bd=0)
        self.preview.pack(fill='both', expand=True)
        self.preview.bind('<Button-1>', self.preview_click)

        self.coach_card = coach = self.card(body); coach.pack(fill='x')
        row = ttk.Frame(coach, style=P); row.pack(fill='x')
        self.side_value = ttk.Label(row, text='You \u00b7 bottom (detecting colour)', foreground='#d9e7e1', background='#111722')
        self.side_value.pack(side='left')
        ttk.Button(row, text='Analyse', style='Accent.TButton', command=self.analyse_async).pack(side='right')
        ttk.Button(row, text='Calibrate', command=self.recalibrate_now).pack(side='right', padx=(0, 6))
        self.detect_label = ttk.Label(coach, text='Looking for a board', style='Muted.TLabel'); self.detect_label.pack(anchor='w', pady=(4, 0))
        self.debug_label = ttk.Label(coach, text='Scanner: starting', style='Muted.TLabel', wraplength=380, justify='left'); self.debug_label.pack(anchor='w', pady=(2, 0))
        self.toggles = ttk.Frame(coach, style=P); self.toggles.pack(fill='x', pady=(6, 0))
        ttk.Checkbutton(self.toggles, text='Auto coach', variable=self.auto_coach).pack(side='left')
        ttk.Checkbutton(self.toggles, text='Preview', variable=self.show_preview, command=self._resize).pack(side='left', padx=10)
        ttk.Checkbutton(self.toggles, text='Settings', variable=self.show_settings, command=self._resize).pack(side='left')

        self.settings = ttk.Frame(coach, style=P)
        r1 = ttk.Frame(self.settings, style=P); r1.pack(fill='x', pady=(0, 6))
        ttk.Label(r1, text='STYLE', style='Muted.TLabel').pack(side='left')
        ttk.Combobox(r1, textvariable=self.personality, values=list(PERSONALITIES), state='readonly', width=11).pack(side='left', padx=6)
        ttk.Label(r1, text='TEXT', style='Muted.TLabel').pack(side='left')
        self.overlay_button = ttk.Button(r1, text='Bottom', width=7, command=self.toggle_overlay_position)
        self.overlay_button.pack(side='left', padx=6)
        r2 = ttk.Frame(self.settings, style=P); r2.pack(fill='x', pady=(0, 6))
        ttk.Label(r2, text='MAIA', style='Muted.TLabel').pack(side='left')
        ttk.Combobox(r2, textvariable=self.maia_model, values=['maia3-5m', 'maia3-23m', 'maia3-79m'], width=10, state='readonly').pack(side='left', padx=6)
        ttk.Label(r2, text='ELO', style='Muted.TLabel').pack(side='left')
        ttk.Spinbox(r2, from_=1100, to=2500, increment=100, textvariable=self.maia_elo, width=5).pack(side='left', padx=6)
        ttk.Label(r2, text='PIECES', style='Muted.TLabel').pack(side='left')
        self.recognition_value = ttk.Label(r2, text=str(len(self.vision.templates)) + '/14', foreground='#d9e7e1', background='#111722')
        self.recognition_value.pack(side='left', padx=6)
        r3 = ttk.Frame(self.settings, style=P); r3.pack(fill='x', pady=(0, 6))
        ttk.Checkbutton(r3, text='Label squares', variable=self.calibration, command=self._on_calibration_toggle).pack(side='left')
        ttk.Checkbutton(r3, text='Show grid', variable=self.grid_debug).pack(side='left', padx=10)
        r4 = ttk.Frame(self.settings, style=P); r4.pack(fill='x')
        ttk.Label(r4, text='STOCKFISH', style='Muted.TLabel').pack(side='left')
        ttk.Entry(r4, textvariable=self.stock_path).pack(side='left', fill='x', expand=True, padx=6)
        ttk.Button(r4, text='...', width=3, command=self.browse_engine).pack(side='left')

        self.status = ttk.Label(body, text='Starting monitor...', foreground='#b6d9c8', background=self.BG, font=('Segoe UI', 8), anchor='w', wraplength=390)
        self.status.pack(fill='x', pady=(8, 6))
        result = self.card(body); result.pack(fill='both', expand=True)
        rhead = ttk.Frame(result, style=P); rhead.pack(fill='x')
        ttk.Label(rhead, text='RECOMMENDATION', style='Section.TLabel').pack(side='left')
        self.eval_label = ttk.Label(rhead, text='-', foreground='#c5e4d7', background='#111722', font=('Segoe UI', 12))
        self.eval_label.pack(side='right')
        self.output = tk.Text(result, bg='#0c121c', fg='#e6edf6', insertbackground='#e6edf6', relief='flat', bd=0,
                              font=('Segoe UI', 9), wrap='word', padx=10, pady=10, height=6, selectbackground='#314257')
        self.output.pack(fill='both', expand=True, pady=(8, 0))
        self.output.insert('end', 'Ready. Open your chess game, pick its window above and press Use. ChessMaster follows the game on its own, and suggests a move whenever it is your turn.')
        self.output.configure(state='disabled')

    def _dbg(self, text):
        self.root.after(0, lambda t=text: self.debug_label.configure(text='Scanner: ' + t))

    def _resize(self):
        if self.show_preview.get(): self.monitor.pack(fill='x', pady=(0, 8), before=self.coach_card)
        else: self.monitor.pack_forget()
        if self.show_settings.get(): self.settings.pack(fill='x', pady=(8, 0), after=self.toggles)
        else: self.settings.pack_forget()
        h = 600 + (200 if self.show_settings.get() else 0) + (240 if self.show_preview.get() else 0)
        self.root.geometry('430x' + str(h))

    def refresh_windows(self):
        self.window_items = self.capture.list_windows()
        labels = [x[0] for x in self.window_items]
        self.window_combo['values'] = labels
        if labels and (self.window_combo.current() < 0):
            idx = next((i for i, x in enumerate(self.window_items) if any(k in x[1].lower() for k in ('chess', 'lichess', 'chess.com', 'roblox'))), 0)
            self.window_combo.current(idx)
        self.status.configure(text=str(len(labels)) + ' visible windows found - choose your chess game')
    def select_window(self):
        idx = self.window_combo.current()
        if idx < 0 or idx >= len(self.window_items):
            self.status.configure(text='Select a game window first'); return
        _, title, hwnd = self.window_items[idx]
        self.capture.stop(); self.capture.set_target(title, hwnd)
        self.capture.latest = None; self.board_rect = None; self.position_confirmed = False
        self.board = chess.Board(); self.player_orientation = None; self._turn_unsure = False
        self._pending_key = None; self._pending_n = 0; self._sync_n = 0; self._miss_n = 0
        self.overlay.hide()
        with self._vision_lock:
            self._calibrated_for_start = False; self._opening_gap = 0
        self.side_value.configure(text='You \u00b7 bottom (detecting colour)')
        self.capture.start()
        self.live_label.configure(text='\u25cf  WINDOW LOCKED', foreground='#b6d9c8')
        self.status.configure(text='Monitoring: ' + title)
    def _start_automatic_monitor(self):
        self.refresh_windows()
        if self.window_items: self.select_window()
        else:
            self.live_label.configure(text='\u25cf  NO WINDOW', foreground=self.AMBER)
            self.status.configure(text='No visible application windows found - press the refresh button')
    def _side_text(self, orient):
        return 'You \u00b7 White (bottom)' if orient == 'white' else 'You \u00b7 Black (bottom)'
    def _refresh_recognition_label(self):
        self.recognition_value.configure(text=str(len(self.vision.templates)) + '/14')
    def _player_colour(self, orient):
        return chess.WHITE if orient == 'white' else chess.BLACK

    def recalibrate_now(self):
        if not self.capture or not self.capture.latest or not self.board_rect:
            with self._vision_lock: self._calibrated_for_start = False
            self.status.configure(text='Board not visible yet - calibration runs as soon as it appears'); return
        x, y, w, h, _ = self.board_rect
        crop = self.capture.latest.crop((x, y, x + w, y + h))
        guessed = self.vision.infer_bottom_orientation(crop)
        orient = guessed or 'white'
        ok, msg = self.vision.auto_calibrate_start_position(crop, orient)
        if not ok:
            self.status.configure(text=msg); return
        with self._vision_lock: self._calibrated_for_start = True
        self._board_found(self.board_rect, orient)
        self._accept_initial_position(orient, None, 'assuming White' if guessed is None else None)
    def _on_calibration_toggle(self):
        if self.calibration.get() and (not self.capture or not self.capture.latest):
            self.calibration.set(False)
            self.status.configure(text='Waiting for the game window before labelling squares'); return
        if self.calibration.get():
            self.show_preview.set(True); self._resize()
            self.status.configure(text='Click a square in the preview, then type P N B R Q K, lowercase for Black, or .')
        else:
            self.status.configure(text='Square labelling off')
    def preview_click(self, event):
        if not self.calibration.get() or not self.capture or not self.capture.latest or not self.board_rect or self.preview_img is None: return
        sw = max(1, self.preview_img.width()); sh = max(1, self.preview_img.height())
        x, y, w, h, _ = self.board_rect
        col = min(7, max(0, int(event.x / sw * 8))); row = min(7, max(0, int(event.y / sh * 8)))
        symbol = simpledialog.askstring('Piece label', 'Enter P N B R Q K, lowercase for Black, or . for empty:')
        if symbol is None: return
        symbol = symbol.strip()
        if symbol not in SYMBOLS and symbol != '.': return
        crop = self.capture.latest.crop((x, y, x + w, y + h))
        self.vision.add_sample(crop, col, row, symbol)
        self._refresh_recognition_label()
        self.status.configure(text='Recognition sample saved - ' + str(len(self.vision.templates)) + '/14 classes')

    def _tick(self):
        if self.capture and self.capture.latest:
            frame = self.capture.latest
            if self.show_preview.get():
                try:
                    if self.board_rect:
                        bx, by, bw, bh, _ = self.board_rect
                        im = frame.crop((bx, by, bx + bw, by + bh))
                        if self.grid_debug.get():
                            draw = ImageDraw.Draw(im)
                            for n in range(1, 8):
                                xx = round(bw * n / 8); yy = round(bh * n / 8)
                                draw.line((xx, 0, xx, bh), fill=(244, 194, 75), width=2)
                                draw.line((0, yy, bw, yy), fill=(244, 194, 75), width=2)
                    else:
                        im = frame.copy()
                    im.thumbnail((390, 390))
                    self.preview_img = ImageTk.PhotoImage(im); self.preview.configure(image=self.preview_img, text='')
                except Exception: pass
            if time.time() - self.last_scan > self.SCAN_EVERY and not self._scanning:
                self.last_scan = time.time(); self._scanning = True
                threading.Thread(target=self._vision_worker, args=(frame.copy(),), daemon=True).start()
            if self.capture.error: self.status.configure(text='Capture error: ' + self.capture.error)
        else:
            self._dbg('Stage 0: no frames captured yet - pick the game window and press Use')
        self.root.after(150, self._tick)

    def _vision_worker(self, frame):
        try: self._scan(frame)
        except Exception as e:
            self._dbg('ERROR ' + type(e).__name__ + ': ' + str(e))
        finally: self._scanning = False

    def _resync_ok(self, d):
        cur = self.board.piece_map(); new = d.piece_map()
        drop = len(cur) - len(new)
        if drop < 0 or drop > 2: return False
        for colour in (chess.WHITE, chess.BLACK):
            if sum(1 for p in new.values() if p.color == colour) > sum(1 for p in cur.values() if p.color == colour): return False
        return True

    def _scan(self, frame):
        loc = locate_chessboard(frame)
        if not loc:
            with self._vision_lock:
                self._opening_gap += 1
                if self._opening_gap >= 3: self._calibrated_for_start = False
            self._lost += 1
            self._dbg('Stage 1: no board found in the captured window (' + str(self._lost) + ')')
            if self._lost >= 3: self.root.after(0, self._board_lost)
            return
        self._lost = 0
        x, y, w, h, _ = loc; rect = loc
        crop = frame.crop((x, y, x + w, y + h))
        guessed = self.vision.infer_bottom_orientation(crop)
        startish = self.vision.looks_like_start_position(crop)
        with self._vision_lock:
            if startish: self._opening_gap = 0
            else:
                self._opening_gap += 1
                if self._opening_gap >= 3: self._calibrated_for_start = False
            should_cal = startish and not self._calibrated_for_start and guessed is not None and not self.vision.ready()
            if should_cal: self._calibrated_for_start = True
        if should_cal:
            ok, msg = self.vision.auto_calibrate_start_position(crop, guessed)
            if not ok:
                with self._vision_lock: self._calibrated_for_start = False
                self.root.after(0, lambda r=rect, o=guessed: self._board_found(r, o)); return
            self.root.after(0, lambda r=rect, o=guessed: self._finish_autocalibration(r, o)); return
        orient = self.player_orientation if (self.position_confirmed and self.player_orientation) else guessed
        self.root.after(0, lambda r=rect, o=orient: self._board_found(r, o))
        if not self.vision.ready():
            self._dbg('Stage 2: only ' + str(len(self.vision.templates)) + '/14 piece templates. Press Calibrate on a fresh start-position board, or use Label squares.')
            return
        if orient is None:
            self._dbg('Stage 2: cannot tell which colour is at the bottom of the board')
            return
        res = self.vision.square_scores(crop)
        if res is None:
            self._dbg('Stage 3: board crop too small'); return
        labels, S = res
        conf = float(S.reshape(64, -1).max(axis=1).mean())
        detected = board_from_scores(S, labels, orient)
        n = len(detected.piece_map())
        info = 'match ' + format(conf, '.2f') + ', ' + str(n) + ' pieces seen'
        if conf < 0.4:
            self._dbg('Stage 3: poor ' + info + '. The board looks unlike the templates (new theme?). Press Calibrate on a start position.'); return
        if detected.piece_map() == chess.Board().piece_map():
            self._pending_key = None; self._pending_n = 0; self._miss_n = 0
            self._dbg('Start position seen - ' + info)
            self.root.after(0, lambda o=orient, s=conf: self._accept_initial_position(o, s)); return
        if not self.position_confirmed:
            self._sync_n += 1
            self._dbg('Stage 4: reading the position - ' + info + ' (' + str(self._sync_n) + '/2)')
            if self._sync_n >= 2 and conf >= 0.6:
                self.root.after(0, lambda b=detected, o=orient, c=conf: self._sync_from_screen(b, o, c))
            return
        self._sync_n = 0
        if detected.board_fen() == self.board.board_fen():
            self._pending_key = None; self._pending_n = 0; self._miss_n = 0
            self._dbg('Tracking live - in sync - ' + info)
            return
        with self._vision_lock: board = self.board.copy(stack=False)
        opts = [board]
        if self._turn_unsure:
            alt = board.copy(stack=False); alt.turn = not board.turn; opts.append(alt)
        best = None
        for b in opts:
            r = best_transition(b, S, labels, orient)
            if r and (best is None or r[1] > best[1][1]): best = (b, r)
        if not best:
            self._pending_key = None; self._pending_n = 0
            self._miss_n += 1
            self._dbg('Tracking - screen differs from my board but no single clear move (' + str(self._miss_n) + '/4) - ' + info)
            if self._miss_n >= 4 and conf >= 0.6 and self._resync_ok(detected):
                self._miss_n = 0
                self.root.after(0, lambda b=detected, o=orient: self._resync(b, o))
            return
        self._miss_n = 0
        base, (path, gain) = best
        key = (base.board_fen(), base.turn, tuple(m.uci() for m in path))
        if key == self._pending_key: self._pending_n += 1
        else: self._pending_key = key; self._pending_n = 1
        self._dbg('Move seen: ' + ' '.join(m.uci() for m in path) + ' (gain ' + format(gain, '.2f') + ', confirm ' + str(self._pending_n) + '/2) - ' + info)
        if self._pending_n < 2: return
        self._pending_key = None; self._pending_n = 0
        after = base.copy(stack=False)
        for m in path: after.push(m)
        if conf >= 0.6: self.vision.learn(crop, expected_labels(after, orient), S, labels)
        self.root.after(0, lambda pl=base.board_fen(), t=base.turn, p=path, c=conf, o=orient: self._accept_moves(pl, t, p, c, o))

    def _board_lost(self):
        self.board_rect = None
        self.detect_label.configure(text='No board detected')
        self.status.configure(text='Board not visible - is the game window uncovered and on the board screen?')

    def _board_found(self, rect, orientation=None):
        self.board_rect = rect
        self.detect_label.configure(text='Board detected \u00b7 tracking live' if self.position_confirmed else 'Board detected \u00b7 reading position')
        if orientation:
            self.player_orientation = orientation
            self.side_value.configure(text=self._side_text(orientation))

    def _finish_autocalibration(self, rect, orient, assumed=False):
        self._board_found(rect, orient)
        self._accept_initial_position(orient, None, 'assuming White' if assumed else None)

    def _accept_initial_position(self, orient, sim, note=None):
        already = self.position_confirmed and self.board.fen() == chess.STARTING_FEN and self.player_orientation == orient
        self.board = chess.Board(); self.position_confirmed = True; self._turn_unsure = False
        self.player_orientation = orient
        self.side_value.configure(text=self._side_text(orient))
        self._refresh_recognition_label()
        if already: return
        self.overlay.hide(); self.chosen = None
        colour = 'White' if orient == 'white' else 'Black'
        extra = (' \u00b7 ' + note) if note else ''
        self.status.configure(text='New game \u00b7 you are ' + colour + extra)
        if self.board.turn == self._player_colour(orient):
            if self.auto_coach.get(): self.analyse_async(auto=True)
        else:
            self.status.configure(text='New game \u00b7 you are Black \u00b7 waiting for White to move')

    def _sync_from_screen(self, b, orient, conf):
        if self.position_confirmed: return
        b.turn = self._player_colour(orient)
        b.castling_rights = guess_castling(b)
        if not b.is_valid():
            self.status.configure(text='Reading the position... (waiting for a clean view of both kings)')
            self._dbg('Stage 4: position read but not a legal chess position (kings/pawns misread?) - ' + b.board_fen())
            return
        self.board = b; self.position_confirmed = True; self._turn_unsure = True
        self.player_orientation = orient
        self.side_value.configure(text=self._side_text(orient))
        self.status.configure(text='Joined mid-game from the screen \u00b7 assuming it is your move')
        if self.auto_coach.get(): self.analyse_async(auto=True)

    def _resync(self, d, orient):
        if not self.position_confirmed: return
        d.turn = self._player_colour(orient)
        d.castling_rights = guess_castling(d)
        if not d.is_valid(): return
        self.board = d; self._turn_unsure = True; self._pending_key = None; self._pending_n = 0
        self.overlay.hide(); self.chosen = None
        self.status.configure(text='Lost track - re-read the board from the screen \u00b7 assuming it is your move')
        if self.auto_coach.get(): self.analyse_async(auto=True)

    def _accept_moves(self, placement, turn, path, conf, orient):
        if self.board.board_fen() != placement: return
        b = self.board.copy(); b.turn = turn
        try:
            for m in path: b.push(m)
        except Exception: return
        self.board = b; self._turn_unsure = False; self.position_confirmed = True
        self.player_orientation = orient
        self.overlay.hide(); self.chosen = None
        self.side_value.configure(text=self._side_text(orient))
        if b.is_game_over():
            self.status.configure(text='Game over'); return
        if b.turn == self._player_colour(orient):
            self.status.configure(text='Your move \u00b7 analysing')
            if self.auto_coach.get(): self.analyse_async(auto=True)
        else:
            self.status.configure(text='Opponent to move \u00b7 watching')

    def analyse_async(self, auto=False):
        if self._busy: return
        if not self.position_confirmed:
            self.output.configure(state='normal'); self.output.delete('1.0', 'end')
            self.output.insert('end', 'Position not read yet. Make sure the whole board is visible. If this is a new game, it starts on its own; for a game in progress, give it a second or two. The Scanner line above says which step it is stuck on.')
            self.output.configure(state='disabled')
            self.status.configure(text='Board located - waiting for verified piece recognition'); return
        self._busy = True; pos = self.board.copy(); self._analysed_fen = pos.fen()
        self.status.configure(text='Analysing with Stockfish and Maia-3...')
        threading.Thread(target=self._analyse_worker, args=(pos, auto), daemon=True).start()
    def _analyse_worker(self, pos, auto):
        self.engine.path = self.stock_path.get().strip()
        candidates, err = self.engine.analyse(pos, 5)
        self.maia.model = self.maia_model.get(); self.maia.elo = int(self.maia_elo.get())
        mlines, merr = self.maia.predict(pos)
        if err:
            out = 'I could not reach Stockfish. Check the Stockfish path in Settings.'
            chosen = None; best = None
        else:
            best = candidates[0] if candidates else None
            chosen = choose_candidate(pos, candidates, self.personality.get())
            if mlines:
                predicted = mlines[0]
                maia_text = ('Maia predicts a player around ' + str(self.maia_elo.get()) + ' Elo may choose ' + predicted['san'] + '. '
                             'Its W/D/L figures describe the expected game outcome after that move, not the chance the opponent chooses it.')
            else:
                maia_text = 'Maia is not responding, so no human-style move prediction is available.'
            out = report(pos, chosen, best, self.personality.get(), maia_text)
        self.root.after(0, lambda: self._analysis_done(candidates, chosen, best, out, auto))
    def _analysis_done(self, candidates, chosen, best, out, auto):
        self._busy = False
        if self.board.fen() != self._analysed_fen:
            if self.position_confirmed and self.player_orientation and self.board.turn == self._player_colour(self.player_orientation) and self.auto_coach.get():
                self.analyse_async(auto=True)
            return
        self.candidates = candidates; self.chosen = chosen
        self.output.configure(state='normal'); self.output.delete('1.0', 'end')
        self.output.insert('end', out); self.output.configure(state='disabled')
        if chosen and best: self.eval_label.configure(text=format(best['cp'] / 100, '+.2f'))
        if chosen and self.board_rect and self.capture and self.position_confirmed:
            x, y, w, h, _ = self.board_rect
            ox, oy = self.capture.latest_origin
            orientation = self.player_orientation or 'white'
            caption = self.personality.get() + '  \u00b7  PLAY ' + chosen['san']
            explanation = explain_move(self.board, chess.Move.from_uci(chosen['move']))
            self.overlay.show((x + ox, y + oy, w, h), chosen['move'], orientation, caption, explanation, self.overlay_position.get())
        self.status.configure(text='Your move \u00b7 suggestion ready' if chosen else 'Analysis incomplete - check engine setup')
    def toggle_overlay_position(self):
        new = 'top' if self.overlay_position.get() == 'bottom' else 'bottom'
        self.overlay_position.set(new)
        self.overlay_button.configure(text=new.title())
        if self.chosen and self.board_rect and self.position_confirmed:
            move = chess.Move.from_uci(self.chosen['move'])
            explanation = explain_move(self.board, move)
            x, y, w, h, _ = self.board_rect; ox, oy = self.capture.latest_origin
            caption = self.personality.get() + '  \u00b7  PLAY ' + self.chosen['san']
            self.overlay.show((x + ox, y + oy, w, h), self.chosen['move'], self.player_orientation or 'white', caption, explanation, self.overlay_position.get())

    def browse_engine(self):
        p = filedialog.askopenfilename(filetypes=[('Executable', '*.exe'), ('All files', '*.*')])
        if p: self.stock_path.set(p)
    def close(self):
        if self.capture: self.capture.stop()
        self.overlay.hide(); self.engine.stop(); self.maia.stop(); self.root.destroy()

def main():
    root = tk.Tk()
    try: ttk.Style().theme_use('clam')
    except Exception: pass
    App(root); root.mainloop()
