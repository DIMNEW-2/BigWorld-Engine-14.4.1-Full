"""Deterministic, server-authoritative rules for the TankArena sample.

This module deliberately has no BigWorld imports so the rules can be tested
with stock Python.  The vehicle profiles below are sandbox defaults, not
recovered retail World of Tanks statistics.  A real client integration should
replace them with validated profiles extracted from the user's matching
client version.
"""

from __future__ import division

import math
import random
import time


PHASE_LOBBY = "lobby"
PHASE_ACTIVE = "active"
PHASE_FINISHED = "finished"

TEAM_ONE = 1
TEAM_TWO = 2
TEAMS = (TEAM_ONE, TEAM_TWO)

MAX_TEAM_SIZE = 15
MAX_PLAYERS = MAX_TEAM_SIZE * 2
MAX_BATTLE_SECONDS = 60 * 60
MAX_TICK_SECONDS = 0.25
INPUT_TIMEOUT_SECONDS = 0.75

# Identifiers only. This sample does not ship map geometry or game assets.
MAPS = (
    "01_karelia",
    "02_malinovka",
    "04_himmelsdorf",
    "05_prohorovka",
)
DEFAULT_MAP = MAPS[0]

ARENA_LIMIT = 500.0
SPAWN_X = 330.0
SPAWN_Z_SPACING = 12.0
CAPTURE_BASE_X = 400.0
CAPTURE_RADIUS = 34.0
CAPTURE_LIMIT = 100.0
CAPTURE_RATE = 2.0
CAPTURE_DECAY_RATE = 3.0


# Small, configurable prototype profiles. These are intentionally generic.
# Do not treat them as historical or client-accurate WoT parameters.
DEMO_VEHICLE_PROFILES = {
    "light": {
        "max_health": 700,
        "max_speed": 21.0,
        "acceleration": 8.0,
        "reverse_factor": 0.48,
        "turn_rate": 1.25,
        "damage": 125.0,
        "penetration": 150.0,
        "reload_seconds": 3.8,
        "range": 600.0,
        "front_armor": 55.0,
        "side_armor": 32.0,
        "rear_armor": 24.0,
        "ammo": 40,
        "radius": 1.8,
        "dispersion": 0.008,
    },
    "medium": {
        "max_health": 1000,
        "max_speed": 15.0,
        "acceleration": 6.0,
        "reverse_factor": 0.45,
        "turn_rate": 0.90,
        "damage": 190.0,
        "penetration": 185.0,
        "reload_seconds": 5.5,
        "range": 650.0,
        "front_armor": 105.0,
        "side_armor": 65.0,
        "rear_armor": 42.0,
        "ammo": 36,
        "radius": 2.0,
        "dispersion": 0.006,
    },
    "heavy": {
        "max_health": 1500,
        "max_speed": 10.0,
        "acceleration": 4.0,
        "reverse_factor": 0.40,
        "turn_rate": 0.62,
        "damage": 300.0,
        "penetration": 220.0,
        "reload_seconds": 9.0,
        "range": 620.0,
        "front_armor": 205.0,
        "side_armor": 125.0,
        "rear_armor": 78.0,
        "ammo": 30,
        "radius": 2.4,
        "dispersion": 0.007,
    },
    "td": {
        "max_health": 950,
        "max_speed": 12.0,
        "acceleration": 4.8,
        "reverse_factor": 0.42,
        "turn_rate": 0.68,
        "damage": 340.0,
        "penetration": 270.0,
        "reload_seconds": 10.0,
        "range": 750.0,
        "front_armor": 145.0,
        "side_armor": 82.0,
        "rear_armor": 48.0,
        "ammo": 25,
        "radius": 2.1,
        "dispersion": 0.005,
    },
}

_PROFILE_FIELDS = (
    "max_speed",
    "acceleration",
    "reverse_factor",
    "turn_rate",
    "damage",
    "penetration",
    "reload_seconds",
    "range",
    "front_armor",
    "side_armor",
    "rear_armor",
    "radius",
    "dispersion",
)

try:
    _STRING_TYPES = (basestring,)
    _INTEGER_TYPES = (int, long)
    _NUMBER_TYPES = (int, long, float)
except NameError:  # Python 3 test runner
    _STRING_TYPES = (str,)
    _INTEGER_TYPES = (int,)
    _NUMBER_TYPES = (int, float)


class BattleError(Exception):
    """A safe, expected rejection of a game action."""


def _is_finite_number(value):
    if isinstance(value, bool) or not isinstance(value, _NUMBER_TYPES):
        return False
    return not math.isnan(float(value)) and not math.isinf(float(value))


