# Phase 8 – Science Features

**Project:** UKRAA PicoMuon
**Scope:** Section 5 of [implementation-plan.md](implementation-plan.md) (Science plan, §5.1–§5.4), plus two
requested extensions: the application of the FFT to muon data to identify
cycles, and the use of two or more PicoMuon units as a pointable muon
telescope, including the solid-angle mathematics.
**Date:** 4 November 2026

---

## 1. Introduction and instrument context

Phase 8 of the implementation plan adds the *science* layer on top of the
data pipeline built in Phases 0–7: the `analysis/` tools (`Harmonics.py`,
`Forbush.py`, `SolarCycle.py`) and the correction chain in
`ComputeCoefficients.py` / `ApplyCorrections.py`. This report explains the
physics, the mathematics, and the practical recipes behind each of the four
science-plan subsections, with citations to the primary literature.

### 1.1 What one PicoMuon unit actually is

Each PicoMuon unit contains **two plastic scintillator layers**, each
5 cm × 5 cm × 1 cm, read out by SiPMs, with the layer centres 30 mm apart
(20 mm gap between the facing surfaces). The raw data stream confirms this:
every event row is tagged `T` (top layer only), `B` (bottom layer only) or
`C` (coincidence, both layers within the firmware window). A single unit is
therefore already a short, wide-angle **muon telescope** in its own right.

Representative rates measured from the Unit 1 raw files
(`examples/RPi4_data/data/raw/2026/…`):

| Quantity | Measured value |
|---|---|
| Top-layer singles rate | ≈ 2.4 s⁻¹ |
| Bottom-layer singles rate | ≈ 2.3 s⁻¹ |
| Coincidence (C) rate | ≈ 880 h⁻¹ ≈ 0.24 s⁻¹ (≈ 21,000 day⁻¹) |

The singles rates are roughly ten times the rate expected from muons alone
through 25 cm² (≈ 0.3–0.4 s⁻¹). The excess is the *soft component*
(electrons, positrons and photons from air showers) plus electronic noise
near threshold — exactly why the two-layer coincidence is the muon channel
[1, 2, 31]. The C rate of ≈ 880 h⁻¹ agrees to better than a factor of two
with the cos²θ-weighted geometric prediction for this geometry (§8.4),
which is good agreement given the uncertainty in the low-energy muon
intensity, shower multi-particle events, and edge effects in 1 cm-thick
scintillator.

### 1.2 Reference numbers for sea-level muons

From the Particle Data Group review and standard references [1, 2, 32]:

- Vertical integral intensity: I₀ ≈ 70 m⁻² s⁻¹ sr⁻¹ ≈ 0.007 cm⁻² s⁻¹ sr⁻¹
  (p > 1 GeV/c); ≈ 0.009–0.011 cm⁻² s⁻¹ sr⁻¹ for all momenta.
- Zenith-angle dependence: I(θ) ≈ I₀ · cosⁿθ with n ≈ 2 at sea level for
  Eμ ≈ 3 GeV (the famous "about 1 muon per cm² per minute" through a
  horizontal surface).
- Mean muon energy at the ground ≈ 4 GeV; muons are produced mostly from
  pion/kaon decay at 100–200 hPa altitude (≈ 12–16 km).

These numbers anchor every section below.

---

## 2. §5.1 Pressure coefficient β (the barometric effect)

### 2.1 Physics

The atmosphere above the detector is an absorber. When surface pressure P
rises, there is more mass overburden, so more muons are stopped or decay
before reaching the ground and the count rate falls. For surface muons the
effect is small and negative: β ≈ −0.12 to −0.20 %/hPa [4, 5]. The fitted
PicoMuon value of −0.188 %/hPa (finding F11 in the implementation plan) sits
comfortably in this range. (Neutron monitors, which respond to the lower-energy
nucleonic component, have a much larger coefficient, ≈ −0.7 %/hPa [4, 25].)

### 2.2 Mathematics

The standard exponential absorption model [4, 5]:

```text
N(P) = N₀ · exp(β · (P − P₀))        ⇔        ln(N/N₀) = β · (P − P₀)
```

so the pressure-corrected count is

```text
N_P = N · exp(−β · (P − P₀))
```

with P₀ a fixed reference pressure (the long-term station mean, frozen in
`config/coefficients.ini`).

β is estimated by **weighted least squares (WLS)** on hourly L2 data. With
xᵢ = Pᵢ − P₀, yᵢ = ln(Nᵢ/N̄) and Poisson weights wᵢ = 1/σᵢ² where
σᵢ = 1/√Nᵢ (the relative error of a count of Nᵢ):

```text
β̂ = Σ wᵢ(xᵢ − x̄_w)(yᵢ − ȳ_w) / Σ wᵢ(xᵢ − x̄_w)²

σ(β̂) = 1 / √( Σ wᵢ(xᵢ − x̄_w)² )
```

where x̄_w, ȳ_w are the weighted means. The fit **must include an
intercept** (the current gnuplot fit forces the line through zero, which
biases β whenever the mean rate drifts).

### 2.3 Procedure and pitfalls

