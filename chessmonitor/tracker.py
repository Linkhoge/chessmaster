import chess

def same_placement(a,b):
    return a.piece_map()==b.piece_map()

def reconcile(current, detected, max_plies=2):
    """Return unique legal continuation matching detected piece placement."""
    matches=[]
    def walk(board,path,depth):
        if same_placement(board,detected) and path:
            matches.append(path[:]); return
        if depth>=max_plies: return
        for mv in list(board.legal_moves):
            nxt=board.copy(); nxt.push(mv)
            if same_placement(nxt,detected):
                matches.append(path+[mv]); continue
            if depth+1<max_plies:
                walk(nxt,path+[mv],depth+1)
            if len(matches)>2: return
    walk(current.copy(),[],0)
    # Remove duplicates and require exactly one path.
    uniq=[]
    for p in matches:
        sig=tuple(m.uci() for m in p)
        if sig not in [tuple(m.uci() for m in q) for q in uniq]: uniq.append(p)
    if len(uniq)==1: return uniq[0],"unique legal transition"
    if not uniq: return None,"No legal one/two-ply transition matches"
    return None,"Ambiguous legal transitions; refusing to guess"
