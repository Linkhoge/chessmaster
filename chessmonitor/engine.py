import os, chess, chess.engine

class UCIEngine:
    def __init__(self, path="", depth=14, threads=4, hash_mb=512):
        self.path = path
        self.depth = depth
        self.threads = threads
        self.hash_mb = hash_mb
        self.engine = None
        self.error = ""

    def start(self):
        self.stop()
        if not self.path or not os.path.isfile(self.path):
            self.error = "Engine executable not found. Set the Stockfish path in Settings."
            return False
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.path)
            opts = self.engine.options
            config = {}
            if "Threads" in opts: config["Threads"] = self.threads
            if "Hash" in opts: config["Hash"] = self.hash_mb
            if config: self.engine.configure(config)
            self.error = ""
            return True
        except Exception as e:
            self.error = str(e)
            self.engine = None
            return False

    def stop(self):
        if self.engine:
            try: self.engine.quit()
            except Exception: pass
        self.engine = None

    def analyse(self, board, multipv=5):
        if not self.engine and not self.start():
            return [], self.error
        try:
            infos = self.engine.analyse(board, chess.engine.Limit(depth=self.depth), multipv=multipv)
            if isinstance(infos, dict): infos = [infos]
            out = []
            for info in infos:
                pv = info.get("pv", [])
                if not pv: continue
                score = info["score"].pov(board.turn).score(mate_score=100000)
                temp = board.copy()
                san = temp.san(pv[0])
                line = []
                for mv in pv[:8]:
                    # SAN must be generated from the position before this move.
                    line.append(temp.san(mv))
                    temp.push(mv)
                out.append({"move": pv[0].uci(), "san": san, "cp": score, "depth": info.get("depth", self.depth), "pv": " ".join(line)})
            return out, ""
        except Exception as e:
            self.error = str(e)
            return [], self.error