1. **Remove the primary cosmic-ray variation first.** Forbush decreases and
   solar modulation move the rate by percent-level amounts that are
   *correlated with weather systems in time* and will bias β. Either divide
   by a pressure-corrected NMDB neutron-monitor rate (scaled) [25], or
   detrend with a 27-day running mean. Exclude flagged Forbush/GLE days.
2. Fit hourly, not daily: with ≈ 880 counts/hour, 90 days of hourly data
   give ≈ 2,160 points spanning typically ±30 hPa, so σ(β) ≪ 0.01 %/hPa —
   far better leverage than daily means.
3. Keep a **rolling 90-day β** for monitoring and a **frozen β** in
   `config/coefficients.ini` for the correction chain, so that reprocessing
   history does not change past corrected values.
4. Once a year of data exists, fit pressure and temperature **together**
   (multiple regression, §3.4), since P and T_eff both vary seasonally and
   are correlated.

Key references: Dorman's monograph on cosmic rays in the atmosphere [4];
De Mendonça et al. for a modern worked analysis of pressure and temperature
effects on muon detectors [5].

---

## 3. §5.2 Temperature coefficient(s)

Two physically distinct temperature effects must be kept apart.

### 3.1 The atmospheric (true) temperature effect

Muons come from π± and K± decay at the 100–200 hPa level. When the upper
atmosphere warms it expands: production moves higher, muons have a longer
path and more decay in flight (negative effect); against this, lower air
density means pions are more likely to decay to muons before interacting
(positive effect). For *surface* detectors, which see mostly low-energy
muons, the **negative effect wins**: α_T ≈ −0.1 to −0.2 %/K, appearing
mainly as a seasonal wave [5, 7, 8, 10]. (Deep underground the sign flips:
MINOS measures a *positive* ≈ +0.9 %/K because only high-energy muons from
decaying pions reach it [9].)

The modern treatment (Barrett et al. [7]; Dmitrieva et al. [8]; Sagisaka
[10]) replaces the full temperature profile with one **effective
temperature**:

```text
T_eff = Σᵢ Wᵢ · T(pᵢ) / Σᵢ Wᵢ
```

a weighted average of the temperatures T(pᵢ) on pressure levels pᵢ. The
rigorous weights Wᵢ come from meson-production theory [7, 8, 9]; a
**mass-weighted average** (Wᵢ = Δpᵢ, the layer thickness in hPa) is an
adequate starting point for a counting experiment of this size, and can be
upgraded to the Dmitrieva weights later without changing the pipeline.

The fit, on *pressure-corrected* data:

```text
ln(N_P / N₀) = α_T · (T_eff − T_eff,₀)
```

with the same WLS machinery as §2.2. Requirements:

- Temperatures on pressure levels for the station location. The free
  **Open-Meteo** historical/forecast API provides 1000–30 hPa levels [12];
  **ERA5** reanalysis is the research-grade alternative [11].
  (`GetDataUpperAir.py` in the plan.)
- At least 6–12 months of data, because the signal is mostly the seasonal
  wave; with less than a full cycle, α_T and any linear drift are
  degenerate.
- Once a year exists, fit P and T together:

```text
ln(N/N₀) = β·ΔP + α_T·ΔT_eff + c
```

solved as a standard multiple linear regression (normal equations
**X**ᵀ**W**​**X** β̂ = **X**ᵀ**W**​**y**), because ΔP and ΔT_eff are
seasonally correlated and separate single-variable fits would double-count.

### 3.2 The instrument temperature effect

The Pico's on-board sensor measures the **detector box**, not the
atmosphere. SiPM gain falls with temperature (breakdown voltage rises
≈ 20–60 mV/K), so a fixed discriminator threshold corresponds to a
temperature-dependent light level — the counting efficiency drifts with room
temperature [31]. Treatment:

- Fit residuals (after P and T_eff correction) against detector temperature
  over short windows: `ln(N_PT/⟨N_PT⟩) = α_det · (T_det − T_det,₀)`.
- **Caution:** indoor temperature has a strong daily cycle. Correcting with
  it can *create or destroy* an apparent solar diurnal variation (§4). The
  independent check is the **ADC spectrum**: real gain drift shifts the
  ADC peak position, whereas a genuine rate anisotropy does not. Prefer
  stabilising the detector temperature over correcting for it.

### 3.3 The correction chain

Implemented in `ApplyCorrections.py`, applied to L2 hourly files:

```text
N_PT = N · exp(−β·ΔP) · exp(−α_T·ΔT_eff) [ · exp(−α_det·ΔT_det) ]
```

All week-to-year plots then carry raw, P-corrected and PT-corrected curves
next to the NMDB reference.

---

## 4. §5.3 Daily (solar) variation – harmonic analysis

### 4.1 Physics

The solar diurnal anisotropy is a genuine ≈ 0.1–0.2 % sinusoidal variation
of the cosmic-ray intensity with a maximum typically around 15–18 h local
time, caused by the corotation of cosmic rays with the interplanetary
magnetic field [17]. It sits on top of (and must be separated from)
atmospheric daily cycles and instrument temperature cycles.

### 4.2 Harmonic fitting mathematics

On PT-corrected hourly data, detrended by a 24-h running mean (or the NMDB
ratio), fit the first two harmonics by least squares:

