"""Stream a Lichess .pgn.zst file and turn it into training positions.

Usage:
    python prepare_data.py --input lichess_db_standard_rated_2024-01.pgn.zst \
        --output data.npz --min-elo 1000 --max-elo 1800 --max-positions 300000

The file is read directly from the compressed archive; nothing is unpacked to disk.
"""
import argparse
import io

import chess
import chess.pgn
import numpy as np
import zstandard as zstd
from tqdm import tqdm

from chess_env import NUM_PLANES, encode_board, is_underpromotion, move_to_index


def make_filter(min_elo, max_elo, speeds):
    def accept(headers):
        try:
            white, black = int(headers["WhiteElo"]), int(headers["BlackElo"])
        except (KeyError, ValueError):
            return False
        if not (min_elo <= white <= max_elo and min_elo <= black <= max_elo):
            return False
        event = headers.get("Event", "")
        if speeds and not any(s.lower() in event.lower() for s in speeds):
            return False
        return headers.get("Termination", "Normal") == "Normal"
    return accept


class FilteredBuilder(chess.pgn.GameBuilder):
    """Skips the move text of games whose headers do not pass the filter."""

    def __init__(self, accept):
        super().__init__()
        self.accept = accept

    def end_headers(self):
        if not self.accept(self.game.headers):
            return chess.pgn.SKIP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default="data.npz")
    ap.add_argument("--min-elo", type=int, default=1000)
    ap.add_argument("--max-elo", type=int, default=1800)
    ap.add_argument("--speeds", default="Blitz,Rapid,Classical",
                    help="comma-separated; matches the Event header")
    ap.add_argument("--max-positions", type=int, default=300_000)
    ap.add_argument("--skip-plies", type=int, default=0,
                    help="ignore the first N plies of each game")
    args = ap.parse_args()

    accept = make_filter(args.min_elo, args.max_elo,
                         [s for s in args.speeds.split(",") if s])
    X = np.zeros((args.max_positions, NUM_PLANES, 8, 8), dtype=np.uint8)
    y = np.zeros(args.max_positions, dtype=np.int16)
    n = games = 0

    with open(args.input, "rb") as fh:
        reader = zstd.ZstdDecompressor().stream_reader(fh)
        text = io.TextIOWrapper(reader, encoding="utf-8")
        bar = tqdm(total=args.max_positions, unit="pos")
        while n < args.max_positions:
            game = chess.pgn.read_game(text, Visitor=lambda: FilteredBuilder(accept))
            if game is None:
                break
            moves = list(game.mainline_moves())
            if not moves:
                continue
            games += 1
            board = game.board()
            for ply, move in enumerate(moves):
                if ply >= args.skip_plies and not is_underpromotion(move):
                    X[n] = encode_board(board)
                    y[n] = move_to_index(move, board)
                    n += 1
                    bar.update(1)
                    if n >= args.max_positions:
                        break
                board.push(move)
        bar.close()

    np.savez_compressed(args.output, X=X[:n], y=y[:n])
    print(f"Saved {n} positions from {games} games to {args.output}")


if __name__ == "__main__":
    main()
