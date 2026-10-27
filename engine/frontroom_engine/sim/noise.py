"""Keyed noise tape: every random draw is addressed by (purpose, tick, player).

Drawing noise in call order would make a counterfactual replay drift: once one action changes,
every later draw shifts by however many calls the new branch made. Here each value is a pure
function of its key, so a factual run and its counterfactual see identical noise wherever they
ask the same question at the same moment.

Values are generated in blocks of `CHUNK_TICKS` ticks per purpose from a seed derived from
(match seed, purpose, chunk, branch salt). A branch salt replaces the noise from a given tick
onwards, which is how scenario steering explores alternative futures from a checkpoint without
touching the past.
"""

from dataclasses import dataclass, field

import numpy as np

CHUNK_TICKS = 100
CACHE_BLOCKS = 256
GENERATOR_DOMAIN = 2
"""Extra seed word that keeps per-draw generator seeds disjoint from block seeds."""
MAX_SLOTS = 22
BEFORE_DECISION = frozenset({"steer", "lapse", "run", "tackle", "control"})
"""Purposes drawn earlier in a tick than the carrier's decision."""

PURPOSES: dict[str, int] = {
    "steer": 2,
    "decide": 16,
    "timing": 2,
    "pass": 3,
    "control": 2,
    "shot": 4,
    "keeper": 3,
    "tackle": 4,
    "lapse": 2,
    "run": 2,
    "referee": 4,
    "restart": 4,
}


@dataclass
class NoiseTape:
    seed: int
    branches: tuple[tuple[int, int], ...] = ()
    """(first tick, salt) pairs, sorted by tick; ticks before the first branch use salt 0."""
    decision_branch: tuple[int, int] | None = None
    """(decision tick, salt): resample everything that happens after a decision made at that tick.

    Movement and tackle noise of the decision tick itself stay as they were, because they are drawn
    before the carrier decides; keeping them is what lets a counterfactual force a different option
    from exactly the same situation."""
    _cache: dict[tuple[str, int, int, str], np.ndarray] = field(default_factory=dict, repr=False)

    def branched(self, tick: int, salt: int) -> "NoiseTape":
        """A tape identical to this one before `tick` and freshly salted from `tick` on."""
        kept = tuple((t, s) for t, s in self.branches if t < tick)
        tape = NoiseTape(self.seed, (*kept, (tick, salt)))
        tape._cache = self._cache
        return tape

    def resampled_after_decision(self, tick: int, salt: int) -> "NoiseTape":
        """This tape with fresh noise for everything downstream of a decision taken at `tick`."""
        tape = NoiseTape(self.seed, self.branches, (tick, salt))
        tape._cache = self._cache
        return tape

    def _salt(self, tick: int, purpose: str) -> int:
        salt = 0
        for start, branch_salt in self.branches:
            if tick >= start:
                salt = branch_salt
        if self.decision_branch is not None:
            start, branch_salt = self.decision_branch
            if tick >= start + (purpose in BEFORE_DECISION):
                salt = branch_salt
        return salt

    def _block(self, purpose: str, tick: int, kind: str) -> np.ndarray:
        chunk = tick // CHUNK_TICKS
        salt = self._salt(tick, purpose)
        key = (purpose, chunk, salt, kind)
        block = self._cache.get(key)
        if block is None:
            purpose_index = list(PURPOSES).index(purpose)
            sequence = np.random.SeedSequence([self.seed, purpose_index, chunk, salt, int(kind == "normal")])
            rng = np.random.default_rng(sequence)
            shape = (CHUNK_TICKS, MAX_SLOTS, PURPOSES[purpose])
            if kind == "uniform":
                block = rng.random(shape, dtype=np.float32)
            else:
                block = rng.standard_normal(shape, dtype=np.float32)
            if len(self._cache) >= CACHE_BLOCKS:
                del self._cache[next(iter(self._cache))]
            self._cache[key] = block
        return block[tick % CHUNK_TICKS]

    def uniform(self, purpose: str, tick: int, slot: int) -> np.ndarray:
        """Uniform(0, 1) values for one player; the vector length is fixed per purpose."""
        return self._block(purpose, tick, "uniform")[slot]

    def normal(self, purpose: str, tick: int, slot: int) -> np.ndarray:
        return self._block(purpose, tick, "normal")[slot]

    def normal_all(self, purpose: str, tick: int) -> np.ndarray:
        """Standard normals for every slot at once, shape (22, dims)."""
        return self._block(purpose, tick, "normal")

    def uniform_all(self, purpose: str, tick: int) -> np.ndarray:
        return self._block(purpose, tick, "uniform")

    def gumbel(self, purpose: str, tick: int, slot: int, count: int) -> np.ndarray:
        """Gumbel noise for a Gumbel-max choice among `count` options (count <= purpose width)."""
        u = self.uniform(purpose, tick, slot)[:count]
        return -np.log(-np.log(np.clip(u, 1e-12, 1 - 1e-12)))

    def generator(self, purpose: str, tick: int, slot: int) -> np.random.Generator:
        """A private generator for draws whose count varies, still addressed by (purpose, tick, slot)."""
        purpose_index = list(PURPOSES).index(purpose)
        return np.random.default_rng(
            [self.seed, purpose_index, tick, slot, self._salt(tick, purpose), GENERATOR_DOMAIN]
        )
