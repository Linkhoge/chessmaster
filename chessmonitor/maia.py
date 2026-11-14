import sys, chess, chess.engine

class Maia3:
    def __init__(self, model="maia3-5m", elo=1500):
        self.model=model; self.elo=elo; self.engine=None; self.error=""
    def start(self):
        self.stop()
        cmd=[sys.executable,"-m","maia3.uci","--model",self.model,"--device","cpu","--no-use-amp","--use-uci-history","--elo",str(self.elo)]
        try:
            self.engine=chess.engine.SimpleEngine.popen_uci(cmd,timeout=180)
            # Maia-3 manages its own UCI options. Do not configure MultiPV here:
            # recent maia3-uci builds expose it as an automatically managed option.
            self.error=""; return True
        except Exception as e:
            self.error=str(e); self.engine=None; return False
    def stop(self):
        if self.engine:
            try:self.engine.quit()
            except Exception:pass
        self.engine=None
    def predict(self, board):
        if not self.engine and not self.start(): return [],self.error
        try:
            # Request one Maia prediction; its UCI wrapper controls its own candidate policy.
            infos=self.engine.analyse(board,chess.engine.Limit(nodes=1))
            if isinstance(infos,dict): infos=[infos]
            out=[]
            for info in infos:
                pv=info.get("pv",[])
                if not pv: continue
                b=board.copy(); san=b.san(pv[0])
                wdl=info.get("wdl")
                wdl_text=str(wdl) if wdl else "WDL unavailable"
                out.append({"uci":pv[0].uci(),"san":san,"wdl":wdl_text,"pv":" ".join(m.uci() for m in pv[:8])})
            return out,""
        except Exception as e:
            self.error=str(e); return [],self.error
