import tkinter as tk, chess

class ArrowOverlay:
    def __init__(self,root):
        self.root=root;self.win=None
    def show(self,rect,uci,orientation="white",caption="",explanation="",bar_position="bottom"):
        self.hide()
        x,y,w,h=map(int,rect)
        strip_h=48
        above=(bar_position=="top")
        top=max(0,y-strip_h) if above else y
        canvas_h=h+strip_h
        self.win=tk.Toplevel(self.root)
        self.win.overrideredirect(True);self.win.attributes("-topmost",True)
        try:self.win.attributes("-transparentcolor","#010203")
        except Exception:pass
        try:self.win.attributes("-alpha",0.96)
        except Exception:pass
        self.win.configure(bg="#010203")
        self.win.geometry(f"{w}x{canvas_h}+{x}+{top}")
        c=tk.Canvas(self.win,width=w,height=canvas_h,bg="#010203",highlightthickness=0)
        c.pack()
        strip_y=strip_h/2 if above else h+strip_h/2
        # No solid bar background: only text is drawn over the transparent screen.
        c.create_text(15,strip_y+1,anchor="w",text=caption[:90],fill="#071018",
                      font=("Segoe UI",10,"bold"))
        c.create_text(14,strip_y,anchor="w",text=caption[:90],fill="#dff7eb",
                      font=("Segoe UI",10,"bold"))
        m=chess.Move.from_uci(uci)
        def center(sq):
            f,r=chess.square_file(sq),chess.square_rank(sq)
            col,row=(f,7-r) if orientation=="white" else (7-f,r)
            yy=(row+.5)*h/8+(strip_h if above else 0)
            return ((col+.5)*w/8,yy)
        a,b=center(m.from_square),center(m.to_square)
        c.create_line(*a,*b,fill="#65f0b5",width=max(5,w/90),
                      arrow=tk.LAST,arrowshape=(22,26,10),capstyle=tk.ROUND)
        c.create_oval(a[0]-7,a[1]-7,a[0]+7,a[1]+7,fill="#65f0b5",outline="")
        # Compact explanation beside the destination square.
        if explanation:
            tx=b[0]+14
            if tx+190>w:tx=b[0]-14
            anchor="w" if tx>b[0] else "e"
            ty=b[1]-10
            if above:ty=max(strip_h+14,min(h+strip_h-14,ty))
            else:ty=max(14,min(h-14,ty))
            wrap=190
            c.create_text(tx+1,ty+1,anchor=anchor,text=explanation,fill="#071018",
                          font=("Segoe UI",9,"bold"),width=wrap,justify="left")
            c.create_text(tx,ty,anchor=anchor,text=explanation,fill="#ffffff",
                          font=("Segoe UI",9,"bold"),width=wrap,justify="left")
    def hide(self):
        if self.win:
            try:self.win.destroy()
            except Exception:pass
            self.win=None
