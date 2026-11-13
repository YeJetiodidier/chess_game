"""Online, per-player adaptation for the neural move predictor.

Every named player gets a personal copy of the network head.  The shared
trunk (stem/body/reduce) stays frozen, which keeps updates fast on a CPU.

Two learning signals are used:

* Supervised - every few recorded moves the head is fine-tuned on that
  player's recent moves, so predictions drift toward their style.
* Reinforcement - when a game ends the moves of that game are replayed with
  REINFORCE, using the game result (+1 win / 0 draw / -1 loss) as reward.
  This lets the model learn *which* of the player's moves actually win.

State lives in ``profiles/<player>/``:

    head.pt          personal head weights
    meta.json        counters shown in the UI
    history.jsonl    append-only move / undo / result events
"""
import json
import os
import re
import threading
import time
from collections import deque

import chess
import numpy as np
import torch
import torch.nn.functional as F

from chess_env import encode_board, index_to_move, legal_move_mask, move_to_index
from predict import load_model

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")

MAX_BUFFER = 5000
UPDATE_EVERY = 8
SUPERVISED_BATCH = 96
SUPERVISED_LR = 1e-3
RL_BATCH_STEPS = 4
RL_LR = 5e-4
ANCHOR = 2e-4          # L2 pull toward the base head (prevents forgetting)
GAMMA = 0.99           # reward discount across plies in a game


def slugify(name):
    """Turn a display name into a safe directory name."""
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", (name or "").strip())
    s = s.strip("_")[:40]
    return s or "guest"


def _outcome_value(result):
    if isinstance(result, (int, float)):
        return max(-1.0, min(1.0, float(result)))
    return {"win": 1.0, "loss": -1.0, "draw": 0.0,
            "1-0": 1.0, "0-1": -1.0, "1/2-1/2": 0.0}.get(str(result).lower(), 0.0)


