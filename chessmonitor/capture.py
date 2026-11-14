import threading, time
from mss import mss
from PIL import Image
try:
    import pygetwindow as gw
except Exception:
    gw=None

class LiveCapture:
    """Capture only a selected visible application window on the primary display."""
    def __init__(self, monitor=0, region=None, interval=.35):
        self.interval=interval;self.latest=None;self.latest_origin=(0,0)
        self.running=False;self.thread=None;self.error=""
        self.target_title=None;self.target_hwnd=None
    def list_windows(self):
        if gw is None:return []
        out=[]
        try:
            for w in gw.getAllWindows():
                title=(w.title or "").strip()
                if title and w.width>120 and w.height>100 and not w.isMinimized:
                    out.append((f"{title[:75]}  [{w.width}×{w.height}]",title,getattr(w,"_hWnd",None)))
        except Exception as e:self.error=str(e)
        return out
    def set_target(self,title,hwnd=None):
        self.target_title=title;self.target_hwnd=hwnd
    def _get_window(self):
        if gw is None:return None
        try:
            for w in gw.getAllWindows():
                if self.target_hwnd is not None and getattr(w,"_hWnd",None)==self.target_hwnd:
                    return None if w.isMinimized or w.width<=0 or w.height<=0 else w
            matches=[w for w in gw.getWindowsWithTitle(self.target_title or "") if not w.isMinimized and w.width>0]
            return matches[0] if matches else None
        except Exception:return None
    def start(self):
        if self.running:return
        self.running=True;self.thread=threading.Thread(target=self._loop,daemon=True);self.thread.start()
    def stop(self):
        self.running=False
        if self.thread:self.thread.join(timeout=2)
    def _loop(self):
        try:
            with mss() as sct:
                while self.running:
                    w=self._get_window()
                    if w is None:
                        self.error="Selected window is unavailable or minimised."
                        time.sleep(self.interval);continue
                    left,top=int(w.left),int(w.top)
                    # Restrict target to primary display bounds.
                    mon=sct.monitors[1]
                    left=max(left,mon["left"]);top=max(top,mon["top"])
                    right=min(int(w.left+w.width),mon["left"]+mon["width"])
                    bottom=min(int(w.top+w.height),mon["top"]+mon["height"])
                    if right<=left or bottom<=top:
                        self.error="Selected window is outside the primary display."
                        time.sleep(self.interval);continue
                    rect={"left":left,"top":top,"width":right-left,"height":bottom-top}
                    shot=sct.grab(rect)
                    self.latest=Image.frombytes("RGB",shot.size,shot.rgb)
                    self.latest_origin=(left,top);self.error=""
                    time.sleep(self.interval)
        except Exception as e:self.error=str(e);self.running=False
