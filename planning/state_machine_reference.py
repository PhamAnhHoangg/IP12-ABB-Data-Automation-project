"""IP12 palletising state machine: reference implementation (simulation).

Flow:
  IDLE -> DETECT -> SELECT -> PLAN -> PICK -> PLACE -> VERIFY -> DETECT ...
                                 \\-> RELOCATE_PICK -> RELOCATE_PLACE -> PICK (new cube)
  VERIFY -> DONE when no cubes are left or the pallet is full.
  Any state -> ERROR on a failure.

The camera, robot and scoring are stubs so the logic can be tested without hardware.
Replace the methods marked HARDWARE / AI with the real WP1/WP2 code.
Standard library only.  Run:  python planning/state_machine_reference.py
"""
from dataclasses import dataclass, field
from enum import Enum, auto

# ---- settings (WP4 can tune these) -----------------------------------------
GRID_ROWS, GRID_COLS = "ABC", 4          # 480 x 360 mm pallet, 120 mm cells (A1..C4)
MAX_PAYLOAD_KG = 4.0                     # WP4 rule 1 (minus gripper mass in reality)
SWAP_MIN_GAIN = 2.0                      # only re-arrange if the score improves this much
MAX_RELOCATIONS_PER_CUBE = 1             # a moved cube is never moved again (no endless loop)
MAX_RELOCATIONS_TOTAL = 3                # per pallet


class S(Enum):
    IDLE = auto(); DETECT = auto(); SELECT = auto(); PLAN = auto()
    PICK = auto(); PLACE = auto(); VERIFY = auto()
    RELOCATE_PICK = auto(); RELOCATE_PLACE = auto()
    DONE = auto(); ERROR = auto()


@dataclass
class Cube:
    id: str
    color: str
    weight_kg: float
    priority: int            # 1 = most important (from color/QR, WP4)
    relocations: int = 0


@dataclass
class World:
    """Simulated table + pallet. Replace with camera/robot feedback."""
    waiting: list                                   # cubes on the table
    pallet: dict = field(default_factory=dict)      # slot -> Cube
    slots: list = field(default_factory=lambda: [f"{r}{c}" for r in GRID_ROWS for c in range(1, GRID_COLS + 1)])


