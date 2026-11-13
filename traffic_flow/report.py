"""Report generation: a Markdown report and a static HTML dashboard.

Both are built from the metrics dict produced by
``analysis.summarize`` -- no re-simulation is needed.
"""

from __future__ import annotations

import json
import os


def _fmt(value, unit: str = "", nd: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{nd}f}{unit}"
    return f"{value}{unit}"


def build_markdown_report(metrics: dict, scenario: dict) -> str:
    """Render the Markdown report for one run."""
    tt = metrics["travel_time"]
    q = metrics["queue"]
    sw = metrics["shockwave"]
    fd = metrics.get("fundamental_diagram_fit")
    rw = metrics.get("ramp_wait", {})
    lines = [
        f"# Traffic Flow Report -- {metrics['scenario']}",
        "",
        scenario.get("description", ""),
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Duration | {metrics['duration_s']:.0f} s ({metrics['duration_s'] / 60:.1f} min) |",
        f"| Vehicles entered | {metrics['vehicles_entered']} |",
        f"| Vehicles completed | {metrics['vehicles_completed']} |",
        f"| Throughput | {_fmt(metrics['throughput_veh_per_h'], ' veh/h', 1)} |",
        f"| Mean speed | {_fmt(metrics['mean_speed_kmh'], ' km/h')} |",
        f"| Mean density | {_fmt(metrics['mean_density_veh_per_km_per_lane'], ' veh/km/lane')} |",
        f"| Max flow per lane | {_fmt(metrics['max_flow_per_lane_veh_per_h'], ' veh/h/ln', 1)} |",
        f"| Level of Service (HCM) | **{metrics['level_of_service']}** |",
        f"| Lane changes | {metrics['lane_changes']} |",
        "",
        "## Travel time",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Mean travel time | {_fmt(tt.get('mean_travel_time_s'), ' s')} |",
        f"| Median travel time | {_fmt(tt.get('median_travel_time_s'), ' s')} |",
        f"| 95th percentile | {_fmt(tt.get('p95_travel_time_s'), ' s')} |",
        f"| Free-flow travel time | {_fmt(tt.get('mean_free_flow_time_s'), ' s')} |",
        f"| Mean delay | {_fmt(tt.get('mean_delay_s'), ' s')} |",
        f"| Mean speed (from travel time) | {_fmt(tt.get('mean_speed_kmh'), ' km/h')} |",
        "",
        "## Queues",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Max queued vehicles (slow, <5 km/h) | {q['max_queued_vehicles']} |",
        f"| Max queue extent | {_fmt(q['max_queue_extent_m'], ' m', 1)} |",
        f"| Slow vehicle-seconds | {_fmt(q['slow_vehicle_seconds'], ' veh-s', 1)} |",
        f"| Max entry queue | {q['max_entry_queue']} |",
        f"| Max ramp queue | {q['max_ramp_queue']} |",
        f"| Ramp vehicles merged | {rw.get('n_vehicles', 0)} |",
        f"| Mean ramp wait | {_fmt(rw.get('mean_wait_s'), ' s')} |",
        f"| Max ramp wait | {_fmt(rw.get('max_wait_s'), ' s')} |",
        "",
        "## Shockwaves (stop-and-go)",
        "",
    ]
    if sw["detected"]:
        lines += [
            f"- Detected: yes ({sw['n_points']} front samples)",
            f"- Backward wave speed: **{_fmt(sw['wave_speed_kmh'], ' km/h')}** "
            "(negative = travelling against traffic, as in Sugiyama et al. 2008)",
            f"- Fit R^2: {_fmt(sw['r_squared'], '', 3)}",
        ]
    else:
        lines.append("- No sustained stop-and-go wave detected.")
    lines += ["", "## Fundamental diagram"]
    if fd:
        lines += [
            "",
            f"- Greenshields fit: vf = {_fmt(fd['vf'], ' km/h', 1)}, "
            f"kj = {_fmt(fd['kj'], ' veh/km', 1)}, "
            f"capacity qmax = {_fmt(fd['q_max'], ' veh/h/ln', 0)} "
            f"(critical density {_fmt(fd['k_crit'], ' veh/km', 1)})",
            f"- Fit R^2 = {_fmt(fd['r_squared'], '', 3)} over "
            f"{int(fd['n_points'])} one-minute bins.",
        ]
    else:
        lines += ["", "- Not enough varied bins to fit the Greenshields model."]
    lines += [
        "",
        "## Figures",
        "",
        "- `space_time.png` -- space-time diagram (colour = speed)",
        "- `fundamental.png` -- flow-density diagram with Greenshields fit",
        "- `speed_time.png` -- space-mean speed and density vs time",
        "- `queues.png` -- entry / ramp queue lengths vs time",
        "",
        "## Method",
        "",
        "Microscopic simulation with the Intelligent Driver Model (IDM, "
        "Treiber et al. 2000) for car-following and MOBIL (Kesting et al. "
        "2007) for lane changing; discrete-time integration (dt = 0.1 s). "
        "See `docs/RESEARCH.md` for the theory and references.",
        "",
    ]
    return "\n".join(lines)