def _require_int(value, name, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, _INTEGER_TYPES):
        raise BattleError("%s must be an integer" % name)
    if low is not None and value < low:
        raise BattleError("%s is out of range" % name)
    if high is not None and value > high:
        raise BattleError("%s is out of range" % name)
    return value


def _require_number(value, name, low=None, high=None):
    if not _is_finite_number(value):
        raise BattleError("%s must be a finite number" % name)
    value = float(value)
    if low is not None and value < low:
        raise BattleError("%s is out of range" % name)
    if high is not None and value > high:
        raise BattleError("%s is out of range" % name)
    return value


def _normalize_angle(angle):
    return (float(angle) + math.pi) % (2.0 * math.pi) - math.pi


def _angle_delta(target, current):
    return _normalize_angle(target - current)


def _rotate_towards(current, target, max_delta):
    delta = _angle_delta(target, current)
    if abs(delta) <= max_delta:
        return _normalize_angle(target)
    return _normalize_angle(current + (max_delta if delta > 0.0 else -max_delta))


def _approach(current, target, amount):
    if current < target:
        return min(current + amount, target)
    return max(current - amount, target)


def _copy_profiles(profiles):
    if not isinstance(profiles, dict) or not profiles:
        raise BattleError("vehicle profiles are missing")

    copied = {}
    for code, raw in profiles.items():
        if not isinstance(code, _STRING_TYPES) or not code or len(code) > 32:
            raise BattleError("invalid vehicle profile code")
        if not isinstance(raw, dict):
            raise BattleError("vehicle profile %s is invalid" % code)

        profile = {}
        for field in _PROFILE_FIELDS:
            value = raw.get(field)
            if not _is_finite_number(value) or float(value) <= 0.0:
                raise BattleError("vehicle profile %s has invalid %s" %
                                  (code, field))
            profile[field] = float(value)

        for field in ("max_health", "ammo"):
            value = raw.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise BattleError("vehicle profile %s has invalid %s" %
                                  (code, field))
            profile[field] = value

        if profile["reverse_factor"] > 1.0:
            raise BattleError("vehicle reverse_factor must be 0..1")
        if profile["dispersion"] > 0.25:
            raise BattleError("vehicle dispersion is too large")
        copied[code] = profile
    return copied


def _display_name(value):
    if not isinstance(value, _STRING_TYPES):
        raise BattleError("player name must be text")
    for character in value:
        if ord(character) < 32 or ord(character) == 127:
            raise BattleError("player name contains a control character")
    value = value.strip()
    if not value or len(value) > 32:
        raise BattleError("player name must contain 1..32 characters")
    return value