# @ip12:state_machine  reference palletising state machine (simulation)
class Palletiser:
    def __init__(self, world, log=print):
        self.w, self.log = world, log
        self.state = S.IDLE
        self.cube = None            # cube being handled
        self.target = None          # slot for self.cube
        self.reloc = None           # (cube, from_slot, to_slot) when re-arranging
        self.total_relocations = 0
        self.error = None

    # ---- AI / scoring (WP2/WP4): replace with the real model or rule score ----
    def score(self, cube, slot):
        """Higher = better fit. Demo: heavy + high-priority cubes prefer row A (near robot)."""
        row = GRID_ROWS.index(slot[0])
        col = int(slot[1:])
        return cube.weight_kg * (3 - row) + (4 - cube.priority) * (3 - row) * 0.5 - col * 0.1

    def gates_ok(self, cube, slot):
        """WP4 pre-placement gates (single layer demo: payload + boundary)."""
        return cube.weight_kg <= MAX_PAYLOAD_KG and slot in self.w.slots

    # ---- HARDWARE stubs (WP1/WP2) ---------------------------------------------
    def camera_detect(self):
        return list(self.w.waiting)

    def robot_move(self, cube, src, dst):
        self.log(f"    robot: {cube.id} {src} -> {dst}")
        return True

    # ---- state machine ----------------------------------------------------------
    def step(self):
        try:
            handler = getattr(self, f"_{self.state.name.lower()}")
            nxt = handler()
        except Exception as e:                   # any failure -> ERROR
            self.error, nxt = str(e), S.ERROR
        if nxt != self.state:
            self.log(f"{self.state.name:<15} -> {nxt.name}")
        self.state = nxt
        return nxt

    def run(self, max_steps=500):
        for _ in range(max_steps):
            if self.step() in (S.DONE, S.ERROR):
                break
        return self.state

    def _idle(self):
        return S.DETECT

    def _detect(self):
        self.seen = self.camera_detect()
        free = [s for s in self.w.slots if s not in self.w.pallet]
        return S.SELECT if self.seen and free else S.DONE

    def _select(self):
        ok = [c for c in self.seen if c.weight_kg <= MAX_PAYLOAD_KG]
        if not ok:
            raise RuntimeError("all detected cubes exceed payload, operator needed")
        self.cube = min(ok, key=lambda c: (c.priority, -c.weight_kg))
        self.log(f"    selected {self.cube.id} ({self.cube.color}, {self.cube.weight_kg} kg, prio {self.cube.priority})")
        return S.PLAN

    def _plan(self):
        c = self.cube
        best = max((s for s in self.w.slots if self.gates_ok(c, s)), key=lambda s: self.score(c, s))
        free = [s for s in self.w.slots if s not in self.w.pallet and self.gates_ok(c, s)]
        if best in self.w.pallet:
            occ = self.w.pallet[best]
            gain = self.score(c, best) - self.score(occ, best)
            elsewhere = [s for s in free if s != best]
            can_move = (occ.relocations < MAX_RELOCATIONS_PER_CUBE
                        and self.total_relocations < MAX_RELOCATIONS_TOTAL
                        and elsewhere)
            if gain >= SWAP_MIN_GAIN and can_move:
                to = max(elsewhere, key=lambda s: self.score(occ, s))
                self.reloc = (occ, best, to)
                self.target = best
                self.log(f"    swap: {c.id} fits {best} better than {occ.id} (gain {gain:.1f}); move {occ.id} -> {to}")
                return S.RELOCATE_PICK
        if not free:
            return S.DONE
        self.target = max(free, key=lambda s: self.score(c, s))
        self.log(f"    plan: {c.id} -> {self.target}")
        return S.PICK

    def _relocate_pick(self):
        occ, src, _ = self.reloc
        return S.RELOCATE_PLACE if self.robot_move(occ, src, "gripper") else S.ERROR

    def _relocate_place(self):
        occ, src, dst = self.reloc
        if not self.robot_move(occ, "gripper", dst):
            return S.ERROR
        del self.w.pallet[src]
        self.w.pallet[dst] = occ
        occ.relocations += 1
        self.total_relocations += 1
        self.reloc = None
        return S.PICK                        # now pick the new cube for the freed slot

    def _pick(self):
        return S.PLACE if self.robot_move(self.cube, "table", "gripper") else S.ERROR

    def _place(self):
        if not self.robot_move(self.cube, "gripper", self.target):
            return S.ERROR
        self.w.pallet[self.target] = self.cube
        self.w.waiting.remove(self.cube)
        return S.VERIFY

    def _verify(self):
        # HARDWARE: camera checks the cube is in the slot; here it always is
        if self.w.pallet.get(self.target) is not self.cube:
            raise RuntimeError(f"verify failed for {self.cube.id} at {self.target}")
        self.cube = self.target = None
        return S.DETECT

    def _done(self):
        return S.DONE

    def _error(self):
        self.log(f"    ERROR: {self.error}")
        return S.ERROR


if __name__ == "__main__":
    # cubes arrive in an order that forces a re-arrange: a light cube first, then a heavy one
    cubes = [
        Cube("c1", "blue", 1.0, priority=2),
        Cube("c2", "green", 0.5, priority=3),
        Cube("c3", "red", 3.0, priority=1),   # heavy, top priority -> wants A1
    ]
    world = World(waiting=[cubes[0], cubes[1]])
    sm = Palletiser(world)
    sm.run()
    print("\n-- heavy red cube arrives later --")
    world.waiting.append(cubes[2])
    sm.state = S.DETECT
    final = sm.run()
    print("\nfinal state:", final.name)
    print("pallet:", {s: c.id for s, c in sorted(world.pallet.items())})
