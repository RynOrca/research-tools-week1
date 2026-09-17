"""Headless regression tests: python -m unittest discover -s tests -v."""

import importlib.util
from pathlib import Path
import random
import sys
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "code" / "snake.py"
SPEC = importlib.util.spec_from_file_location("snake_under_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Cannot load game module: {MODULE_PATH}")
snake_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = snake_module
SPEC.loader.exec_module(snake_module)
SnakeGame = snake_module.SnakeGame


class SnakeGameTests(unittest.TestCase):
    def make_game(self, width=8, height=6):
        return SnakeGame(width=width, height=height, rng=random.Random(7))

    def configure(self, game, body, direction="right", food=(6, 4)):
        game.snake = list(body)
        game.direction = direction
        game.pending_direction = direction
        game.food = food

    def assert_valid_food(self, game):
        self.assertIsNotNone(game.food)
        self.assertNotIn(game.food, game.snake)
        x, y = game.food
        self.assertTrue(0 <= x < game.width)
        self.assertTrue(0 <= y < game.height)

    def test_initial_state_and_minimum_board(self):
        for width, height in [(24, 18), (4, 4)]:
            with self.subTest(width=width, height=height):
                game = self.make_game(width, height)
                self.assertEqual(len(game.snake), 3)
                self.assertEqual(len(set(game.snake)), 3)
                self.assertTrue(all(0 <= x < width and 0 <= y < height
                                    for x, y in game.snake))
                self.assertEqual(game.direction, "right")
                self.assertEqual(game.pending_direction, "right")
                self.assertEqual(game.score, 0)
                self.assertEqual(game.state, "running")
                self.assert_valid_food(game)

    def test_board_rejects_dimensions_below_four(self):
        for width, height in [(3, 6), (8, 3), (0, 6), (8, -1)]:
            with self.subTest(width=width, height=height):
                with self.assertRaises(ValueError):
                    self.make_game(width, height)

    def test_normal_movement_preserves_length_and_score(self):
        game = self.make_game()
        self.configure(game, [(3, 2), (2, 2), (1, 2)])
        game.tick()
        self.assertEqual(game.snake, [(4, 2), (3, 2), (2, 2)])
        self.assertEqual(game.score, 0)
        self.assertEqual(game.food, (6, 4))
        self.assertEqual(game.state, "running")

    def test_eating_grows_scores_and_places_food_on_free_cell(self):
        game = self.make_game()
        self.configure(game, [(3, 2), (2, 2), (1, 2)], food=(4, 2))
        game.tick()
        self.assertEqual(game.snake, [(4, 2), (3, 2), (2, 2), (1, 2)])
        self.assertEqual(game.score, 1)
        self.assertEqual(game.state, "running")
        self.assert_valid_food(game)

    def test_all_four_walls_end_game_without_changing_body(self):
        cases = [
            ("left", [(0, 2), (1, 2), (2, 2)]),
            ("right", [(7, 2), (6, 2), (5, 2)]),
            ("up", [(2, 0), (2, 1), (2, 2)]),
            ("down", [(2, 5), (2, 4), (2, 3)]),
        ]
        for direction, body in cases:
            with self.subTest(direction=direction):
                game = self.make_game()
                self.configure(game, body, direction=direction)
                game.tick()
                self.assertEqual(game.state, "game_over")
                self.assertEqual(game.snake, body)
                self.assertEqual(game.score, 0)
                self.assertEqual(game.food, (6, 4))

    def test_body_collision_ends_game_without_changing_body(self):
        game = self.make_game()
        body = [(2, 2), (1, 2), (1, 3), (2, 3), (3, 3), (3, 2), (4, 2)]
        self.configure(game, body)
        game.tick()
        self.assertEqual(game.state, "game_over")
        self.assertEqual(game.snake, body)
        self.assertEqual(game.score, 0)

    def test_entering_departing_tail_cell_is_allowed(self):
        game = self.make_game()
        self.configure(game, [(2, 2), (1, 2), (1, 3), (2, 3)])
        self.assertTrue(game.change_direction("down"))
        game.tick()
        self.assertEqual(game.snake, [(2, 3), (2, 2), (1, 2), (1, 3)])
        self.assertEqual(game.state, "running")
        self.assertEqual(game.score, 0)

    def test_invalid_same_and_reverse_inputs_do_not_consume_turn(self):
        game = self.make_game()
        self.configure(game, [(3, 2), (2, 2), (1, 2)])
        for direction in ["diagonal", "", "UP", "right", "left"]:
            with self.subTest(direction=direction):
                self.assertFalse(game.change_direction(direction))
        self.assertTrue(game.change_direction("up"))
        game.tick()
        self.assertEqual(game.snake, [(3, 1), (3, 2), (2, 2)])

    def test_two_rapid_turns_cannot_reverse_between_ticks(self):
        game = self.make_game()
        self.configure(game, [(3, 3), (2, 3), (1, 3)])
        self.assertTrue(game.change_direction("up"))
        self.assertFalse(game.change_direction("left"))
        game.tick()
        self.assertEqual(game.snake, [(3, 2), (3, 3), (2, 3)])
        self.assertTrue(game.change_direction("left"))
        game.tick()
        self.assertEqual(game.snake, [(2, 2), (3, 2), (3, 3)])
        self.assertEqual(game.state, "running")

    def test_pause_freezes_game_and_resume_allows_movement(self):
        game = self.make_game()
        body = [(3, 2), (2, 2), (1, 2)]
        self.configure(game, body)
        game.toggle_pause()
        self.assertEqual(game.state, "paused")
        self.assertFalse(game.change_direction("up"))
        game.tick()
        game.tick()
        self.assertEqual(game.snake, body)
        self.assertEqual(game.score, 0)
        self.assertEqual(game.food, (6, 4))
        game.toggle_pause()
        self.assertEqual(game.state, "running")
        self.assertTrue(game.change_direction("up"))
        game.tick()
        self.assertEqual(game.snake[0], (3, 1))

    def test_finished_games_ignore_tick_turn_and_pause(self):
        for state in ["game_over", "won"]:
            with self.subTest(state=state):
                game = self.make_game()
                game.state = state
                body = list(game.snake)
                self.assertFalse(game.change_direction("up"))
                game.tick()
                game.toggle_pause()
                self.assertEqual(game.state, state)
                self.assertEqual(game.snake, body)

    def test_reset_clears_score_game_state_and_pending_turn(self):
        game = self.make_game()
        self.assertTrue(game.change_direction("down"))
        game.score = 9
        game.state = "game_over"
        game.food = None
        game.reset()
        self.assertEqual(game.state, "running")
        self.assertEqual(game.score, 0)
        self.assertEqual(len(game.snake), 3)
        self.assertEqual(game.direction, "right")
        self.assertEqual(game.pending_direction, "right")
        head_x, head_y = game.snake[0]
        self.assertEqual(game.snake, [(head_x, head_y),
                                     (head_x - 1, head_y),
                                     (head_x - 2, head_y)])
        self.assert_valid_food(game)
        self.assertTrue(game.change_direction("up"))

    def test_eating_last_free_cell_wins_without_generating_food(self):
        game = self.make_game(4, 4)
        complete_path = [
            (0, 0), (1, 0), (2, 0), (3, 0),
            (3, 1), (2, 1), (1, 1), (0, 1),
            (0, 2), (1, 2), (2, 2), (3, 2),
            (3, 3), (2, 3), (1, 3), (0, 3),
        ]
        self.configure(game, complete_path[1:], direction="left", food=(0, 0))
        game.tick()
        self.assertEqual(game.state, "won")
        self.assertEqual(game.snake, complete_path)
        self.assertEqual(len(set(game.snake)), 16)
        self.assertEqual(game.score, 1)
        self.assertIsNone(game.food)
        game.tick()
        self.assertEqual(game.snake, complete_path)


if __name__ == "__main__":
    unittest.main()
