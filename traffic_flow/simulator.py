"""Microscopic traffic simulator (IDM + MOBIL, discrete time).

The simulator steps a multi-lane road forward in fixed steps of
``dt`` (default 0.1 s):

1. generate arrivals (main entry + on-ramps) from Poisson demand;
2. compute IDM accelerations against the leader in the same lane,
   with virtual leaders for red lights, incidents and lane drops;
3. evaluate MOBIL lane changes (once per second, plus mandatory
   merges before a lane drop);
4. integrate positions with semi-implicit (ballistic) Euler;
5. remove vehicles that leave the road, sample trajectories and
   record detector crossings.

Vehicles are kept per lane, sorted by position (leader first), so
leader/follower lookups are local.  All randomness comes from one
seeded ``random.Random`` instance, so a run is reproducible.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from .demand import ArrivalGenerator, DemandProfile
from .idm import idm_acceleration
from .mobil import MobilParams, mobil_should_change
from .ramp_metering import AlineaMeter
from .road import Bottleneck, OnRamp, Road, TrafficLight
from .trajectory import TrajectoryRecorder
from .vehicle import Vehicle, create_vehicle


@dataclass
class SimulationResult:
    """Everything one simulation run produces."""

    scenario_name: str
    road_length: float
    n_lanes: int
    duration: float
    dt: float
    seed: int
    recorder: TrajectoryRecorder
    detector_crossings: dict[float, list[dict]] = field(default_factory=dict)
    entry_queue_series: list[tuple[float, int]] = field(default_factory=list)
    ramp_queue_series: list[tuple[float, int]] = field(default_factory=list)
    metering_series: list[dict] = field(default_factory=list)
    ramp_waits: list[float] = field(default_factory=list)
    runtime_s: float = 0.0
    metrics: dict = field(default_factory=dict)

    @property
    def completed_vehicles(self) -> int:
        """Vehicles that reached the end of the road."""
        return sum(1 for e in self.recorder.events if e["completed"])

    @property
    def entered_vehicles(self) -> int:
        """Vehicles that entered the road (main + ramps)."""
        return len(self.recorder.events)


class Simulator:
    """Discrete-time microscopic simulator for one road."""

    def __init__(
        self,
        road: Road,
        demand: DemandProfile,
        ramp_demands: dict[float, DemandProfile] | None = None,
        *,
        duration: float,
        dt: float = 0.1,
        seed: int = 42,
        sample_dt: float = 2.0,
        detector_positions: list[float] | None = None,
        mobil_params: MobilParams | None = None,
        lane_change_dt: float = 1.0,
        ramp_metering: AlineaMeter | None = None,
        mix: dict[str, float] | None = None,
        driver_mix: dict[str, float] | None = None,
        jitter: float = 0.05,
        scenario_name: str = "simulation",
    ):
        self.road = road
        self.demand = demand
        self.ramp_demands = ramp_demands or {}
        self.duration = duration
        self.dt = dt
        self.seed = seed
        self.rng = random.Random(seed)
        self.recorder = TrajectoryRecorder(sample_dt=sample_dt)
        self.detector_positions = sorted(detector_positions or [])
        self.detector_crossings: dict[float, list[dict]] = {
            x: [] for x in self.detector_positions
        }
        self.mobil_params = mobil_params or MobilParams()
        self.lane_change_dt = lane_change_dt
        self.ramp_metering = ramp_metering
        self.mix = mix
        self.driver_mix = driver_mix
        self.jitter = jitter
        self.scenario_name = scenario_name

        self.lanes: list[list[Vehicle]] = [[] for _ in range(road.n_lanes)]
        self.t = 0.0
        self.next_id = 1
        self.main_arrivals = ArrivalGenerator(demand, self.rng)
        self.next_main_arrival = self.main_arrivals.next_arrival(0.0)
        self.pending_main: Vehicle | None = None
        # Ramp state: x_merge -> {"generator", "next_arrival", "queue", "next_release"}
        self.ramps: dict[float, dict] = {}
        for ramp in road.on_ramps:
            profile = self.ramp_demands.get(ramp.x_merge)
            gen = ArrivalGenerator(profile, self.rng) if profile else None
            self.ramps[ramp.x_merge] = {
                "ramp": ramp,
                "generator": gen,
                "next_arrival": gen.next_arrival(0.0) if gen else None,
                "queue": [],
                "next_release": 0.0,
            }
        self._next_mobil_t = 0.0
        self._next_meter_t = 0.0
        self._next_queue_t = 0.0
        self._last_lane_change: dict[int, float] = {}
        self.entry_queue_series: list[tuple[float, int]] = []
        self.ramp_queue_series: list[tuple[float, int]] = []
        self.metering_series: list[dict] = []
        self.ramp_waits: list[float] = []
        self._entry_queue = 0

    # -- helpers ----------------------------------------------------------

    def _all_vehicles(self) -> list[Vehicle]:
        out: list[Vehicle] = []
        for lane in self.lanes:
            out.extend(lane)
        return out

    def _leader_follower(self, lane_list: list[Vehicle], x: float):
        """(leader, follower) around position ``x`` in a sorted lane list.

        Lists are sorted by ``x`` descending (leader first).
        """
        leader = None
        follower = None
        for veh in lane_list:
            if veh.x >= x:
                leader = veh
            else:
                follower = veh
                break
        return leader, follower

    def _gap_to(self, veh: Vehicle, leader: Vehicle | None) -> tuple[float | None, float | None]:
        if leader is None:
            return None, None
        gap = leader.rear_x - veh.x
        return gap, leader.v

    def _virtual_leader(self, veh: Vehicle) -> tuple[float | None, float]:
        """Nearest virtual obstacle ahead: (gap, speed=0) or (None, 0).

        Virtual obstacles are a red/yellow light, an incident blockage
        and the end of a closing lane.  Only obstacles within the
        look-ahead distance matter.
        """
        best_gap: float | None = None
        t = self.t
        # Traffic lights.
        light = self.road.next_light(veh.x)
        if light is not None:
            state = light.state_at(t)
            dist = light.x - veh.x
            if dist < 250.0:
                if state == "red" or (state == "yellow" and dist > 30.0):
                    best_gap = dist
        # Incidents.
        inc = self.road.incident_ahead(veh.x, t)
        if inc is not None:
            dist = inc - veh.x
            if dist < 300.0 and (best_gap is None or dist < best_gap):
                best_gap = dist
        # Lane drop: a vehicle still in a closing lane is stopped at
        # the taper so it must merge (see _mandatory_merge).
        for b in self.road.bottlenecks:
            if (
                b.kind == "lane_drop"
                and b.is_active(t)
                and veh.lane >= (b.lanes_after or 0)
                and veh.x < b.x_start
            ):
                dist = b.x_start - veh.x
                if dist < 5.0 and (best_gap is None or dist < best_gap):
                    best_gap = dist
        return best_gap, 0.0

    def _accel_with_leader(
        self, veh: Vehicle, leader: Vehicle | None, gap: float | None,
        leader_v: float | None,
    ) -> float:
        """IDM acceleration, taking the nearest virtual leader into account."""
        v_gap, _ = self._virtual_leader(veh)
        if v_gap is not None and (gap is None or v_gap < gap):
            gap, leader_v = v_gap, 0.0
        return idm_acceleration(veh.v, leader_v, gap, veh.params)

    # -- arrivals ----------------------------------------------------------

    def _try_enter_main(self) -> None:
        """Insert the pending main-entry vehicle if a lane has room."""
        if self.pending_main is None:
            return
        veh = self.pending_main
        best_lane = None
        best_gap = -1.0
        for lane_idx, lane_list in enumerate(self.lanes):
            rearmost = lane_list[-1] if lane_list else None
            gap = (rearmost.rear_x - 0.0) if rearmost else float("inf")
            if gap > best_gap:
                best_gap = gap
                best_lane = lane_idx
        if best_lane is not None and best_gap >= 8.0:
            lane_list = self.lanes[best_lane]
            veh.lane = best_lane
            veh.x = 0.0
            veh.v = min(
                veh.params.v0,
                lane_list[-1].v if lane_list else veh.params.v0,
            )
            lane_list.append(veh)
            lane_list.sort(key=lambda v: -v.x)
            self.recorder.record_entry(
                veh.id, veh.kind, veh.profile, self.t,
                "main", veh.params.v0, entry_x=0.0,
            )
            self.pending_main = None
            self._entry_queue = 0
        else:
            self._entry_queue = 1

    def _make_vehicle(self, entered_via: str) -> Vehicle:
        veh = create_vehicle(
            self.next_id, self.rng,
            mix=self.mix, driver_mix=self.driver_mix,
            speed_limit=self.road.speed_limit,
            jitter=self.jitter,
            entry_time=self.t, entered_via=entered_via,
        )
        self.next_id += 1
        return veh

    def _ramp_gap_ok(self, x_merge: float, veh: Vehicle) -> bool:
        """Gap acceptance for a ramp vehicle merging into lane 0."""
        lane_list = self.lanes[0]
        leader, follower = self._leader_follower(lane_list, x_merge)
        if leader is not None and (leader.rear_x - x_merge) < 10.0:
            return False
        if follower is not None:
            gap_f = x_merge - veh.length - follower.x
            if gap_f < 10.0:
                return False
            # The follower must not be forced into hard braking.
            a_f = idm_acceleration(
                follower.v, veh.v,
                x_merge - veh.length - follower.x, follower.params,
            )
            if a_f < -self.mobil_params.b_safe:
                return False
        return True

    def _process_ramps(self) -> None:
        for x_merge, state in self.ramps.items():
            gen = state["generator"]
            # Generate arrivals into the ramp queue.
            while (
                gen is not None
                and state["next_arrival"] is not None
                and state["next_arrival"] <= self.t
            ):
                veh = self._make_vehicle("ramp")
                veh.x = x_merge
                veh.v = 0.0
                state["queue"].append(veh)
                state["next_arrival"] = gen.next_arrival(state["next_arrival"])
            # Metering: update the release rate on its cycle.
            if self.ramp_metering is not None and self.t >= self._next_meter_t:
                density = self._downstream_density(x_merge)
                rate = self.ramp_metering.update(density)
                self.metering_series.append({
                    "t": round(self.t, 1),
                    "rate_veh_per_h": round(rate, 1),
                    "downstream_density": round(density, 2),
                })
            # Release at most one vehicle per headway.
            if not state["queue"]:
                continue
            headway = (
                self.ramp_metering.headway()
                if self.ramp_metering is not None
                else 0.0
            )
            if self.t < state["next_release"]:
                continue
            veh = state["queue"][0]
            if self._ramp_gap_ok(x_merge, veh):
                lane_list = self.lanes[0]
                leader, _ = self._leader_follower(lane_list, x_merge)
                veh.lane = 0
                veh.v = min(leader.v if leader else 20.0, 20.0)
                veh.v = max(veh.v, 5.0)
                # Waiting time on the ramp (arrival -> merge).
                self.ramp_waits.append(self.t - veh.entry_time)
                lane_list.append(veh)
                lane_list.sort(key=lambda v: -v.x)
                self.recorder.record_entry(
                    veh.id, veh.kind, veh.profile, self.t,
                    "ramp", veh.params.v0, entry_x=x_merge,
                )
                state["queue"].pop(0)
                state["next_release"] = self.t + headway
            state["ramp"].queue = len(state["queue"])

    def _downstream_density(self, x_merge: float) -> float:
        """Density (veh/km/lane) in [x_merge, x_merge+500 m]."""
        count = 0
        for lane_list in self.lanes:
            for veh in lane_list:
                if x_merge <= veh.x <= x_merge + 500.0:
                    count += 1
        return count / 0.5 / max(self.road.n_lanes, 1)

    # -- lane changing -----------------------------------------------------

    def _evaluate_lane_changes(self) -> None:
        """One MOBIL pass over all vehicles (discretionary + mandatory)."""
        t = self.t
        for lane_idx, lane_list in enumerate(self.lanes):
            for veh in list(lane_list):
                if veh.id in self._last_lane_change:
                    if t - self._last_lane_change[veh.id] < 5.0:
                        continue
                # Mandatory merge: closing lane near a lane drop.
                forced = False
                for b in self.road.bottlenecks:
                    if (
                        b.kind == "lane_drop"
                        and b.is_active(t)
                        and veh.lane >= (b.lanes_after or 0)
                        and b.x_start - 300.0 <= veh.x < b.x_start
                    ):
                        forced = True
                for target in (lane_idx - 1, lane_idx + 1):
                    if target < 0 or target >= self.road.n_lanes:
                        continue
                    if not self.road.is_lane_open(target, veh.x, t):
                        continue
                    if self._try_lane_change(veh, lane_idx, target, forced):
                        break

    def _try_lane_change(
        self, veh: Vehicle, from_lane: int, to_lane: int, forced: bool
    ) -> bool:
        """Attempt one lane change; returns True when it happened."""
        target_list = self.lanes[to_lane]
        leader_t, follower_t = self._leader_follower(target_list, veh.x)
        # Gap acceptance in the target lane (safety first).
        if leader_t is not None and (leader_t.rear_x - veh.x) < 2.0:
            return False
        if follower_t is not None and (veh.rear_x - follower_t.x) < 2.0:
            return False
        a_ego = veh.accel
        gap_t, v_t = self._gap_to(veh, leader_t)
        a_ego_new = idm_acceleration(veh.v, v_t, gap_t, veh.params)
        if follower_t is not None:
            a_f_new_before = follower_t.accel
            gap_f = veh.rear_x - follower_t.x
            a_f_new_after = idm_acceleration(
                follower_t.v, veh.v, gap_f, follower_t.params
            )
        else:
            a_f_new_before = a_f_new_after = 0.0
        cur_list = self.lanes[from_lane]
        _, follower_o = self._leader_follower(cur_list, veh.x)
        # The old follower's leader after the change is veh's old leader.
        old_leader = None
        for cand in cur_list:
            if cand.x > veh.x:
                old_leader = cand
                break
        if follower_o is not None:
            a_f_old_before = follower_o.accel
            gap_o, v_o = self._gap_to(follower_o, old_leader)
            a_f_old_after = idm_acceleration(
                follower_o.v, v_o, gap_o, follower_o.params
            )
        else:
            a_f_old_before = a_f_old_after = 0.0
        if forced:
            # Mandatory: only the safety criterion applies.
            if follower_t is not None and a_f_new_after < -self.mobil_params.b_safe:
                return False
            ok = True
        else:
            ok = mobil_should_change(
                a_ego, a_ego_new,
                a_f_new_before, a_f_new_after,
                a_f_old_before, a_f_old_after,
                self.mobil_params,
                to_left=(to_lane < from_lane),
            )
        if not ok:
            return False
        cur_list.remove(veh)
        veh.lane = to_lane
        veh.lane_changes += 1
        target_list.append(veh)
        target_list.sort(key=lambda v: -v.x)
        self._last_lane_change[veh.id] = self.t
        return True

    # -- main loop ----------------------------------------------------------

    def run(self) -> SimulationResult:
        """Run the simulation and return the collected result."""
        started = time.perf_counter()
        dt = self.dt
        while self.t < self.duration:
            # 1. Main-entry arrivals.
            while (
                self.next_main_arrival is not None
                and self.next_main_arrival <= self.t
                and self.pending_main is None
            ):
                self.pending_main = self._make_vehicle("main")
                self.next_main_arrival = self.main_arrivals.next_arrival(
                    self.next_main_arrival
                )
            self._try_enter_main()
            # 2. Ramps.
            self._process_ramps()
            if self.ramp_metering is not None and self.t >= self._next_meter_t:
                self._next_meter_t = self.t + self.ramp_metering.cycle
            # 3. Sort lanes (leader first) and compute accelerations.
            for lane_list in self.lanes:
                lane_list.sort(key=lambda v: -v.x)
            for lane_list in self.lanes:
                for i, veh in enumerate(lane_list):
                    leader = lane_list[i - 1] if i > 0 else None
                    gap, leader_v = self._gap_to(veh, leader)
                    veh.accel = self._accel_with_leader(veh, leader, gap, leader_v)
            # 4. Lane changes (once per lane_change_dt).
            if self.t >= self._next_mobil_t:
                self._evaluate_lane_changes()
                self._next_mobil_t = self.t + self.lane_change_dt
            # 5. Integrate (ballistic Euler) and detect detector crossings.
            prev_x = {veh.id: veh.x for veh in self._all_vehicles()}
            for lane_list in self.lanes:
                for veh in lane_list:
                    a = veh.accel
                    veh.x = veh.x + veh.v * dt + 0.5 * a * dt * dt
                    veh.v = max(0.0, veh.v + a * dt)
            for det_x, crossings in self.detector_crossings.items():
                for veh in self._all_vehicles():
                    if prev_x.get(veh.id, veh.x) < det_x <= veh.x:
                        crossings.append({
                            "t": round(self.t + dt, 3),
                            "vehicle_id": veh.id,
                            "v": round(veh.v, 3),
                            "kind": veh.kind,
                        })
            # 6. Exits.
            for lane_list in self.lanes:
                exited = [v for v in lane_list if v.x >= self.road.length_m]
                for veh in exited:
                    lane_list.remove(veh)
                    self.recorder.record_exit(veh.id, self.t + dt, veh.lane_changes)
            # 7. Sampling + queue series (once per second).
            if self.t >= self._next_queue_t:
                self._next_queue_t = self.t + 1.0
                self.recorder.maybe_sample(self.t, self._all_vehicles())
                total_ramp_q = sum(len(s["queue"]) for s in self.ramps.values())
                self.entry_queue_series.append((round(self.t, 1), self._entry_queue))
                self.ramp_queue_series.append((round(self.t, 1), total_ramp_q))
            self.t += dt
        runtime = time.perf_counter() - started
        return SimulationResult(
            scenario_name=self.scenario_name,
            road_length=self.road.length_m,
            n_lanes=self.road.n_lanes,
            duration=self.duration,
            dt=self.dt,
            seed=self.seed,
            recorder=self.recorder,
            detector_crossings=self.detector_crossings,
            entry_queue_series=self.entry_queue_series,
            ramp_queue_series=self.ramp_queue_series,
            metering_series=self.metering_series,
            ramp_waits=self.ramp_waits,
            runtime_s=runtime,
        )


def build_road(cfg: dict) -> Road:
    """Build a :class:`Road` from a scenario config dict."""
    bottlenecks = [Bottleneck(**b) for b in cfg.get("bottlenecks", [])]
    lights = [TrafficLight(**tl) for tl in cfg.get("traffic_lights", [])]
    ramps = []
    for r in cfg.get("on_ramps", []):
        # "demand" belongs to the ramp's arrival profile, not the road.
        r_road = {k: v for k, v in r.items() if k != "demand"}
        ramps.append(OnRamp(**r_road))
    road_cfg = cfg["road"]
    return Road(
        length_m=road_cfg["length_m"],
        n_lanes=road_cfg["n_lanes"],
        speed_limit=road_cfg.get("speed_limit", 33.3),
        bottlenecks=bottlenecks,
        traffic_lights=lights,
        on_ramps=ramps,
        name=cfg.get("name", "road"),
    )


def build_demand(cfg: dict) -> DemandProfile:
    """Build a :class:`DemandProfile` from a scenario config dict."""
    from .demand import DemandInterval

    intervals = [
        DemandInterval(iv["t_start"], iv["t_end"], iv["rate_veh_per_h"])
        for iv in cfg["demand"]["intervals"]
    ]
    return DemandProfile(intervals)