```text
y(t) = A₀ + Σ_{k=1,2} [ a_k·cos(2πk·t/24) + b_k·sin(2πk·t/24) ]

amplitude  A_k = √(a_k² + b_k²)        phase  φ_k = atan2(b_k, a_k)
```

Least-squares harmonic fitting handles data gaps correctly (unlike a plain
FFT, §7.4) and returns amplitudes in physical units directly.

Also produce a **superposed-day plot**: average the fractional deviation in
each local-solar-time hour bin over many days, with error bars σ_bin =
1/√(ΣN_bin). This is the most honest visualisation and reveals non-sinusoidal
shapes (e.g. a temperature-driven kink).

### 4.3 Sensitivity

For a Poisson counting experiment, the 1σ uncertainty on a fitted relative
sinusoid amplitude is [15]:

```text
σ_A ≈ √(2 / N_total)
```

With ≈ 21,000 C events/day:

| Duration | N_total | σ_A |
|---|---|---|
| 1 month | ≈ 6.3 × 10⁵ | ≈ 0.18 % |
| 1 year | ≈ 7.7 × 10⁶ | ≈ 0.05 % |

The expected amplitude is 0.1–0.2 %, so **one year gives a ≈ 3σ detection;
one month does not**.

### 4.4 The solar / sidereal / anti-sidereal test

A solar day is 24 h; a sidereal day is 23.934 h. Any *seasonally modulated*
solar-time variation leaks symmetrically into the sidereal (24 h − 3.93 min)
and **anti-sidereal** (24 h + 3.93 min, a purely artificial frequency)
sidebands. The Farley–Storey test [16]: measure all three amplitudes; the
anti-sidereal amplitude estimates the seasonal contamination of the sidereal
result. A real sidereal (galactic) anisotropy — ≈ 0.05 % at these energies —
shows at the sidereal frequency only. Also check that the fitted solar phase
does not track the room-temperature cycle (§3.2).

### 4.5 27-day recurrence

The Sun rotates (synodically) in ≈ 27.3 days, so long-lived active regions
and high-speed streams imprint a 27-day recurrence on cosmic rays. Apply the
Lomb–Scargle periodogram (§7.5) to *daily* PT-corrected means and look for
power near 0.037 day⁻¹; compare with the same analysis on the NMDB station.

---

## 5. §5.4 Solar cycle and Forbush decreases

### 5.1 Forbush decreases (good prospects)

A Forbush decrease (FD) is a sudden drop in cosmic-ray intensity — hours to
onset, ≈ a week to recover — caused by an interplanetary CME and/or
high-speed stream sweeping past Earth [20, 21, 22]. Large events give
≈ 1–5 % drops in surface muon rates (5–20 % in neutron monitors). Daily
Poisson noise here is ≈ 0.7 % (1/√21,000), so big FDs are clearly visible in
6–24 h averages of one detector.

**Detection algorithm** (`Forbush.py`):

1. Baseline B(t): median of the previous 27 days of PT-corrected hourly
   rates (robust to the event itself).
2. Test statistic on a 6-h (and 24-h) moving mean R̄:

```text
z(t) = ( R̄(t) − B(t) ) / σ        flag if z ≤ −k   (k ≈ 3)
```

   with σ the combined Poisson + observed scatter of the baseline window.
3. Cross-check: require a simultaneous decrease in one or more NMDB
   stations [25] — this kills local/instrumental false positives.
