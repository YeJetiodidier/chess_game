"""Chess environment + board/move encoding shared by training and the bot.

Everything is encoded from the point of view of the side to move: when it is
Black's turn the board is flipped vertically, so the network always sees "my
pieces moving up the board". This halves what the model has to learn.
"""
import chess
import numpy as np

NUM_PLANES = 18   # 12 piece planes + 4 castling + 1 en passant + 1 constant
NUM_MOVES = 4096  # from_square * 64 + to_square (promotions -> queen)


def _sq(square: int, flip: bool) -> int:
    return square ^ 56 if flip else square


def encode_board(board: chess.Board) -> np.ndarray:
    """Return a (18, 8, 8) uint8 array from the side-to-move's perspective."""
    me = board.turn
    flip = me == chess.BLACK
    planes = np.zeros((NUM_PLANES, 8, 8), dtype=np.uint8)

    for square, piece in board.piece_map().items():
        s = _sq(square, flip)
        offset = 0 if piece.color == me else 6
        planes[offset + piece.piece_type - 1, s // 8, s % 8] = 1

    planes[12].fill(board.has_kingside_castling_rights(me))
    planes[13].fill(board.has_queenside_castling_rights(me))
    planes[14].fill(board.has_kingside_castling_rights(not me))
    planes[15].fill(board.has_queenside_castling_rights(not me))
    if board.ep_square is not None:
        s = _sq(board.ep_square, flip)
        planes[16, s // 8, s % 8] = 1
    planes[17].fill(1)
    return planes


def move_to_index(move: chess.Move, board: chess.Board) -> int:
    flip = board.turn == chess.BLACK
    return _sq(move.from_square, flip) * 64 + _sq(move.to_square, flip)


def is_underpromotion(move: chess.Move) -> bool:
    return move.promotion is not None and move.promotion != chess.QUEEN


def index_to_move(index: int, board: chess.Board):
    """Decode an index to a legal move on this board (or None if illegal)."""
    flip = board.turn == chess.BLACK
    frm = _sq(index // 64, flip)
    to = _sq(index % 64, flip)
    move = chess.Move(frm, to)
    piece = board.piece_at(frm)
    if piece and piece.piece_type == chess.PAWN and chess.square_rank(to) in (0, 7):
        move.promotion = chess.QUEEN
    return move if move in board.legal_moves else None


def legal_move_mask(board: chess.Board) -> np.ndarray:
    mask = np.zeros(NUM_MOVES, dtype=bool)
    for move in board.legal_moves:
        if not is_underpromotion(move):
            mask[move_to_index(move, board)] = True
    return mask


class ChessEnv:
    """Small interface the bot / training code talks to."""

    def __init__(self):
        self.board = chess.Board()

    def reset(self) -> chess.Board:
        self.board = chess.Board()
        return self.board

    def legal_moves(self):
        return list(self.board.legal_moves)

    def step(self, move: chess.Move):
        self.board.push(move)
        return self.board, self.board.is_game_over()

    def result(self) -> str:
        return self.board.result(claim_draw=True)

    def observation(self) -> np.ndarray:
        return encode_board(self.board)
