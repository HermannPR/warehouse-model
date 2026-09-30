# config_constants.py
JSON_INITIALIZATION = True
PRETRAIN_ENABLED = False
VISUALIZATION_ENABLED = True
CYCLE_DELIVERIES_TARGET = 4

ACTIONS = ["UP", "DOWN", "LEFT", "RIGHT", "WAIT", "PICKUP", "DISCHARGE", "RECHARGE"]

MOVE_TO_HEADING = {
    "UP": 0, "RIGHT": 1, "DOWN": 2, "LEFT": 3
}

ACTION_TO_UNITY = {
    "UP": "move", "DOWN": "move", "LEFT": "move", "RIGHT": "move",
    "WAIT": "idle", "PICKUP": "pickup", "DISCHARGE": "drop", "RECHARGE": "charge"
}

# Q-learning parameters
ALPHA = 0.1
GAMMA = 0.99
EPSILON_START = 0.9
EPSILON_END = 0.05
DECAY_STEPS = 10000
EPSILON_TAU = 2500.0

# Feature engineering
FEAT_PER_ACT = 12
N_FEATURES = FEAT_PER_ACT * len(ACTIONS)  # 96 features total

# Reward constants
R_STEP = -0.01
R_SHAPING_K = 0.4  # Increased from 0.1 for stronger distance incentive
R_PICKUP = 7.0  # Increased from 5.0 for better success amplification
R_DROP = 13.0  # Increased from 10.0 for better delivery incentive
R_RECHARGE = 1.0
R_BUMP = -1.0
R_CONFLICT = -0.5
LOW_BATT_THR = 0.15
R_LOW_BATT = -0.1

# New proximity and efficiency bonuses
R_PROXIMITY_BONUS = 0.5  # Bonus when within 3 cells of target
R_ADJACENT_BONUS = 1.0   # Extra bonus when adjacent to target
R_INEFFICIENCY_PENALTY = 0.2  # Penalty for moving away from target

# Coordination (see blackboard.py / auction.py)
# ALLOCATION_MODE: "greedy"  = nearest idle robot takes each pending mission (original behavior)
#                  "auction" = Contract-Net auction over tasks posted on the blackboard
# CONFLICT_MODE:   "legacy"     = original multi-pass resolver
#                  "blackboard" = next-cell reservations on the blackboard
# Both can be overridden per model: Warehouse(parameters={"allocation_mode": ..., "conflict_mode": ...})
ALLOCATION_MODE = "greedy"
CONFLICT_MODE = "legacy"
BID_W_CONGESTION = 2.0   # cost per unit of congestion heat on the planned path
BID_W_CROWDING = 3.0     # cost per other robot already near the box
BID_W_BATTERY = 0.2      # cost per battery point below 100
STUCK_RELEASE_STEPS = 15 # claimed task is released if its robot has not moved for this many ticks