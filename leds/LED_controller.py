import sqlite3
import time
from contextlib import contextmanager
from LEDs import LEDs
from LEDs_db_init import initialize_leds_database
from moving_target_db_init import initialize_moving_target_database

class LEDController:
    def __init__(self, db_path='LEDs.db', poll_interval=0.5):
        print("Resetting LEDs database...")
        initialize_leds_database()
        initialize_moving_target_database()

        self.db_path = db_path
        self.moving_target_db_path = 'moving_target.db'
        self.poll_interval = poll_interval
        self.led_control = LEDs()
        self.current_mode = None
        self.previous_mode = None
        self.current_player = 1
        self.classic_hits_this_turn = []

        # Moving Target
        self.moving_target_sequence = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
        self.current_target_index = 0
        self.last_target_move_time = time.time()
        self.target_move_interval = 3.0
        self.moving_target_hits = 0
        self.successful_targets = set()

    @contextmanager
    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def get_moving_target_connection(self):
        conn = sqlite3.connect(self.moving_target_db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def get_current_mode(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mode FROM game_mode WHERE id = 1")
            row = cursor.fetchone()
            if not row:
                return 'neutral'
            mode = row['mode'].lower()
            if mode in ['301', '501', 'classic']:
                return 'classic'
            elif mode in ['around_clock', 'around_the_clock']:
                return 'around_clock'
            elif mode == 'moving_target':
                return 'moving_target'
            else:
                return 'neutral'

    def get_current_player(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT current_player FROM player_state WHERE id = 1")
            row = cursor.fetchone()
            if row:
                self.current_player = row['current_player']
            return self.current_player

    def get_around_clock_target(self, player_id):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT current_target FROM around_clock_state WHERE player_id = ?", (player_id,))
            row = cursor.fetchone()
            return row['current_target'] if row else 1

    def setup_classic_mode(self):
        self.led_control.clearAll(wait_ms=1)
        self.classic_hits_this_turn = []

    def process_dart_event_classic(self, event):
        if len(self.classic_hits_this_turn) >= 3:
            return

        score = event['score']
        segment_type = event['segment_type']
        if segment_type == 'bullseye':
            self.led_control.bullseye((0, 255, 0))
            self.classic_hits_this_turn.append('bullseye')
        elif score in self.led_control.DARTBOARD_MAPPING:
            seg_id = f'{segment_type}_{score}'
            if segment_type == 'double':
                self.led_control.doubleSeg(score, (0, 255, 0))
            elif segment_type == 'triple':
                self.led_control.tripleSeg(score, (0, 255, 0))
            elif segment_type == 'inner_single':
                self.led_control.innerSingleSeg(score, (0, 255, 0))
            elif segment_type == 'outer_single':
                self.led_control.outerSingleSeg(score, (0, 255, 0))
            self.classic_hits_this_turn.append(seg_id)

    def setup_around_clock_mode(self):
        self.led_control.clearAll(wait_ms=1)

    def process_dart_event_around_clock(self, event):
        score = event['score']
        segment_type = event['segment_type']
        target = self.get_around_clock_target(self.current_player)

        if score == target:
            if segment_type == 'bullseye':
                self.led_control.bullseye((0, 255, 0))
            elif score in self.led_control.DARTBOARD_MAPPING:
                getattr(self.led_control, f'{segment_type}Seg')(score, (0, 255, 0))
        else:
            if segment_type == 'bullseye':
                self.led_control.bullseye((255, 0, 0))
                time.sleep(0.2)
                self.led_control.bullseye((0, 0, 0))
            elif score in self.led_control.DARTBOARD_MAPPING:
                getattr(self.led_control, f'{segment_type}Seg')(score, (255, 0, 0))
                time.sleep(0.2)
                getattr(self.led_control, f'{segment_type}Seg')(score, (0, 0, 0))

    def setup_moving_target_mode(self, target_number=None):
        self.led_control.clearAll(wait_ms=1)
        if target_number is None:
            with self.get_moving_target_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT current_target FROM target_state WHERE id = 1")
                row = cursor.fetchone()
                target_number = row['current_target'] if row else 20

        print(f"Moving Target: lighting {target_number} red")
        for seg_type in ['double', 'triple', 'inner_single', 'outer_single']:
            getattr(self.led_control, f'{seg_type}Seg')(target_number, (255, 0, 0))

    def update_moving_target(self):
        if self.moving_target_hits >= 3:
            return

        now = time.time()
        if now - self.last_target_move_time < self.target_move_interval:
            return

        self.current_target_index = (self.current_target_index + 1) % len(self.moving_target_sequence)
        new_target = self.moving_target_sequence[self.current_target_index]

        with self.get_moving_target_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE target_state SET current_target = ?, last_moved_at = CURRENT_TIMESTAMP WHERE id = 1", (new_target,))
            cursor.execute("DELETE FROM active_segments")
            for t in ['double', 'triple', 'inner_single', 'outer_single']:
                cursor.execute("INSERT INTO active_segments (segment_number, segment_type) VALUES (?, ?)", (new_target, t))
            conn.commit()

        self.setup_moving_target_mode(new_target)
        self.last_target_move_time = now

    def process_dart_event_moving_target(self, event):
        if self.moving_target_hits >= 3:
            return

        score = event['score']
        segment_type = event['segment_type']
        current_target = self.moving_target_sequence[self.current_target_index]
        if score != current_target:
            return

        seg_id = f'{segment_type}_{score}'
        if seg_id in self.successful_targets:
            return

        getattr(self.led_control, f'{segment_type}Seg')(score, (0, 255, 0))
        self.successful_targets.add(seg_id)
        self.moving_target_hits += 1

    def setup_neutral_mode(self):
        self.led_control.clearAll(wait_ms=1)

    def get_new_dart_events(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, score, multiplier, segment_type FROM dart_events WHERE processed = 0 ORDER BY timestamp ASC")
            events = cursor.fetchall()
            if events:
                ids = [str(e['id']) for e in events]
                cursor.execute(f"UPDATE dart_events SET processed = 1 WHERE id IN ({','.join(['?'] * len(ids))})", ids)
                conn.commit()
            return events

    def run(self):
        try:
            print("Starting LED controller...")
            self.setup_neutral_mode()
            self.current_mode = 'neutral'

            while True:
                mode = self.get_current_mode()
                if mode != self.current_mode:
                    self.current_mode = mode
                    print(f"Switched to mode: {mode}")
                    if mode == 'classic':
                        self.setup_classic_mode()
                    elif mode == 'around_clock':
                        self.setup_around_clock_mode()
                    elif mode == 'moving_target':
                        self.setup_moving_target_mode()
                    else:
                        self.setup_neutral_mode()

                if self.current_mode == 'classic':
                    old_player = self.current_player
                    self.get_current_player()
                    if old_player != self.current_player:
                        print(f"Player changed: {old_player} -> {self.current_player}")
                        self.led_control.clearAll(wait_ms=1)
                        self.classic_hits_this_turn = []

                if self.current_mode == 'moving_target':
                    self.update_moving_target()

                for event in self.get_new_dart_events():
                    print(f"Event: {event['score']}x{event['multiplier']} [{event['segment_type']}]")
                    if self.current_mode == 'classic':
                        self.process_dart_event_classic(event)
                    elif self.current_mode == 'around_clock':
                        self.process_dart_event_around_clock(event)
                    elif self.current_mode == 'moving_target':
                        self.process_dart_event_moving_target(event)

                    if hasattr(self.led_control, 'print_board_state'):
                        self.led_control.print_board_state()

                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            print("Stopping LED controller.")
            self.led_control.clearAll()

def main():
    controller = LEDController()
    controller.run()

if __name__ == "__main__":
    main()
