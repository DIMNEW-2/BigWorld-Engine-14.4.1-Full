"""BigWorld ServiceApp adapter for the tested TankArena rules."""

import BigWorld
import service_utils

from battle_rules import BattleError, BattleRoom, DEFAULT_MAP


class OfflineBattleService(BigWorld.Service):
    """Owns one in-memory battle room and relays snapshots to player proxies."""

    TICK_SECONDS = 0.1
    SNAPSHOT_EVERY_TICKS = 2

    def __init__(self):
        BigWorld.Service.__init__(self)
        self._room = BattleRoom(map_name=DEFAULT_MAP)
        self._last_time = BigWorld.time()
        self._tick_count = 0
        self._timer_id = self.addTimer(self.TICK_SECONDS, self.TICK_SECONDS)
        print("OfflineBattleService ready; map=%s" % DEFAULT_MAP)

    def join(self, player_id, display_name, vehicle_code, player_mailbox):
        return self._command(
            lambda: self._room.join(
                player_id, display_name, vehicle_code,
                mailbox=player_mailbox, now=BigWorld.time()),
            publish=True)

    def leave(self, player_id):
        return self._command(
            lambda: self._room.leave(player_id, now=BigWorld.time()),
            publish=True)

    def setVehicle(self, player_id, vehicle_code):
        return self._command(
            lambda: self._room.set_vehicle(player_id, vehicle_code),
            publish=True)

    def setReady(self, player_id, is_ready):
        return self._command(
            lambda: self._room.set_ready(player_id, is_ready),
            publish=True)

    def startBattle(self, player_id, team_one_size, team_two_size,
                    fill_bots):
        return self._command(
            lambda: self._room.start(
                player_id, team_one_size, team_two_size,
                fill_bots=fill_bots, now=BigWorld.time()),
            publish=True)

    def resetBattle(self, player_id):
        return self._command(
            lambda: self._room.reset(player_id, now=BigWorld.time()),
            publish=True)

    def submitInput(self, player_id, sequence, throttle, steering):
        return self._command(
            lambda: self._room.submit_input(
                player_id, sequence, throttle, steering,
                now=BigWorld.time()),
            publish=False)

    def submitAim(self, player_id, sequence, relative_yaw, pitch):
        return self._command(
            lambda: self._room.submit_aim(
                player_id, sequence, relative_yaw, pitch,
                now=BigWorld.time()),
            publish=False)

    def fire(self, player_id, sequence):
        return self._command(
            lambda: self._room.fire(
                player_id, sequence, now=BigWorld.time()),
            publish=True)

    def snapshot(self, player_id):
        def make_snapshot():
            self._room.status_for(player_id, now=BigWorld.time())
            return self._room.snapshot(now=BigWorld.time())
        return self._command(make_snapshot, publish=False)

    def _command(self, callback, publish):
        try:
            result = callback()
            if isinstance(result, dict):
                response = result
            else:
                response = {"ok": True, "value": result}
        except BattleError as error:
            response = {"ok": False, "error": str(error)}
        except Exception as error:
            # Do not leak a traceback or internal state to an untrusted client.
            print("OfflineBattleService command failed: %s" % error)
            response = {"ok": False, "error": "server command failed"}

        self._send_events()
        if publish:
            self._publish_snapshot()
        return (response,)

    def _send_events(self, events=None):
        if events is None:
            events = self._room.drain_events()
        for event in events:
            for unused_player_id, mailbox in self._room.connected_humans():
                try:
                    mailbox.deliverBattleEvent(event)
                except Exception as error:
                    print("OfflineBattleService event delivery failed: %s" % error)

    def _publish_snapshot(self):
        snapshot = self._room.snapshot(now=BigWorld.time())
        for unused_player_id, mailbox in self._room.connected_humans():
            try:
                mailbox.deliverBattleSnapshot(snapshot)
            except Exception as error:
                print("OfflineBattleService snapshot delivery failed: %s" % error)

    def onTimer(self, timer_id, user_data):
        if timer_id != self._timer_id:
            return
        now = BigWorld.time()
        events = self._room.tick(now=now)
        self._send_events(events)
        self._tick_count += 1
        if self._tick_count % self.SNAPSHOT_EVERY_TICKS == 0:
            self._publish_snapshot()

    def onDestroy(self):
        print("OfflineBattleService stopped")


service_utils.addStandardWatchers(OfflineBattleService)