class PlayerProfile:
    def __init__(self, name, base_model, device="cpu", base_sig=""):
        self.name = (name or "Guest").strip()[:40] or "Guest"
        self.slug = slugify(self.name)
        self.dir = os.path.join(PROFILES_DIR, self.slug)
        os.makedirs(self.dir, exist_ok=True)

        self.base = base_model
        self.device = device
        self.base_sig = base_sig
        self.head = torch.nn.Linear(*self._head_shape(base_model)).to(device)
        self.head.load_state_dict(base_model.head.state_dict())
        self.head.eval()

        self.lock = threading.RLock()
        self.update_lock = threading.Lock()
        self.buffer = deque(maxlen=MAX_BUFFER)
        self.finished = set()
        self.pending = 0
        self.meta = {
            "name": self.name, "slug": self.slug, "moves": 0, "games": 0,
            "wins": 0, "losses": 0, "draws": 0, "updates": 0,
            "created": time.time(), "last_seen": time.time(),
        }
        self._load()

    @staticmethod
    def _head_shape(base_model):
        return base_model.head.in_features, base_model.head.out_features

    # ------------------------------------------------------------------ io
    @property
    def head_path(self):
        return os.path.join(self.dir, "head.pt")

    @property
    def meta_path(self):
        return os.path.join(self.dir, "meta.json")

    @property
    def history_path(self):
        return os.path.join(self.dir, "history.jsonl")

    def _load(self):
        if os.path.exists(self.meta_path):
            try:
                with open(self.meta_path, "r", encoding="utf-8") as fh:
                    self.meta.update(json.load(fh))
            except Exception:
                pass

        if os.path.exists(self.head_path):
            try:
                ckpt = torch.load(self.head_path, map_location=self.device)
                same_shape = list(ckpt.get("shape", [])) == list(self._head_shape(self.base))
                same_base = ckpt.get("base_sig") in (None, "", self.base_sig)
                if same_shape and same_base:
                    self.head.load_state_dict(ckpt["state"])
                    self.head.eval()
            except Exception as exc:
                print(f"[Profile:{self.slug}] head load failed: {exc}")

        try:
            self._load_history()
        except Exception as exc:
            print(f"[Profile:{self.slug}] history load failed: {exc}")

        self.meta["name"] = self.name
        self._save_meta()

    def _load_history(self):
        if not os.path.exists(self.history_path):
            return
        with open(self.history_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                self._apply_event(event, persist=False, count_stats=False)
        self._save_meta()

    def _apply_event(self, event, persist=True, count_stats=True):
        kind = event.get("t")
        if kind == "m":
            self.buffer.append({
                "fen": event.get("fen", ""),
                "uci": event.get("uci", ""),
                "game": event.get("g", ""),
                "color": event.get("c", ""),
                "ts": event.get("ts", time.time()),
                "reward": None,
                "done": False,
            })
        elif kind == "u":
            game = event.get("g")
            removed = False
            for i in range(len(self.buffer) - 1, -1, -1):
                if self.buffer[i]["game"] == game and not self.buffer[i]["done"]:
                    del self.buffer[i]
                    removed = True
                    break
            if removed and count_stats:
                self.meta["moves"] = max(0, self.meta["moves"] - 1)
        elif kind == "r":
            game = event.get("g")
            color = event.get("c", "")
            outcome = _outcome_value(event.get("outcome", "draw"))
            samples = [s for s in self.buffer
                       if s["game"] == game and (not color or s["color"] == color)
                       and not s["done"]]
            self._assign_rewards(samples, outcome)
            key = (game, color)
            if count_stats and key not in self.finished:
                self.meta["games"] += 1
                if outcome > 0:
                    self.meta["wins"] += 1
                elif outcome < 0:
                    self.meta["losses"] += 1
                else:
                    self.meta["draws"] += 1
            self.finished.add(key)
        if persist:
            self._append_event(event)

    def _append_event(self, event):
        with open(self.history_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, separators=(",", ":")) + "\n")

    def _save_meta(self):
        tmp = self.meta_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.meta, fh)
        os.replace(tmp, self.meta_path)

    def _save_head(self):
        tmp = self.head_path + ".tmp"
        payload = {"state": self.head.state_dict(),
                   "shape": list(self._head_shape(self.base)),
                   "base_sig": self.base_sig}
        torch.save(payload, tmp)
        os.replace(tmp, self.head_path)

    def _compress_history_if_needed(self):
        if not os.path.exists(self.history_path):
            return
        if os.path.getsize(self.history_path) < 8 * 1024 * 1024:
            return
        events = []
        for sample in self.buffer:
            events.append({"t": "m", "fen": sample["fen"], "uci": sample["uci"],
                           "g": sample["game"], "c": sample["color"],
                           "ts": sample["ts"]})
        tmp = self.history_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event, separators=(",", ":")) + "\n")
        os.replace(tmp, self.history_path)

    # ------------------------------------------------------------- helpers
    def _features(self, boards):
        x = torch.from_numpy(np.stack([encode_board(b) for b in boards])).float()
        with torch.no_grad():
            return self.base.reduce(self.base.body(self.base.stem(x.to(self.device))))

    @staticmethod
    def _assign_rewards(samples, outcome):
        n = len(samples)
        for i, sample in enumerate(samples):
            sample["reward"] = float(outcome) * (GAMMA ** (n - 1 - i))
            sample["done"] = True

    def stats(self):
        with self.lock:
            return dict(self.meta)

    # ------------------------------------------------------------ learning
    def predict(self, board, topn=5):
        head = self.head
        features = self._features([board])
        with torch.no_grad():
            logits = head(features)[0].cpu()
        mask = torch.from_numpy(legal_move_mask(board))
        logits[~mask] = float("-inf")
        probs = torch.softmax(logits, dim=0)
        out = []
        for idx in torch.nonzero(mask).flatten().tolist():
            move = index_to_move(idx, board)
            if move is not None:
                out.append((move, probs[idx].item()))
        return sorted(out, key=lambda t: -t[1])[:topn]

    def record_move(self, fen, uci, game, color=None):
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError("illegal move")
        event = {"t": "m", "fen": fen, "uci": uci, "g": game or "",
                 "c": color or "", "ts": time.time()}
        with self.lock:
            self._apply_event(event)
            self.meta["moves"] += 1
            self.meta["last_seen"] = time.time()
            self.pending += 1
            self._save_meta()
        self._compress_history_if_needed()
        if self.pending >= UPDATE_EVERY:
            threading.Thread(target=self._supervised_worker, daemon=True).start()
        return self.stats()

    def undo_move(self, game):
        event = {"t": "u", "g": game or ""}
        with self.lock:
            self._apply_event(event)
            self.meta["last_seen"] = time.time()
            self._save_meta()
        return self.stats()

    def record_result(self, game, outcome, color=None):
        value = _outcome_value(outcome)
        event = {"t": "r", "g": game or "", "c": color or "", "outcome": value}
        samples = []
        with self.lock:
            self._apply_event(event)
            samples = [s for s in self.buffer
                       if s["game"] == (game or "") and s["done"]
                       and s.get("reward") is not None
                       and (not color or s["color"] == color)]
            self.meta["last_seen"] = time.time()
            self._save_meta()
            self._save_head()
        if samples:
            threading.Thread(target=self._policy_worker,
                             args=(list(samples), value), daemon=True).start()
        return self.stats()

    def _supervised_worker(self):
        if not self.update_lock.acquire(blocking=False):
            return
        try:
            while True:
                with self.lock:
                    if self.pending < UPDATE_EVERY:
                        break
                    self.pending = 0
                    samples = list(self.buffer)[-SUPERVISED_BATCH:]
                self._train_supervised(samples)
        finally:
            self.update_lock.release()

    def _train_supervised(self, samples):
        boards, labels = [], []
        for sample in samples:
            try:
                board = chess.Board(sample["fen"])
                move = chess.Move.from_uci(sample["uci"])
                if move not in board.legal_moves:
                    continue
                boards.append(board)
                labels.append(move_to_index(move, board))
            except Exception:
                continue
        if len(boards) < 8:
            return

        features = self._features(boards)
        labels = torch.tensor(labels, dtype=torch.long, device=self.device)

        head = torch.nn.Linear(*self._head_shape(self.base)).to(self.device)
        head.load_state_dict(self.head.state_dict())
        head.train()
        opt = torch.optim.Adam(head.parameters(), lr=SUPERVISED_LR)
        w0 = self.base.head.weight.detach()
        b0 = self.base.head.bias.detach()

        for _ in range(2):
            perm = torch.randperm(len(labels), device=self.device)
            loss = F.cross_entropy(head(features[perm]), labels[perm])
            loss = loss + ANCHOR * (F.mse_loss(head.weight, w0) +
                                    F.mse_loss(head.bias, b0))
            opt.zero_grad()
            loss.backward()
            opt.step()

        head.eval()
        with self.lock:
            self.head = head
            self.meta["updates"] += 1
            self._save_head()
            self._save_meta()

    def _policy_worker(self, samples, outcome):
        if outcome == 0.0 or len(samples) < 4:
            return
        if not self.update_lock.acquire(blocking=False):
            return
        try:
            self._train_policy(samples)
        finally:
            self.update_lock.release()

    def _train_policy(self, samples):
        boards, labels, masks, rewards = [], [], [], []
        for sample in samples:
            try:
                board = chess.Board(sample["fen"])
                move = chess.Move.from_uci(sample["uci"])
                if move not in board.legal_moves:
                    continue
                boards.append(board)
                labels.append(move_to_index(move, board))
                masks.append(legal_move_mask(board))
                rewards.append(sample.get("reward") or 0.0)
            except Exception:
                continue
        if len(boards) < 4:
            return

        features = self._features(boards)
        labels = torch.tensor(labels, dtype=torch.long, device=self.device)
        masks = torch.from_numpy(np.stack(masks)).to(self.device)
        rewards = torch.tensor(rewards, dtype=torch.float32, device=self.device)
        advantage = rewards - rewards.mean()

        head = torch.nn.Linear(*self._head_shape(self.base)).to(self.device)
        head.load_state_dict(self.head.state_dict())
        head.train()
        opt = torch.optim.Adam(head.parameters(), lr=RL_LR)

        for _ in range(RL_BATCH_STEPS):
            logits = head(features).masked_fill(~masks, -1e9)
            logp = torch.log_softmax(logits, dim=1)
            chosen = logp.gather(1, labels[:, None]).squeeze(1)
            entropy = -(logp.exp() * logp).sum(dim=1).mean()
            loss = -(chosen * advantage).mean() - 0.01 * entropy
            opt.zero_grad()
            loss.backward()
            opt.step()

        head.eval()
        with self.lock:
            self.head = head
            self.meta["updates"] += 1
            self._save_head()
            self._save_meta()


