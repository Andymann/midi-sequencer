import tkinter as tk
from enum import Enum, auto


class AppState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()
    RECORDING_IDLE = auto()   # armed, transport stopped
    RECORDING = auto()        # armed + playing
    PAUSED_RECORDING = auto() # armed + paused


# --- Configuration ---
NUM_STEPS = 16
NUM_ROWS = 16
WIN_WIDTH = 800
WIN_HEIGHT = 480
NUM_STATES = 64           # total states
NUM_VISIBLE = 16          # states shown at once (one group)
NUM_GROUPS = NUM_STATES // NUM_VISIBLE
BPM = 94
NOTE_INTERVALS = [(4, "1/16"), (1, "1/4"), (2, "1/8")]  # (divisor, label); first entry is default

TILE_COLORS = ("#1e1e3a", "#252545")          # alternating shades
TILE_COLORS_GREEN = ("#1a2e1a", "#203a20")   # greenish area shades
DEDICATED_TILES = set(range(1, 10)) | set(range(161, 170))  # tiles 1-9 and 161-169
BUTTON_DEFAULT_COLOR = "#3a3a5c"
BUTTON_ACTIVE_COLOR = "#2d7a2d"
BUTTON_RECORDING_COLOR = "#8b1a1a"
TRANSPORT_DEFAULT_COLOR = "#2e2e4e"
TRANSPORT_PLAY_ACTIVE_COLOR = "#2d7a2d"
TRANSPORT_STOP_ACTIVE_COLOR = "#4a90d9"
TRANSPORT_RECORD_ACTIVE_COLOR = "#8b1a1a"
BPM_AREA_COLOR = "#12122a"
BPM_TEXT_COLOR = "#e0e0e0"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MIDI Sequencer")
        self.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT}")
        self.resizable(False, False)

        self._numbers_visible = True
        self.states = [{"selected": False, "active": False} for _ in range(NUM_STATES)]
        self.app_state = AppState.STOPPED
        self._current_step = 0
        self._group_index = 0
        self._step_job = None
        self._blink_job = None
        self._blink_on = False
        self._bpm_hold_job = None
        self._interval_index = 0  # default: 1/16
        self._follow_mode = False

        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("n", lambda _: self._toggle_numbers())

        self._build_ui()
        self._select_state(0)

    def _build_ui(self):
        self._canvas = tk.Canvas(self, width=WIN_WIDTH, height=WIN_HEIGHT,
                                 highlightthickness=0, bd=0)
        self._canvas.pack()

        tile_w = WIN_WIDTH / NUM_STEPS
        tile_h = WIN_HEIGHT / NUM_ROWS
        self._number_ids = []

        for row in range(NUM_ROWS):
            y0 = row * tile_h
            y1 = y0 + tile_h
            for col in range(NUM_STEPS):
                x0 = col * tile_w
                x1 = x0 + tile_w
                tile_num = row * NUM_STEPS + col + 1
                palette = TILE_COLORS_GREEN if tile_num in DEDICATED_TILES else TILE_COLORS
                color = palette[(row + col) % len(palette)]
                self._canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")
                text_id = self._canvas.create_text(
                    (x0 + x1) / 2, (y0 + y1) / 2,
                    text=str(tile_num),
                    fill="#aaaacc",
                    font=("Helvetica", 8),
                )
                self._number_ids.append(text_id)

        # BPM display — tiles 11-30
        bx0, by0, bx1, by1 = self._tile_rect(11, 30)
        self._canvas.create_rectangle(bx0, by0, bx1, by1, fill=BPM_AREA_COLOR, outline="")
        self._bpm_text = self._canvas.create_text(
            (bx0 + bx1) / 2, (by0 + by1) / 2,
            text=f"{BPM} BPM",
            fill=BPM_TEXT_COLOR,
            font=("Helvetica", 22, "bold"),
        )

        # Interval selector button — tiles 10 and 26
        pad = 4
        ix0, iy0, ix1, iy1 = self._tile_rect(10, 26)
        self._interval_rect = self._canvas.create_rectangle(
            ix0 + pad, iy0 + pad, ix1 - pad, iy1 - pad,
            fill=TRANSPORT_DEFAULT_COLOR, outline=""
        )
        self._interval_text = self._canvas.create_text(
            (ix0 + ix1) / 2, (iy0 + iy1) / 2,
            text=NOTE_INTERVALS[self._interval_index][1],
            fill="#e0e0e0", font=("Helvetica", 9, "bold")
        )
        for item in (self._interval_rect, self._interval_text):
            self._canvas.tag_bind(item, "<Button-1>", lambda _: self._cycle_interval())

        # BPM +/- buttons
        self._build_bpm_button(43, 44, "BPM -", -1)
        self._build_bpm_button(45, 46, "BPM +", +1)

        # Group cycle button — tiles 179-180 and 195-196
        gx0, gy0, gx1, gy1 = self._tile_rect(179, 196)
        self._group_btn_rect = self._canvas.create_rectangle(
            gx0 + pad, gy0 + pad, gx1 - pad, gy1 - pad,
            fill=TRANSPORT_DEFAULT_COLOR, outline=""
        )
        self._group_btn_text = self._canvas.create_text(
            (gx0 + gx1) / 2, (gy0 + gy1) / 2,
            text="Group", fill="#e0e0e0", font=("Helvetica", 8)
        )
        # Group label — tiles 181-182 and 197-198
        lx0, ly0, lx1, ly1 = self._tile_rect(181, 198)
        self._canvas.create_rectangle(lx0, ly0, lx1, ly1, fill=BPM_AREA_COLOR, outline="")
        self._group_label = self._canvas.create_text(
            (lx0 + lx1) / 2, (ly0 + ly1) / 2,
            text=self._group_label_text(),
            fill=BPM_TEXT_COLOR, font=("Helvetica", 22, "bold")
        )
        # Group indicator lines at the bottom of the label area
        indicator_h = 3
        seg_w = (lx1 - lx0) / NUM_GROUPS
        self._group_indicators = []
        for g in range(NUM_GROUPS):
            x0 = lx0 + g * seg_w + 1
            x1 = lx0 + (g + 1) * seg_w - 1
            ind = self._canvas.create_rectangle(
                x0, ly1 - indicator_h, x1, ly1,
                fill="#ffffff" if g == 0 else "#444466", outline=""
            )
            self._group_indicators.append(ind)
        for item in (self._group_btn_rect, self._group_btn_text):
            self._canvas.tag_bind(item, "<Button-1>", lambda _: self._cycle_group())

        # Follow-mode toggle button — tiles 183 and 199
        fx0, fy0, fx1, fy1 = self._tile_rect(183, 199)
        self._follow_rect = self._canvas.create_rectangle(
            fx0 + pad, fy0 + pad, fx1 - pad, fy1 - pad,
            fill=TRANSPORT_DEFAULT_COLOR, outline=""
        )
        self._follow_text = self._canvas.create_text(
            (fx0 + fx1) / 2, (fy0 + fy1) / 2,
            text="Follow", fill="#e0e0e0", font=("Helvetica", 8)
        )
        for item in (self._follow_rect, self._follow_text):
            self._canvas.tag_bind(item, "<Button-1>", lambda _: self._toggle_follow())

        # State buttons across the bottom two rows
        self._button_rects = []
        self._button_labels = []
        for i in range(NUM_VISIBLE):
            start = 225 + i
            end = 241 + i
            x0, y0, x1, y1 = self._tile_rect(start, end)
            rect = self._canvas.create_rectangle(
                x0 + pad, y0 + pad, x1 - pad, y1 - pad,
                fill=BUTTON_DEFAULT_COLOR, outline="", tags=f"btn{i}"
            )
            label = self._canvas.create_text(
                (x0 + x1) / 2, (y0 + y1) / 2,
                text=str(i + 1), fill="#e0e0e0",
                font=("Helvetica", 22), tags=f"btn{i}"
            )
            self._button_rects.append(rect)
            self._button_labels.append(label)
            for tag in (rect, label):
                self._canvas.tag_bind(tag, "<Button-1>",
                    lambda _, b=i: self._select_state(self._group_index * NUM_VISIBLE + b))

        # Transport buttons: Play (187-204), Record (189-206), Stop (191-208)
        self._build_transport_button(187, 204, "▶  Play", "play")
        self._build_transport_button(189, 206, "⏺  Rec",  "record")
        self._build_transport_button(191, 208, "■  Stop", "stop")

    def _group_label_text(self):
        return f"{self._group_index + 1} / {NUM_GROUPS}"

    def _cycle_group(self):
        self._group_index = (self._group_index + 1) % NUM_GROUPS
        self._canvas.itemconfigure(self._group_label, text=self._group_label_text())
        self._refresh_button_labels()
        self._refresh_buttons()

    def _refresh_button_labels(self):
        offset = self._group_index * NUM_VISIBLE
        for i, label_id in enumerate(self._button_labels):
            self._canvas.itemconfigure(label_id, text=str(offset + i + 1))

    def _build_transport_button(self, start, end, label, action):
        pad = 4
        x0, y0, x1, y1 = self._tile_rect(start, end)
        rect = self._canvas.create_rectangle(
            x0 + pad, y0 + pad, x1 - pad, y1 - pad,
            fill=TRANSPORT_DEFAULT_COLOR, outline="", tags=action
        )
        text = self._canvas.create_text(
            (x0 + x1) / 2, (y0 + y1) / 2,
            text=label, fill="#e0e0e0",
            font=("Helvetica", 8), tags=action
        )
        setattr(self, f"_transport_{action}_rect", rect)
        setattr(self, f"_transport_{action}_text", text)
        for item in (rect, text):
            self._canvas.tag_bind(item, "<Button-1>", lambda _, a=action: self._on_transport(a))

    def _on_transport(self, action):
        if action == "play":
            if self.app_state == AppState.PLAYING:
                self.app_state = AppState.PAUSED
            elif self.app_state == AppState.PAUSED:
                self.app_state = AppState.PLAYING
            elif self.app_state == AppState.RECORDING:
                self.app_state = AppState.PAUSED_RECORDING
            elif self.app_state == AppState.PAUSED_RECORDING:
                self.app_state = AppState.RECORDING
            elif self.app_state == AppState.RECORDING_IDLE:
                self.app_state = AppState.RECORDING
            else:
                self.app_state = AppState.PLAYING
        elif action == "record":
            if self.app_state == AppState.STOPPED:
                self.app_state = AppState.RECORDING_IDLE
            elif self.app_state == AppState.RECORDING_IDLE:
                self.app_state = AppState.STOPPED
            elif self.app_state == AppState.PLAYING:
                self.app_state = AppState.RECORDING
            elif self.app_state == AppState.RECORDING:
                self.app_state = AppState.PLAYING
            elif self.app_state == AppState.PAUSED:
                self.app_state = AppState.PAUSED_RECORDING
            elif self.app_state == AppState.PAUSED_RECORDING:
                self.app_state = AppState.PAUSED
        elif action == "stop":
            self.app_state = AppState.STOPPED
            self._current_step = 0
            self._group_index = 0
            self._canvas.itemconfigure(self._group_label, text=self._group_label_text())
            self._select_state(0)
        self._update_transport_ui()
        self._update_playback()

    def _update_playback(self):
        if self.app_state in (AppState.PLAYING, AppState.RECORDING):
            if self._step_job is None:
                self._schedule_step()
        else:
            if self._step_job is not None:
                self.after_cancel(self._step_job)
                self._step_job = None
            if self.app_state == AppState.STOPPED:
                self._current_step = 0
            self._refresh_buttons()

    def _cycle_interval(self):
        self._interval_index = (self._interval_index + 1) % len(NOTE_INTERVALS)
        self._canvas.itemconfigure(self._interval_text, text=NOTE_INTERVALS[self._interval_index][1])

    def _schedule_step(self):
        divisor = NOTE_INTERVALS[self._interval_index][0]
        interval_ms = int(60_000 / BPM / divisor)
        self._select_state(self._current_step)
        self._current_step = (self._current_step + 1) % NUM_STATES
        self._step_job = self.after(interval_ms, self._schedule_step)

    def _toggle_follow(self):
        self._follow_mode = not self._follow_mode
        color = BUTTON_ACTIVE_COLOR if self._follow_mode else TRANSPORT_DEFAULT_COLOR
        self._canvas.itemconfigure(self._follow_rect, fill=color)

    def _select_state(self, global_index):
        for i, state in enumerate(self.states):
            state["selected"] = i == global_index
            state["active"] = i == global_index
        active_group = global_index // NUM_VISIBLE
        if self._follow_mode and self._group_index != active_group:
            self._group_index = active_group
            self._canvas.itemconfigure(self._group_label, text=self._group_label_text())
            self._refresh_button_labels()
        for g, ind in enumerate(self._group_indicators):
            self._canvas.itemconfigure(ind, fill="#ffffff" if g == active_group else "#444466")
        self._refresh_buttons()

    def _refresh_buttons(self):
        is_recording = self.app_state in (AppState.RECORDING, AppState.RECORDING_IDLE, AppState.PAUSED_RECORDING)
        active_color = BUTTON_RECORDING_COLOR if is_recording else BUTTON_ACTIVE_COLOR
        offset = self._group_index * NUM_VISIBLE
        for i, rect in enumerate(self._button_rects):
            color = active_color if self.states[offset + i]["selected"] else BUTTON_DEFAULT_COLOR
            self._canvas.itemconfigure(rect, fill=color)

    def _update_transport_ui(self):
        is_playing = self.app_state in (AppState.PLAYING, AppState.RECORDING)
        is_paused = self.app_state in (AppState.PAUSED, AppState.PAUSED_RECORDING)
        is_recording = self.app_state in (AppState.RECORDING, AppState.RECORDING_IDLE, AppState.PAUSED_RECORDING)
        is_stopped = self.app_state in (AppState.STOPPED, AppState.RECORDING_IDLE)

        if is_paused:
            self._start_blink()
        else:
            self._stop_blink()
            self._canvas.itemconfigure(self._transport_play_rect,
                fill=TRANSPORT_PLAY_ACTIVE_COLOR if is_playing else TRANSPORT_DEFAULT_COLOR)
        self._canvas.itemconfigure(self._transport_play_text,
            text="⏸  Pause" if is_playing else "▶  Play")
        self._canvas.itemconfigure(self._transport_record_rect,
            fill=TRANSPORT_RECORD_ACTIVE_COLOR if is_recording else TRANSPORT_DEFAULT_COLOR)

        if is_stopped:
            self._canvas.itemconfigure(self._transport_stop_rect, fill=TRANSPORT_STOP_ACTIVE_COLOR)
            self.after(200, lambda: self._canvas.itemconfigure(
                self._transport_stop_rect, fill=TRANSPORT_DEFAULT_COLOR))

    def _build_bpm_button(self, start, end, label, delta):
        pad = 4
        x0, y0, x1, y1 = self._tile_rect(start, end)
        rect = self._canvas.create_rectangle(
            x0 + pad, y0 + pad, x1 - pad, y1 - pad,
            fill=TRANSPORT_DEFAULT_COLOR, outline=""
        )
        text = self._canvas.create_text(
            (x0 + x1) / 2, (y0 + y1) / 2,
            text=label, fill="#e0e0e0", font=("Helvetica", 8)
        )
        for item in (rect, text):
            self._canvas.tag_bind(item, "<ButtonPress-1>",   lambda _, d=delta, r=rect: self._bpm_press(d, r))
            self._canvas.tag_bind(item, "<ButtonRelease-1>", lambda _, r=rect: self._bpm_release(r))

    def _bpm_press(self, delta, rect):
        self._canvas.itemconfigure(rect, fill=TRANSPORT_STOP_ACTIVE_COLOR)
        self._change_bpm(delta)
        self._bpm_hold_job = self.after(1500, lambda: self._bpm_hold_start(delta * 10))

    def _bpm_hold_start(self, delta):
        self._change_bpm(delta)
        self._bpm_hold_job = None

    def _bpm_release(self, rect):
        if self._bpm_hold_job is not None:
            self.after_cancel(self._bpm_hold_job)
            self._bpm_hold_job = None
        self._canvas.itemconfigure(rect, fill=TRANSPORT_DEFAULT_COLOR)

    def _change_bpm(self, delta):
        global BPM
        BPM = max(1, BPM + delta)
        self._canvas.itemconfigure(self._bpm_text, text=f"{BPM} BPM")

    def _start_blink(self):
        if self._blink_job is None:
            self._do_blink()

    def _stop_blink(self):
        if self._blink_job is not None:
            self.after_cancel(self._blink_job)
            self._blink_job = None
        self._blink_on = False

    def _do_blink(self):
        self._blink_on = not self._blink_on
        color = TRANSPORT_PLAY_ACTIVE_COLOR if self._blink_on else TRANSPORT_DEFAULT_COLOR
        self._canvas.itemconfigure(self._transport_play_rect, fill=color)
        self._blink_job = self.after(500, self._do_blink)

    def _tile_rect(self, tile_start, tile_end):
        """Return (x0, y0, x1, y1) for a rectangle spanning tile_start to tile_end."""
        tile_w = WIN_WIDTH / NUM_STEPS
        tile_h = WIN_HEIGHT / NUM_ROWS
        col0 = (tile_start - 1) % NUM_STEPS
        row0 = (tile_start - 1) // NUM_STEPS
        col1 = (tile_end - 1) % NUM_STEPS
        row1 = (tile_end - 1) // NUM_STEPS
        return col0 * tile_w, row0 * tile_h, (col1 + 1) * tile_w, (row1 + 1) * tile_h

    def _toggle_numbers(self):
        self._numbers_visible = not self._numbers_visible
        state = "normal" if self._numbers_visible else "hidden"
        for text_id in self._number_ids:
            self._canvas.itemconfigure(text_id, state=state)


if __name__ == "__main__":
    app = App()
    app.mainloop()