4. Mark candidate times from NASA DONKI ICME/CME lists and Kp/Dst indices
   [27] (reuse the Magnetometer suite's `space_weather.py`).
5. **Superposed-epoch (Chree) analysis** [23]: align many events on their
   onset time and average. The mean FD profile emerges from events far too
   small to see individually.
6. The **muon/neutron drop ratio** δμ/δNM is a crude rigidity-spectrum
   probe: muon detectors respond to higher median rigidity (tens of GV)
   than neutron monitors (few GV), and FDs suppress low rigidities more
   [21, 22].

### 5.2 The 11-year solar cycle (long-term, harder)

Solar modulation makes cosmic-ray intensity anti-correlate with the sunspot
cycle, with a lag of some months [24]. At surface-muon rigidities the full
cycle swing is only a **few percent** (vs 15–25 % for high-latitude neutron
monitors), so detector stability — SiPM ageing, threshold and temperature
drift — is the real limit, not statistics.

Planned approach (`SolarCycle.py`):

- Monthly or 27-day means of the PT-corrected rate.
- Monthly SILSO sunspot number: `https://www.sidc.be/SILSO/INFO/snmtotcsv.php` [26].
- The NMDB monthly rate for the same months [25].
- **Lagged cross-correlation** between rate x and sunspot number y:

```text
r(ℓ) = Σ_t (x_t − x̄)(y_{t+ℓ} − ȳ) / ( √Σ(x_t − x̄)² · √Σ(y_t − ȳ)² )
```

  Scan ℓ = 0…24 months; cosmic rays should lag sunspots by ≈ 2–12 months
  depending on cycle phase and polarity [24].
- Track the **muon/NM ratio**: real heliospheric modulation moves both in
  a known proportion; detector drift moves only the muon channel. The ratio
  therefore separates instrument drift from real modulation.

Cycle 25 peaked around 2024–25, so the cosmic-ray intensity should *rise*
through 2026–2030. With stable detectors this is detectable in ≈ 3–5 years,
sooner if several UKRAA stations are combined.

---

## 6. Interlude: why gaps and cadence shape the method choice

Sections 4 and 5 both reduce to finding periodic signals in a noisy,
*gapped*, unevenly sampled counting series. The next section treats this
properly, because the user-facing deliverable of `Harmonics.py` is a
periodogram and its correct interpretation.

---

## 7. Applying the FFT to muon data to identify cycles

### 7.1 The discrete Fourier transform

For N samples x₀…x_{N−1} taken at a uniform interval Δt, the DFT is

```text
X_k = Σ_{n=0}^{N−1} x_n · exp(−2πi·k·n/N),      k = 0 … N−1
```

computed in O(N log N) by the FFT [18, 19]. The power spectrum is
P_k = |X_k|²/N, and bin k corresponds to frequency f_k = k/(N·Δt). The
relative amplitude of a sinusoid at bin k is A_k = 2|X_k|/(N·x̄).

Two hard limits govern everything:

```text
Nyquist frequency:      f_max = 1/(2Δt)
Frequency resolution:   Δf   = 1/(N·Δt) = 1/T_obs
```

For **hourly** muon data: f_max = 12 cycles/day — ample for the 1 and
2 cycles/day harmonics. For **daily** means: f_max = 0.5 cycles/day — fine
for 27-day and annual lines.

### 7.2 What the resolution limit means physically

The cycles of interest, in cycles per day (cpd):

| Signal | Period | Frequency (cpd) |
|---|---|---|
| Solar diurnal | 24 h | 1.00000 |
| Sidereal diurnal | 23.934 h | 1.00274 |
| Anti-sidereal (artefact test) | 24.066 h | 0.99726 |
| Semidiurnal | 12 h | 2.00000 |
| Solar rotation | ≈ 27.3 d | 0.0366 |
| Seasonal (T_eff wave) | 365.25 d | 0.00274 |
| Solar cycle | ≈ 11 yr | 0.00025 |

Note that the solar and sidereal lines are separated by **exactly
1/365.25 cpd** (one extra sidereal cycle per year). Since Δf = 1/T_obs, you
need **T_obs ≥ 1 year just to split the solar from the sidereal line**, and
several years to measure the sidereal amplitude cleanly. This is the
spectral-resolution restatement of the Farley–Storey argument (§4.4) [16].

### 7.3 Practical FFT recipe for this dataset

1. Work on **PT-corrected hourly fractional deviations**:
   xₙ = N_PT,ₙ/⟨N_PT⟩ − 1. Corrections first — otherwise the spectrum is
   dominated by pressure weather noise (broadband, days-scale) and the
   seasonal temperature wave.
2. **Detrend** (subtract a 27-day running mean) before looking at diurnal
   frequencies; long-period power otherwise leaks across the spectrum.
3. **Window** the data (Hann window) to control spectral leakage from the
   finite record length; quote the window's amplitude correction factor [19].
4. **Zero-pad** (e.g. 4×) for a smoother spectrum display — this
   interpolates bins but does *not* add resolution.
5. Estimate significance against the Poisson floor: a pure counting series
   has a flat (white) spectrum with mean power 1/N_total in relative-power
   units; a line is interesting when it exceeds the local background by the
   standard false-alarm criterion (§7.5).

### 7.4 The gap problem → Lomb–Scargle

Real muon records have holes (USB drops, reboots, cron windows). A plain FFT
needs uniform sampling; filling gaps with zeros or interpolation injects
spurious power at exactly the daily frequencies of interest (gaps are not
random — they correlate with maintenance habits). Two correct options:

- **Harmonic least-squares fitting** at the handful of frequencies of
  interest (§4.2) — gaps simply mean fewer equations.
- The **Lomb–Scargle periodogram** [13, 14, 15], the generalisation of the
  periodogram to uneven sampling. For data (tₙ, xₙ) with mean removed:

```text
P(ω) = 1/2 · { [Σₙ xₙ cos ω(tₙ−τ)]² / Σₙ cos² ω(tₙ−τ)
             + [Σₙ xₙ sin ω(tₙ−τ)]² / Σₙ sin² ω(tₙ−τ) }

with   tan(2ωτ) = Σₙ sin 2ωtₙ / Σₙ cos 2ωtₙ
```

  The time offset τ makes the result invariant to time translation and
  equivalent to least-squares sine fitting at each frequency [14, 15].
  Under the null hypothesis (Gaussian noise), P at one frequency is
  exponentially distributed, giving the **false-alarm probability**
  FAP ≈ 1 − (1 − e^(−P))^M for M independent frequencies [14, 15].

Implementation: `astropy.timeseries.LombScargle` (or
`scipy.signal.lombscargle`) — both run easily on a Pi for ≤ 10⁵ hourly
points. VanderPlas [15] is the definitive practical guide (normalisation,
aliasing, FAP, floating mean).

### 7.5 Expected result sequence

| Dataset | Method | Expected detection |
|---|---|---|
| 1 month hourly | superposed day | atmospheric daily cycle only |
| 1 year hourly | harmonic fit / L-S | solar diurnal ≈ 0.1–0.2 % at ≈ 3σ; semidiurnal marginal |
| 1 year daily | Lomb–Scargle | 27-day recurrence (compare with NMDB) |
| ≥ 2 years hourly | L-S, three-frequency test | sidereal vs anti-sidereal separation |
| 3–5 years monthly | cross-correlation | 11-year modulation trend (with NMDB ratio for drift control) |

---

## 8. A pointable muon telescope from two (or more) PicoMuon units

### 8.1 Concept

A single unit's T·B coincidence already defines a telescope with a 30 mm
baseline — but a very wide one (acceptance out to ≈ 67° from the axis). By
operating **two units one above the other** and demanding a four-fold
coincidence C₁·C₂ (or the pair of outermost layers T₁·B₂), the baseline
grows from 3 cm to tens of cm, the acceptance cone narrows, and the stack
becomes a **directional instrument**: tilt it, and the counting rate
measures the muon intensity from that part of the sky.

A key geometric fact: for equal-area, aligned, parallel layers, any straight
track through the two *outermost* layers necessarily crosses the inner
layers too. So the four-fold geometry is set by the **outermost layer pair**,
and the inner layers add redundancy (background rejection and efficiency
measurement, §8.6) at no geometric cost.

### 8.2 Inter-unit coincidence: timing

The two Picos free-run on separate clocks, so coincidences between units
must be formed from timestamps. Two regimes:

**(a) Offline matching of RPi timestamps (current hardware).**
Each event row carries `RPiTimestamp` with microsecond *format*, but the
real accuracy is limited by USB/serial buffering and host scheduling —
realistically ≈ 1–10 ms jitter. Matching rule: pair a C event from Unit 1
with a C event from Unit 2 when |Δt| ≤ τ. The **accidental (chance)
coincidence rate** for singles rates R₁, R₂ and full window 2τ is [30]:

```text
R_acc = 2 τ R₁ R₂
```

With R₁ = R₂ ≈ 0.24 s⁻¹ (C events) and τ = 1 ms: R_acc ≈ 1.2 × 10⁻⁴ s⁻¹ ≈
**10 day⁻¹** — small compared with the true stacked-telescope rates below
(hundreds to thousands per day), so ms timing is already usable *provided
the matching is done between C events*, not raw singles (matching raw
T/B singles at 2.4 s⁻¹ each would give ≈ 1,000 accidentals/day).
Verification plot: the histogram of Δt between the two units must show a
sharp true-coincidence peak standing on a flat accidental floor; the floor
level measures R_acc directly and is subtracted.

**(b) GPS PPS timing (planned upgrade).**
A GPS pulse-per-second disciplining both Picos gives ≈ µs absolute
timestamps. Then τ = 1 µs ⇒ R_acc ≈ 0.01 day⁻¹ — negligible — and the same
hardware can do **inter-site shower coincidence** with other UKRAA stations
(see "Other improvement suggestions" in the implementation plan).

NTP/chrony on the two RPis (or one RPi reading both units, the current
two-unit setup) keeps the clocks within a few ms, which is sufficient for
regime (a).

### 8.3 The zenith-angle law the telescope will measure

The telescope's first science target is the angular distribution itself:

```text
I(θ) = I₀ · cosⁿθ,        n ≈ 2 at sea level [1, 2, 32]
```

Procedure: fix the separation (e.g. d = 20 cm), point the stack at zenith
angles θ_z = 0°, 15°, 30°, 45°, 60°, 75°, 90°, accumulate equal live times,
and fit n from

```text
ln R(θ_z) = ln R(0) + n · ln cos θ_z
```

Expected systematics: at large θ_z the detector sees partially through
buildings (note the overburden in each direction); near θ_z = 90° the rate
does not go to zero (n ≈ 2 is an approximation; high-energy muons flatten
the distribution [1]).

### 8.4 Solid angle and geometric factor: the mathematics

**Definitions.** For a telescope of two parallel plane detectors, the
counting rate in an isotropic flux I (particles cm⁻² s⁻¹ sr⁻¹) is R = I·G,
where G is the **geometric factor** (also called gathering power, units
cm² sr) [28]:

```text
G = ∫_{A₁} ∫_{A₂}  cos θ₁ · cos θ₂ / r²  dA₁ dA₂
```

Here r is the distance between area elements dA₁ and dA₂ and θ₁ = θ₂ = θ is
the angle of the connecting line to the (common) normal; for parallel planes
separated by d, cos θ = d/r. Sullivan's classic paper [28] is the standard
reference for this formalism.

A useful companion quantity is the **effective solid angle**

```text
Ω_eff = G / A        (sr, with A the detector area)
```

i.e. the solid angle that, multiplied by area and intensity, reproduces the
rate.

**Limit 1 — detectors stacked (d → 0).** Every particle through one layer
passes the other, so the telescope degenerates into a single horizontal
plane exposed to the upper hemisphere:

```text
G → A · ∫_{2π} cos θ dΩ = A · π          ⇒   Ω_eff = π sr  ≈ 3.14 sr
```

(The *geometric* half-sky is 2π sr; the cos θ projection factor reduces the
effective value to π. For the 5 × 5 cm layer: G = 78.5 cm² sr.)

**Limit 2 — large separation (d ≫ a).** Each detector sees the other as a
point: every pair of area elements has r ≈ d, cos θ ≈ 1, so

```text
G → A₁·A₂ / d²    = A²/d²            ⇒   Ω_eff ≈ A/d²
```

which is the familiar "solid angle subtended by the far detector". For two
25 cm² layers at d = 50 cm: G ≈ 0.25 cm² sr, Ω_eff ≈ 0.01 sr.

**Exact closed form for all separations.** The double integral above is
π·A₁ times the **radiative view factor** F₁₂ between two directly opposed
parallel rectangles — a standard result of radiative heat transfer [29]:

```text
G = π · A · F₁₂
```

For two identical squares of side a at separation d, writing X = Y = a/d:

```text
F₁₂ = 2/(π X Y) · [ ln √( (1+X²)(1+Y²) / (1+X²+Y²) )
                    + X √(1+Y²) · atan( X / √(1+Y²) )
                    + Y √(1+X²) · atan( Y / √(1+X²) )
                    − X·atan X  −  Y·atan Y ]
```

This reproduces both limits above and is trivial to evaluate in Python
(≈ 10 lines; it belongs in `analysis/Telescope.py`).

**Muon-weighted rate.** Because the real flux is not isotropic
(I = I₀ cos²θ), the predicted vertical-pointing rate is

```text
R = I₀ · ∫∫ cos²θ · cosθ₁ cosθ₂ / r² dA₁ dA₂
  = I₀ · ∫∫ d⁴ / r⁶ dA₁ dA₂
```

evaluated numerically (a 10⁵-sample Monte Carlo over both planes converges
to < 1 %).

### 8.5 Worked numbers for the PicoMuon geometry

For two 5 cm × 5 cm layers (A = 25 cm²), as a function of centre-to-centre
separation d. G from the exact view-factor formula; R from the cos²-weighted
Monte Carlo with I₀ = 0.007 cm⁻² s⁻¹ sr⁻¹ (p > 1 GeV/c — a conservative
floor; the all-momentum rate is ≈ 1.3–1.5× higher); FWHM is the full width
at half maximum of the on-axis angular response (from the layer-overlap
function):

| d (cm) | Configuration example | G (cm² sr) | Ω_eff (sr) | Predicted R (h⁻¹) | R (day⁻¹) | FWHM |
|---:|---|---:|---:|---:|---:|---:|
| → 0 | single layer limit | 78.5 | 3.14 (= π) | — | — | — |
| 3 | one unit, internal T·B | 27.8 | 1.11 | 514 | 12,300 | 52° |
| 6 | two units touching, B₁·T₂ | 12.2 | 0.49 | 265 | 6,360 | 27° |
| 9 | two units touching, T₁·B₂ ≈ | 6.45 | 0.26 | 150 | 3,600 | 19° |
| 10 | small gap | 5.39 | 0.22 | 127 | 3,040 | 17° |
| 15 | | 2.59 | 0.104 | 63 | 1,510 | 11° |
| 20 | | 1.50 | 0.060 | 37 | 890 | 8.4° |
| 25 | | 0.97 | 0.039 | 24 | 580 | 6.7° |
| 30 | | 0.68 | 0.027 | 17 | 410 | 5.6° |
| 40 | | 0.39 | 0.0155 | 9.7 | 230 | 4.2° |
| 50 | | 0.25 | 0.0099 | 6.2 | 150 | 3.4° |
| 53 | 50 cm gap, outer layers | 0.22 | 0.0088 | 5.6 | 130 | 3.2° |

Notes:

- **"Units directly on top of each other":** the usable baselines are the
  internal 3 cm pair in each unit, the two facing layers (B₁·T₂ — 3 cm plus
  twice the layer-centre-to-case distance; measure your cases), and the
  outermost pair T₁·B₂ at ≈ 9 cm + case allowance. The table rows at 6 and
  9 cm are placeholders — substitute the measured centre-to-centre values.
  The formula needs only a, A and d.
- The internal-telescope prediction (514 h⁻¹ at I₀ = 0.007) brackets the
  observed ≈ 880 h⁻¹ once the all-momentum intensity (×≈1.4) and shower
  multi-particle coincidences are included — a useful absolute sanity check
  for `Telescope.py`.
- **Statistics planning:** for a target 5 % rate measurement per pointing
  you need N = 400 events; at d = 30 cm vertical that is ≈ 1 day, and at
  θ_z = 60° (cos²θ ⇒ ×0.25) ≈ 4 days. Narrow telescopes buy resolution with
  observing time — choose d to match the question.
- Angular resolution vs separation is the design trade: d = 10 cm sees a
  ≈ 17° cone (good for a 5-point zenith scan in a week); d = 50 cm sees
  ≈ 3–4° (sky-map pixels, but 150 events/day vertical).

### 8.6 Efficiency calibration with the four-layer stack

With four layers the per-layer efficiency is measured in situ: select
tracks defined by three layers and ask how often the fourth fired:

```text
ε₄ = N(1·2·3·4) / N(1·2·3)
```

Apply to each layer in turn. This separates real rate changes from SiPM
drift — directly supporting the §3.2 and §5.2 drift-control requirements.

### 8.7 Data to generate

Suggested per-run record (one CSV row per pointing/configuration,
`data/telescope/runs.csv`):

```text
run_id, utc_start, utc_end, live_s,
d_cm, zenith_deg, azimuth_deg,
n_c1, n_c2, n_coinc, n_accidental_est,
rate_hz, rate_err_hz, pressure_mean_hPa, rate_P_corrected_hz,
tau_ms, notes
```

plus the raw matched-pair file (one row per inter-unit coincidence:
both timestamps, Δt, both ADC values) so the analysis can be re-cut later —
consistent with the project's preserve-raw-data rule.

Every rate must be **pressure-corrected** (§2) before angles are compared,
because a pointing sequence spanning days will otherwise fold weather into
the angular distribution.

### 8.8 Plots to generate

1. **Δt histogram** between Unit 1 and Unit 2 C events: true-coincidence
   peak on flat accidental floor. The commissioning plot; also measures the
   effective τ and R_acc.
2. **Rate vs zenith angle** with fitted I₀cosⁿθ overlay (linear and
   log–cos axes); residuals panel. The headline science plot.
3. **Polar sky plot**: rate (colour) on a zenith/azimuth polar grid from a
   pointing campaign; even an 8-azimuth × 4-zenith map shows the cos²
   bowl and any building shadowing.
4. **Rate vs separation d** at fixed vertical pointing, with the G(d)
   prediction curve of §8.5 overlaid — a direct experimental verification
   of the solid-angle mathematics.
5. **Angular response curves**: computed G vs tilt for each d (from the
   Monte Carlo), showing the narrowing FWHM — the "beam pattern" of the
   telescope.
6. **East–West asymmetry**: rate at θ_z = 45° East vs 45° West. The
   geomagnetic field deflects the (positive-excess) muon parents, giving a
   measurable West excess of order a few percent [2] — a classic experiment
   feasible at d ≈ 10–15 cm in a few weeks.
7. **ADC spectra in coincidence vs singles** for each layer: the coincidence
   requirement isolates the muon (Landau-like) peak from the soft-component
   and noise pedestal — the efficiency/threshold monitoring plot.
8. Long-term: **sidereal-time superposed histogram** from the narrow
   configuration (ties into §4.4).

### 8.9 Extensions with more than two units

- **Three stacked units (six layers):** tracking redundancy, better
  efficiency calibration, and a hardware-free trigger purity cross-check.
- **Two units side-by-side, horizontal baseline:** extensive-air-shower
  (EAS) coincidences — two muons from the same shower arrive within ≈ 100 ns
  over tens of metres; with GPS PPS timing this extends to inter-site shower
  astronomy between UKRAA stations (implementation-plan "Other improvement
  suggestions").
- **Fixed orthogonal telescopes (one vertical, one at 45°):** continuous
  differential monitoring — Forbush decreases are anisotropic in their onset
  phase, and a two-direction muon system sees the loss-cone precursor [21].

---

## 9. References

1. R. L. Workman et al. (Particle Data Group), *Review of Particle Physics*,
   Prog. Theor. Exp. Phys. 2022, 083C01 — Ch. 30 "Cosmic Rays".
   https://pdg.lbl.gov/
2. P. K. F. Grieder, *Cosmic Rays at Earth: Researcher's Reference Manual
   and Data Book*, Elsevier (2001). ISBN 978-0-444-50710-5.
3. B. Rossi, *Cosmic Rays*, McGraw-Hill (1964).
4. L. I. Dorman, *Cosmic Rays in the Earth's Atmosphere and Underground*,
   Kluwer Academic (2004). doi:10.1007/978-1-4020-2113-8
5. R. R. S. De Mendonça, J.-P. Raulin, E. Echer, V. S. Makhmutov,
   G. Fernandez, "Analysis of atmospheric pressure and temperature effects
   on cosmic ray measurements", J. Geophys. Res. Space Physics 118 (2013)
   1403–1409. doi:10.1029/2012JA018026
6. M. L. Duldig, "Muon Observations", Space Sci. Rev. 93 (2000) 207–226.
   doi:10.1023/A:1026596529381
7. P. H. Barrett, L. M. Bollinger, G. Cocconi, Y. Eisenberg, K. Greisen,
   "Interpretation of Cosmic-Ray Measurements Far Underground",
   Rev. Mod. Phys. 24 (1952) 133. doi:10.1103/RevModPhys.24.133
8. A. N. Dmitrieva, R. P. Kokoulin, A. A. Petrukhin, D. A. Timashkov,
   "Corrections for temperature effect for ground-based muon hodoscopes",
   Astropart. Phys. 34 (2011) 401–411.
   doi:10.1016/j.astropartphys.2010.10.013
9. P. Adamson et al. (MINOS Collaboration), "Observation of muon intensity
   variations by season with the MINOS far detector", Phys. Rev. D 81
   (2010) 012001. doi:10.1103/PhysRevD.81.012001
10. S. Sagisaka, "Atmospheric effects on cosmic-ray muon intensities at
    deep underground depths", Il Nuovo Cimento C 9 (1986) 809–828.
    doi:10.1007/BF02558081
11. H. Hersbach et al., "The ERA5 global reanalysis", Q. J. R. Meteorol.
    Soc. 146 (2020) 1999–2049. doi:10.1002/qj.3803
12. Open-Meteo historical weather & pressure-level API.
    https://open-meteo.com/ (accessed November 2026).
13. N. R. Lomb, "Least-squares frequency analysis of unequally spaced
    data", Astrophys. Space Sci. 39 (1976) 447–462. doi:10.1007/BF00648343
14. J. D. Scargle, "Studies in astronomical time series analysis. II.
    Statistical aspects of spectral analysis of unevenly spaced data",
    Astrophys. J. 263 (1982) 835–853. doi:10.1086/160554
15. J. T. VanderPlas, "Understanding the Lomb–Scargle Periodogram",
    Astrophys. J. Suppl. 236 (2018) 16. doi:10.3847/1538-4365/aab766
16. F. J. M. Farley, J. R. Storey, "The Sidereal Correlation of Extensive
    Air Showers", Proc. Phys. Soc. A 67 (1954) 996–1004.
    doi:10.1088/0370-1298/67/11/306
17. D. L. Hall, M. L. Duldig, J. E. Humble, "Analyses of sidereal and solar
    anisotropies in cosmic rays", Space Sci. Rev. 78 (1996) 401–442.
    doi:10.1007/BF00171926
18. J. W. Cooley, J. W. Tukey, "An algorithm for the machine calculation of
    complex Fourier series", Math. Comp. 19 (1965) 297–301.
    doi:10.1090/S0025-5718-1965-0178586-1
19. W. H. Press, S. A. Teukolsky, W. T. Vetterling, B. P. Flannery,
    *Numerical Recipes*, 3rd ed., Cambridge University Press (2007) —
    Chs. 12–13 (FFT, spectral analysis, Lomb periodogram).
20. S. E. Forbush, "On the Effects in Cosmic-Ray Intensity Observed During
    the Recent Magnetic Storm", Phys. Rev. 51 (1937) 1108.
    doi:10.1103/PhysRev.51.1108.3
21. H. V. Cane, "Coronal Mass Ejections and Forbush Decreases", Space Sci.
    Rev. 93 (2000) 55–77. doi:10.1023/A:1026532125747
22. J. A. Lockwood, "Forbush decreases in the cosmic radiation", Space Sci.
    Rev. 12 (1971) 658–715. doi:10.1007/BF00173346
23. C. Chree, "Some Phenomena of Sunspots and of Terrestrial Magnetism at
    Kew Observatory", Phil. Trans. R. Soc. A 212 (1913) 75–116.
    doi:10.1098/rsta.1913.0003 (origin of superposed-epoch analysis).
24. I. G. Usoskin, "A history of solar activity over millennia", Living
    Rev. Sol. Phys. 14 (2017) 3. doi:10.1007/s41116-017-0006-9
25. H. Mavromichalaki et al., "Applications and usage of the real-time
    Neutron Monitor Database", Adv. Space Res. 47 (2011) 2210–2222.
    doi:10.1016/j.asr.2010.02.019 — https://www.nmdb.eu/ (acknowledgement
    required by the NMDB data policy).
26. SILSO, World Data Center – Sunspot Number, Royal Observatory of
    Belgium. https://www.sidc.be/SILSO/ (accessed November 2026).
27. NASA Space Weather Database Of Notifications, Knowledge, Information
    (DONKI). https://kauai.ccmc.gsfc.nasa.gov/DONKI/ (accessed November
    2026).
