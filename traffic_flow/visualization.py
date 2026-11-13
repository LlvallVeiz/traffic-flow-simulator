"""Visualisation: space-time diagram, fundamental diagram, speed and
queue time series.  All plots use the Agg backend so they render
without a display, and every figure is saved as a PNG.
"""

from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

MAX_POINTS = 250_000


def plot_space_time(samples: list[dict], road_length: float,
                    duration: float, path: str) -> str:
    """Space-time diagram: vehicle positions coloured by speed.

    Stop-and-go waves show up as diagonal bands running backwards
    (down-left) against the traffic direction.
    """
    if len(samples) > MAX_POINTS:
        step = len(samples) // MAX_POINTS + 1
        samples = samples[::step]
    t = np.array([s["t"] / 60.0 for s in samples])  # minutes
    x = np.array([s["x"] / 1000.0 for s in samples])  # km
    v = np.array([s["v"] * 3.6 for s in samples])  # km/h
    fig, ax = plt.subplots(figsize=(10, 6))
    sc = ax.scatter(t, x, c=v, s=1.5, cmap="RdYlGn", vmin=0, vmax=120)
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Position along road (km)")
    ax.set_xlim(0, duration / 60.0)
    ax.set_ylim(0, road_length / 1000.0)
    ax.set_title("Space-time diagram (colour = speed, km/h)")
    fig.colorbar(sc, ax=ax, label="Speed (km/h)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_fundamental(stats: list[dict], fit: dict | None, path: str) -> str:
    """Flow-density scatter with the fitted Greenshields parabola."""
    densities = [r["density_veh_per_km_per_lane"] for r in stats]
    flows = [r["flow_per_lane"] for r in stats]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(densities, flows, s=25, alpha=0.7, label="1-min bins")
    if fit is not None:
        from .fundamental import greenshields_flow

        ks = np.linspace(0, fit["kj"] * 1.05, 200)
        qs = [greenshields_flow(k, fit["vf"], fit["kj"]) for k in ks]
        ax.plot(ks, qs, "r-", label=(
            f"Greenshields fit: vf={fit['vf']:.1f} km/h, "
            f"kj={fit['kj']:.1f} veh/km, qmax={fit['q_max']:.0f} veh/h/ln"
        ))
        ax.axvline(fit["k_crit"], color="grey", linestyle="--",
                   label=f"critical density {fit['k_crit']:.1f} veh/km")
    ax.set_xlabel("Density (veh/km/lane)")
    ax.set_ylabel("Flow (veh/h/lane)")
    ax.set_title("Fundamental diagram (flow vs density)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_speed_time(stats: list[dict], path: str) -> str:
    """Mean speed and density against time (one line per 1-min bin)."""
    t = [r["t_mid"] / 60.0 for r in stats]
    speed = [r["speed_kmh"] if math.isfinite(r["speed_kmh"]) else float("nan")
             for r in stats]
    density = [r["density_veh_per_km_per_lane"] for r in stats]
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(t, speed, "b-o", ms=3, label="Space-mean speed")
    ax1.set_xlabel("Time (min)")
    ax1.set_ylabel("Speed (km/h)", color="b")
    ax1.tick_params(axis="y", labelcolor="b")
    ax2 = ax1.twinx()
    ax2.plot(t, density, "r-s", ms=3, label="Density")
    ax2.set_ylabel("Density (veh/km/lane)", color="r")
    ax2.tick_params(axis="y", labelcolor="r")
    ax1.set_title("Space-mean speed and density vs time")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_queues(entry_series: list, ramp_series: list, path: str) -> str:
    """Entry-queue and ramp-queue lengths against time."""
    fig, ax = plt.subplots(figsize=(10, 4))
    if entry_series:
        ax.plot([t / 60.0 for t, _ in entry_series],
                [n for _, n in entry_series], label="Entry queue")
    if ramp_series:
        ax.plot([t / 60.0 for t, _ in ramp_series],
                [n for _, n in ramp_series], label="Ramp queue")
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Queued vehicles")
    ax.set_title("Queue lengths vs time")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
