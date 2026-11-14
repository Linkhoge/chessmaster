import os, cv2, numpy as np, chess

SYMBOLS = list("PNBRQKpnbrqk")
EMPTY_LIGHT = ".L"
EMPTY_DARK = ".D"

class BoardVision:
    """Template-based recognizer for a calibrated, fixed-size 2D board crop."""
    def __init__(self, path):
        self.path=path
        self.templates={}
        self.load()
    def load(self):
        if not os.path.exists(self.path): return
        try:
            z=np.load(self.path,allow_pickle=False)
            labels=z["labels"].tolist()
            patches=z["patches"]
            for lab,patch in zip(labels,patches):
                self.templates.setdefault(str(lab),[]).append(patch.astype(np.uint8))
        except Exception: self.templates={}
    def save(self):
        labels=[]; patches=[]
        for lab,items in self.templates.items():
            for p in items: labels.append(lab); patches.append(p)
        if patches:
            np.savez_compressed(self.path,labels=np.array(labels),patches=np.stack(patches))
    @staticmethod
    def _patch(img, col, row):
        h,w=img.shape[:2]; sw=w/8; sh=h/8
        x0=int(col*sw+sw*.18); x1=int((col+1)*sw-sw*.18)
        y0=int(row*sh+sh*.15); y1=int((row+1)*sh-sh*.15)
        crop=img[y0:y1,x0:x1]
        crop=cv2.resize(crop,(40,40),interpolation=cv2.INTER_AREA)
        # Keep colour: it helps distinguish white/black pieces and board themes.
        return cv2.cvtColor(crop,cv2.COLOR_BGR2Lab)
    def add_sample(self, frame_rgb, col, row, symbol):
        if symbol not in SYMBOLS and symbol!=".": raise ValueError("Use P N B R Q K p n b r q k or .")
        bgr=cv2.cvtColor(np.array(frame_rgb),cv2.COLOR_RGB2BGR)
        lab=symbol
        if symbol==".":
            lab=EMPTY_LIGHT if (col+row)%2==0 else EMPTY_DARK
        self.templates.setdefault(lab,[]).append(self._patch(bgr,col,row))
        self.save()
        return lab

    @staticmethod
    def _square_polarity(gray, col, row):
        """How much lighter the piece centre is than the square's own corners.

        Positive means a light piece. Negative means a dark piece. Comparing the
        centre with the corners ignores whether the square itself is light or dark.
        """
        h,w=gray.shape[:2]; sw=w/8.0; sh=h/8.0
        def med(fx0,fy0,fx1,fy1):
            x0=int((col+fx0)*sw); x1=max(x0+1,int((col+fx1)*sw))
            y0=int((row+fy0)*sh); y1=max(y0+1,int((row+fy1)*sh))
            patch=gray[max(0,y0):min(h,y1), max(0,x0):min(w,x1)]
            return float(np.median(patch)) if patch.size else 0.0
        centre=med(0.36,0.32,0.64,0.68)
        corners=[med(0.04,0.04,0.16,0.16), med(0.84,0.04,0.96,0.16),
                 med(0.04,0.84,0.16,0.96), med(0.84,0.84,0.96,0.96)]
        return centre-float(np.median(corners))

    @staticmethod
    def infer_bottom_orientation(frame_rgb):
        """Which colour is sitting on the bottom of the screen.

        The player is always the bottom side. Returns "white", "black", or None
        when the two ends of the board are too similar to trust.
        """
        gray=cv2.cvtColor(np.asarray(frame_rgb),cv2.COLOR_RGB2GRAY)
        def end_polarity(rows):
            vals=[BoardVision._square_polarity(gray,col,row) for row in rows for col in range(8)]
            return float(np.median(vals)) if vals else 0.0
        # Image row 0 is the top of the screen. Rows 6 and 7 are the player's side.
        bottom=end_polarity((6,7))
        top=end_polarity((0,1))
        if abs(bottom-top)<8:
            return None
        return "white" if bottom>top else "black"

    @staticmethod
    def looks_like_start_position(frame_rgb):
        """True when the outer ranks hold pieces and the middle of the board is empty."""
        gray=cv2.cvtColor(np.asarray(frame_rgb),cv2.COLOR_RGB2GRAY)
        def presence(rows):
            vals=[abs(BoardVision._square_polarity(gray,col,row)) for row in rows for col in range(8)]
            return float(np.median(vals)) if vals else 0.0
        outer=presence((0,1,6,7))
        inner=presence((3,4))
        return outer>15 and outer>inner*1.6

    def auto_calibrate_start_position(self, frame_rgb, orientation="white"):
        """Seed piece/empty-square templates from a standard initial chess position.

        This is safe only when the visible board is the untouched starting position.
        It does not infer arbitrary mid-game piece identities.
        """
        bgr=cv2.cvtColor(np.array(frame_rgb),cv2.COLOR_RGB2BGR)
        h,w=bgr.shape[:2]
        if w<240 or h<240:return False,"Board crop is too small."
        samples={}
        # Board rows/columns in the screen crop for each colour orientation.
        for row in range(8):
            for col in range(8):
                if orientation=="white":
                    file_idx=col; rank_idx=7-row
                else:
                    file_idx=7-col; rank_idx=row
                if rank_idx==0:
                    symbol="RNBQKBNR"[file_idx]
                elif rank_idx==1:
                    symbol="P"
                elif rank_idx==6:
                    symbol="p"
                elif rank_idx==7:
                    symbol="rnbqkbnr"[file_idx]
                else:
                    symbol="."
                # map empty squares to their visible square tone
                if symbol==".":
                    symbol=EMPTY_LIGHT if (row+col)%2==0 else EMPTY_DARK
                samples.setdefault(symbol,[]).append(self._patch(bgr,col,row))
        needed=set(SYMBOLS+[EMPTY_LIGHT,EMPTY_DARK])
        if not needed.issubset(samples):
            return False,"Could not construct all required starting-position classes."
        # Keep a small number of representative patches per class.
        self.templates={k:v[:3] for k,v in samples.items()}
        self.save()
        return True,"Templates learned from the standard starting position."
    def ready(self):
        needed=set(SYMBOLS+[EMPTY_LIGHT,EMPTY_DARK])
        return needed.issubset(self.templates)
    def classify(self, frame_rgb, orientation="white"):
        bgr=cv2.cvtColor(np.array(frame_rgb),cv2.COLOR_RGB2BGR)
        h,w=bgr.shape[:2]
        if w<160 or h<160: return None,0.0,"Capture crop is too small."
        pieces={}; confidences=[]
        for row in range(8):
            for col in range(8):
                patch=self._patch(bgr,col,row)
                lab0=EMPTY_LIGHT if (col+row)%2==0 else EMPTY_DARK
                best_lab=None; best=-1
                for lab,refs in self.templates.items():
                    for ref in refs:
                        # Normalized correlation across colour channels.
                        a=patch.astype(np.float32).reshape(-1)
                        b=ref.astype(np.float32).reshape(-1)
                        a-=a.mean(); b-=b.mean()
                        den=float(np.linalg.norm(a)*np.linalg.norm(b))+1e-6
                        score=float(np.dot(a,b)/den)
                        if score>best: best,best_lab=score,lab
                if best_lab is None: return None,0.0,"No calibration templates."
                # Scores are similarity, not calibrated probabilities.
                confidences.append(best)
                if best_lab not in (EMPTY_LIGHT,EMPTY_DARK):
                    if orientation=="white": file,rank=col,7-row
                    else: file,rank=7-col,row
                    pieces[chess.square(file,rank)]=chess.Piece.from_symbol(best_lab)
        avg=float(np.mean(confidences))
        board=chess.Board(None)
        for sq,p in pieces.items(): board.set_piece_at(sq,p)
        # Caller supplies side-to-move/castling from its tracked game state.
        return board,avg,"Template similarity (not probability)"
