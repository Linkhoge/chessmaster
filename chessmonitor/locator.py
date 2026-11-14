import cv2, numpy as np

# The edge contour sits a little inside the playing area, so the crop looks
# zoomed in and clips the outer squares. Grow the box by this fraction of the
# shorter side, on every side, and clamp it to the frame.
BOARD_CROP_MARGIN = 0.03

def expand_board_rect(x, y, bw, bh, frame_w, frame_h, margin=BOARD_CROP_MARGIN):
    """Return x,y,w,h expanded outward by `margin` and clamped to the frame."""
    pad=int(round(min(bw, bh)*margin))
    x0=max(0, int(x)-pad)
    y0=max(0, int(y)-pad)
    x1=min(int(frame_w), int(x)+int(bw)+pad)
    y1=min(int(frame_h), int(y)+int(bh)+pad)
    if x1<=x0 or y1<=y0:
        return int(x), int(y), int(bw), int(bh)
    return x0, y0, x1-x0, y1-y0

def locate_chessboard(frame_rgb):
    """The v0.4 window-local edge/grid detector, returning x,y,w,h,score."""
    rgb=np.asarray(frame_rgb)
    h,w=rgb.shape[:2]
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    edges=cv2.Canny(cv2.GaussianBlur(gray,(5,5),0),45,130)
    horizontal=cv2.morphologyEx(edges,cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT,(max(12,w//45),1)))
    vertical=cv2.morphologyEx(edges,cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(12,h//45))))
    combined=cv2.dilate(cv2.bitwise_or(horizontal,vertical),np.ones((3,3),np.uint8),iterations=2)
    contours,_=cv2.findContours(combined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    candidates=[]
    for c in contours:
        x,y,bw,bh=cv2.boundingRect(c);area=bw*bh;ratio=bw/max(1,bh)
        if area<w*h*.012 or area>w*h*.88 or not .72<=ratio<=1.38:continue
        roi=gray[y:y+bh,x:x+bw]
        if roi.size==0:continue
        gx=cv2.Sobel(roi,cv2.CV_32F,1,0,ksize=3)
        gy=cv2.Sobel(roi,cv2.CV_32F,0,1,ksize=3)
        candidates.append((float(np.mean(np.abs(gx))+np.mean(np.abs(gy)))*area,(x,y,bw,bh)))
    if not candidates:return None
    candidates.sort(reverse=True,key=lambda a:a[0])
    score,(x,y,bw,bh)=candidates[0]
    x0,y0,ew,eh=expand_board_rect(x,y,bw,bh,w,h)
    return (x0,y0,ew,eh,float(score))

def square_centres(rect,orientation="white"):
    x,y,w,h=rect[:4];out={}
    for f in range(8):
        for r in range(8):
            col,row=(f,7-r) if orientation=="white" else (7-f,r)
            out[f"{chr(97+f)}{r+1}"]=(x+(col+.5)*w/8,y+(row+.5)*h/8)
    return out
