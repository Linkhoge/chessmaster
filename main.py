from chessmonitor.config import load_hf_token
load_hf_token()

from chessmonitor.app import main
if __name__ == "__main__":
    main()
