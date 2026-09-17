"""标准库窗口版贪吃蛇。

运行：python code/snake.py
测试：python -m unittest discover -s tests -v
操作：方向键移动，空格暂停，R / 回车重新开始，Esc 退出。
"""

import random


class SnakeGame:
    """与界面无关的游戏规则；snake 的第一个坐标是蛇头。"""

    DIRECTIONS = {
        "up": (0, -1),
        "down": (0, 1),
        "left": (-1, 0),
        "right": (1, 0),
    }

    def __init__(self, width=24, height=18, rng=None):
        if width < 4 or height < 4:
            raise ValueError("棋盘宽度和高度都必须至少为 4。")
        self.width = width
        self.height = height
        self.rng = rng if rng is not None else random.Random()
        self.reset()

    def reset(self):
        """重开时也清除尚未执行的转向。"""
        x, y = self.width // 2, self.height // 2
        self.snake = [(x, y), (x - 1, y), (x - 2, y)]
        self.direction = "right"
        self.pending_direction = "right"
        self._turn_queued = False
        self.score = 0
        self.state = "running"
        self._place_food()

    def _place_food(self):
        occupied = set(self.snake)
        empty_cells = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if (x, y) not in occupied
        ]
        if empty_cells:
            self.food = self.rng.choice(empty_cells)
        else:
            self.food = None
            self.state = "won"

    def change_direction(self, direction):
        """每次移动前最多转向一次，避免连续按键导致瞬间掉头。"""
        if (
            self.state != "running"
            or self._turn_queued
            or direction not in self.DIRECTIONS
            or direction == self.direction
        ):
            return False
        dx, dy = self.DIRECTIONS[self.direction]
        if self.DIRECTIONS[direction] == (-dx, -dy):
            return False
        self.pending_direction = direction
        self._turn_queued = True
        return True

    def toggle_pause(self):
        if self.state == "running":
            self.state = "paused"
        elif self.state == "paused":
            self.state = "running"

    def tick(self):
        """推进一格；暂停或结束后调用不会改变棋盘。"""
        if self.state != "running":
            return

        self.direction = self.pending_direction
        self._turn_queued = False
        dx, dy = self.DIRECTIONS[self.direction]
        head_x, head_y = self.snake[0]
        new_head = (head_x + dx, head_y + dy)
        eating = new_head == self.food

        # 不增长时，尾巴会同时离开，因此允许蛇头进入旧尾巴所在格。
        occupied = self.snake if eating else self.snake[:-1]
        if (
            not 0 <= new_head[0] < self.width
            or not 0 <= new_head[1] < self.height
            or new_head in occupied
        ):
            self.state = "game_over"
            return

        self.snake.insert(0, new_head)
        if eating:
            self.score += 1
            self._place_food()
        else:
            self.snake.pop()


