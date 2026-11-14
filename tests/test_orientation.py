import os, tempfile, unittest
import numpy as np
from chessmonitor.locator import expand_board_rect, square_centres
from chessmonitor.vision import BoardVision

def painted_board(bottom="white", centre_pieces=False):
    """8x8 board. Light pieces on the named side, dark pieces on the other."""
    n=320
    img=np.zeros((n,n,3),np.uint8)
    sq=n//8
    light=np.array([210,180,140],np.uint8)
    dark=np.array([110,75,45],np.uint8)
    white=np.array([245,245,235],np.uint8)
    black=np.array([20,20,24],np.uint8)
    for row in range(8):
        for col in range(8):
            y0,x0=row*sq,col*sq
            img[y0:y0+sq,x0:x0+sq]=light if (row+col)%2==0 else dark
            occupied=row in (0,1,6,7) or (centre_pieces and row in (3,4))
            if not occupied:continue
            if row in (3,4):
                piece=white if (row+col)%2==0 else black
            elif bottom=="white":
                piece=white if row>=6 else black
            else:
                piece=black if row>=6 else white
            m=int(sq*0.30)
            img[y0+m:y0+sq-m, x0+m:x0+sq-m]=piece
    return img

class OrientationTests(unittest.TestCase):
    def test_white_pieces_at_the_bottom_are_white(self):
        self.assertEqual(BoardVision.infer_bottom_orientation(painted_board("white")),"white")

    def test_black_pieces_at_the_bottom_are_black(self):
        self.assertEqual(BoardVision.infer_bottom_orientation(painted_board("black")),"black")

    def test_empty_board_does_not_guess(self):
        blank=np.full((320,320,3),140,np.uint8)
        self.assertIsNone(BoardVision.infer_bottom_orientation(blank))
        self.assertFalse(BoardVision.looks_like_start_position(blank))

    def test_start_layout_is_recognised_and_a_crowded_centre_is_not(self):
        self.assertTrue(BoardVision.looks_like_start_position(painted_board("white")))
        self.assertFalse(BoardVision.looks_like_start_position(painted_board("white",centre_pieces=True)))

    def test_calibration_labels_the_bottom_pieces_as_the_player(self):
        img=painted_board("white")
        fd,path=tempfile.mkstemp(suffix=".npz");os.close(fd)
        try:
            vision=BoardVision(path)
            ok,msg=vision.auto_calibrate_start_position(img,"white")
            self.assertTrue(ok,msg)
            # Lab L is the first channel. The white-pawn class must be the bright set.
            white_l=float(vision.templates["P"][0][:,:,0].mean())
            black_l=float(vision.templates["p"][0][:,:,0].mean())
            self.assertGreater(white_l,black_l+20)
        finally:
            if os.path.exists(path):os.remove(path)

    def test_player_back_rank_is_the_bottom_of_the_screen(self):
        white=square_centres((0,0,80,80),"white")
        self.assertGreater(white["a1"][1],40)
        self.assertLess(white["a8"][1],40)
        black=square_centres((0,0,80,80),"black")
        self.assertGreater(black["a8"][1],40)
        self.assertLess(black["a1"][1],40)

    def test_crop_zooms_out_a_little_and_stays_inside_the_frame(self):
        x,y,w,h=expand_board_rect(100,80,200,200,1000,800,0.03)
        self.assertEqual((x,y,w,h),(94,74,212,212))
        self.assertEqual(expand_board_rect(0,0,50,50,60,55,0.5),(0,0,60,55))

if __name__=="__main__":
    unittest.main()