28. J. D. Sullivan, "Geometrical factor and directional response of single
    and multi-element particle telescopes", Nucl. Instrum. Meth. 95 (1971)
    5–11. doi:10.1016/0029-554X(71)90033-4
29. J. R. Howell, M. P. Mengüç, R. Siegel, *Thermal Radiation Heat
    Transfer*, 7th ed., CRC Press (2020) — view factor for directly opposed
    parallel rectangles (catalogue entry C-11,
    http://www.thermalradiation.net/).
30. G. F. Knoll, *Radiation Detection and Measurement*, 4th ed., Wiley
    (2010) — Ch. 17 (coincidence methods, chance-coincidence rate).
31. S. N. Axani, K. Frankiewicz, J. M. Conrad, "The CosmicWatch Desktop
    Muon Detector: a self-contained, pocket sized particle detector",
    JINST 13 (2018) P03019. doi:10.1088/1748-0221/13/03/P03019
    (arXiv:1801.03029) — comparable 5 × 5 cm SiPM scintillator design,
    singles vs coincidence rates, SiPM temperature dependence.
32. R. G. Crookes, B. C. Rastin, "An investigation of the absolute
    intensity of muons at sea-level", Nucl. Phys. B 39 (1972) 493–508.
    doi:10.1016/0550-3213(72)90380-2

---

*Computed values in §8.5 were generated with the exact view-factor formula
and a 4 × 10⁵-sample Monte Carlo (cos²θ weighting); scripts to reproduce
them belong in `analysis/Telescope.py` (Phase 8 deliverable).*
