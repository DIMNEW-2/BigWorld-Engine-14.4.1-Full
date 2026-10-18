"""Minimal personality entry points for the offline TankArena server."""


def onInit(is_reload):
    print("TankArena personality loaded; reload=%s" % bool(is_reload))


def onFini():
    print("TankArena personality unloaded")


def onAppReady(is_bootstrap, did_autoload_entities_from_db):
    print("TankArena app ready; bootstrap=%s autoload=%s" %
          (bool(is_bootstrap), bool(did_autoload_entities_from_db)))


def onBaseAppReady(is_bootstrap, did_autoload_entities_from_db):
    # No persistent world objects are required by this service-based starter.
    return


def onAppShutDown(state):
    return
