import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RULES_DIR = os.path.join(ROOT, "game", "res", "tankarena", "scripts", "common")
sys.path.insert(0, RULES_DIR)

from battle_rules import (  # noqa: E402
    BattleError,
    BattleRoom,
    DEMO_VEHICLE_PROFILES,
    PHASE_ACTIVE,
    PHASE_FINISHED,
    PHASE_LOBBY,
    TEAM_ONE,
    TEAM_TWO,
)


def ready_room(**kwargs):
    room = BattleRoom(seed=7, **kwargs)
    room.join(101, "alpha", "medium", team=TEAM_ONE, now=0.0)
    room.join(202, "bravo", "medium", team=TEAM_TWO, now=0.0)
    room.set_ready(101, True)
    room.set_ready(202, True)
    return room


class BattleRoomTests(unittest.TestCase):
    def test_join_balances_teams_and_validates_vehicle(self):
        room = BattleRoom(seed=1)
        first = room.join(11, "Moscow", "medium", now=10.0)
        second = room.join(12, "Игрок", "light", now=10.0)

        self.assertEqual(first["host_id"], 11)
        self.assertEqual(room._players[11]["team"], TEAM_ONE)
        self.assertEqual(room._players[12]["team"], TEAM_TWO)
        self.assertEqual(second["phase"], PHASE_LOBBY)
        with self.assertRaises(BattleError):
            room.join(13, "bad vehicle", "not-a-tank", now=10.0)
        with self.assertRaises(BattleError):
            room.join(14, "bad name\n", "medium", now=10.0)

    def test_start_is_host_only_and_fills_empty_slots_with_server_bots(self):
        room = BattleRoom(seed=3)
        room.join(1, "host", "medium", team=TEAM_ONE, now=0.0)
        room.join(2, "guest", "light", team=TEAM_TWO, now=0.0)
        with self.assertRaises(BattleError):
            room.start(2, 2, 2, now=1.0)
        with self.assertRaises(BattleError):
            room.start(1, 2, 2, now=1.0)

        room.set_ready(1, True)
        room.set_ready(2, True)
        state = room.start(1, 2, 2, fill_bots=True, now=1.0)
        self.assertEqual(state["phase"], PHASE_ACTIVE)
        self.assertEqual(state["team_sizes"], {"1": 2, "2": 2})
        self.assertEqual(sum(row["is_bot"] for row in state["players"]), 2)

    def test_single_player_can_start_against_a_filled_bot_team(self):
        room = BattleRoom(seed=2)
        room.join(71, "solo", "medium", team=TEAM_ONE, now=0.0)
        room.set_ready(71, True)
        state = room.start(71, 1, 3, fill_bots=True, now=1.0)
        self.assertEqual(state["phase"], PHASE_ACTIVE)
        self.assertEqual(state["team_sizes"], {"1": 1, "2": 3})
        self.assertEqual(sum(row["is_bot"] for row in state["players"]), 3)

    def test_input_is_server_validated_and_applied_on_tick(self):
        room = BattleRoom(seed=4)
        room.join(1, "driver", "light", team=TEAM_ONE, now=0.0)
        room.set_ready(1, True)
        room.start(1, 1, 1, fill_bots=True, now=1.0)

        with self.assertRaises(BattleError):
            room.submit_input(1, 1, 1.01, 0.0, now=1.05)
        with self.assertRaises(BattleError):
            room.submit_input(1, 1, float("nan"), 0.0, now=1.05)
        room.submit_input(1, 1, 1.0, 0.0, now=1.05)
        before = list(room._players[1]["position"])
        room.tick(now=1.15)
        after = room._players[1]["position"]
        self.assertGreater(after[0], before[0])
        with self.assertRaises(BattleError):
            room.submit_input(1, 1, 0.0, 0.0, now=1.2)

    def test_shot_uses_server_side_ray_ammo_reload_and_damage(self):
        profiles = {key: dict(value)
                    for key, value in DEMO_VEHICLE_PROFILES.items()}
        profiles["medium"].update({
            "range": 750.0,
            "penetration": 1000.0,
            "damage": 100.0,
            "reload_seconds": 2.0,
            "dispersion": 0.00001,
        })
        room = BattleRoom(profiles=profiles, seed=1, duration_seconds=300)
        room.join(1, "gunner", "medium", team=TEAM_ONE, now=0.0)
        room.join(2, "target", "medium", team=TEAM_TWO, now=0.0)
        room.set_ready(1, True)
        room.set_ready(2, True)
        room.start(1, 1, 1, fill_bots=False, now=1.0)

        shooter = room._players[1]
        target = room._players[2]
        shooter["position"] = [0.0, 0.0]
        shooter["yaw"] = 0.0
        target["position"] = [0.0, 50.0]
        target["yaw"] = 3.141592653589793
        initial_health = target["health"]
        initial_ammo = shooter["ammo"]

        result = room.fire(1, 1, now=2.0)
        self.assertTrue(result["hit"])
        self.assertLess(target["health"], initial_health)
        self.assertEqual(shooter["ammo"], initial_ammo - 1)
        with self.assertRaises(BattleError):
            room.fire(1, 2, now=2.5)
        with self.assertRaises(BattleError):
            room.fire(1, 1, now=4.5)
        self.assertEqual(shooter["ammo"], initial_ammo - 1)

    def test_capture_pauses_when_contested_and_finishes_round(self):
        room = ready_room(duration_seconds=300)
        room.start(101, 1, 1, fill_bots=False, now=1.0)
        attacker = room._players[101]
        defender = room._players[202]
        attacker["position"] = [400.0, 0.0]
        defender["position"] = [-330.0, 0.0]

        room.tick(now=1.1)
        progress = room._capture[TEAM_ONE]
        self.assertGreater(progress, 0.0)

        defender["position"] = [400.0, 0.0]
        room.tick(now=1.2)
        self.assertAlmostEqual(room._capture[TEAM_ONE], progress)

        defender["position"] = [-330.0, 0.0]
        for step in range(1, 205):
            room.tick(now=1.2 + step * 0.25)
            if room.phase == PHASE_FINISHED:
                break
        self.assertEqual(room.phase, PHASE_FINISHED)
        self.assertEqual(room.snapshot(now=60.0)["result"]["winner"], TEAM_ONE)
        self.assertEqual(room.snapshot(now=60.0)["result"]["reason"], "capture")

    def test_disconnect_of_last_tank_finishes_battle(self):
        room = ready_room(duration_seconds=300)
        room.start(101, 1, 1, fill_bots=False, now=1.0)
        state = room.leave(202, now=2.0)
        self.assertEqual(state["phase"], PHASE_FINISHED)
        self.assertEqual(state["result"]["winner"], TEAM_ONE)
        self.assertEqual(state["result"]["reason"], "elimination")

    def test_timeout_uses_surviving_health_as_tiebreak(self):
        room = ready_room(duration_seconds=60)
        room.start(101, 1, 1, fill_bots=False, now=0.0)
        room._players[101]["health"] = 800
        room._players[202]["health"] = 400
        room.tick(now=60.0)
        result = room.snapshot(now=60.0)["result"]
        self.assertEqual(result["reason"], "timeout")
        self.assertEqual(result["winner"], TEAM_ONE)

    def test_host_can_reset_finished_room_for_next_round(self):
        room = ready_room(duration_seconds=300)
        room.start(101, 1, 1, fill_bots=True, now=1.0)
        room._finish(TEAM_ONE, "test", now=2.0)
        old_round = room._round_id
        state = room.reset(101, now=3.0)
        self.assertEqual(state["phase"], PHASE_LOBBY)
        self.assertEqual(state["round"], old_round + 1)
        self.assertEqual(state["team_sizes"], {"1": 1, "2": 1})
        self.assertFalse(room._players[101]["ready"])
        self.assertFalse(any(player["is_bot"] for player in room._players.values()))
        with self.assertRaises(BattleError):
            room.reset(202, now=3.0)

    def test_finished_room_without_humans_is_reopened(self):
        room = BattleRoom(seed=9)
        room.join(1, "host", "medium", now=0.0)
        room.set_ready(1, True)
        room.start(1, 1, 1, fill_bots=True, now=1.0)
        room._players[1]["connected"] = False
        room._players[1]["mailbox"] = None
        room._finish(0, "test", now=2.0)
        self.assertEqual(room.phase, PHASE_LOBBY)
        self.assertEqual(room._players, {})
        self.assertIsNone(room.host_id)

    def test_snapshot_does_not_expose_internal_mailbox(self):
        room = BattleRoom(seed=5)
        room.join(1, "private", "medium", mailbox=object(), now=0.0)
        snapshot = room.snapshot(now=0.0)
        self.assertNotIn("mailbox", snapshot["players"][0])
        self.assertEqual(snapshot["players"][0]["player_id"], 1)


if __name__ == "__main__":
    unittest.main()
