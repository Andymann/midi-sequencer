import tkinter as tk

# --- Configuration ---
NUM_STEPS = 16
NUM_ROWS = 16
WIN_WIDTH = 800
WIN_HEIGHT = 480
NUM_STATES = 8

TILE_COLORS = ("#1e1e3a", "#252545")  # alternating shades
BUTTON_DEFAULT_COLOR = "#3a3a5c"
BUTTON_ACTIVE_COLOR = "#2d7a2d"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MIDI Sequencer")
        self.geometry(f"{WIN_WIDTH}x{WIN_HEIGHT}")
        self.resizable(False, False)

        self._numbers_visible = True
        self.states = [{"selected": False} for _ in range(NUM_STATES)]

        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("n", lambda _: self._toggle_numbers())

        self._build_ui()

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
                color = TILE_COLORS[(row + col) % len(TILE_COLORS)]
                self._canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")
                tile_num = row * NUM_STEPS + col + 1
                text_id = self._canvas.create_text(
                    (x0 + x1) / 2, (y0 + y1) / 2,
                    text=str(tile_num),
                    fill="#aaaacc",
                    font=("Helvetica", 8),
                )
                self._number_ids.append(text_id)

        # State buttons across the bottom two rows
        pad = 4
        self._button_rects = []
        for i in range(NUM_STATES):
            start = 225 + i * 2
            end = 242 + i * 2
            x0, y0, x1, y1 = self._tile_rect(start, end)
            rect = self._canvas.create_rectangle(
                x0 + pad, y0 + pad, x1 - pad, y1 - pad,
                fill=BUTTON_DEFAULT_COLOR, outline="", tags=f"btn{i}"
            )
            label = self._canvas.create_text(
                (x0 + x1) / 2, (y0 + y1) / 2,
                text=f"Button {i + 1}", fill="#e0e0e0",
                font=("Helvetica", 8), tags=f"btn{i}"
            )
            self._button_rects.append(rect)
            for tag in (rect, label):
                self._canvas.tag_bind(tag, "<Button-1>", lambda _, b=i: self._select_button(b))

    def _select_button(self, index):
        for i, state in enumerate(self.states):
            state["selected"] = i == index
        for i, rect in enumerate(self._button_rects):
            color = BUTTON_ACTIVE_COLOR if self.states[i]["selected"] else BUTTON_DEFAULT_COLOR
            self._canvas.itemconfigure(rect, fill=color)

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
