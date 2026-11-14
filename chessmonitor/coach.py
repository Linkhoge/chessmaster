import chess

PERSONALITIES = {
 "Assassin": "Patiently build threats and punish loose pieces.",
 "Fortress": "Keep the king safe and build a resilient position.",
 "Puppeteer": "Create awkward choices and practical problems.",
 "Berserker": "Take the initiative and keep the pressure on.",
 "Grandmaster": "Choose sound moves and precise technique.",
 "Trickster": "Look for tricky tactics and unexpected ideas.",
 "Pacifist": "Keep things quiet and avoid unnecessary attacks.",
 "Jester": "Mix things up while keeping an eye on tactical safety.",
 "MAGNUS CARLSEN": "Apply practical pressure, manoeuvre and convert advantages."
}

PIECE_NAMES={chess.PAWN:"pawn",chess.KNIGHT:"knight",chess.BISHOP:"bishop",
             chess.ROOK:"rook",chess.QUEEN:"queen",chess.KING:"king"}

def explain_move(board, move):
    piece=board.piece_at(move.from_square)
    if not piece:return "Improves your position."
    name=PIECE_NAMES[piece.piece_type]
    target=board.piece_at(move.to_square)
    if board.is_capture(move):
        captured=PIECE_NAMES[target.piece_type] if target else "piece"
        text=f"Your {name} takes their {captured}."
    elif board.gives_check(move):
        text=f"Your {name} checks the king and makes them respond."
    elif piece.piece_type==chess.KNIGHT:
        text="Your knight heads toward the centre, where it controls more squares."
    elif piece.piece_type==chess.BISHOP:
        text="Your bishop gets a clearer diagonal and aims into the position."
    elif piece.piece_type==chess.ROOK:
        text="Your rook moves toward a more active line."
    elif piece.piece_type==chess.QUEEN:
        text="Your queen becomes more active; keep it safe from attacks."
    elif piece.piece_type==chess.PAWN:
        text="This pawn gains space and supports the squares ahead."
    else:
        text="Your king steps to a safer or more useful square."
    b=board.copy();b.push(move)
    if b.is_checkmate():return "Checkmate — the game ends."
    if b.is_check():text += " It also gives check."
    return text

def choose_candidate(board, candidates, personality):
    if not candidates:return None
    if personality in ("Grandmaster","MAGNUS CARLSEN"):return candidates[0]
    scored=[]
    for c in candidates:
        move=chess.Move.from_uci(c["move"]);piece=board.piece_at(move.from_square)
        score=c["cp"]/100.0
        capture=board.is_capture(move);check=board.gives_check(move)
        if personality=="Assassin":score+=(2 if capture else 0)+(1.3 if check else 0)
        elif personality=="Fortress":score+=(.5 if not check else -.2)+(.4 if piece and piece.piece_type in (chess.KING,chess.ROOK) else 0)
        elif personality=="Puppeteer":score+=.8 if not capture and not check else 0
        elif personality=="Berserker":score+=(2 if check else 0)+(1 if capture else 0)
        elif personality=="Trickster":score+=1.2 if check or capture else .2
        elif personality=="Pacifist":score+=1 if not capture and not check else -1
        elif personality=="Jester":score+=.5 if (move.from_square+move.to_square)%2 else -.1
        scored.append((score,c))
    return max(scored,key=lambda x:x[0])[1]

def report(board, chosen, best, personality, maia_status):
    if not chosen:return "ChessMaster couldn't get a move from the engine."
    move=chess.Move.from_uci(chosen["move"])
    explanation=explain_move(board,move)
    cost=max(0.0,((best["cp"]-chosen["cp"])/100.0)) if best else 0.0
    if cost<.15:risk="Very small difference from the engine's top move"
    elif cost<.5:risk="A little less accurate than the top move"
    elif cost<1.0:risk="Noticeably riskier"
    else:risk="Risky — the engine prefers another move"
    best_san=best["san"] if best else "not available"
    lines=[
        f"{personality} says: Play {chosen['san']}.",
        explanation,
        f"Why this move: Stockfish's top choice is {best_san}; this suggestion is about {cost:.2f} pawns behind it.",
        risk+"."
    ]
    if maia_status and maia_status.lower() not in ("unavailable","not configured",""):
        lines.append("Maia's human-style prediction: "+maia_status)
    return "\n".join(lines)
