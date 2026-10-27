"""Pitch geometry shared by the simulator, the extractor and the calibration code.

All coordinates are metres on a 105 x 68 pitch with the origin in a corner, matching
`common.schema.json#/$defs/PitchPoint`.
"""

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
CENTRE_X = PITCH_LENGTH / 2
CENTRE_Y = PITCH_WIDTH / 2

GOAL_WIDTH = 7.32
GOAL_HEIGHT = 2.44
GOAL_LEFT_POST = CENTRE_Y - GOAL_WIDTH / 2
GOAL_RIGHT_POST = CENTRE_Y + GOAL_WIDTH / 2

PENALTY_AREA_DEPTH = 16.5
PENALTY_AREA_HALF_WIDTH = 20.16
PENALTY_SPOT_DISTANCE = 11.0


def in_penalty_area(x: float, y: float, defending_goal_x: float) -> bool:
    """True when (x, y) lies inside the penalty area in front of the goal at `defending_goal_x`."""
    depth = abs(x - defending_goal_x)
    return depth <= PENALTY_AREA_DEPTH and abs(y - CENTRE_Y) <= PENALTY_AREA_HALF_WIDTH