def build_html_dashboard(metrics: dict, scenario: dict,
                         plots: dict[str, str]) -> str:
    """Render a small static HTML dashboard (no JavaScript needed)."""
    tt = metrics["travel_time"]
    q = metrics["queue"]
    sw = metrics["shockwave"]
    fd = metrics.get("fundamental_diagram_fit")

    def img(key: str, alt: str) -> str:
        if key in plots:
            return (f'<figure><img src="{plots[key]}" alt="{alt}">'
                    f"<figcaption>{alt}</figcaption></figure>")
        return ""

    fd_html = "n/a"
    if fd:
        fd_html = (f"vf = {fd['vf']:.1f} km/h, kj = {fd['kj']:.1f} veh/km, "
                   f"q<sub>max</sub> = {fd['q_max']:.0f} veh/h/ln, "
                   f"R&sup2; = {fd['r_squared']:.3f}")
    sw_html = "No sustained stop-and-go wave detected."
    if sw["detected"]:
        sw_html = (f"Backward wave speed "
                   f"<b>{sw['wave_speed_kmh']:.2f} km/h</b> "
                   f"(R&sup2; = {sw['r_squared']:.3f}, "
                   f"{sw['n_points']} front samples)")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Traffic Flow Dashboard — {metrics['scenario']}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto;
       padding: 0 1rem; color: #1a1a1a; background: #fafafa; }}
h1 {{ font-size: 1.6rem; }} h2 {{ font-size: 1.2rem; margin-top: 2rem; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
         gap: 0.75rem; }}
.card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 0.8rem; }}
.card .k {{ font-size: 0.8rem; color: #666; }}
.card .v {{ font-size: 1.4rem; font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; }}
td, th {{ border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; }}
th {{ background: #f0f0f0; }}
figure img {{ max-width: 100%; }}
figcaption {{ font-size: 0.85rem; color: #555; }}
</style>
</head>
<body>
<h1>Traffic Flow Dashboard — {metrics['scenario']}</h1>
<p>{scenario.get('description', '')}</p>
<div class="cards">
<div class="card"><div class="k">Throughput</div><div class="v">{metrics['throughput_veh_per_h']:.0f} veh/h</div></div>
<div class="card"><div class="k">Mean speed</div><div class="v">{_fmt(metrics['mean_speed_kmh'], ' km/h')}</div></div>
<div class="card"><div class="k">Level of Service (HCM)</div><div class="v">{metrics['level_of_service']}</div></div>
<div class="card"><div class="k">Mean delay</div><div class="v">{_fmt(tt.get('mean_delay_s'), ' s')}</div></div>
<div class="card"><div class="k">Vehicles completed</div><div class="v">{metrics['vehicles_completed']} / {metrics['vehicles_entered']}</div></div>
<div class="card"><div class="k">Max queue extent</div><div class="v">{q['max_queue_extent_m']:.0f} m</div></div>
</div>
<h2>Travel time</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Mean travel time</td><td>{_fmt(tt.get('mean_travel_time_s'), ' s')}</td></tr>
<tr><td>Median travel time</td><td>{_fmt(tt.get('median_travel_time_s'), ' s')}</td></tr>
<tr><td>95th percentile</td><td>{_fmt(tt.get('p95_travel_time_s'), ' s')}</td></tr>
<tr><td>Free-flow travel time</td><td>{_fmt(tt.get('mean_free_flow_time_s'), ' s')}</td></tr>
<tr><td>Mean delay</td><td>{_fmt(tt.get('mean_delay_s'), ' s')}</td></tr>
</table>
<h2>Shockwaves</h2>
<p>{sw_html}</p>
<h2>Fundamental diagram (Greenshields fit)</h2>
<p>{fd_html}</p>
<h2>Figures</h2>
{img('space_time', 'Space-time diagram (colour = speed)')}
{img('fundamental', 'Fundamental diagram with Greenshields fit')}
{img('speed_time', 'Space-mean speed and density vs time')}
{img('queues', 'Queue lengths vs time')}
<p><small>Generated by traffic-flow-simulator (IDM + MOBIL). See docs/RESEARCH.md.</small></p>
</body>
</html>
"""


def write_reports(metrics: dict, scenario: dict, out_dir: str,
                  plots: dict[str, str]) -> dict[str, str]:
    """Write ``report.md`` and ``dashboard.html`` into ``out_dir``."""
    md_path = os.path.join(out_dir, "report.md")
    html_path = os.path.join(out_dir, "dashboard.html")
    with open(md_path, "w") as fh:
        fh.write(build_markdown_report(metrics, scenario))
    with open(html_path, "w") as fh:
        fh.write(build_html_dashboard(metrics, scenario, plots))
    return {"report_md": md_path, "dashboard_html": html_path}


def write_metrics(metrics: dict, path: str) -> None:
    """Write the metrics dict as JSON."""
    with open(path, "w") as fh:
        json.dump(metrics, fh, indent=2)