class PlayerStore:
    """Keeps one adaptor per player name and loads them lazily."""

    def __init__(self, model_path=os.path.join(BASE_DIR, "model.pt"), device="cpu"):
        self.device = device
        self.base = load_model(model_path, device=device)
        self.base.eval()
        try:
            stat = os.stat(model_path)
            self.base_sig = f"{stat.st_size}:{int(stat.st_mtime)}"
        except OSError:
            self.base_sig = ""
        self.players = {}
        self.lock = threading.Lock()

    def get(self, name):
        key = slugify(name or "Guest")
        with self.lock:
            profile = self.players.get(key)
            if profile is None:
                profile = PlayerProfile(name or "Guest", self.base, self.device,
                                        self.base_sig)
                self.players[key] = profile
            return profile

    def predict(self, name, board, topn=5):
        return self.get(name).predict(board, topn)

    def record_move(self, name, fen, uci, game, color=None):
        return self.get(name).record_move(fen, uci, game, color)

    def undo_move(self, name, game):
        return self.get(name).undo_move(game)

    def record_result(self, name, game, outcome, color=None):
        return self.get(name).record_result(game, outcome, color)

    def stats(self, name):
        return self.get(name).stats()

    def profiles(self):
        out = []
        if not os.path.isdir(PROFILES_DIR):
            return out
        for entry in sorted(os.listdir(PROFILES_DIR)):
            path = os.path.join(PROFILES_DIR, entry)
            if not os.path.isdir(path):
                continue
            meta_path = os.path.join(path, "meta.json")
            meta = {"slug": entry, "name": entry, "moves": 0, "games": 0}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as fh:
                        meta.update(json.load(fh))
                except Exception:
                    pass
            out.append(meta)
        return out
