"""Thin client proxy; all authoritative match state lives in the ServiceApp."""

import BigWorld


class TankPlayer(BigWorld.Proxy):
    def __init__(self):
        BigWorld.Proxy.__init__(self)
        self._joinedBattleService = False

    def onEntitiesEnabled(self):
        # Unknown offline accounts are accepted by server/bw.xml.  The account
        # name is supplied by BigWorld's login/billing layer, never by a battle
        # action after the session has been established.
        self._callService(
            "join", self.id, self.accountName, self.vehicleCode, self)
        self._joinedBattleService = True

    def setVehicle(self, vehicle_code):
        self._callService("setVehicle", self.id, vehicle_code)

    def setReady(self, is_ready):
        self._callService("setReady", self.id, is_ready)

    def startBattle(self, team_one_size, team_two_size, fill_bots):
        self._callService(
            "startBattle", self.id, team_one_size, team_two_size, fill_bots)

    def resetBattle(self):
        self._callService("resetBattle", self.id)

    def submitInput(self, sequence, throttle, steering):
        self._callService(
            "submitInput", self.id, sequence, throttle, steering)

    def submitAim(self, sequence, relative_yaw, pitch):
        self._callService(
            "submitAim", self.id, sequence, relative_yaw, pitch)

    def fire(self, sequence):
        self._callService("fire", self.id, sequence)

    def requestSnapshot(self):
        self._callService("snapshot", self.id)

    def leaveBattle(self):
        self._callService("leave", self.id)

    def deliverBattleSnapshot(self, snapshot):
        self.client.onBattleSnapshot(snapshot)

    def deliverBattleEvent(self, event):
        self.client.onBattleEvent(event)

    def onClientDeath(self):
        if self._joinedBattleService:
            self._callService("leave", self.id)
        self.destroy()

    def _callService(self, method_name, *args):
        try:
            service = BigWorld.services["OfflineBattleService"]
            deferred = getattr(service, method_name)(*args)
        except Exception as error:
            self._notify_error("battle service is unavailable")
            print("TankPlayer service call %s failed: %s" %
                  (method_name, error))
            return

        if hasattr(deferred, "addCallbacks"):
            deferred.addCallbacks(
                self._onServiceResult,
                lambda failure: self._onServiceFailure(method_name, failure))
        else:
            self._onServiceResult(deferred)

    def _onServiceResult(self, result):
        # Service RPCs resolve to a tuple matching the ReturnValues section in
        # the .def.  Accept a direct dictionary as well for local test doubles.
        if isinstance(result, tuple) and len(result) == 1:
            result = result[0]
        if isinstance(result, dict) and not result.get("ok", True):
            self._notify_error(result.get("error", "battle request rejected"))
        return result

    def _onServiceFailure(self, method_name, failure):
        print("TankPlayer service request %s failed: %s" %
              (method_name, failure))
        self._notify_error("battle service request failed")
        return failure

    def _notify_error(self, message):
        try:
            self.client.onBattleEvent({"type": "error", "message": message})
        except Exception:
            pass
