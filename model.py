import torch
import torch.nn as nn

from chess_env import NUM_MOVES, NUM_PLANES


class ResBlock(nn.Module):
    def __init__(self, ch):
        super().__init__()
        self.c1 = nn.Conv2d(ch, ch, 3, padding=1, bias=False)
        self.b1 = nn.BatchNorm2d(ch)
        self.c2 = nn.Conv2d(ch, ch, 3, padding=1, bias=False)
        self.b2 = nn.BatchNorm2d(ch)

    def forward(self, x):
        out = torch.relu(self.b1(self.c1(x)))
        out = self.b2(self.c2(out))
        return torch.relu(out + x)


class MovePredictor(nn.Module):
    """Board planes -> logits over 4096 (from, to) moves.

    `head` is the last layer: the part we fine-tune per user later.
    """

    def __init__(self, channels=64, blocks=4):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(NUM_PLANES, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(),
        )
        self.body = nn.Sequential(*[ResBlock(channels) for _ in range(blocks)])
        self.reduce = nn.Sequential(
            nn.Conv2d(channels, 32, 1), nn.BatchNorm2d(32), nn.ReLU(), nn.Flatten()
        )
        self.head = nn.Linear(32 * 64, NUM_MOVES)

    def forward(self, x):
        return self.head(self.reduce(self.body(self.stem(x))))
