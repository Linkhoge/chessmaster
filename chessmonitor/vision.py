import os, cv2, numpy as np, chess

SYMBOLS = list('PNBRQKpnbrqk')
EMPTY_LIGHT = '.L'
EMPTY_DARK = '.D'

class BoardVision:
    '''Template-based recognizer for a calibrated, fixed-size 2D board crop.'''
    def __init__(self, path):
        self.path = path
        self.templates = {}
        self._dirty = True; self._mat = None; self._label_list = []; self._label_idx = None
        self.load()
    def load(self):
        if not os.path.exists(self.path): return
        try:
            z = np.load(self.path, allow_pickle=False)
            labels = z['labels'].tolist()
            patches = z['patches']
            for lab, patch in zip(labels, patches):
                self.templates.setdefault(str(lab), []).append(patch.astype(np.uint8))
        except Exception: self.templates = {}
        self._dirty = True
    def save(self):
        labels = []; patches = []
        for lab, items in self.templates.items():
            for p in items: labels.append(lab); patches.append(p)
        if patches:
            np.savez_compressed(self.path, labels=np.array(labels), patches=np.stack(patches))
    @staticmethod
    def _patch(img, col, row):
        h, w = img.shape[:2]; sw = w / 8; sh = h / 8
        x0 = int(col * sw + sw * .18); x1 = int((col + 1) * sw - sw * .18)
        y0 = int(row * sh + sh * .15); y1 = int((row + 1) * sh - sh * .15)
        crop = img[y0:y1, x0:x1]
        crop = cv2.resize(crop, (40, 40), interpolation=cv2.INTER_AREA)
        return cv2.cvtColor(crop, cv2.COLOR_BGR2Lab)
    def add_sample(self, frame_rgb, col, row, symbol):
        if symbol not in SYMBOLS and symbol != '.': raise ValueError('Use P N B R Q K p n b r q k or .')
        bgr = cv2.cvtColor(np.array(frame_rgb), cv2.COLOR_RGB2BGR)
        lab = symbol
        if symbol == '.':
            lab = EMPTY_LIGHT if (col + row) % 2 == 0 else EMPTY_DARK
        self.templates.setdefault(lab, []).append(self._patch(bgr, col, row))
        self._dirty = True
        self.save()
        return lab

    @staticmethod
    def _square_polarity(gray, col, row):
        h, w = gray.shape[:2]; sw = w / 8.0; sh = h / 8.0
        def med(fx0, fy0, fx1, fy1):
            x0 = int((col + fx0) * sw); x1 = max(x0 + 1, int((col + fx1) * sw))
            y0 = int((row + fy0) * sh); y1 = max(y0 + 1, int((row + fy1) * sh))
            patch = gray[max(0, y0):min(h, y1), max(0, x0):min(w, x1)]
            return float(np.median(patch)) if patch.size else 0.0
        centre = med(0.36, 0.32, 0.64, 0.68)
        corners = [med(0.04, 0.04, 0.16, 0.16), med(0.84, 0.04, 0.96, 0.16),
                   med(0.04, 0.84, 0.16, 0.96), med(0.84, 0.84, 0.96, 0.96)]
        return centre - float(np.median(corners))

    @staticmethod
    def infer_bottom_orientation(frame_rgb):
        gray = cv2.cvtColor(np.asarray(frame_rgb), cv2.COLOR_RGB2GRAY)
        def end_polarity(rows):
            vals = [BoardVision._square_polarity(gray, col, row) for row in rows for col in range(8)]
            return float(np.median(vals)) if vals else 0.0
        bottom = end_polarity((6, 7))
        top = end_polarity((0, 1))
        if abs(bottom - top) < 8:
            return None
        return 'white' if bottom > top else 'black'

    @staticmethod
    def looks_like_start_position(frame_rgb):
        gray = cv2.cvtColor(np.asarray(frame_rgb), cv2.COLOR_RGB2GRAY)
        def presence(rows):
            vals = [abs(BoardVision._square_polarity(gray, col, row)) for row in rows for col in range(8)]
            return float(np.median(vals)) if vals else 0.0
        outer = presence((0, 1, 6, 7))
        inner = presence((3, 4))
        return outer > 15 and outer > inner * 1.6

    def auto_calibrate_start_position(self, frame_rgb, orientation='white'):
        bgr = cv2.cvtColor(np.array(frame_rgb), cv2.COLOR_RGB2BGR)
        h, w = bgr.shape[:2]
        if w < 240 or h < 240: return False, 'Board crop is too small.'
        samples = {}
        for row in range(8):
            for col in range(8):
                if orientation == 'white':
                    file_idx = col; rank_idx = 7 - row
                else:
                    file_idx = 7 - col; rank_idx = row
                if rank_idx == 0:
                    symbol = 'RNBQKBNR'[file_idx]
                elif rank_idx == 1:
                    symbol = 'P'
                elif rank_idx == 6:
                    symbol = 'p'
                elif rank_idx == 7:
                    symbol = 'rnbqkbnr'[file_idx]
                else:
                    symbol = '.'
                if symbol == '.':
                    symbol = EMPTY_LIGHT if (row + col) % 2 == 0 else EMPTY_DARK
                samples.setdefault(symbol, []).append(self._patch(bgr, col, row))
        needed = set(SYMBOLS + [EMPTY_LIGHT, EMPTY_DARK])
        if not needed.issubset(samples):
            return False, 'Could not construct all required starting-position classes.'
        self.templates = {k: v[:3] for k, v in samples.items()}
        self._dirty = True
        self.save()
        return True, 'Templates learned from the standard starting position.'
    def ready(self):
        needed = set(SYMBOLS + [EMPTY_LIGHT, EMPTY_DARK])
        return needed.issubset(self.templates)

    def _stack(self):
        labels = []; vecs = []
        for lab, refs in self.templates.items():
            for ref in refs:
                v = ref.astype(np.float32).reshape(-1); v = v - v.mean()
                vecs.append(v / (np.linalg.norm(v) + 1e-6)); labels.append(lab)
        self._label_list = sorted(set(labels))
        self._mat = np.stack(vecs) if vecs else None
        self._label_idx = np.array([self._label_list.index(l) for l in labels]) if labels else None
        self._dirty = False

    def square_scores(self, frame_rgb):
        '''Return (labels, S) where S[row, col, k] is the best similarity of that square to label k.'''
        if self._dirty: self._stack()
        if self._mat is None: return None
        bgr = cv2.cvtColor(np.array(frame_rgb), cv2.COLOR_RGB2BGR)
        h, w = bgr.shape[:2]
        if w < 160 or h < 160: return None
        P = np.stack([self._patch(bgr, c, r).astype(np.float32).reshape(-1) for r in range(8) for c in range(8)])
        P = P - P.mean(axis=1, keepdims=True)
        P = P / (np.linalg.norm(P, axis=1, keepdims=True) + 1e-6)
        sims = P @ self._mat.T
        K = len(self._label_list)
        S = np.full((64, K), -1.0, np.float32)
        for k in range(K):
            S[:, k] = sims[:, self._label_idx == k].max(axis=1)
        return list(self._label_list), S.reshape(8, 8, K)

    def learn(self, frame_rgb, expected, S, labels, max_per=10):
        '''Add new looks (highlighted squares, themes) for squares we are fairly sure about. Memory only.'''
        bgr = cv2.cvtColor(np.array(frame_rgb), cv2.COLOR_RGB2BGR)
        idx = {l: i for i, l in enumerate(labels)}
        S2 = S.reshape(64, -1)
        for n, lab in enumerate(expected):
            if lab not in idx: continue
            s = float(S2[n, idx[lab]])
            if 0.45 <= s < 0.93:
                r, c = divmod(n, 8)
                lst = self.templates.setdefault(lab, [])
                lst.append(self._patch(bgr, c, r))
                if len(lst) > max_per: del lst[3]
        self._dirty = True
