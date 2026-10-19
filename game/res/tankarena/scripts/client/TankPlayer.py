"""Minimal client-side receiver for BigWorld client builds.

The user interface can observe ``battleSnapshot`` and ``battleEvents``.  This
module intentionally contains no WoT client hooks or copyrighted game assets.
"""

import BigWorld


class TankPlayer(BigWorld.Entity):
    def __init__(self):
        BigWorld.Entity.__init__(self)
        self.battleSnapshot = None
        self.battleEvents = []

    def onBattleSnapshot(self, snapshot):
        self.battleSnapshot = snapshot

    def onBattleEvent(self, event):
        self.battleEvents.append(event)
        if len(self.battleEvents) > 128:
            del self.battleEvents[:-128]
