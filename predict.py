"""Use a trained model to predict the opponent's next move.

    python predict.py --model model.pt            # starting position
    python predict.py --model model.pt --fen "<FEN>"

In the bot, call `predict_moves(model, board)` at the user's turns in the
search tree and weight each reply by its probability (expectimax).
"""
import argparse

import chess
import torch

from chess_env import encode_board, index_to_move, legal_move_mask
from model import MovePredictor


def load_model(path, device="cpu"):
    ckpt = torch.load(path, map_location=device)
    model = MovePredictor(ckpt["channels"], ckpt["blocks"]).to(device)
    model.load_state_dict(ckpt["state"])
    model.eval()
    return model


def predict_moves(model, board: chess.Board, device="cpu"):
    """Return [(move, probability), ...] over legal moves, most likely first."""
    x = torch.from_numpy(encode_board(board)).float().unsqueeze(0).to(device)
    with torch.no_grad():
        logits = model(x)[0].cpu()
    mask = torch.from_numpy(legal_move_mask(board))
    logits[~mask] = float("-inf")
    probs = torch.softmax(logits, dim=0)
    out = []
    for idx in torch.nonzero(mask).flatten().tolist():
        move = index_to_move(idx, board)
        if move is not None:
            out.append((move, probs[idx].item()))
    return sorted(out, key=lambda t: -t[1])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="model.pt")
    ap.add_argument("--fen", default=chess.STARTING_FEN)
    args = ap.parse_args()
    board = chess.Board(args.fen)
    for move, p in predict_moves(load_model(args.model), board)[:5]:
        print(f"{board.san(move):8s} {p:.1%}")
