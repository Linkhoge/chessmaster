import os, tkinter as tk, threading, time
from tkinter import ttk, filedialog, simpledialog
from PIL import ImageTk
import chess
from .capture import LiveCapture
from .engine import UCIEngine
from .coach import PERSONALITIES, choose_candidate, report, explain_move
from .overlay import ArrowOverlay
from .vision import BoardVision, SYMBOLS
from .tracker import reconcile
from .maia import Maia3
from .locator import locate_chessboard, square_centres

BASE=os.path.dirname(os.path.dirname(__file__))

class App:
    BG="#090d14"; PANEL="#111722"; PANEL2="#1b2533"; LINE="#273244"
    FG="#edf3fc"; MUTED="#91a1b8"; GREEN="#63e6b1"; AMBER="#f5c56b"

    def __init__(self,root):
        self.root=root;root.title("ChessMaster — v2.1 Calibration Foundation")
        root.geometry("1180x820");root.minsize(1040,720);root.configure(bg=self.BG)
        self.board=chess.Board();self.position_confirmed=False;self.capture=LiveCapture(interval=.35);self.preview_img=None;self.window_items=[];self.window_choice=tk.StringVar(value="")
        self.overlay=ArrowOverlay(root);self.chosen=None;self.candidates=[]
        self.personality=tk.StringVar(value="Jester")
        self.overlay_position=tk.StringVar(value="bottom")
        self.orientation=tk.StringVar(value="white")
        self.auto_coach=tk.BooleanVar(value=True)
        self.maia_model=tk.StringVar(value="maia3-5m")
        self.maia_elo=tk.IntVar(value=1500)
        self.stock_path=tk.StringVar(value=os.path.join(BASE,"engines","stockfish.exe"))
        self.vision=BoardVision(os.path.join(BASE,"vision_templates.npz"))
        self.engine=UCIEngine(self.stock_path.get());self.maia=Maia3()
        self.board_rect=None;self.board_score=0;self.player_orientation=None;self.square_map={};self.last_scan=0;self.last_detected_fen=None
        self._busy=False;self.calibration=tk.BooleanVar(value=False)
        self._vision_lock=threading.Lock();self._calibrated_for_start=False;self._opening_gap=0
        self._style();self._ui();self._start_automatic_monitor()
        root.protocol("WM_DELETE_WINDOW",self.close);root.after(250,self._tick)

    def _style(self):
        s=ttk.Style()
        try:s.theme_use("clam")
        except:pass
        s.configure(".",background=self.BG,foreground=self.FG,font=("Segoe UI",10))
        s.configure("TFrame",background=self.BG)
        s.configure("Panel.TFrame",background="#111722")
        s.configure("TLabel",background=self.BG,foreground=self.FG)
        s.configure("Muted.TLabel",background="#111722",foreground="#8492a6")
        s.configure("Title.TLabel",background=self.BG,foreground="#f4f6fa",font=("Segoe UI",22,"normal"))
        s.configure("Section.TLabel",background="#111722",foreground="#cbd5e1",font=("Segoe UI",9,"bold"))
        s.configure("TButton",background="#1b2533",foreground="#e7edf5",borderwidth=0,padding=(11,7),font=("Segoe UI",9))
        s.map("TButton",background=[("active","#29374a")],foreground=[("active","#ffffff")])
        s.configure("Accent.TButton",background="#d9e7e1",foreground="#102019",font=("Segoe UI",9,"bold"))
        s.map("Accent.TButton",background=[("active","#eff8f3")])
        s.configure("TEntry",fieldbackground="#0c121c",foreground=self.FG,insertcolor=self.FG,bordercolor="#273244",padding=6)
        s.configure("TCombobox",fieldbackground="#0c121c",foreground=self.FG,background="#1b2533",arrowcolor="#dce5ef",padding=6)
        s.map("TCombobox",fieldbackground=[("readonly","#0c121c")],foreground=[("readonly",self.FG)])
        s.configure("TCheckbutton",background="#111722",foreground="#cbd5e1")
        s.map("TCheckbutton",background=[("active","#111722")])

    def card(self,p):
        return ttk.Frame(p,style="Panel.TFrame",padding=14)

    def _ui(self):
        self.root.configure(bg=self.BG)
        header=ttk.Frame(self.root,padding=(26,20,26,16));header.pack(fill="x")
        brand=ttk.Frame(header);brand.pack(side="left")
        ttk.Label(brand,text="CHESSMASTER",foreground="#c5e4d7",font=("Segoe UI",9,"bold")).pack(anchor="w")
        ttk.Label(brand,text="A quieter kind of advantage.",style="Title.TLabel").pack(anchor="w",pady=(3,0))
        actions=ttk.Frame(header);actions.pack(side="right")
        self.live_label=ttk.Label(actions,text="●  MONITORING",foreground="#b6d9c8",font=("Segoe UI",9))
        self.live_label.pack(side="right",padx=16)
        ttk.Separator(self.root).pack(fill="x",padx=26)
        targetbar=ttk.Frame(self.root,padding=(26,10,26,4));targetbar.pack(fill="x")
        ttk.Label(targetbar,text="GAME WINDOW",foreground="#8492a6",font=("Segoe UI",8,"bold")).pack(side="left")
        self.window_combo=ttk.Combobox(targetbar,textvariable=self.window_choice,state="readonly",width=42)
        self.window_combo.pack(side="left",padx=8)
        ttk.Button(targetbar,text="Refresh",command=self.refresh_windows).pack(side="left",padx=3)
        ttk.Button(targetbar,text="Use window",command=self.select_window).pack(side="left",padx=3)
        self.grid_debug=tk.BooleanVar(value=True)
        ttk.Checkbutton(targetbar,text="Show calibration grid",variable=self.grid_debug).pack(side="right")

        body=ttk.Frame(self.root,padding=(26,12,26,20));body.pack(fill="both",expand=True)
        body.columnconfigure(0,weight=5);body.columnconfigure(1,weight=6);body.rowconfigure(0,weight=1)
        left=ttk.Frame(body);left.grid(row=0,column=0,sticky="nsew",padx=(0,12))
        right=ttk.Frame(body);right.grid(row=0,column=1,sticky="nsew",padx=(12,0))
        left.rowconfigure(0,weight=1);right.rowconfigure(1,weight=1)

        monitor=self.card(left);monitor.pack(fill="both",expand=True)
        bar=ttk.Frame(monitor,style="Panel.TFrame");bar.pack(fill="x")
        ttk.Label(bar,text="SCREEN",style="Section.TLabel").pack(side="left")
        self.detect_label=ttk.Label(bar,text="Looking for a board",style="Muted.TLabel");self.detect_label.pack(side="right")
        self.preview=tk.Label(monitor,bg="#080c13",fg="#758397",text="Waiting for first display",font=("Segoe UI",10),bd=0)
        self.preview.pack(fill="both",expand=True,pady=(14,10))
        self.preview.bind("<Button-1>",self.preview_click)
        ttk.Label(monitor,text="You play from the bottom of the board  ·  private, on-device processing",style="Muted.TLabel").pack(anchor="w")

        coach=self.card(right);coach.pack(fill="x")
        line=ttk.Frame(coach,style="Panel.TFrame");line.pack(fill="x")
        ttk.Label(line,text="COACH",style="Section.TLabel").pack(side="left")
        ttk.Label(line,text="LIVE",foreground="#b6d9c8",background="#111722",font=("Segoe UI",8,"bold")).pack(side="right")
        side=ttk.Frame(coach,style="Panel.TFrame");side.pack(fill="x",pady=(12,0))
        ttk.Label(side,text="YOUR SIDE",style="Muted.TLabel").pack(side="left")
        self.side_value=ttk.Label(side,text="You · bottom (detecting colour)",foreground="#d9e7e1",background="#111722")
        self.side_value.pack(side="left",padx=9)
        ttk.Button(side,text="Analyse",style="Accent.TButton",command=self.analyse_async).pack(side="right")
        ttk.Button(side,text="Calibrate",command=self.recalibrate_now).pack(side="right",padx=(0,8))
        opts=ttk.Frame(coach,style="Panel.TFrame");opts.pack(fill="x",pady=(10,0))
        ttk.Label(opts,text="PERSONALITY",style="Muted.TLabel").pack(side="left")
        ttk.Combobox(opts,textvariable=self.personality,values=list(PERSONALITIES),state="readonly",width=14).pack(side="left",padx=(8,14))
        ttk.Label(opts,text="COACH TEXT",style="Muted.TLabel").pack(side="left")
        self.overlay_button=ttk.Button(opts,text="Bottom",command=self.toggle_overlay_position)
        self.overlay_button.pack(side="left",padx=(8,14))
        ttk.Checkbutton(opts,text="Auto coach",variable=self.auto_coach).pack(side="left")
        engines=ttk.Frame(coach,style="Panel.TFrame");engines.pack(fill="x",pady=(10,0))
        ttk.Label(engines,text="MAIA",style="Muted.TLabel").pack(side="left")
        ttk.Combobox(engines,textvariable=self.maia_model,values=["maia3-5m","maia3-23m","maia3-79m"],width=12,state="readonly").pack(side="left",padx=(8,12))
        ttk.Label(engines,text="ELO",style="Muted.TLabel").pack(side="left")
        ttk.Spinbox(engines,from_=1100,to=2500,increment=100,textvariable=self.maia_elo,width=6).pack(side="left",padx=(8,12))
        ttk.Label(engines,text="PIECES",style="Muted.TLabel").pack(side="left")
        self.recognition_value=ttk.Label(engines,text=f"{len(self.vision.templates)}/14",foreground="#d9e7e1",background="#111722")
        self.recognition_value.pack(side="left",padx=(8,12))
        ttk.Checkbutton(engines,text="Label squares",variable=self.calibration,command=self._on_calibration_toggle).pack(side="left")
        fish=ttk.Frame(coach,style="Panel.TFrame");fish.pack(fill="x",pady=(10,0))
        ttk.Label(fish,text="STOCKFISH",style="Muted.TLabel").pack(side="left")
        ttk.Entry(fish,textvariable=self.stock_path).pack(side="left",fill="x",expand=True,padx=8)
        ttk.Button(fish,text="Browse",command=self.browse_engine).pack(side="left")

        self.status=ttk.Label(right,text="Starting first-display monitor…",foreground="#b6d9c8",background=self.BG,font=("Segoe UI",9),anchor="w")
        self.status.pack(fill="x",pady=(13,9))
        result=self.card(right);result.pack(fill="both",expand=True)
        rhead=ttk.Frame(result,style="Panel.TFrame");rhead.pack(fill="x")
        ttk.Label(rhead,text="RECOMMENDATION",style="Section.TLabel").pack(side="left")
        self.eval_label=ttk.Label(rhead,text="—",foreground="#c5e4d7",background="#111722",font=("Segoe UI",14))
        self.eval_label.pack(side="right")
        self.output=tk.Text(result,bg="#0c121c",fg="#e6edf6",insertbackground="#e6edf6",relief="flat",bd=0,
                            font=("Segoe UI",10),wrap="word",padx=14,pady=14,selectbackground="#314257")
        self.output.pack(fill="both",expand=True,pady=(12,0))
        self.output.insert("end","Ready when you are.\n\nYou play from the bottom of the board. When the starting position is on screen, ChessMaster detects whether you are White or Black and calibrates on its own.")
        self.output.configure(state="disabled")

    def refresh_windows(self):
        self.window_items=self.capture.list_windows()
        labels=[x[0] for x in self.window_items]
        self.window_combo["values"]=labels
        if labels and (self.window_combo.current()<0):
            # Prefer a likely chess/game title, otherwise first visible window.
            idx=next((i for i,x in enumerate(self.window_items) if any(k in x[1].lower() for k in ("chess","lichess","chess.com","roblox"))),0)
            self.window_combo.current(idx)
        self.status.configure(text=f"{len(labels)} visible windows found · choose your chess game")
    def select_window(self):
        idx=self.window_combo.current()
        if idx<0 or idx>=len(self.window_items):
            self.status.configure(text="Select a game window first");return
        _,title,hwnd=self.window_items[idx]
        self.capture.stop();self.capture.set_target(title,hwnd)
        self.capture.latest=None;self.board_rect=None;self.position_confirmed=False;self.board=chess.Board();self.player_orientation=None
        with self._vision_lock:
            self._calibrated_for_start=False;self._opening_gap=0
        self.side_value.configure(text="You · bottom (detecting colour)")
        self.capture.start()
        self.live_label.configure(text="● WINDOW LOCKED",foreground="#b6d9c8")
        self.status.configure(text=f"Monitoring selected window: {title}")
    def _start_automatic_monitor(self):
        self.refresh_windows()
        if self.window_items:
            self.select_window()
        else:
            self.live_label.configure(text="● NO WINDOW",foreground=self.AMBER)
            self.status.configure(text="No visible application windows found · press Refresh")
    def _side_text(self,orient):
        return "You · White (bottom)" if orient=="white" else "You · Black (bottom)"
    def _refresh_recognition_label(self):
        self.recognition_value.configure(text=f"{len(self.vision.templates)}/14")
    def recalibrate_now(self):
        """Learn the piece set from the board on screen. The player is the bottom side."""
        if not self.capture or not self.capture.latest or not self.board_rect:
            with self._vision_lock:
                self._calibrated_for_start=False
            self.status.configure(text="Board not visible yet · calibration runs as soon as it appears")
            return
        x,y,w,h,_=self.board_rect
        crop=self.capture.latest.crop((x,y,x+w,y+h))
        guessed=self.vision.infer_bottom_orientation(crop)
        orient=guessed or "white"
        ok,msg=self.vision.auto_calibrate_start_position(crop,orient)
        if not ok:
            self.status.configure(text=msg);return
        with self._vision_lock:
            self._calibrated_for_start=True
        self._finish_autocalibration(self.board_rect,orient,assumed=guessed is None)
    def _finish_autocalibration(self,rect,orient,assumed=False):
        self._board_found(rect,orient)
        note="assuming White" if assumed else None
        self._accept_initial_position(orient,None,note)
    def _on_calibration_toggle(self):
        if self.calibration.get() and (not self.capture or not self.capture.latest):
            self.calibration.set(False)
            self.status.configure(text="Waiting for the game window before labelling squares")
            return
        if self.calibration.get():
            self.status.configure(text="Click a square in the preview, then type P N B R Q K, lowercase for Black, or .")
        else:
            self.status.configure(text="Square labelling off")
    def preview_click(self,event):
        if not self.calibration.get() or not self.capture or not self.capture.latest or not self.board_rect:return
        # Click position on scaled preview maps to board crop.
        sw=max(1,self.preview_img.width());sh=max(1,self.preview_img.height())
        full=self.capture.latest
        x,y,w,h,_=self.board_rect
        col=min(7,max(0,int(event.x/sw*8)));row=min(7,max(0,int(event.y/sh*8)))
        symbol=simpledialog.askstring("Piece label","Enter P N B R Q K, lowercase for Black, or . for empty:")
        if symbol is None:return
        symbol=symbol.strip()
        if symbol not in SYMBOLS and symbol!=".":return
        crop=full.crop((x,y,x+w,y+h))
        self.vision.add_sample(crop,col,row,symbol)
        self._refresh_recognition_label()
        self.status.configure(text=f"Recognition sample saved · {len(self.vision.templates)}/14 classes")
    def _tick(self):
        if self.capture and self.capture.latest:
            frame=self.capture.latest
            try:
                if self.board_rect:
                    bx,by,bw,bh,_=self.board_rect
                    im=frame.crop((bx,by,bx+bw,by+bh))
                    if self.grid_debug.get():
                        from PIL import ImageDraw
                        draw=ImageDraw.Draw(im)
                        for n in range(1,8):
                            xx=round(bw*n/8);yy=round(bh*n/8)
                            draw.line((xx,0,xx,bh),fill=(244,194,75),width=2)
                            draw.line((0,yy,bw,yy),fill=(244,194,75),width=2)
                else:
                    im=frame.copy()
                im.thumbnail((560,560))
                self.preview_img=ImageTk.PhotoImage(im);self.preview.configure(image=self.preview_img,text="")
            except Exception:pass
            if time.time()-self.last_scan>1.0:
                self.last_scan=time.time()
                threading.Thread(target=self._vision_worker,args=(frame.copy(),self.board.copy()),daemon=True).start()
            if self.capture.error:self.status.configure(text="Capture error: "+self.capture.error)
        self.root.after(250,self._tick)

    def _vision_worker(self,frame,board_snapshot):
        # Search the captured window for a square board.
        loc=locate_chessboard(frame)
        if not loc:
            with self._vision_lock:
                self._opening_gap+=1
                if self._opening_gap>=3:self._calibrated_for_start=False
            self.root.after(0,lambda:self.detect_label.configure(text="No board detected"))
            return
        x,y,w,h,score=loc
        rect=(x,y,w,h,score)
        crop=frame.crop((x,y,x+w,y+h))
        # The player is the bottom of the screen. Colour comes from that side only,
        # so the opponent's pieces at the top are never treated as our back rank.
        guessed=self.vision.infer_bottom_orientation(crop)
        startish=self.vision.looks_like_start_position(crop)
        with self._vision_lock:
            if startish:self._opening_gap=0
            else:
                self._opening_gap+=1
                # Early moves still look like the start. Only arm a new calibration
                # after the layout has clearly left the opening ranks.
                if self._opening_gap>=3:self._calibrated_for_start=False
            should_cal=startish and not self._calibrated_for_start and guessed is not None
            if should_cal:self._calibrated_for_start=True
        if should_cal:
            ok,msg=self.vision.auto_calibrate_start_position(crop,guessed)
            if not ok:
                with self._vision_lock:self._calibrated_for_start=False
                self.root.after(0,lambda r=rect,o=guessed:self._board_found(r,o))
                return
            self.root.after(0,lambda r=rect,o=guessed:self._finish_autocalibration(r,o))
            return
        if self.position_confirmed and self.player_orientation:
            orient=self.player_orientation
        else:
            orient=guessed
        if not self.vision.ready():
            self.root.after(0,lambda r=rect,o=orient:self._board_found(r,o))
            return
        detected,sim,note=self.vision.classify(crop,orient or "white")
        if detected is None:
            self.root.after(0,lambda r=rect,o=orient:self._board_found(r,o))
            return
        self.root.after(0,lambda r=rect,o=orient:self._board_found(r,o))
        if sim<.82:return
        if detected.piece_map()==chess.Board().piece_map():
            self.root.after(0,lambda o=orient or "white",s=sim:self._accept_initial_position(o,s))
            return
        path,msg=reconcile(board_snapshot,detected,max_plies=2)
        if path:
            base_fen=board_snapshot.fen()
            self.root.after(0,lambda p=path,s=sim,f=base_fen,r=rect,o=orient or "white":self._accept_moves(p,s,f,r,o))

    def _board_found(self,rect,orientation=None):
        self.board_rect=rect
        # Internal coordinate map only; no labels are drawn over the user's board.
        x,y,w,h=rect[:4]
        side=orientation or self.player_orientation or "white"
        self.square_map={}
        for f in range(8):
            for r in range(8):
                col,row=(f,7-r) if side=="white" else (7-f,r)
                self.square_map[f"{chr(97+f)}{r+1}"]=(x+(col+.5)*w/8,y+(row+.5)*h/8)
        self.detect_label.configure(text="Board detected · you play from the bottom")
        if orientation:
            self.player_orientation=orientation
            self.side_value.configure(text=self._side_text(orientation))
        if not self.position_confirmed and not self.calibration.get():
            self.status.configure(text="Board located · you are the bottom side · checking colour")

    def _accept_initial_position(self,orient,sim,note=None):
        already=self.position_confirmed and self.board.fen()==chess.STARTING_FEN and self.player_orientation==orient
        self.board=chess.Board();self.position_confirmed=True
        self.player_orientation=orient
        self.side_value.configure(text=self._side_text(orient))
        self._refresh_recognition_label()
        colour="White" if orient=="white" else "Black"
        extra=f" · {note}" if note else ""
        sim_txt=f" · similarity {sim:.2f}" if sim is not None else ""
        self.status.configure(text=f"Calibrated · you are {colour} at the bottom{extra}{sim_txt}")
        if self.auto_coach.get() and not already:self.analyse_async(auto=True)

    def _accept_moves(self,path,sim,base_fen,rect,orient):
        if self.board.fen()!=base_fen:return
        b=self.board.copy()
        try:
            for m in path:b.push(m)
        except Exception:return
        self.board=b;self.last_detected_fen=b.fen();self.position_confirmed=True
        self.player_orientation=orient
        self.side_value.configure(text=self._side_text(orient))
        self.status.configure(text=f"Move detected · you are {'White' if orient=='white' else 'Black'} at the bottom · similarity {sim:.2f} · analysing")
        if self.auto_coach.get():self.analyse_async(auto=True)

    def analyse_async(self,auto=False):
        if self._busy:return
        if not self.position_confirmed:
            self.output.configure(state="normal");self.output.delete("1.0","end")
            self.output.insert("end","BOARD FOUND — POSITION NOT YET VERIFIED\n\nThe bottom of the screen is your side. ChessMaster calibrates on its own when that board is still the starting position, and it reads your colour from the pieces sitting there.\n\nIf this game has already begun, tick Label squares and click the preview, or start a game from the opening. Calibrate in the coach panel runs the same starting-position pass immediately.")
            self.output.configure(state="disabled")
            self.status.configure(text="Board located · waiting for verified piece recognition")
            return
        self._busy=True;pos=self.board.copy()
        self.status.configure(text="Analysing with Stockfish and Maia-3…")
        threading.Thread(target=self._analyse_worker,args=(pos,auto),daemon=True).start()
    def _analyse_worker(self,pos,auto):
        self.engine.path=self.stock_path.get().strip()
        candidates,err=self.engine.analyse(pos,5)
        self.maia.model=self.maia_model.get();self.maia.elo=int(self.maia_elo.get())
        mlines,merr=self.maia.predict(pos)
        if err:
            out="I couldn't reach Stockfish. Check the Stockfish path in the coach panel."
            chosen=None;best=None
        else:
            best=candidates[0] if candidates else None
            chosen=choose_candidate(pos,candidates,self.personality.get())
            if mlines:
                predicted=mlines[0]
                maia_text=(f"Maia predicts a player around {self.maia_elo.get()} Elo may choose {predicted['san']}. "
                           "Its W/D/L figures describe the expected game outcome after that move, not the chance the opponent chooses it.")
            else:
                maia_text="Maia is not responding, so no human-style move prediction is available."
            out=report(pos,chosen,best,self.personality.get(),maia_text)
        self.root.after(0,lambda:self._analysis_done(candidates,chosen,best,out,auto))
    def _analysis_done(self,candidates,chosen,best,out,auto):
        self._busy=False;self.candidates=candidates;self.chosen=chosen
        self.output.configure(state="normal");self.output.delete("1.0","end")
        self.output.insert("end",out);self.output.configure(state="disabled")
        if chosen and best:self.eval_label.configure(text=f"{best['cp']/100:+.2f}")
        if chosen and self.board_rect and self.capture and self.position_confirmed:
            x,y,w,h,_=self.board_rect
            ox,oy=self.capture.latest_origin
            orientation=self.player_orientation or "white"
            caption=f"{self.personality.get()}  ·  PLAY {chosen['san']}"
            explanation=explain_move(self.board,chess.Move.from_uci(chosen["move"]))
            self.overlay.show((x+ox,y+oy,w,h),chosen["move"],orientation,caption,
                              explanation,self.overlay_position.get())
        self.status.configure(text="Analysis ready" if chosen else "Analysis incomplete · check engine setup")
    def toggle_overlay_position(self):
        new="top" if self.overlay_position.get()=="bottom" else "bottom"
        self.overlay_position.set(new)
        self.overlay_button.configure(text=new.title())
        if self.chosen and self.board_rect and self.position_confirmed:
            move=chess.Move.from_uci(self.chosen["move"])
            explanation=explain_move(self.board,move)
            x,y,w,h,_=self.board_rect;ox,oy=self.capture.latest_origin
            caption=f"{self.personality.get()}  ·  PLAY {self.chosen['san']}"
            self.overlay.show((x+ox,y+oy,w,h),self.chosen["move"],
                self.player_orientation or "white",caption,explanation,self.overlay_position.get())

    def browse_engine(self):
        p=filedialog.askopenfilename(filetypes=[("Executable","*.exe"),("All files","*.*")])
        if p:self.stock_path.set(p)
    def close(self):
        if self.capture:self.capture.stop()
        self.overlay.hide();self.engine.stop();self.maia.stop();self.root.destroy()

def main():
    root=tk.Tk()
    try:ttk.Style().theme_use("clam")
    except:pass
    App(root);root.mainloop()
