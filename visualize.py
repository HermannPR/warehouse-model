from collections import deque
from typing import List, Tuple, Optional

import matplotlib.pyplot as plt
import matplotlib.patches as patches


from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.patches as patches


class WarehouseVisualizer:
    """Matplotlib-based visualization for the Warehouse model.
    Controls: SPACE=Pause/Resume, S=Step once, R=Reset, Q=Quit, +/-=Speed.
    """

    def __init__(self, model, interval: int = 200, fps: Optional[int] = None, cell_size: Optional[int] = None):
        self.model = model
        # Backward-compat: accept fps and cell_size like the old pygame visualizer.
        # cell_size is ignored in the matplotlib version.
        if fps is not None:
            self.interval_ms = max(10, int(1000 / max(1, fps)))
        else:
            self.interval_ms = max(10, int(interval))
        self.running = True
        self.paused = False
        self.step_once = False

        # Figure with gridspec for layout - map on top, info panel on bottom
        self.fig = plt.figure(figsize=(12, 10))
        from matplotlib.gridspec import GridSpec
        gs = GridSpec(2, 1, figure=self.fig, height_ratios=[3, 1], hspace=0.15)
        
        # Main map axes
        self.ax = self.fig.add_subplot(gs[0, 0])
        
        # Info panel axes (invisible, just for text placement)
        self.info_ax = self.fig.add_subplot(gs[1, 0])
        self.info_ax.set_xlim(0, 1)
        self.info_ax.set_ylim(0, 1)
        self.info_ax.axis('off')  # Hide axes decorations
        
        plt.ion()
        self.fig.canvas.mpl_connect('key_press_event', self._on_key)

        # Initial draw
        self._init_axes()
        self._draw_static()

        # Dynamic artists container
        self._dynamic = []
        self._info_dynamic = []

    # ---------- drawing ----------
    def _init_axes(self):
        self.ax.clear()
        self.ax.set_aspect('equal')
        self.ax.set_xlim(-0.5, self.model.W - 0.5)
        self.ax.set_ylim(-0.5, self.model.H - 0.5)
        self.ax.invert_yaxis()
        self.ax.set_xticks(range(self.model.W))
        self.ax.set_yticks(range(self.model.H))
        self.ax.grid(True, alpha=0.3, linewidth=0.5)
        self.ax.set_title('Warehouse Q-Learning Visualization')

    def _draw_static(self):
        # Floor background
        self.ax.add_patch(
            patches.Rectangle((-0.5, -0.5), self.model.W, self.model.H,
                              facecolor='#f5f5f5', alpha=0.25, zorder=0)
        )

        # Blocked cells
        for x, y in getattr(self.model, 'occupied', []):
            try:
                self.ax.add_patch(patches.Rectangle((float(x)-0.5, float(y)-0.5), 1, 1,
                                                    facecolor='#666666', alpha=0.6, zorder=1))
            except (ValueError, TypeError):
                continue

        # Boxes colored by level (1=blue, 2=green, 3=orange, 4=red) - hide picked boxes
        if hasattr(self.model, 'boxes'):
            for box in self.model.boxes:
                try:
                    pos = box.get('pos') if isinstance(box, dict) else None
                    if pos and len(pos) >= 3:
                        x, y, lvl = float(pos[0]), float(pos[1]), pos[2]
                    elif pos and len(pos) >= 2:
                        x, y = float(pos[0]), float(pos[1])
                        lvl = 1  # Default to level 1
                    else:
                        continue
                    
                    # Check if this box is currently picked up (hide it if so)
                    box_key = (int(x), int(y))
                    if hasattr(self.model, 'picked_boxes') and box_key in self.model.picked_boxes:
                        continue  # Skip rendering picked boxes
                    
                    # Color mapping for new level system
                    level_colors = {
                        1: '#1E90FF',  # Level 1: Blue (robots 1&2)
                        2: '#32CD32',  # Level 2: Green (robots 1&2) 
                        3: '#FFA500',  # Level 3: Orange (robots 3&4)
                        4: '#DC143C'   # Level 4: Red (robots 3&4)
                    }
                    color = level_colors.get(lvl, '#808080')  # Default gray for unknown levels
                    # Slight inset so grid lines remain visible
                    self.ax.add_patch(patches.Rectangle((x-0.45, y-0.45), 0.9, 0.9,
                                                        facecolor=color, alpha=0.6, edgecolor='black', linewidth=0.5, zorder=1))
                except (ValueError, TypeError, KeyError):
                    continue
        # Updated legend for 4-level system (top-right corner)  
        try:
            if hasattr(self.model, 'W') and self.model.W > 5:
                legend_x = float(self.model.W) - 0.5
                legend_y = -0.5
                # Background for legend (wider for 4 levels)
                legend_bg = patches.Rectangle((legend_x-3.2, legend_y+0.1), 3.0, 1.8, 
                                            facecolor='white', alpha=0.8, edgecolor='gray', linewidth=0.5, zorder=3)
                self.ax.add_patch(legend_bg)
                
                # Level boxes and labels
                levels = [
                    (1, '#1E90FF', 'L1 (R1,2)'),
                    (2, '#32CD32', 'L2 (R1,2)'),
                    (3, '#FFA500', 'L3 (R3,4)'),
                    (4, '#DC143C', 'L4 (R3,4)')
                ]
                
                for i, (level, color, label) in enumerate(levels):
                    y_offset = legend_y + 0.25 + (i * 0.35)
                    level_box = patches.Rectangle((legend_x-3.0, y_offset), 0.25, 0.25, 
                                               facecolor=color, edgecolor='black', linewidth=0.5, zorder=4)
                    self.ax.add_patch(level_box)
                    self.ax.text(legend_x-2.7, y_offset + 0.125, label, fontsize=6, va='center', zorder=5)
        except Exception as e:
            pass

        # Special points
        for x, y in getattr(self.model, 'drop_points', []):
            try:
                self.ax.add_patch(patches.Rectangle((float(x)-0.35, float(y)-0.35), 0.7, 0.7,
                                                    facecolor='#32CD32', alpha=0.9, zorder=2))
            except (ValueError, TypeError):
                continue
        for x, y in getattr(self.model, 'recharge_points', []):
            try:
                self.ax.add_patch(patches.Rectangle((float(x)-0.35, float(y)-0.35), 0.7, 0.7,
                                                    facecolor='#FFD700', alpha=0.9, zorder=2))
            except (ValueError, TypeError):
                continue
        # SPAWN points are no longer used; keep compatibility if present
        for x, y in getattr(self.model, 'spawn_points', []):
            self.ax.add_patch(patches.Rectangle((x-0.25, y-0.25), 0.5, 0.5,
                                                facecolor='#00CED1', alpha=0.5, zorder=2))
        
        # Draw guidance lines (vertical paths next to boxes for improved pathfinding)
        try:
            from warehouse import get_guidance_lines_for_boxes
            guidance_positions = get_guidance_lines_for_boxes(self.model)
            for x, y in guidance_positions:
                # Draw subtle guidance lines as light blue dashed lines
                self.ax.add_patch(patches.Rectangle((float(x)-0.1, float(y)-0.1), 0.2, 0.2,
                                                    facecolor='#87CEEB', alpha=0.3, zorder=1))
        except (ImportError, AttributeError, Exception):
            pass  # Gracefully handle if guidance lines not available

    def _draw_robots(self):
        # Remove previous dynamic artists
        for artist in self._dynamic:
            try:
                artist.remove()
            except Exception:
                pass
        self._dynamic.clear()

        # Draw robots
        mission_colors = {
            'DELIVERY': '#00CC66',
            'RECHARGE': '#FFD700',
            'RESTING':  '#808080',
        }
        for robot in getattr(self.model, 'robots', []):
            x, y = robot.position
            color = '#4169E1' if getattr(robot, 'r_type', 'A') == 'A' else '#DC143C'
            circ = patches.Circle((x, y), 0.35, facecolor=color, edgecolor='black', linewidth=1.5, zorder=3)
            self.ax.add_patch(circ); self._dynamic.append(circ)

            # Mission ring highlight
            m = getattr(robot, 'mission', None)
            if m in mission_colors:
                ring = patches.Circle((x, y), 0.42, facecolor='none', edgecolor=mission_colors[m], linewidth=2.0, alpha=0.9, zorder=3)
                self.ax.add_patch(ring); self._dynamic.append(ring)

            # Conflict-forced wait ring (subtle red ring when resolver stopped the robot this step)
            try:
                if hasattr(self.model, 'forced_wait_by_conflict') and robot.id in self.model.forced_wait_by_conflict:
                    fr = patches.Circle((x, y), 0.48, facecolor='none', edgecolor='#FF0000', linewidth=2.0, alpha=0.9, zorder=4)
                    self.ax.add_patch(fr); self._dynamic.append(fr)
            except Exception:
                pass

            # ID label
            txt = self.ax.text(x, y, str(getattr(robot, 'id', '?')), color='white', ha='center', va='center', fontsize=8, zorder=4)
            self._dynamic.append(txt)

            # Carrying indicator
            if getattr(robot, 'carrying', False):
                load = patches.Rectangle((x-0.25, y-0.65), 0.5, 0.22, facecolor='#FFA500', edgecolor='black', linewidth=1.0, zorder=5)
                self.ax.add_patch(load); self._dynamic.append(load)
                lbl = self.ax.text(x, y-0.62, 'B', color='black', ha='center', va='center', fontsize=8, zorder=6)
                self._dynamic.append(lbl)

            # Mission badge & simplified intent line (single line policy)
            # Logic: if carrying -> preferred drop; else if battery >80% -> rest point; else -> nearest charger
            try:
                badge_color = mission_colors.get(m, '#AAAAAA') if m else '#AAAAAA'
                badge = patches.Rectangle((x+0.18, y-0.55), 0.22, 0.18, facecolor=badge_color, edgecolor='black', linewidth=0.6, zorder=5)
                self.ax.add_patch(badge); self._dynamic.append(badge)
                btxt = self.ax.text(x+0.29, y-0.46, (m[0] if m else 'R'), color='black', ha='center', va='center', fontsize=7, zorder=6)
                self._dynamic.append(btxt)
            except Exception:
                pass

            # Draw line to robot's current goal (box, drop point, or service point)
            try:
                line_target = None
                line_color = '#555555'
                
                # Priority 1: If carrying, point to drop location
                if getattr(robot, 'carrying', False):
                    if hasattr(robot, 'target') and robot.target:
                        tgt = robot.target
                        if isinstance(tgt, (list, tuple)) and len(tgt) >= 2:
                            line_target = (tgt[0], tgt[1])
                            line_color = '#32CD32'  # Green for delivery
                    elif hasattr(robot, 'drop_pref'):
                        dp = robot.drop_pref
                        if isinstance(dp, (list, tuple)) and len(dp) >= 2:
                            line_target = (dp[0], dp[1])
                            line_color = '#32CD32'  # Green for delivery
                
                # Priority 2: If DELIVERY mission but not carrying, point to box location
                elif getattr(robot, 'mission', '') == 'DELIVERY' and hasattr(robot, 'box_location') and robot.box_location:
                    box_loc = robot.box_location
                    if isinstance(box_loc, (list, tuple)) and len(box_loc) >= 2:
                        line_target = (box_loc[0], box_loc[1])
                        line_color = '#1E90FF'  # Blue for pickup
                
                # Priority 3: Other missions - use target
                elif hasattr(robot, 'target') and robot.target:
                    tgt = robot.target
                    if isinstance(tgt, (list, tuple)) and len(tgt) >= 2:
                        line_target = (tgt[0], tgt[1])
                        # Color by mission type
                        mission = getattr(robot, 'mission', '')
                        if mission == 'RECHARGE':
                            line_color = '#FFD700'  # Yellow for charge
                        elif mission == 'RESTING':
                            line_color = '#808080'  # Gray for rest
                        else:
                            line_color = '#1E90FF'  # Default blue
                
                # Priority 3: Smart default based on battery/state
                else:
                    if float(getattr(robot, 'battery', 100)) < 20 and self.model.recharge_points:
                        # Low battery - head to charger
                        cp = self.model.closest_pick(robot.position, self.model.recharge_points, self.model.resting_point_free)
                        if cp:
                            line_target = cp
                            line_color = '#FFD700'  # Yellow for charge
                    elif self.model.resting_points:
                        # Default to resting point
                        rp = self.model.closest_pick(robot.position, self.model.resting_points, self.model.resting_point_free)
                        if rp:
                            line_target = rp
                            line_color = '#808080'  # Gray for rest
                
                if line_target:
                    try:
                        lx, ly = float(line_target[0]), float(line_target[1])
                        ln2, = self.ax.plot([x, lx], [y, ly], color=line_color, alpha=0.6, linewidth=1.5, zorder=2)
                        self._dynamic.append(ln2)
                    except (ValueError, TypeError, IndexError):
                        pass
            except Exception:
                pass

            # Battery bar
            batt = max(0.0, min(1.0, float(getattr(robot, 'battery', 100))/100.0))
            bar = patches.Rectangle((x-0.15, y+0.45), 0.3*batt, 0.08, facecolor='#32CD32' if batt>0.6 else ('#FFA500' if batt>0.3 else '#FF4500'), zorder=4)
            frame = patches.Rectangle((x-0.15, y+0.45), 0.3, 0.08, facecolor='none', edgecolor='black', linewidth=0.8, zorder=4)
            self.ax.add_patch(bar); self.ax.add_patch(frame)
            self._dynamic.extend([bar, frame])

        # Stats box
        # Resolve delivery target for HUD
        try:
            target_deliv = int(getattr(self.model, 'CYCLE_DELIVERIES_TARGET', 4))
        except Exception:
            target_deliv = 4

        info = [
            f"Step: {self.model.stats.get('step', 0)}",
            f"Epsilon: {getattr(self.model,'global_epsilon',0):.3f}",
            f"Deliveries: {self.model.stats.get('deliveries',0)}/{target_deliv}  Pickups: {self.model.stats.get('pickups',0)}",
            f"Conflicts: {self.model.stats.get('conflicts',0)}  Moves: {self.model.stats.get('moves',0)}  Waits: {self.model.stats.get('waits',0)}",
        ]
        # Recent reward line (last step reward and short average)
        try:
            rh = self.model.stats.get('reward_hist', [])
            if rh:
                last_r = rh[-1]
                window = rh[-25:] if len(rh) >= 25 else rh
                avg_r = sum(window)/len(window)
                info.append(f"Reward(last): {last_r:+.2f}  Avg(25): {avg_r:+.2f}")
        except Exception:
            pass
        # Forced waits / bumps (congestion indicators)
        try:
            fw = self.model.stats.get('forced_waits', 0)
            bumps = self.model.stats.get('bumps', 0)
            current_forced = len(getattr(self.model, 'forced_wait_by_conflict', set()))
            info.append(f"Bumps: {bumps}  Forced waits: {fw}  Current: {current_forced}")
        except Exception:
            pass
        
        # Robot priorities for current step (for debugging conflict resolution)
        try:
            if hasattr(self.model, 'robots') and len(self.model.robots) <= 4:  # Only show for small numbers
                priorities = []
                for robot in self.model.robots:
                    priority = self.model.get_robot_priority(robot)
                    carrying = "C" if getattr(robot, 'carrying', False) else " "
                    battery = int(getattr(robot, 'battery', 100))
                    priorities.append(f"R{robot.id}:{priority:.1f}({carrying}B{battery})")
                info.append(f"Priorities: {' '.join(priorities)}")
        except Exception:
            pass
        # Clear previous info panel content
        for artist in self._info_dynamic:
            try:
                artist.remove()
            except Exception:
                pass
        self._info_dynamic.clear()
        
        # Create a better organized layout with proper spacing
        # Group related information together
        
        # Main status info (first few lines)
        status_info = info[:3] if len(info) >= 3 else info
        status_txt = self.info_ax.text(0.02, 0.90, "\n".join(status_info), transform=self.info_ax.transAxes,
                                      va='top', ha='left', fontsize=9, 
                                      bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.9), zorder=5)
        self._info_dynamic.append(status_txt)
        
        # Performance metrics (middle section)
        if len(info) > 3:
            perf_info = info[3:6] if len(info) >= 6 else info[3:]
            if perf_info:
                perf_txt = self.info_ax.text(0.35, 0.90, "\n".join(perf_info), transform=self.info_ax.transAxes,
                                           va='top', ha='left', fontsize=9,
                                           bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.9), zorder=5)
                self._info_dynamic.append(perf_txt)
        
        # Robot details (right section)
        if len(info) > 6:
            robot_info = info[6:]
            if robot_info:
                robot_txt = self.info_ax.text(0.68, 0.90, "\n".join(robot_info), transform=self.info_ax.transAxes,
                                            va='top', ha='left', fontsize=8,
                                            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9), zorder=5)
                self._info_dynamic.append(robot_txt)
        
        # Controls information with better spacing
        controls_info = "CONTROLS: SPACE=Pause | S=Step | R=Reset | Q=Quit | +/-=Speed"
        controls_txt = self.info_ax.text(0.5, 0.15, controls_info, transform=self.info_ax.transAxes,
                                        va='center', ha='center', fontsize=8,
                                        bbox=dict(boxstyle='round', facecolor='navy', alpha=0.9),
                                        color='white', zorder=5)
        self._info_dynamic.append(controls_txt)

        self.fig.canvas.draw_idle()

    # ---------- Event handling ----------
    def _on_key(self, event):
        if event.key == ' ':  # space
            self.paused = not self.paused
        elif event.key in ('s', 'S'):
            self.step_once = True
        elif event.key in ('r', 'R'):
            try:
                # Preserve important runtime flags across reset
                eps_override = getattr(self.model, 'epsilon_override', None)
                auto_cycle   = bool(getattr(self.model, 'auto_cycle_reset', False))

                self.model.setup()

                # Restore flags
                if eps_override is not None:
                    self.model.epsilon_override = float(eps_override)
                self.model.auto_cycle_reset = auto_cycle
            except Exception:
                pass
        elif event.key in ('q', 'Q'):
            self.running = False
        elif event.key in ('+', '='):
            self.interval_ms = max(10, int(self.interval_ms * 0.8))
        elif event.key == '-':
            self.interval_ms = int(self.interval_ms * 1.25)
    # No robot-count hotkeys in the baseline

    # ---------- Main loop ----------
    def run(self, max_steps: int = 1000):
        step = 0
        while self.running and step < max_steps:
            if not self.paused or self.step_once:
                try:
                    self.model.step()
                except Exception as e:
                    print(f"Model step error: {e}")
                    break
                step += 1
                self.step_once = False

            self._init_axes()
            self._draw_static()
            self._draw_robots()

            plt.pause(self.interval_ms / 1000.0)

        plt.ioff()
        try:
            plt.show(block=False)
        except Exception:
            pass


def main():
    """Optional standalone runner for quick demo."""
    try:
        from warehouse import Warehouse
    except Exception as e:
        print(f"Cannot import Warehouse: {e}")
        return

    params = {'config_path': 'layout.json'}
    model = Warehouse(parameters=params)
    try:
        model.setup()
    except Exception:
        pass
    # Enable smooth demo cycles by default
    try:
        model.auto_cycle_reset = True
    except Exception:
        pass
    viz = WarehouseVisualizer(model, fps=5)
    viz.run(max_steps=500)


if __name__ == "__main__":
    main()