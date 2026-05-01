# Requirements: none
import json
import random
from pathlib import Path

State = tuple[int, int, int]


class QLearningAgent:
    def __init__(
        self,
        qtable_path: str = "qtable.json",
        alpha: float = 0.1,
        epsilon: float = 1.0,
        epsilon_min: float = 0.05,
        epsilon_decay: float = 0.95,
    ) -> None:
        self.alpha = alpha
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.qtable_path = Path(qtable_path)
        self.qtable = self._load_qtable()

    @staticmethod
    def _initial_qtable() -> dict[str, list[float]]:
        return {
            f"{a}_{b}_{c}": [0.0, 0.0, 0.0, 0.0]
            for a in range(3)
            for b in range(3)
            for c in range(3)
        }

    def _load_qtable(self) -> dict[str, list[float]]:
        qtable = self._initial_qtable()
        if not self.qtable_path.exists():
            return qtable
        payload = json.loads(self.qtable_path.read_text(encoding="utf-8"))
        for key, values in payload.items():
            qtable[str(key)] = [float(value) for value in values]
        return qtable

    @staticmethod
    def state_key(state: State) -> str:
        return "_".join(str(value) for value in state)

    def _values(self, state: State) -> list[float]:
        key = self.state_key(state)
        self.qtable.setdefault(key, [0.0, 0.0, 0.0, 0.0])
        return self.qtable[key]

    def select_action(self, state: State) -> int:
        values = self._values(state)
        if random.random() < self.epsilon:
            return random.randrange(4)
        best_value = max(values)
        return min(index for index, value in enumerate(values) if value == best_value)

    def update(self, state: State, action: int, reward: float) -> None:
        values = self._values(state)
        values[action] = values[action] + self.alpha * (reward - values[action])

    def decay_epsilon(self) -> None:
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    def save(self) -> None:
        self.qtable_path.write_text(json.dumps(self.qtable, indent=2), encoding="utf-8")
