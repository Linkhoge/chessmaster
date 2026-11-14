import chess, numpy as np

MIN_GAIN = 0.7
MIN_LEAD = 0.3
REQUIRED = ('.L', '.D', *'PNBRQKpnbrqk')

def expected_labels(board, orient):
    pm = board.piece_map(); out = []
    for r in range(8):
        for c in range(8):
            f, rk = (c, 7 - r) if orient == 'white' else (7 - c, r)
            p = pm.get(chess.square(f, rk))
            out.append(p.symbol() if p else ('.L' if (r + c) % 2 == 0 else '.D'))
    return out

def board_from_scores(S, labels, orient):
    S2 = S.reshape(64, -1); b = chess.Board(None)
    for n in range(64):
        lab = labels[int(S2[n].argmax())]
        if lab in ('.L', '.D'): continue
        r, c = divmod(n, 8)
        f, rk = (c, 7 - r) if orient == 'white' else (7 - c, r)
        b.set_piece_at(chess.square(f, rk), chess.Piece.from_symbol(lab))
    return b

def guess_castling(b):
    rights = 0
    W, B = chess.WHITE, chess.BLACK
    if b.piece_at(chess.E1) == chess.Piece(chess.KING, W):
        if b.piece_at(chess.H1) == chess.Piece(chess.ROOK, W): rights |= chess.BB_H1
        if b.piece_at(chess.A1) == chess.Piece(chess.ROOK, W): rights |= chess.BB_A1
    if b.piece_at(chess.E8) == chess.Piece(chess.KING, B):
        if b.piece_at(chess.H8) == chess.Piece(chess.ROOK, B): rights |= chess.BB_H8
        if b.piece_at(chess.A8) == chess.Piece(chess.ROOK, B): rights |= chess.BB_A8
    return rights

def best_transition(board, S, labels, orient, max_plies=2):
    '''Score every legal 1-ply and 2-ply continuation against per-square similarity.

    Tolerates a few misread squares (toasts, highlights, arrows). Returns (path, gain) or None.
    '''
    idx = {l: i for i, l in enumerate(labels)}
    if not all(l in idx for l in REQUIRED): return None
    S2 = S.reshape(64, -1); ar = np.arange(64)
    def score(b):
        return float(S2[ar, [idx[l] for l in expected_labels(b, orient)]].sum())
    base_key = board.board_fen(); base = score(board)
    cands = {}
    def consider(b, path):
        key = b.board_fen()
        if key == base_key: return
        old = cands.get(key)
        if old is not None and len(old[1]) <= len(path): return
        cands[key] = (score(b), path)
    for m1 in list(board.legal_moves):
        b1 = board.copy(stack=False); b1.push(m1); consider(b1, [m1])
        if max_plies >= 2:
            for m2 in list(b1.legal_moves):
                b2 = b1.copy(stack=False); b2.push(m2); consider(b2, [m1, m2])
    if not cands: return None
    ranked = sorted(cands.values(), key=lambda t: -t[0])
    best, path = ranked[0]
    if best - base < MIN_GAIN: return None
    if len(ranked) > 1 and best - ranked[1][0] < MIN_LEAD: return None
    return path, best - base