class SnakeApp:
    """tkinter 窗口；只维护一个定时器，重开不会叠加移动速度。"""

    CELL_SIZE = 26
    TICK_MS = 140
    BACKGROUND = "#111827"
    FONT = "Microsoft YaHei UI"

    def __init__(self, root):
        # 延迟导入，让规则测试可以在没有图形环境的机器上运行。
        import tkinter as tk

        self.root = root
        self.game = SnakeGame()
        self._after_id = None
        self._closed = False
        root.title("贪吃蛇 · Python")
        root.resizable(False, False)
        root.configure(bg=self.BACKGROUND)

        self.score_text = tk.StringVar()
        tk.Label(
            root,
            textvariable=self.score_text,
            bg=self.BACKGROUND,
            fg="#f9fafb",
            font=(self.FONT, 16, "bold"),
            pady=12,
        ).pack()

        self.canvas = tk.Canvas(
            root,
            width=self.game.width * self.CELL_SIZE,
            height=self.game.height * self.CELL_SIZE,
            bg=self.BACKGROUND,
            highlightthickness=1,
            highlightbackground="#374151",
        )
        self.canvas.pack(padx=16)

        tk.Label(
            root,
            text="方向键移动  ·  空格暂停 / 继续  ·  R / 回车重开  ·  Esc 退出",
            bg=self.BACKGROUND,
            fg="#d1d5db",
            font=(self.FONT, 10),
            pady=12,
        ).pack()
        buttons = tk.Frame(root, bg=self.BACKGROUND)
        buttons.pack(pady=(0, 14))
        self.pause_button = tk.Button(
            buttons, text="暂停", width=12, command=self.toggle_pause,
            font=(self.FONT, 10), takefocus=False,
        )
        self.pause_button.pack(side="left", padx=6)
        tk.Button(
            buttons, text="重新开始", width=12, command=self.restart,
            font=(self.FONT, 10), takefocus=False,
        ).pack(side="left", padx=6)

        root.bind("<KeyPress>", self._on_key)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._render()
        self._schedule_tick()

    def _on_key(self, event):
        key = event.keysym.lower()
        if key in self.game.DIRECTIONS:
            self.game.change_direction(key)
        elif key == "space":
            self.toggle_pause()
        elif key in ("r", "return"):
            self.restart()
        elif key == "escape":
            self.close()
        else:
            return None
        # 防止空格同时触发具有焦点的按钮。
        return "break"

    def _schedule_tick(self):
        self._after_id = self.root.after(self.TICK_MS, self._tick)

    def _tick(self):
        self._after_id = None
        if self._closed:
            return
        self.game.tick()
        self._render()
        self._schedule_tick()

    def toggle_pause(self):
        self.game.toggle_pause()
        self._render()

    def restart(self):
        # 从重开时刻重新计算下一步，避免恰好在旧定时器触发前重开。
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
        self.game.reset()
        self._render()
        self._schedule_tick()

    def _render(self):
        canvas = self.canvas
        cell = self.CELL_SIZE
        width = self.game.width * cell
        height = self.game.height * cell
        canvas.delete("all")
        self.score_text.set(f"贪吃蛇    得分：{self.game.score}")
        self.pause_button.configure(
            text="继续" if self.game.state == "paused" else "暂停",
            state="normal" if self.game.state in ("running", "paused") else "disabled",
        )

        for x in range(0, width, cell):
            canvas.create_line(x, 0, x, height, fill="#1f2937")
        for y in range(0, height, cell):
            canvas.create_line(0, y, width, y, fill="#1f2937")

        if self.game.food is not None:
            x, y = self.game.food
            canvas.create_oval(
                x * cell + 5, y * cell + 5,
                (x + 1) * cell - 5, (y + 1) * cell - 5,
                fill="#fb7185", outline="",
            )

        for index, (x, y) in enumerate(self.game.snake):
            canvas.create_rectangle(
                x * cell + 2, y * cell + 2,
                (x + 1) * cell - 2, (y + 1) * cell - 2,
                fill="#a3e635" if index == 0 else "#22c55e", outline="",
            )

        overlays = {
            "paused": ("已暂停", "按空格继续"),
            "game_over": ("游戏结束", "按 R / 回车重新开始"),
            "won": ("恭喜通关！", "棋盘已填满，按 R / 回车再玩一次"),
        }
        if self.game.state in overlays:
            title, subtitle = overlays[self.game.state]
            cx, cy = width / 2, height / 2
            canvas.create_rectangle(
                cx - 220, cy - 64, cx + 220, cy + 64,
                fill="#0f172a", outline="#64748b", width=2,
            )
            canvas.create_text(
                cx, cy - 20, text=title, fill="#f9fafb",
                font=(self.FONT, 24, "bold"),
            )
            canvas.create_text(
                cx, cy + 26, text=subtitle, fill="#d1d5db",
                font=(self.FONT, 12),
            )

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self.root.destroy()


def main():
    try:
        import tkinter as tk
    except ImportError as exc:
        raise SystemExit("未安装 tkinter，请安装带 Tcl/Tk 的 Python。") from exc

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise SystemExit(f"无法创建窗口，请在图形桌面环境中运行：{exc}") from exc

    SnakeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
