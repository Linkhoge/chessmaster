import unittest, chess
from chessmonitor.tracker import reconcile

class TrackerTests(unittest.TestCase):
    def test_detect_single_legal_move(self):
        b=chess.Board()
        d=b.copy(); d.push_uci("e2e4")
        path,msg=reconcile(b,d,2)
        self.assertIsNotNone(path)
        self.assertEqual([m.uci() for m in path],["e2e4"])
    def test_reject_unrelated_position(self):
        b=chess.Board()
        d=chess.Board()
        d.remove_piece_at(chess.E2)
        path,msg=reconcile(b,d,2)
        self.assertIsNone(path)

if __name__=="__main__": unittest.main()