class BattleRoom(object):
    """One authoritative two-team room.

    The service adapter owns a single BattleRoom in this starter project.
    State is in memory: a process restart closes the current round.
    """

    def __init__(self, map_name=DEFAULT_MAP, duration_seconds=900,
                 profiles=None, seed=None, clock=None):
        if map_name not in MAPS:
            raise BattleError("unsupported map")
        self._duration_seconds = _require_int(
            duration_seconds, "duration_seconds", 60, MAX_BATTLE_SECONDS)
        self._profiles = _copy_profiles(
            DEMO_VEHICLE_PROFILES if profiles is None else profiles)
        self._clock = time.time if clock is None else clock
        self._rng = random.Random(seed)

        self.map_name = map_name
        self.phase = PHASE_LOBBY
        self.host_id = None
        self._players = {}
        self._next_bot_id = -1
        self._created_at = self._now(None)
        self._started_at = None
        self._ends_at = None
        self._last_tick_at = None
        self._capture = {TEAM_ONE: 0.0, TEAM_TWO: 0.0}
        self._result = None
        self._events = []
        self._round_id = 1

    @staticmethod
    def _now(value):
        if value is None:
            value = time.time()
        if not _is_finite_number(value):
            raise BattleError("server time is invalid")
        return float(value)

    def _resolve_time(self, value):
        if value is None:
            value = self._clock()
        return self._now(value)

    def _profile(self, vehicle_code):
        if not isinstance(vehicle_code, _STRING_TYPES):
            raise BattleError("unknown vehicle")
        try:
            return self._profiles[vehicle_code]
        except KeyError:
            raise BattleError("unknown vehicle")

    def _emit(self, event_type, **fields):
        event = {"type": event_type, "round": self._round_id}
        event.update(fields)
        self._events.append(event)
        # Protect a long-lived room from a stalled or disconnected consumer.
        if len(self._events) > 2048:
            del self._events[:len(self._events) - 2048]
        return event

    def drain_events(self):
        events = self._events
        self._events = []
        return events

    def _team_members(self, team, include_disconnected=True):
        result = []
        for player in self._players.values():
            if player["team"] != team:
                continue
            if not include_disconnected and not player["connected"]:
                continue
            result.append(player)
        return result

    def _team_count(self, team):
        return len(self._team_members(team))

    def _choose_team(self, requested_team):
        if requested_team is not None:
            team = _require_int(requested_team, "team", TEAM_ONE, TEAM_TWO)
            if self._team_count(team) >= MAX_TEAM_SIZE:
                raise BattleError("team is full")
            return team

        counts = {team: self._team_count(team) for team in TEAMS}
        if counts[TEAM_ONE] <= counts[TEAM_TWO]:
            selected = TEAM_ONE
        else:
            selected = TEAM_TWO
        if counts[selected] >= MAX_TEAM_SIZE:
            selected = TEAM_TWO if selected == TEAM_ONE else TEAM_ONE
        if counts[selected] >= MAX_TEAM_SIZE:
            raise BattleError("battle is full")
        return selected

    def _spawn_position(self, team):
        members = self._team_members(team)
        slot = len(members)
        z = (slot - (MAX_TEAM_SIZE - 1) / 2.0) * SPAWN_Z_SPACING
        x = -SPAWN_X if team == TEAM_ONE else SPAWN_X
        yaw = math.pi / 2.0 if team == TEAM_ONE else -math.pi / 2.0
        return [x, z], yaw

    def join(self, player_id, name, vehicle_code="medium", team=None,
             mailbox=None, now=None):
        if self.phase != PHASE_LOBBY:
            raise BattleError("the battle is no longer accepting players")
        player_id = _require_int(player_id, "player_id", 1)
        if player_id in self._players:
            raise BattleError("player is already in this room")
        if len(self._players) >= MAX_PLAYERS:
            raise BattleError("battle is full")

        now = self._resolve_time(now)
        display_name = _display_name(name)
        profile = self._profile(vehicle_code)
        assigned_team = self._choose_team(team)
        position, yaw = self._spawn_position(assigned_team)

        player = self._make_player(
            player_id, display_name, vehicle_code, assigned_team,
            position, yaw, profile, is_bot=False, mailbox=mailbox)
        player["joined_at"] = now
        self._players[player_id] = player
        if self.host_id is None:
            self.host_id = player_id
        self._emit("player_joined", player_id=player_id,
                   name=display_name, team=assigned_team,
                   vehicle=vehicle_code)
        return self.snapshot(now=now)

    def _make_player(self, player_id, name, vehicle_code, team, position,
                     yaw, profile, is_bot, mailbox=None):
        return {
            "id": player_id,
            "name": name,
            "team": team,
            "vehicle": vehicle_code,
            "profile": profile,
            "mailbox": mailbox,
            "is_bot": bool(is_bot),
            "connected": True,
            "ready": bool(is_bot),
            "position": list(position),
            "yaw": _normalize_angle(yaw),
            "speed": 0.0,
            "throttle": 0.0,
            "steering": 0.0,
            "gun_yaw": 0.0,
            "gun_pitch": 0.0,
            "last_input_sequence": 0,
            "last_aim_sequence": 0,
            "last_shot_sequence": 0,
            "last_input_at": 0.0,
            "last_aim_at": 0.0,
            "next_fire_at": 0.0,
            "health": profile["max_health"],
            "ammo": profile["ammo"],
            "shots_fired": 0,
            "shots_hit": 0,
            "damage_dealt": 0,
            "kills": 0,
            "deaths": 0,
        }

    def set_vehicle(self, player_id, vehicle_code):
        if self.phase != PHASE_LOBBY:
            raise BattleError("vehicle cannot be changed after battle start")
        player = self._human_player(player_id)
        profile = self._profile(vehicle_code)
        player["vehicle"] = vehicle_code
        player["profile"] = profile
        player["health"] = profile["max_health"]
        player["ammo"] = profile["ammo"]
        self._emit("vehicle_changed", player_id=player["id"],
                   vehicle=vehicle_code)
        return self.snapshot()

    def set_ready(self, player_id, ready):
        if self.phase != PHASE_LOBBY:
            raise BattleError("readiness can only be changed in the lobby")
        player = self._human_player(player_id)
        if not isinstance(ready, bool):
            raise BattleError("ready must be true or false")
        player["ready"] = ready
        self._emit("ready_changed", player_id=player["id"], ready=ready)
        return self.snapshot()

    def _human_player(self, player_id):
        player_id = _require_int(player_id, "player_id", 1)
        try:
            player = self._players[player_id]
        except KeyError:
            raise BattleError("player is not in this room")
        if player["is_bot"]:
            raise BattleError("bots are controlled by the server")
        return player

    def start(self, player_id, team_one_size=15, team_two_size=15,
              fill_bots=True, now=None):
        if self.phase != PHASE_LOBBY:
            raise BattleError("battle has already started")
        player_id = _require_int(player_id, "player_id", 1)
        if player_id != self.host_id:
            raise BattleError("only the room host can start the battle")
        team_one_size = _require_int(
            team_one_size, "team_one_size", 1, MAX_TEAM_SIZE)
        team_two_size = _require_int(
            team_two_size, "team_two_size", 1, MAX_TEAM_SIZE)
        if not isinstance(fill_bots, bool):
            raise BattleError("fill_bots must be true or false")
        if not self._players:
            raise BattleError("the room is empty")

        for player in self._players.values():
            if not player["is_bot"] and not player["ready"]:
                raise BattleError("all human players must be ready")
        capacities = {TEAM_ONE: team_one_size, TEAM_TWO: team_two_size}
        for team in TEAMS:
            if self._team_count(team) > capacities[team]:
                raise BattleError("team size is smaller than its human roster")

        now = self._resolve_time(now)
        if fill_bots:
            for team in TEAMS:
                while self._team_count(team) < capacities[team]:
                    self._add_bot(team, now)
        elif not all(self._team_count(team) for team in TEAMS):
            raise BattleError("both teams need at least one tank")

        if not all(self._team_count(team) for team in TEAMS):
            raise BattleError("both teams need at least one tank")
        if len(self._players) > MAX_PLAYERS:
            raise BattleError("battle is full")

        self.phase = PHASE_ACTIVE
        self._started_at = now
        self._ends_at = now + self._duration_seconds
        self._last_tick_at = now
        for player in self._players.values():
            player["last_input_at"] = now
            player["last_aim_at"] = now
        self._emit("battle_started", map=self.map_name,
                   team_one_size=team_one_size,
                   team_two_size=team_two_size,
                   duration=self._duration_seconds)
        return self.snapshot(now=now)

    def _add_bot(self, team, now):
        player_id = self._next_bot_id
        self._next_bot_id -= 1
        count = self._team_count(team)
        vehicle_choices = ("light", "medium", "heavy", "td")
        vehicle_code = vehicle_choices[count % len(vehicle_choices)]
        if vehicle_code not in self._profiles:
            vehicle_code = sorted(self._profiles.keys())[0]
        profile = self._profile(vehicle_code)
        position, yaw = self._spawn_position(team)
        bot = self._make_player(
            player_id,
            "BOT-%02d" % abs(player_id),
            vehicle_code,
            team,
            position,
            yaw,
            profile,
            is_bot=True)
        bot["joined_at"] = now
        bot["last_input_at"] = now
        bot["last_aim_at"] = now
        self._players[player_id] = bot
        self._emit("bot_spawned", player_id=player_id,
                   name=bot["name"], team=team, vehicle=vehicle_code)

    def submit_input(self, player_id, sequence, throttle, steering, now=None):
        if self.phase != PHASE_ACTIVE:
            raise BattleError("movement is only accepted during a battle")
        player = self._human_player(player_id)
        if player["health"] <= 0 or not player["connected"]:
            raise BattleError("destroyed or disconnected tanks cannot move")
        sequence = _require_int(sequence, "sequence", 1)
        if sequence <= player["last_input_sequence"]:
            raise BattleError("stale movement sequence")
        throttle = _require_number(throttle, "throttle", -1.0, 1.0)
        steering = _require_number(steering, "steering", -1.0, 1.0)
        now = self._resolve_time(now)

        player["last_input_sequence"] = sequence
        player["throttle"] = throttle
        player["steering"] = steering
        player["last_input_at"] = now
        return {"ok": True, "sequence": sequence}

    def submit_aim(self, player_id, sequence, relative_yaw, pitch, now=None):
        if self.phase != PHASE_ACTIVE:
            raise BattleError("aim is only accepted during a battle")
        player = self._human_player(player_id)
        if player["health"] <= 0 or not player["connected"]:
            raise BattleError("destroyed or disconnected tanks cannot aim")
        sequence = _require_int(sequence, "sequence", 1)
        if sequence <= player["last_aim_sequence"]:
            raise BattleError("stale aim sequence")
        relative_yaw = _require_number(relative_yaw, "relative_yaw")
        pitch = _require_number(pitch, "pitch", -0.45, 0.45)
        now = self._resolve_time(now)

        requested = _normalize_angle(relative_yaw)
        elapsed = max(0.0, min(now - player["last_aim_at"], 1.0))
        max_turn = player["profile"]["turn_rate"] * 2.5 * max(elapsed, 0.05)
        player["gun_yaw"] = _rotate_towards(
            player["gun_yaw"], requested, max_turn)
        player["gun_pitch"] = pitch
        player["last_aim_sequence"] = sequence
        player["last_aim_at"] = now
        return {"ok": True, "sequence": sequence,
                "gun_yaw": player["gun_yaw"], "gun_pitch": pitch}

    def fire(self, player_id, sequence, now=None):
        if self.phase != PHASE_ACTIVE:
            raise BattleError("fire is only accepted during a battle")
        player = self._human_player(player_id)
        sequence = _require_int(sequence, "sequence", 1)
        if sequence <= player["last_shot_sequence"]:
            raise BattleError("stale shot sequence")
        player["last_shot_sequence"] = sequence
        now = self._resolve_time(now)
        return self._fire_player(player, now)

    def _fire_player(self, player, now):
        if self.phase != PHASE_ACTIVE:
            raise BattleError("battle is not active")
        if not player["connected"] or player["health"] <= 0:
            raise BattleError("destroyed or disconnected tanks cannot fire")
        if now < player["next_fire_at"]:
            raise BattleError("weapon is reloading")
        if player["ammo"] <= 0:
            raise BattleError("no ammunition")

        profile = player["profile"]
        player["ammo"] -= 1
        player["shots_fired"] += 1
        player["next_fire_at"] = now + profile["reload_seconds"]

        # Server-side dispersion; the client never submits damage or a target.
        spread = self._rng.gauss(0.0, profile["dispersion"])
        shot_yaw = _normalize_angle(player["yaw"] + player["gun_yaw"] + spread)
        direction_x = math.sin(shot_yaw)
        direction_z = math.cos(shot_yaw)
        origin_x, origin_z = player["position"]
        nearest = None
        nearest_distance = profile["range"] + 1.0

        for target in self._players.values():
            if (target["team"] == player["team"] or not target["connected"] or
                    target["health"] <= 0):
                continue
            target_x, target_z = target["position"]
            offset_x = target_x - origin_x
            offset_z = target_z - origin_z
            along = offset_x * direction_x + offset_z * direction_z
            if along <= 0.0 or along > profile["range"]:
                continue
            lateral = abs(offset_x * direction_z - offset_z * direction_x)
            hit_radius = target["profile"]["radius"] + along * 0.0015
            if lateral <= hit_radius and along < nearest_distance:
                nearest = target
                nearest_distance = along

        if nearest is None:
            event = self._emit("shot_missed", player_id=player["id"],
                               ammo=player["ammo"])
            return {"ok": True, "hit": False, "event": event}

        effective_armor = self._effective_armor(nearest, player)
        penetration = profile["penetration"] * self._rng.uniform(0.75, 1.25)
        penetrated = penetration >= effective_armor
        if penetrated:
            damage = int(round(profile["damage"] * self._rng.uniform(0.75, 1.25)))
            damage = max(1, damage)
        else:
            damage = 0

        nearest["shots_hit"] += 1
        if damage:
            nearest["health"] = max(0, nearest["health"] - damage)
            player["damage_dealt"] += damage
        if nearest["health"] <= 0:
            nearest["deaths"] += 1
            player["kills"] += 1
            nearest["speed"] = 0.0
            nearest["throttle"] = 0.0
            nearest["steering"] = 0.0

        event = self._emit(
            "shot_hit",
            player_id=player["id"],
            target_id=nearest["id"],
            damage=damage,
            penetrated=penetrated,
            health=nearest["health"],
            destroyed=nearest["health"] <= 0,
            ammo=player["ammo"])
        self._check_elimination(now)
        return {"ok": True, "hit": True, "event": event}

    @staticmethod
    def _effective_armor(target, shooter):
        target_x, target_z = target["position"]
        shooter_x, shooter_z = shooter["position"]
        to_shooter_x = shooter_x - target_x
        to_shooter_z = shooter_z - target_z
        distance = math.sqrt(to_shooter_x * to_shooter_x +
                             to_shooter_z * to_shooter_z)
        if distance <= 0.001:
            return target["profile"]["front_armor"]
        to_shooter_x /= distance
        to_shooter_z /= distance

        front_x = math.sin(target["yaw"])
        front_z = math.cos(target["yaw"])
        front_dot = front_x * to_shooter_x + front_z * to_shooter_z
        side_dot = abs(front_x * to_shooter_z - front_z * to_shooter_x)

        if front_dot >= 0.5:
            armor = target["profile"]["front_armor"]
            cosine = abs(front_dot)
        elif front_dot <= -0.5:
            armor = target["profile"]["rear_armor"]
            cosine = abs(front_dot)
        else:
            armor = target["profile"]["side_armor"]
            cosine = side_dot
        return armor / max(cosine, 0.25)

    def leave(self, player_id, now=None):
        player = self._human_player(player_id)
        now = self._resolve_time(now)
        if self.phase == PHASE_LOBBY:
            del self._players[player_id]
            self._emit("player_left", player_id=player_id)
            if self.host_id == player_id:
                humans = sorted(
                    key for key, value in self._players.items()
                    if not value["is_bot"] and value["connected"])
                self.host_id = humans[0] if humans else None
        else:
            player["connected"] = False
            player["mailbox"] = None
            player["ready"] = False
            player["throttle"] = 0.0
            player["steering"] = 0.0
            player["speed"] = 0.0
            if self.phase == PHASE_ACTIVE and player["health"] > 0:
                player["health"] = 0
                player["deaths"] += 1
                self._emit("player_disconnected", player_id=player_id)
                self._check_elimination(now)
            if self.host_id == player_id:
                humans = sorted(
                    key for key, value in self._players.items()
                    if not value["is_bot"] and value["connected"])
                self.host_id = humans[0] if humans else None
            if self.phase == PHASE_FINISHED and not any(
                    not value["is_bot"] and value["connected"]
                    for value in self._players.values()):
                self._clear_empty_room(now)
        return self.snapshot(now=now)

    def reset(self, player_id, now=None):
        if self.phase != PHASE_FINISHED:
            raise BattleError("only a finished battle can be reset")
        player_id = _require_int(player_id, "player_id", 1)
        if player_id != self.host_id:
            raise BattleError("only the room host can reset the battle")
        now = self._resolve_time(now)
        humans = [player for player in self._players.values()
                  if not player["is_bot"] and player["connected"]]
        if not humans:
            self._clear_empty_room(now)
            return self.snapshot(now=now)

        self._players = {}
        for team in TEAMS:
            members = sorted((player for player in humans if player["team"] == team),
                             key=lambda player: player["id"])
            for slot, old in enumerate(members):
                z = (slot - (len(members) - 1) / 2.0) * SPAWN_Z_SPACING
                x = -SPAWN_X if team == TEAM_ONE else SPAWN_X
                yaw = math.pi / 2.0 if team == TEAM_ONE else -math.pi / 2.0
                player = self._make_player(
                    old["id"], old["name"], old["vehicle"], team,
                    [x, z], yaw, old["profile"], is_bot=False,
                    mailbox=old["mailbox"])
                player["joined_at"] = old.get("joined_at", now)
                self._players[player["id"]] = player

        if self.host_id not in self._players:
            self.host_id = min(self._players.keys())
        self.phase = PHASE_LOBBY
        self._capture = {TEAM_ONE: 0.0, TEAM_TWO: 0.0}
        self._result = None
        self._started_at = None
        self._ends_at = None
        self._last_tick_at = None
        self._created_at = now
        self._next_bot_id = -1
        self._events = []
        self._round_id += 1
        self._emit("lobby_reset", host_id=self.host_id)
        return self.snapshot(now=now)

    def _clear_empty_room(self, now):
        self._players = {}
        self.host_id = None
        self.phase = PHASE_LOBBY
        self._capture = {TEAM_ONE: 0.0, TEAM_TWO: 0.0}
        self._result = None
        self._started_at = None
        self._ends_at = None
        self._last_tick_at = None
        self._created_at = now
        self._next_bot_id = -1
        self._events = []
        self._round_id += 1

    def _move_players(self, dt, now):
        for player in self._players.values():
            if not player["connected"] or player["health"] <= 0:
                continue
            if not player["is_bot"] and now - player["last_input_at"] > INPUT_TIMEOUT_SECONDS:
                player["throttle"] = 0.0
                player["steering"] = 0.0

            profile = player["profile"]
            target_speed = player["throttle"] * profile["max_speed"]
            if target_speed < 0.0:
                target_speed *= profile["reverse_factor"]
            acceleration = profile["acceleration"]
            player["speed"] = _approach(
                player["speed"], target_speed, acceleration * dt)
            player["yaw"] = _normalize_angle(
                player["yaw"] + player["steering"] * profile["turn_rate"] * dt)

            x, z = player["position"]
            x += math.sin(player["yaw"]) * player["speed"] * dt
            z += math.cos(player["yaw"]) * player["speed"] * dt
            clipped_x = max(-ARENA_LIMIT, min(ARENA_LIMIT, x))
            clipped_z = max(-ARENA_LIMIT, min(ARENA_LIMIT, z))
            if clipped_x != x or clipped_z != z:
                player["speed"] = 0.0
            player["position"] = [clipped_x, clipped_z]

    def _tick_bots(self, dt, now):
        bots = [player for player in self._players.values()
                if player["is_bot"] and player["connected"] and player["health"] > 0]
        for bot in bots:
            enemies = [player for player in self._players.values()
                       if player["team"] != bot["team"] and player["connected"]
                       and player["health"] > 0]
            if not enemies:
                bot["throttle"] = 0.0
                bot["steering"] = 0.0
                continue

            target = min(
                enemies,
                key=lambda player: self._distance(bot["position"], player["position"]))
            distance = self._distance(bot["position"], target["position"])
            desired_yaw = math.atan2(
                target["position"][0] - bot["position"][0],
                target["position"][1] - bot["position"][1])
            hull_error = _angle_delta(desired_yaw, bot["yaw"])
            bot["steering"] = max(-1.0, min(1.0, hull_error * 1.4))
            bot["throttle"] = 1.0 if distance > 24.0 else 0.0

            desired_gun_yaw = _angle_delta(desired_yaw, bot["yaw"])
            bot["gun_yaw"] = _rotate_towards(
                bot["gun_yaw"], desired_gun_yaw,
                bot["profile"]["turn_rate"] * 2.5 * dt)
            if (self.phase == PHASE_ACTIVE and
                    distance <= bot["profile"]["range"] and
                    abs(_angle_delta(desired_gun_yaw, bot["gun_yaw"])) <= 0.035 and
                    now >= bot["next_fire_at"] and bot["ammo"] > 0):
                self._fire_player(bot, now)
            if self.phase != PHASE_ACTIVE:
                break

    @staticmethod
    def _distance(first, second):
        dx = first[0] - second[0]
        dz = first[1] - second[1]
        return math.sqrt(dx * dx + dz * dz)

    def _tick_capture(self, dt, now):
        for team in TEAMS:
            enemy_base_x = CAPTURE_BASE_X if team == TEAM_ONE else -CAPTURE_BASE_X
            attackers = []
            defenders = []
            for player in self._players.values():
                if not player["connected"] or player["health"] <= 0:
                    continue
                x, z = player["position"]
                if self._distance((x, z), (enemy_base_x, 0.0)) > CAPTURE_RADIUS:
                    continue
                if player["team"] == team:
                    attackers.append(player)
                else:
                    defenders.append(player)

            if attackers and not defenders:
                multiplier = min(1.0 + 0.2 * (len(attackers) - 1), 2.5)
                previous = self._capture[team]
                self._capture[team] = min(
                    CAPTURE_LIMIT, previous + CAPTURE_RATE * multiplier * dt)
                if int(previous) < CAPTURE_LIMIT <= int(self._capture[team]):
                    self._emit("base_captured", team=team)
                    self._finish(team, "capture", now)
                    return
            elif not defenders and self._capture[team] > 0.0:
                self._capture[team] = max(
                    0.0, self._capture[team] - CAPTURE_DECAY_RATE * dt)

    def _check_elimination(self, now):
        if self.phase != PHASE_ACTIVE:
            return
        alive = {}
        for team in TEAMS:
            alive[team] = sum(
                1 for player in self._players.values()
                if player["team"] == team and player["connected"] and
                player["health"] > 0)
        if alive[TEAM_ONE] == 0 and alive[TEAM_TWO] == 0:
            self._finish(0, "elimination", now)
        elif alive[TEAM_ONE] == 0:
            self._finish(TEAM_TWO, "elimination", now)
        elif alive[TEAM_TWO] == 0:
            self._finish(TEAM_ONE, "elimination", now)

    def _finish(self, winner, reason, now):
        if self.phase != PHASE_ACTIVE:
            return
        self.phase = PHASE_FINISHED
        duration = max(0.0, now - self._started_at)
        self._result = {
            "winner": winner,
            "reason": reason,
            "duration": duration,
            "capture": {str(team): self._capture[team] for team in TEAMS},
            "players": self._result_rows(),
        }
        self._emit("battle_finished", winner=winner, reason=reason,
                   duration=duration)
        if not any(not player["is_bot"] and player["connected"]
                   for player in self._players.values()):
            # With no connected humans there is nobody left to receive a
            # result; reopen the empty service room for the next host.
            self._clear_empty_room(now)

    def _resolve_timeout(self, now):
        alive_count = {}
        health_ratio = {}
        for team in TEAMS:
            members = [player for player in self._players.values()
                       if player["team"] == team and player["connected"]]
            alive = [player for player in members if player["health"] > 0]
            alive_count[team] = len(alive)
            denominator = sum(player["profile"]["max_health"] for player in members)
            numerator = sum(player["health"] for player in members)
            health_ratio[team] = numerator / denominator if denominator else 0.0

        if alive_count[TEAM_ONE] != alive_count[TEAM_TWO]:
            winner = TEAM_ONE if alive_count[TEAM_ONE] > alive_count[TEAM_TWO] else TEAM_TWO
        elif abs(health_ratio[TEAM_ONE] - health_ratio[TEAM_TWO]) > 1e-9:
            winner = TEAM_ONE if health_ratio[TEAM_ONE] > health_ratio[TEAM_TWO] else TEAM_TWO
        elif abs(self._capture[TEAM_ONE] - self._capture[TEAM_TWO]) > 1e-9:
            winner = TEAM_ONE if self._capture[TEAM_ONE] > self._capture[TEAM_TWO] else TEAM_TWO
        else:
            winner = 0
        self._finish(winner, "timeout", now)

    def tick(self, now=None):
        now = self._resolve_time(now)
        if self.phase != PHASE_ACTIVE:
            return []
        elapsed = max(0.0, now - self._last_tick_at)
        dt = min(elapsed, MAX_TICK_SECONDS)
        self._last_tick_at = now
        if dt > 0.0:
            self._tick_bots(dt, now)
            if self.phase == PHASE_ACTIVE:
                self._move_players(dt, now)
                self._tick_capture(dt, now)
        if self.phase == PHASE_ACTIVE:
            self._check_elimination(now)
        if self.phase == PHASE_ACTIVE and now >= self._ends_at:
            self._resolve_timeout(now)
        return self.drain_events()

    def _result_rows(self):
        rows = []
        for player in sorted(self._players.values(),
                             key=lambda item: (item["team"], item["id"])):
            rows.append({
                "player_id": player["id"],
                "name": player["name"],
                "team": player["team"],
                "vehicle": player["vehicle"],
                "is_bot": player["is_bot"],
                "health": player["health"],
                "shots_fired": player["shots_fired"],
                "shots_hit": player["shots_hit"],
                "damage_dealt": player["damage_dealt"],
                "kills": player["kills"],
                "deaths": player["deaths"],
            })
        return rows

    def snapshot(self, now=None):
        now = self._resolve_time(now)
        remaining = None
        if self.phase == PHASE_ACTIVE and self._ends_at is not None:
            remaining = max(0.0, self._ends_at - now)

        players = []
        for player in sorted(self._players.values(),
                             key=lambda item: (item["team"], item["id"])):
            players.append({
                "player_id": player["id"],
                "name": player["name"],
                "team": player["team"],
                "vehicle": player["vehicle"],
                "is_bot": player["is_bot"],
                "ready": player["ready"],
                "connected": player["connected"],
                "position": [player["position"][0], player["position"][1]],
                "yaw": player["yaw"],
                "gun_yaw": player["gun_yaw"],
                "gun_pitch": player["gun_pitch"],
                "speed": player["speed"],
                "health": player["health"],
                "max_health": player["profile"]["max_health"],
                "ammo": player["ammo"],
                "shots_fired": player["shots_fired"],
                "damage_dealt": player["damage_dealt"],
                "kills": player["kills"],
                "deaths": player["deaths"],
            })

        return {
            "ok": True,
            "round": self._round_id,
            "phase": self.phase,
            "map": self.map_name,
            "host_id": self.host_id,
            "team_sizes": {
                str(team): self._team_count(team) for team in TEAMS
            },
            "capture": {
                str(team): self._capture[team] for team in TEAMS
            },
            "remaining_seconds": remaining,
            "players": players,
            "result": self._result,
        }

    def connected_humans(self):
        """Return ``(player_id, mailbox)`` pairs for the service adapter."""
        return [(player["id"], player["mailbox"])
                for player in self._players.values()
                if not player["is_bot"] and player["connected"] and
                player["mailbox"] is not None]

    def status_for(self, player_id, now=None):
        player_id = _require_int(player_id, "player_id", 1)
        if player_id not in self._players:
            raise BattleError("player is not in this room")
        return self.snapshot(now=now)
