import importlib.util
import os
import sys
import types
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
COMMON_DIR = os.path.join(ROOT, "game", "res", "tankarena", "scripts", "common")
SERVICE_PATH = os.path.join(
    ROOT, "game", "res", "tankarena", "scripts", "service",
    "OfflineBattleService.py")
sys.path.insert(0, COMMON_DIR)


class FakeServiceBase(object):
    def addTimer(self, initial_delay, repeat_delay):
        self.timer_configuration = (initial_delay, repeat_delay)
        return 17


class FakeClientMailbox(object):
    def __init__(self):
        self.snapshots = []
        self.events = []

    def onBattleSnapshot(self, snapshot):
        self.snapshots.append(snapshot)

    def onBattleEvent(self, event):
        self.events.append(event)


class FakePlayerMailbox(object):
    def __init__(self):
        self.client_messages = FakeClientMailbox()

    def deliverBattleSnapshot(self, snapshot):
        self.client_messages.onBattleSnapshot(snapshot)

    def deliverBattleEvent(self, event):
        self.client_messages.onBattleEvent(event)


def load_service_module(clock):
    fake_bigworld = types.ModuleType("BigWorld")
    fake_bigworld.Service = FakeServiceBase
    fake_bigworld.time = lambda: clock[0]

    fake_service_utils = types.ModuleType("service_utils")
    fake_service_utils.addStandardWatchers = lambda unused_class: None

    old_bigworld = sys.modules.get("BigWorld")
    old_service_utils = sys.modules.get("service_utils")
    sys.modules["BigWorld"] = fake_bigworld
    sys.modules["service_utils"] = fake_service_utils
    try:
        spec = importlib.util.spec_from_file_location(
            "tankarena_offline_battle_service_test", SERVICE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if old_bigworld is None:
            sys.modules.pop("BigWorld", None)
        else:
            sys.modules["BigWorld"] = old_bigworld
        if old_service_utils is None:
            sys.modules.pop("service_utils", None)
        else:
            sys.modules["service_utils"] = old_service_utils


class BigWorldAdapterTests(unittest.TestCase):
    def test_service_rpc_drives_room_and_publishes_client_snapshots(self):
        clock = [0.0]
        module = load_service_module(clock)
        service = module.OfflineBattleService()
        mailbox = FakePlayerMailbox()

        joined, = service.join(501, "offline-player", "medium", mailbox)
        self.assertTrue(joined["ok"])
        self.assertEqual(joined["phase"], "lobby")
        self.assertTrue(mailbox.client_messages.snapshots)

        ready, = service.setReady(501, True)
        self.assertTrue(ready["ok"])
        started, = service.startBattle(501, 1, 1, True)
        self.assertTrue(started["ok"])
        self.assertEqual(started["phase"], "active")
        self.assertTrue(any(event["type"] == "battle_started"
                            for event in mailbox.client_messages.events))

        moved, = service.submitInput(501, 1, 1.0, 0.0)
        self.assertTrue(moved["ok"])
        clock[0] = 0.1
        service.onTimer(17, None)
        self.assertEqual(service._room.phase, "active")
        self.assertGreater(len(mailbox.client_messages.snapshots), 1)

        snapshot, = service.snapshot(501)
        self.assertEqual(snapshot["phase"], "active")
        self.assertNotIn("mailbox", snapshot["players"][0])

    def test_service_returns_safe_rejections(self):
        clock = [1.0]
        module = load_service_module(clock)
        service = module.OfflineBattleService()
        response, = service.setReady(12345, True)
        self.assertFalse(response["ok"])
        self.assertIn("player is not in this room", response["error"])


if __name__ == "__main__":
    unittest.main()
