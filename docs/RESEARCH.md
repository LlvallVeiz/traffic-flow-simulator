# Research notes — traffic flow theory behind this simulator

This document collects the theory the simulator implements, with the
sources each claim rests on. Every reference below was checked to exist
(title, authors, venue, year) before it was cited here.

## 1. The fundamental diagram

Traffic on a road is described by three aggregate variables: flow `q`
(vehicles per hour passing a point), density `k` (vehicles per km) and
space-mean speed `v` (km/h), linked by the identity

```
q = k * v
```

**Greenshields (1935)** proposed the first closed form: speed falls
linearly with density, `v(k) = vf * (1 - k/kj)`, where `vf` is the
free-flow speed and `kj` the jam density. The flow–density curve is
then a parabola with capacity `q_max = vf * kj / 4` at `k = kj/2`,
`v = vf/2`. Later shapes (Greenberg's logarithmic model, Underwood's
exponential model, Daganzo's triangular diagram, 1994) fit real data
better in parts of the range, but Greenshields remains the standard
first model and the one this simulator fits to its detector data
(`traffic_flow/fundamental.py`).

## 2. Kinematic waves and shockwaves

**Lighthill & Whitham (1955)** and **Richards (1956)** treated traffic
as a compressible fluid: with flow a function of density only, the
conservation law `∂k/∂t + ∂q(k)/∂x = 0` sends disturbances along
characteristics at speed `dq/dk`. Where characteristics converge, a
discontinuity forms — a **shockwave** — whose speed follows the
Rankine–Hugoniot condition

```
w = (q2 - q1) / (k2 - k1)
```

i.e. the slope of the chord between the two traffic states on the
fundamental diagram. A jam front therefore moves *backwards* (against
traffic) whenever the downstream state is denser, at typically
15–20 km/h on freeways. The simulator's shockwave detector
(`analysis.detect_shockwaves`) tracks the upstream front of stopped
vehicles in the space-time diagram and fits its speed by linear
regression.

## 3. Microscopic car-following: the Intelligent Driver Model

Macroscopic models cannot say what one driver does. The **Intelligent
Driver Model (IDM)** of **Treiber, Hennecke & Helbing (2000)** is a
time-continuous car-following model whose acceleration

```
a = a_max * [1 - (v/v0)^δ - (s*(v, Δv)/s)^2]
s*(v, Δv) = s0 + v*T + v*Δv / (2*sqrt(a_max*b))
```

depends only on the vehicle's own speed, the gap `s` to its leader and
the approach rate `Δv`. Its parameters are all behaviourally
interpretable (desired speed, time gap, minimum gap, max acceleration,
comfortable deceleration), it is essentially crash-free, and it
reproduces free flow, congested flow, capacity drop and stop-and-go
waves. It is the standard model in the textbook **Treiber & Kesting
(2013)** and the basis of this simulator's longitudinal dynamics
(`traffic_flow/idm.py`, `traffic_flow/simulator.py`).

## 4. Lane changing: MOBIL

Lane changes are decided by **MOBIL** (Minimizing Overall Braking
Induced by Lane changes; **Kesting, Treiber & Helbing, 2007**). A
change is made only when it is *safe* (the new follower is not forced
to brake harder than `b_safe`) and *worthwhile* (the gain in the ego
vehicle's acceleration, plus a politeness-weighted share of the
followers' gains, exceeds a threshold). The simulator adds a
keep-right bias and a mandatory-merge mode for lane drops
(`traffic_flow/mobil.py`).

## 5. Phantom jams: from model to experiment

Both the IDM and the cellular-automaton model of **Nagel &
Schreckenberg (1992)** predict that jams can emerge with no bottleneck
at all: at high density, small disturbances amplify into stop-and-go
waves. **Sugiyama et al. (2008)** proved it with real drivers: 22
vehicles on a 230 m circular track, asked only to cruise at 30 km/h,
formed a jam cluster within minutes that travelled backwards at
roughly 20 km/h. The `stop_and_go_wave` scenario reproduces this
mechanism (a brief incident seeds the disturbance; the wave then
propagates on its own).

## 6. Ramp metering: ALINEA

**Papageorgiou, Hadj-Salem & Blosseville (1991)** proposed ALINEA, a
local feedback law for on-ramp metering:

```
r(k) = r(k-1) + K_R * (o* - o(k))
```

The release rate `r` is nudged up when the measured downstream
occupancy `o(k)` is below its target `o*` (the critical occupancy) and
down when it is above. It needs only one downstream detector and has
been deployed at hundreds of sites worldwide. The simulator implements
it in `traffic_flow/ramp_metering.py`; the `ramp_metering_on` /
`ramp_metering_off` scenarios are the controlled comparison.

## 7. Level of service

The **Highway Capacity Manual (HCM, 6th edition, 2016, ch. 12)**
grades basic freeway segments A (best) to F (worst) by density
`D = vp / S` (flow rate per lane divided by space-mean speed). The
metric thresholds used here (pc/km/ln) are A ≤ 7, B ≤ 11, C ≤ 16,
D ≤ 22, E ≤ 28, F > 28 (HCM 2000, Exhibit 23-3; HCM 6th ed. ch. 12).

## 8. What this simulator deliberately leaves out

- **Reaction time and perception errors.** The IDM reacts instantly;
  real drivers have ~1 s of delay, which matters for stability
  analysis. Adding a delay is a natural extension.
- **Stochastic driver behaviour.** Apart from seeded parameter jitter
  and Poisson arrivals, drivers are deterministic; real traffic has
  day-to-day and within-driver variability (the "wide scattering" of
  flow–density data discussed by Treiber & Helbing, 2003).
- **Network effects.** One straight road, no junctions, no route
  choice, no signals coordination.
- **Calibration to a real road.** Parameters sit inside the ranges
  reported by Treiber & Kesting (2013) but are not fitted to loop
  detector data from any specific freeway; headline capacities are
  therefore the *model's* capacities, not a measured road's.

## References

1. Treiber, M., Hennecke, A., Helbing, D. (2000). Congested traffic states in empirical observations and microscopic simulations. *Physical Review E*, 62(2), 1805–1824. doi:10.1103/PhysRevE.62.1805 — https://arxiv.org/abs/cond-mat/0002177
2. Treiber, M., Kesting, A. (2013). *Traffic Flow Dynamics: Data, Models and Simulation*. Springer. ISBN 978-3-642-32459-8 — https://pubs.aip.org/physicstoday/article/67/3/54/1017356/Traffic-Flow-Dynamics-Data-Models-and-Simulation (review)
3. Kesting, A., Treiber, M., Helbing, D. (2007). General lane-changing model MOBIL for car-following models. *Transportation Research Record*, 1999, 86–94 — http://www.mtreiber.de/publications/MOBIL%5C_TRB.pdf
4. Greenshields, B. D. (1935). A study of traffic capacity. *Proceedings of the 14th Annual Meeting of the Highway Research Board*, 14, 448–477 — https://www.civil.iitb.ac.in/tvm/1100_LnTse/503_lnTse/plain/plain.html (lecture notes summarising the model)
5. Lighthill, M. J., Whitham, G. B. (1955). On kinematic waves. II. A theory of traffic flow on long crowded roads. *Proceedings of the Royal Society of London A*, 229, 281–345.
6. Richards, P. I. (1956). Shock waves on the highway. *Operations Research*, 4(1), 42–51.
7. Nagel, K., Schreckenberg, M. (1992). A cellular automaton model for freeway traffic. *Journal de Physique I*, 2(12), 2221–2229. doi:10.1051/jp1:1992277 — https://en.wikipedia.org/wiki/Nagel–Schreckenberg_model
8. Sugiyama, Y., Fukui, M., Kikuchi, M., Hasebe, K., Nakayama, A., Nishinari, K., Tadaki, S., Yukawa, S. (2008). Traffic jams without bottlenecks — experimental evidence for the physical mechanism of the formation of a jam. *New Journal of Physics*, 10, 033001. doi:10.1088/1367-2630/10/3/033001 — https://www.newscientist.com/article/1906335-shockwave-traffic-jam-recreated-for-first-time/
9. Papageorgiou, M., Hadj-Salem, H., Blosseville, J.-M. (1991). ALINEA: A local feedback control law for on-ramp metering. *Transportation Research Record*, 1320, 58–64 — http://onlinepubs.trb.org/Onlinepubs/trr/1991/1320/1320-008.pdf
10. Transportation Research Board (2016). *Highway Capacity Manual*, 6th edition, ch. 12 (Basic Freeway Segments). LOS density thresholds — https://www.txdot.gov/manuals/des/tsp/chapter-9-segment-analysis--freeways--multi-lane-h/9-3-hcm-based--mesoscopic--analysis/9-3-4-measures-of-effectiveness--moes-.html
11. Helbing, D. (2001). Traffic and related self-driven many-particle systems. *Reviews of Modern Physics*, 73, 1067–1141. doi:10.1103/RevModPhys.73.1067
12. Daganzo, C. F. (1994). The cell transmission model: A dynamic representation of highway traffic consistent with the hydrodynamic theory. *Transportation Research Part B*, 28(4), 269–287.
