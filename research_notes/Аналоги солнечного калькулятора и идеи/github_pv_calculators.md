# Open-source PV / off-grid / hybrid calculators and simulators (GitHub etc.): catalogue and comparison with solar_calc v1.2.1

Research date: 2026-10-08. Method: web search, GitHub topic pages (star counts and "last updated" dates were read from these pages on 2026-10-08), PyPI JSON metadata (version and upload date of the latest release), and README files read from raw.githubusercontent.com because most documentation sites (readthedocs, pv-magazine, JRC) were blocked by the network proxy. No GitHub MCP tools were used. "Stars n/a" means no star count was visible in the sources I could reach.

Naming note: NREL's GitHub organisation is now **NatLabRockies**. The SAM and REopt READMEs call the lab the "National Laboratory of the Rockies (NLR)", and old `NREL/...` URLs redirect there. — [SAM README](https://github.com/NatLabRockies/SAM); [REopt.jl README](https://github.com/NatLabRockies/REopt.jl)

---

## Q1. Which open-source PV simulation libraries and tools exist? (catalogue)

### Takeaway
The mature, actively maintained core is small: **pvlib-python** (1.7k stars, v0.16.1, Sept 2026) and **NREL/NLR SAM + PySAM + SSC** (490 / 152 / 95 stars, SAM 2026.7.3). Around them sit specialised libraries: bifacial, mismatch, degradation, data QC, battery ageing, load profiles and synthetic weather. Small-system calculators on GitHub (string/battery/off-grid sizing, mostly single-file web apps or Python scripts) are numerous but very small: 0–50 stars, often 2025–2026 "vibe-coded" projects. I found **no open-source GitHub calculator aimed at Ukraine or Russia**. The Ukrainian open-source ecosystem has outage-schedule integrations (Yasno) but no PV sizing tool.

### Cited Findings

**A. Core simulation libraries / engines**
- **pvlib-python** (Python, BSD-3). 1.7k stars, updated 2026-10-08. Latest PyPI release 0.16.1 (2026-09-26). It provides documented functions for simulating PV system performance: solar position, clear sky, transposition, DC and AC models. — [GitHub topic solar-energy](https://github.com/topics/solar-energy?o=desc&s=stars); [PyPI pvlib](https://pypi.org/project/pvlib/); [Wikipedia](https://en.wikipedia.org/wiki/Pvlib_python)
  - Model inventory, read from the current source (`main` branch):
    - **Transposition:** isotropic, Klucher, Hay-Davies, Reindl, King, Perez, Perez-Driesse.
    - **Decomposition:** DISC, DIRINT, DIRINDEX, GTI-DIRINT, Erbs, Erbs-Driesse, Orgill-Hollands, Boland, Campbell-Norman, Louche.
    - **Clear sky:** Ineichen (with Linke turbidity lookup), Haurwitz, Simplified Solis, Bird, plus `detect_clearsky`.
    - **IAM:** ASHRAE, physical, Martin-Ruiz (+diffuse), SAPM, Schlick (+diffuse), Marion diffuse integration, interp, convert/fit.
    - **Cell temperature:** SAPM, PVsyst, Faiman, Faiman-rad, Ross, Fuentes, NOCT-SAM, Prilliman (thermal inertia), generic linear.
    - **Module electrical:** De Soto / CEC / PVsyst single-diode parameter functions, `singlediode`, Bishop88, Batzelis, `estimate_voc`, Huld (the PVGIS efficiency model), ADR efficiency model, PVWatts DC.
    - **Wiring and losses:** `dc_ohms_from_percent`, `dc_ohmic_losses`, `pvwatts_losses`, `combine_loss_factors`.
    - **Inverter:** Sandia, Sandia-multi, ADR, PVWatts, PVWatts-multi, `fit_sandia`. **Transformer:** simple efficiency.
    - **Shading:** masking angle, Passias sky-diffuse, projected zenith, `shaded_fraction1d`, `direct_martinez` (shading to power loss).
    - **Snow:** NREL full-cover, coverage and DC loss; Townsend loss. **Soiling:** HSU, Kimber.
    - **Spectral mismatch:** First Solar, SAPM, Caballero, PVSPEC, JRC, Polo; also SPECTRL2.
    - **Bifacial:** infinite sheds, pvfactors, ants2d, Deline mismatch.
    - **Data access (iotools):** PVGIS TMY/hourly/**horizon**, NASA POWER, ERA5, MERRA-2, CAMS, BSRN, NSRDB PSM4, Meteonorm TMY/forecast, Solcast, SolarAnywhere, Solargis, EPW/TMY3 readers, and `read_panond` (PVsyst .PAN/.OND files).
    - **CEC / Sandia module and inverter databases:** via `retrieve_sam`.
    - — Sources: [irradiance.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/irradiance.py), [iam.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/iam.py), [temperature.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/temperature.py), [pvsystem.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/pvsystem.py), [inverter.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/inverter.py), [shading.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/shading.py), [snow.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/snow.py), [soiling.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/soiling.py), [clearsky.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/clearsky.py), [singlediode.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/singlediode.py), [pvarray.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/pvarray.py), [spectrum/](https://github.com/pvlib/pvlib-python/tree/main/pvlib/spectrum), [bifacial/](https://github.com/pvlib/pvlib-python/tree/main/pvlib/bifacial), [iotools/](https://github.com/pvlib/pvlib-python/tree/main/pvlib/iotools)
  - pvlib has **no battery, MPPT-controller or off-grid dispatch model**. Those have to be built on top of it, as MiGUEL, SolarPV-Simulator and EMHASS do. — [pdb-94/miguel](https://github.com/pdb-94/miguel); [itprorh66/SolarPV-Simulator](https://github.com/itprorh66/SolarPV-Simulator)
- **SAM — System Advisor Model** (C++/wxWidgets desktop app for Windows, Mac and Linux).
  - 490 stars, updated 2026-10-07. Current citation version: SAM 2026.7.3.
  - The README now states the open-source code is **BSD-3-Clause**. The openpvtools catalogue still lists the older MIT/GPL-3 dual licence, so the two sources conflict.
  - Components: SSC (compute modules, 95 stars), LK scripting, and the Sandia LHS/stepwise libraries for uncertainty and parametrics.
  - — [SAM README](https://github.com/NatLabRockies/SAM); [NatLabRockies repos](https://github.com/orgs/NatLabRockies/repositories?q=SAM+OR+pysam+OR+rdtools+OR+REopt&sort=stargazers); [openpvtools](https://openpvtools.readthedocs.io/en/latest/tools.html)
  - **Detailed PV model.** Module options are simple efficiency, single-diode (CEC database or datasheet), extended single-diode (IEC 61853) and the Sandia array model. Inverter options are the Sandia/CEC model or a datasheet part-load efficiency curve. The CEC module and inverter library is rebuilt for each release. — [SAM forum](https://sam.nrel.gov/forum/forum-general/2768-pv-modules-and-inverters-not-in-database)
  - **3D Shade Calculator.** It turns a drawing of the array and nearby objects into time-series beam shading factors and sky-diffuse view-factor loss, and it can import map underlays. It was originally designed for small rooftop arrays. Row-to-row self-shading uses GCR separately. — [SAM forum](https://sam.nrel.gov/forum/forum-general/1382-3d-shade-calculator-for-large-arrays.html); [SAM forum self-shading](https://sam.nrel.gov/forum/forum-general/1865-parametric-analysis-dual-tilt-and-self-shading.html)
  - **Snow loss.** Based on Marion et al. (2013), it removes the DC output of strings covered by snow and is designed for tilts of 10–45°. — [NREL research-hub](https://research-hub.nrel.gov/en/publications/integration-validation-and-application-of-a-pv-snow-coverage-mode/); [SAM forum](https://sam.nrel.gov/forum/forum-general/1460-bill-marions-algorithm-for-snow-losses.html)
  - **Battery.** Chemistries are lead-acid, Li-ion, vanadium flow and all-iron flow. Internal models cover voltage, temperature and degradation. All Li-ion chemistries share the same capacity, voltage and lifetime models, and lifetime models exist for NMC/graphite (Smith 2017) and LMO/LTO. Dispatch options include peak shaving, and self-consumption dispatch for behind-the-meter systems was added in a late-2023 release. A Nov 2025 forum thread reports a bug in calendar-only degradation replacement timing (issue #2134). — [SAM battery page](https://sam.nrel.gov/node/69635); [NREL 2025 workshop PDF](https://docs.nrel.gov/docs/fy25osti/93555.pdf); [SAM forum](https://sam.nrel.gov/forum/forum-general/5101-battery-degradation-and-lifetime.html?start=6)
- **PySAM** (Python wrapper of SSC). 152 stars, updated 2026-09-27. PyPI nrel-pysam 7.1.1.post1 (2026-04-28). Configurations include detailed PV + battery, PVWatts + battery behind the meter, custom generation + battery, and standalone battery. PySAM does not expose every feature of the SAM GUI. — [PyPI](https://pypi.org/project/nrel-pysam/); [NatLabRockies repos](https://github.com/orgs/NatLabRockies/repositories?q=SAM+OR+pysam+OR+rdtools+OR+REopt&sort=stargazers); [SAM webinar](https://SAM.NREL.GOV/images/webinar_files/sam-webinars-2020-pysam.pdf)
- **CASSYS** (Canadian Solar). Excel (XLSM) UI with a C# engine, Windows, v1.5.3. It simulates **grid-connected** PV only. Activity is not visible. — [CanadianSolar/CASSYS](https://github.com/CanadianSolar/CASSYS)
- **GSEE** (Global Solar Energy Estimator, Renewables.ninja). Python, BSD-3, 149 stars, updated 2026-09-01, PyPI 0.4.0 (2026-08-26). It runs fast simulations from a single site up to global grids, and climate-data PDFs are optional. — [renewables-ninja/gsee](https://github.com/renewables-ninja/gsee); [topic photovoltaic](https://github.com/topics/photovoltaic?o=desc&s=stars); [PyPI](https://pypi.org/project/gsee/)
- **feedinlib** (oemof). Creates PV and wind feed-in time series. The latest stable PyPI release is 0.0.12 (2017), so it appears low-activity. — [PyPI](https://pypi.org/project/feedinlib/)
- **PVGIS** (JRC, EU). The web tool and API are free, but PVGIS 5.x is not open source.
  - **PVGIS 6** is a rewrite in Python (FastAPI, CLI), licensed EUPL-1.2, and adds multi-section systems and bifacial modules. It was still in **beta** as of 2026; production is 5.3. — [JRC PVGIS 6](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-6_en); [JRC v6 vs v5 comparison](https://draft-2-3c2e4a.pages.code.europa.eu/reference/comparison_pvgis_v6_vs_v52)
  - A related Python project, **pvgis-prototype**, sits in a personal GitLab namespace (EUPL-1.2), so it is not confirmed as the official JRC code. — [gitlab pvgis-prototype](https://gitlab.com/NikosAlexandris/pvgis-prototype)
  - PVGIS 5.3 (Nov 2024) added battery-energy-flow simulation for off-grid systems and improved modelling of snow-covered panels. — [ess-news](https://www.ess-news.com/2024/11/18/eu-upgrades-open-access-tool-to-assess-residential-solar-plus-storage-yield/)

**B. Specialised PV-physics and data libraries**
- **pvfactors → solarfactors.** 2D view-factor bifacial irradiance model. The original SunPower/pvfactors is unmaintained (last PyPI release 1.5.2 in 2022, **abandoned**). The pvlib fork **solarfactors** (17 stars, 1.6.1, Jan 2026) keeps it working. — [pvlib/solarfactors](https://github.com/pvlib/solarfactors); [PyPI pvfactors](https://pypi.org/project/pvfactors/); [PyPI solarfactors](https://pypi.org/project/solarfactors/)
- **bifacial_radiance** (NLR). RADIANCE ray-tracing for bifacial modules. 109 stars, 0.5.4 (2026-09-25). — [topic photovoltaics](https://github.com/topics/photovoltaics?o=desc&s=stars); [PyPI](https://pypi.org/project/bifacial-radiance/)
- **PVMismatch** (SunPower). Explicit I-V/P-V curves along cell → cell string → module (with **bypass diodes**) → string → system, for mismatch and partial shading. 87 stars. Last update April 2022 and PyPI 4.1 (2019), so it is **dormant**. — [SunPower/PVMismatch](https://github.com/SunPower/PVMismatch); [topic photovoltaic](https://github.com/topics/photovoltaic?o=desc&s=stars)
- **RdTools** (NLR). Degradation-rate and **soiling-loss** analysis of measured PV time series. 189 stars, 3.2.1 (2026-07-08). — [NatLabRockies/rdtools](https://github.com/NatLabRockies/rdtools); [PyPI](https://pypi.org/project/rdtools/)
- **pvanalytics** (pvlib). Quality control, filtering and feature labelling of measured PV data. 143 stars, PyPI 0.2.2 (2024-11). — [topic solar-energy](https://github.com/topics/solar-energy?o=desc&s=stars); [PyPI](https://pypi.org/project/pvanalytics/)
- **pvdeg** (NLR). Degradation-related parameters for PV modules. PyPI 0.7.4 (2026-10-03). — [PyPI](https://pypi.org/project/pvdeg/)
- **solar-data-tools** 2.1.5 (2026-06) for PV signal processing, and **solarspatialtools** 0.5.6 (2026-09), which includes synthetic cloud fields. — [PyPI solar-data-tools](https://pypi.org/project/solar-data-tools/); [PyPI solarspatialtools](https://pypi.org/project/solarspatialtools/); [solarspatialtools synthetic clouds](https://solarspatialtools.readthedocs.io/en/latest/demos/synthetic_clouds_demo.html)
- **PV_Performance_Loss_Tool_Snow_Soiling.** Townsend snow-loss (via pvlib) and soiling from monthly climate inputs. 56 stars, Jul 2026. — [topic pvlib](https://github.com/topics/pvlib?o=desc&s=stars)
- **twoaxistracking** 0.2.5 (2024) and **pvpumpingsystem** 0.9 (2020, off-grid PV pumping, **abandoned**). — [PyPI twoaxistracking](https://pypi.org/project/twoaxistracking/); [PyPI pvpumpingsystem](https://pypi.org/project/pvpumpingsystem/)

**C. Battery modelling libraries**
- **BLAST-Lite** (NLR). Library of lifetime and degradation models for commercial Li-ion cells, with a stationary-storage use case and the trade-off of oversizing against degradation. It notes that pack life is typically 20–30% shorter than cell life. PyPI 1.1.1 (2026-06-24). — [NatLabRockies/BLAST-Lite](https://github.com/NatLabRockies/BLAST-Lite); [PyPI](https://pypi.org/project/blast-lite/)
- **SimSES** (TUM). Stationary storage simulation with calendar and cycle ageing by half-cycle counting. Published models include "LFP Naumann" and "NMC Schmalstieg", and use cases include home self-consumption. PyPI 2.1.1 (2026-05-17). — [PyPI simses](https://pypi.org/project/simses/); [openmod wiki](https://wiki.openmod-initiative.org/wiki/SimSES)
- **bslib** (HTW Berlin / FZJ). AC- and DC-coupled PV-battery storage simulation with parameters from the HTW PerMod database and "Stromspeicher-Inspektion" measured-device data. MIT licence, data CC BY 4.0. v0.7 (Jan 2023), so **dormant**. — [FZJ-IEK3-VSA/bslib](https://github.com/FZJ-IEK3-VSA/bslib); [PyPI](https://pypi.org/project/bslib/)
- **PyBaMM.** Electrochemical cell modelling. PyPI 26.9.0.0 (2026-09-28). — [PyPI](https://pypi.org/project/pybamm/)

**D. Small-system calculators and simulators on GitHub** (the closest analogues to solar_calc)
- **WillemVanM/SolarBatterySimulator** (Python). Off-grid/hybrid sizing; detailed in Q2. — [repo](https://github.com/WillemVanM/SolarBatterySimulator)
- **sohaibiqbaal/Microgrid-Calculator** (Python, scipy LP). Off-grid panel, battery and inverter sizing; detailed in Q2. — [repo](https://github.com/sohaibiqbaal/Microgrid-Calculator)
- **projecthelloworld-org/solarplanner** ("Hello Solar Planner", browser app, MIT, v1.4.0). Detailed in Q2 and Q5. — [repo](https://github.com/projecthelloworld-org/solarplanner)
- **Migelo/solar-battery-simulator** (Python 3.12, uv). 15-min PV + battery + grid simulation with batch scenarios and economics. — [repo](https://github.com/Migelo/solar-battery-simulator)
- **briancpotter/solarsim** (Python). Hourly multi-day PV + battery simulation with synthetic clouds, panel degradation and LCOE. — [repo](https://github.com/briancpotter/solarsim)
- **energy-modelling-toolkit/prosumpy** (Python, EUPL; JRC origin). Self-consumption dispatch strategies with unit-tested energy balance. The README badges show Python 2.7/3.6, so the project is old. — [repo](https://github.com/energy-modelling-toolkit/prosumpy)
- **squoilin/Self-Consumption** (Python 2.7, JRC). Self-consumption toolbox with a synthetic household profile database. **Abandoned** (Python 2.7). — [repo](https://github.com/squoilin/Self-Consumption)
- **PV-Soft/Battery-Simulation** (Jupyter). "Virtual battery" simulation driven by smart-meter import/export logs. — [repo](https://github.com/PV-Soft/Battery-Simulation)
- **sunbeam60/Solar-Panel-and-Battery-Calculator** (single HTML file). Orientation, output, battery and cost, using NASA sky clarity data. — [repo](https://github.com/sunbeam60/Solar-Panel-and-Battery-Calculator)
- **Thomas-HTW-Berlin/PV_Calculator** (**C# Windows desktop**, GPL-3, by Prof. Thomas Hücker, HTW Berlin, 2025). PV + battery with many load profiles, from heat pump to industry, and optimisation of peak power and battery size for minimum LCOE. A newer branch uses NASA POWER data. 0 stars, updated 2025-11-06. — [repo](https://github.com/Thomas-HTW-Berlin/PV_Calculator); [topic solar-calculator](https://github.com/topics/solar-calculator)
- **itprorh66/SolarPV-Simulator** (Python, pvlib + NASA POWER, off-grid sizing). Mostly a requirements specification; 33 stars, last update 2021-05-27, so **abandoned**. — [repo](https://github.com/itprorh66/SolarPV-Simulator); [topic pvlib](https://github.com/topics/pvlib?o=desc&s=stars)
- **grollie/solar-calculator** (single HTML file, vanilla JS + Chart.js). Multi-string, multi-inverter residential sizing with NEC checks and finance. — [repo](https://github.com/grollie/solar-calculator)
- **pblakez/solar-string-calc** (single HTML file, Apache-2.0). Series/parallel string designs for a charge controller. — [repo](https://github.com/pblakez/solar-string-calc)
- **patrickpasquini/pypv** (Python, pip). Automatic string layouts per MPPT. — [repo](https://github.com/patrickpasquini/pypv)
- **toddkarin/vocmax** (Python, pip; web tool). NEC 690.7 maximum string length from weather data. PyPI 1.0.4 (2025-02). — [repo](https://github.com/toddkarin/vocmax); [PyPI](https://pypi.org/project/vocmax/)
- **KeshviEnterprise/SolarProject** ("Solar Plant Designer", React + TypeScript + Three.js). Preliminary rooftop and ground design with 3D shading, energy yield and string sizing. — [repo](https://github.com/KeshviEnterprise/SolarProject)
- **Wooinxlkz/solair-core** (TypeScript engine). Sizing, controller and battery recommendation, ROI, LCOE and cold-Voc functions. Non-OSI "NullTrace-SAL-1.0" licence. — [repo](https://github.com/Wooinxlkz/solair-core)
- **mbax0009/GreenInvest-Pakistan** (web plus Windows download, v4.5.0). Consumer decision tool with Monte Carlo risk and installer quote checking. 2 stars, updated 2026-09-02. — [repo](https://github.com/mbax0009/GreenInvest-Pakistan); [topic solar-calculator](https://github.com/topics/solar-calculator)
- **imtona44/solarcalc** (Flask). PV, battery, inverter and charge-controller sizing plus a bill of materials. 0 stars, Jul 2026. — [repo](https://github.com/imtona44/solarcalc)
- Other tiny calculators found but not analysed in depth:
  - salahudinsatti36-art/solar-calculator (web)
  - sohelmd0188/SS-SunPower-Calculator-Solario (Streamlit: appliances with surge, LiFePO4/lead-acid, satellite roof placement, Bengali UI)
  - JoseSholly/Inverter_power_project (Django REST API: inverter, battery and panel count from appliance list and backup hours)
  - jpanasuk-netizen/solarsizer
  - ossmydev/uk-solar-calculators
  - playbadrprogram/Solar-Calculator- (Arabic)
  - spyridouladev/PVCalc (forecast-based)
  - — [sohelmd0188 repo](https://github.com/sohelmd0188/SS-SunPower-Calculator-Solario); [search listing](https://github.com/JoseSholly/Inverter_power_project); [topic solar-calculator](https://github.com/topics/solar-calculator)

**E. Microgrid / energy-system optimisers that cover off-grid PV + battery + generator**
- **Offgridders** (RLI, oemof).
- **MicroGridsPy** (PoliMi SESAM, Pyomo, with GUI).
- **REopt.jl / REopt API** (NLR, Julia, JuMP). 47 / 127 stars, both updated Oct 2026.
- **MiGUEL** (Python, pvlib-based, GUI and PDF report). 8 stars, Aug 2026.
- **multi-vector-simulator** (RLI). PyPI 1.1.1, 2024-05.
- **oemof-solph** 0.6.5 (2026-09) and **PyPSA** (2.2k stars, 1.3.0 2026-08). Generic frameworks.
- **pymgrid** (219 stars, last update 2023, dormant).
- **QuESt** (Sandia, 159 stars, v3.0 May 2026). Includes a behind-the-meter storage app and a microgrid app.
- — [rl-institut/offgridders](https://github.com/rl-institut/offgridders); [MicroGridsPy-SESAM](https://github.com/SESAM-Polimi/MicroGridsPy-SESAM); [REopt.jl](https://github.com/NatLabRockies/REopt.jl); [pdb-94/miguel](https://github.com/pdb-94/miguel); [PyPI MVS](https://pypi.org/project/multi-vector-simulator/); [PyPI oemof-solph](https://pypi.org/project/oemof-solph/); [topic renewable-energy](https://github.com/topics/renewable-energy?o=desc&s=stars); [topic microgrid](https://github.com/topics/microgrid?o=desc&s=stars); [sandialabs/snl-quest](https://github.com/sandialabs/snl-quest)

**F. Home-energy-management tools with battery SoC simulation** (forecast and dispatch rather than sizing)
- **EMHASS.** Home Assistant, Python, MIT, LP optimisation with CVXPY; PV forecast through pvlib or Open-Meteo, ML load forecast, thermal loads. PyPI 0.18.4 (2026-09-27). — [docs](https://emhass.readthedocs.io/en/latest/); [PyPI](https://pypi.org/project/emhass/)
- **Akkudoktor EOS.** Python. Genetic-algorithm optimisation of PV, battery, EV, heat pump and dynamic prices, with REST API, Docker and Home Assistant / Node-RED integrations. About 1,414 stars in a months-old third-party snapshot. — [Akkudoktor-EOS/EOS](https://github.com/Akkudoktor-EOS/EOS); [EOS docs](https://akkudoktor-eos.readthedocs.io/en/latest/akkudoktoreos/introduction.html); [ost.ecosyste.ms](https://ost.ecosyste.ms/projects/301397)
- **Predbat / batpred.** Home battery prediction and automatic charging for Home Assistant across many inverter brands. The licence says "may be used at no cost for personal use only" (**not OSI open source**). — [springfall2008/batpred](https://github.com/springfall2008/batpred)
- **battery_sim.** Home Assistant "virtual battery" built on real import/export meters, with efficiencies, rate limits, cycle counting, a degradation factor and money saved. 228 stars, updated 2026-10-07. — [hif2k1/battery_sim](https://github.com/hif2k1/battery_sim); [topic energy-storage](https://github.com/topics/energy-storage?o=desc&s=stars)
- **OpenEMS.** Java EMS, 1.6k stars. — [topic energy-management](https://github.com/topics/energy-management?o=desc&s=stars)

**G. Forecast and monitoring apps with PV models**
- **solXpect** (Android, GPL-3, F-Droid). 126 stars, last update 2025-12. — [woheller69/solxpect](https://github.com/woheller69/solxpect)
- **ha-pvstrings.** Per-string pvlib physics plus a learned correction. — [doccodyblue/ha-pvstrings](https://github.com/doccodyblue/ha-pvstrings)
- **Helios-Forecast.** Self-learning PV forecast; 251 stars. — [ReikanYsora/Helios-Forecast](https://github.com/ReikanYsora/Helios-Forecast); [topic photovoltaic](https://github.com/topics/photovoltaic?o=desc&s=stars)
- **ha-open-meteo-solar-forecast.** 164 stars. — [topic solar-energy](https://github.com/topics/solar-energy?o=desc&s=stars)
- **SOLECTRUS.** Self-hosted dashboard; 166 stars. — [topic photovoltaics](https://github.com/topics/photovoltaics?o=desc&s=stars)

**H. Load-profile and weather generators** (inputs for simulators)
- **RAMP.** Stochastic bottom-up appliance load profiles. rampdemand 0.5.2 (2024-06). — [PyPI](https://pypi.org/project/rampdemand/); [RAMP algorithm](https://rampdemand.readthedocs.io/en/latest/algorithm.html)
- **demandlib** (oemof). BDEW standard load profiles (H0 household, G0–G6, L0–L2) at 15-minute resolution, scaled to annual kWh. 0.2.2 (2025-04). — [BDEW docs](https://demandlib.readthedocs.io/en/latest/bdew.html); [PyPI](https://pypi.org/project/demandlib/)
- **LoadProfileGenerator.** C#, agent-based, 1-minute resolution, 60 predefined German households. — [JOSS paper](https://joss.theoj.org/papers/10.21105/joss.03574)
- **alpg.** Artificial load profile generator; 68 stars. — [topic energy-management](https://github.com/topics/energy-management?o=desc&s=stars)
- **meteosynth.** Markov-chain synthetic weather with PVGIS data integration, aimed at Monte Carlo of energy-project output. 0.3.2 (2026-08-03). — [PyPI meteosynth](https://pypi.org/project/meteosynth/)

**I. Ukraine-specific open source** (adjacent; no PV calculators found)
- **ha-yasno-outages** (denysdovhan, MIT). Home Assistant integration exposing Yasno planned-outage plans as a calendar and as sensors for the next outage. 189 stars, last commit 2026-04-03. The same author also publishes integrations for the Ukrainian Hydrometeorological Center (weather and radiation) and air-raid alerts. — [repo](https://github.com/denysdovhan/ha-yasno-outages); [goodfirstissue listing](https://www.goodfirstissue.org/denysdovhan?page=2)
- Searches in Ukrainian and Russian ("сонячна електростанція калькулятор github", "солнечная электростанция калькулятор github") returned only commercial web calculators (atmosfera.ua, generacia.energy, kavelsib.ru, etc.), no open-source repositories. — [atmosfera.ua calculator](https://www.atmosfera.ua/for-home/kalkulyator-sonyachnyh-stantsiy-dlya-domu); [kavelsib.ru](https://www.kavelsib.ru/kalkulyator/)

**J. Meta-lists**
- **openpvtools.** Catalogue of open-source PV modelling tools. — [openpvtools](https://openpvtools.readthedocs.io/en/latest/tools.html)
- **Open Sustainable Technology.** 2.6k stars. — [protontypes/open-sustainable-technology](https://github.com/topics/photovoltaic?o=desc&s=stars); [opensustain.tech](https://opensustain.tech/)
- **pv-foss-engagement.** Kevin Anderson's star and usage statistics for FOSS PV packages. — [kanderso-nrel](https://kanderso-nrel.github.io/pv-foss-engagement/)

### Inferences
- For a desktop PySide6 app, **pvlib** is the natural library to borrow from: same language, BSD licence, and it already has PVGIS TMY/hourly/horizon readers and the Huld (PVGIS) module model. SAM/PySAM is the only open-source engine with an integrated battery lifetime, thermal and voltage model, but it is heavy and US-oriented.
- Small "solar calculator" repos are numerous but immature: almost all have 0–5 stars, appeared in 2025–2026 and are partly AI-generated (pblakez explicitly says "Built with Claude Code"). solar_calc v1.2.1 is already more physically detailed than most of them in DC wiring, MPPT and battery-preset handling.
- I found no Ukrainian or Russian open-source competitor, which leaves a niche for solar_calc: Kyiv defaults, ПУЭ ampacity, UAH tariffs and Yasno/DTEK outage awareness.

### Gaps
- Star counts for several projects were not visible: WillemVanM, Migelo, grollie, pblakez, solarplanner, Microgrid-Calculator, MicroGridsPy, Offgridders, EMHASS, Predbat, vocmax. shields.io and the GitHub API were not used or were blocked.
- openpvtools and the pv-foss-engagement statistics page could not be fetched (blocked), so the full tool table was not reproduced.
- I could not verify whether PVGIS 6 is generally released or still beta as of October 2026. The JRC pages were blocked; the latest evidence (Feb 2026) says beta.

---

## Q2. Which projects simulate off-grid/hybrid battery SoC, autonomy days, loss-of-load probability, generator backup and grid fallback?

### Takeaway
Reliability-oriented off-grid simulation exists at two levels:
- **Simple scripts** time-step SoC over real or synthetic weather and report reliability metrics:
  - WillemVanM: unserved kWh per year, blackout hours per year, blackout events per year, and a cost-vs-reliability Pareto front.
  - Microgrid-Calculator: hourly LP over N autonomy days with one bad day.
  - PVGIS off-grid tool: % of days the battery is full or empty, and average energy missing, over many years of hourly data.
- **Optimisers** add genset, weak grid with blackouts, and allowed annual shortage: Offgridders, MicroGridsPy, REopt, MiGUEL.

**REopt** is the only tool found that estimates **probability of surviving an outage** of a given duration by simulating outages that start at random times. **MiGUEL** and **Offgridders** accept **blackout time series** for unreliable grids. That maps directly onto Ukrainian outage schedules.

### Cited Findings
- **WillemVanM/SolarBatterySimulator** (Python: numpy, scipy, matplotlib).
  - **Purpose.** Sizes and validates "off-grid / hybrid solar-plus-battery systems from historical irradiance data". It answers "how often and how badly does the system fail" (unserved energy, blackout hours, number of blackouts per year) and "cheapest PV+battery meeting a reliability threshold".
  - **Inputs.**
    - Irradiance CSVs from Solcast, SoDa/HelioClim, PVGIS or Victron exports.
    - Consumption from a measured CSV, or built from an appliance library with stochastic duty cycles (fridge 100 W at 33% duty, etc.).
  - **Model.**
    - SoC at any time step (default 15 minutes), with charge and discharge efficiency and a DoD floor.
    - Energy below the floor counts as `energy_from_grid`, read as unserved load (off-grid) or grid import (hybrid).
    - Metrics are annualised.
  - **Optimisation.** Gaussian-process root finding for the cheapest system, plus a brute-force Pareto front with hover annotations.
  - **Validation.** Compares modelled production with Victron VRM exports.
  - **Stated simplifications:** no inverter or charge-controller limits, no C-rate limits, no temperature or ageing model, no load shedding, no self-discharge.
  - — [README](https://github.com/WillemVanM/SolarBatterySimulator)
- **sohaibiqbaal/Microgrid-Calculator** (Python).
  - **Method.** Linear programme minimising `c1·panel_W + c2·battery_Wh + c3·inverter_W`, subject to hourly SoC dynamics over N autonomy days. Default: day 1 clear, day 2 at 30% of normal output.
  - **Inverter constraints.** The inverter must cover the worst steady hour and about half the motor surge.
  - **Rationale.** "A system can look fine on a daily total and still have the battery die at 4am."
  - **Limitations.** Sine-bell solar curve, not real weather data.
  - — [README](https://github.com/sohaibiqbaal/Microgrid-Calculator)
- **Hello Solar Planner.** Plans daily energy, running power, **startup demand**, **critical-load energy**, battery usable energy and **estimated autonomy**. It compares a "Fully DC" option against a "Hybrid DC + AC" option, and its equipment checks are marked passed, failed or unverified. — [README](https://github.com/projecthelloworld-org/solarplanner)
- **PVGIS off-grid tool** (web, not open source; shown for method).
  - **Inputs:** peak power, battery Wh, cutoff %, consumption Wh per day.
  - **Outputs:** % days with full battery, % days with empty battery, average energy not captured, average energy missing, a monthly table (Ed, Ff, Fe), and a histogram of battery charge state.
  - **Example:** 300 W, 12 V 350 Ah, 50% cutoff and 1200 Wh/day gives an empty battery on 66% of 1801 simulated days.
  - — [akkudoktor sample report](https://akkudoktor.net/uploads/short-url/7A4LUUstP0cmCIztnOrIBz8wdmQ.pdf); [hobbielektronika sample](https://hobbielektronika.hu/forum/getfile.php?id=198807)
- **Offgridders** (RLI, oemof, linearised components).
  - **Components.** AC and DC demand, inverter/rectifier, central grid "optional: with blackouts", diesel generator, PV, wind, storage.
  - **Constraints.** A defined annual shortage can be allowed, or a renewable share or stability constraint forced. Constraints such as "Discharge of battery only when maingrid experiences blackout" and "Linearized forced charge when national grid available" are available.
  - **Use cases.** "Backup systems (diesel generator, SHS, ...) to ensure reliable supply of consumers connected to weak national grids".
  - **Status.** Input via an Excel template; last push 2024-07-18 (low activity).
  - — [README](https://github.com/rl-institut/offgridders); [ost.ecosyste.ms](https://ost.ecosyste.ms/projects/248)
  - **Published use.** Hoffmann et al. 2020, "Overcoming the Bottleneck of Unreliable Grids: Increasing Reliability of Household Supply with Decentralized Backup Systems". — [Offgridders literature](https://offgridders.readthedocs.io/en/latest/Literature.html)
- **MicroGridsPy 2.1** (Pyomo, GUI).
  - Least-cost sizing of PV, wind, **back-up genset** and battery, optimising NPC or operating cost, with LCOE.
  - Two-stage stochastic optimisation.
  - MILP unit commitment with **genset partial-load** operation.
  - **1-minute** time steps (coupled with RAMP loads).
  - Grid-connected microgrids, NASA POWER integration.
  - Solvers: Gurobi or GLPK.
  - — [README](https://github.com/SESAM-Polimi/MicroGridsPy-SESAM)
  - **Unmet demand.** The related method allows 1% unmet demand ("levelized cost of supplied and lost energy"). I found no explicit LOLP output. — [MicroGridsPy model page](https://paris-reinforce.epu.ntua.gr/detailed_model_doc/microgridspy)
- **REopt (REopt.jl / API).**
  - **Solver.** PV + storage is an LP; generator, net metering or multiple outages make it a MILP.
  - **Resilience mode.** Sizes PV, battery and generator to carry a **critical-load fraction** through outages.
  - **Outputs.** **Survival probability** versus outage duration, from many outages that start at random times, plus min/avg/max hours survived.
  - **Generator.** Existing or optimised, default diesel.
  - — [REopt.jl README](https://github.com/NatLabRockies/REopt.jl); [REopt Lite tutorial module 6](https://www.nrel.gov/reopt/curriculum/videos/reopt-lite-tutorial-module-6-text); [DOE article](https://www.energy.gov/indianenergy/articles/valuing-resilience-provided-solar-and-battery-energy-storage-systems)
- **MiGUEL** (Python, pvlib-based).
  - **Components.** PV, wind, battery, grid import/export, legacy diesel, hydrogen.
  - **Unreliable grid.** `blackout=True` with `blackout_data` = a **CSV of boolean grid availability per time step**.
  - **Economics and output.** LCOE, NPV, CO2; PDF report and modern GUI.
  - — [README](https://github.com/pdb-94/miguel)
- **briancpotter/solarsim.** Hourly multi-day simulation with grid, battery efficiency and SoC, **synthetic cloud patterns with monthly variation**, panel degradation by age, and an LCOE including component replacement. — [README](https://github.com/briancpotter/solarsim)
- **Migelo/solar-battery-simulator.** 15-minute grid-connected flows with inverter clipping, battery C-rate and round-trip losses, a heat-pump load add-on and Slovenian tariff blocks. Batch outputs include heatmaps of savings, ROI, self-sufficiency and NPV. — [README](https://github.com/Migelo/solar-battery-simulator)
- **Galuyoo/offgrid-streetlight-dimming-control.** Battery runtime forecasts and "blackout severity metrics" for off-grid street lights. 12 stars. — [topic off-grid-solar](https://github.com/topics/off-grid-solar?o=desc&s=stars)
- **WHO "solar autonomy calculation method"** (Excel, not GitHub). Energy balance with days of autonomy and LOLP; a larger array oversize factor improves LOLP. — [WHO](https://extranet.who.int/prequal/key-resources/documents/solar-autonomy-calculation-method)
- **Accuracy caveat.** A 2025 TU Wien diploma thesis comparing online PV-battery calculators with measured household data found that most online tools **overestimate** self-consumption and self-sufficiency. — [TU Wien repositum](https://repositum.tuwien.at/handle/20.500.12708/212024)

### Inferences
- solar_calc's "N consecutive days with chosen weather" is close to Microgrid-Calculator's "clear day + 30% day" approach. Neither captures the statistics of real winter overcast spells.
- The **PVGIS-style metrics** (% days full / % days empty / energy missing, per month) are cheap to add if solar_calc can load **PVGIS hourly series** (`seriescalc`, multi-year SARAH data). They would replace the three fixed weather types with real day sequences.
- For Ukraine, the most valuable reliability feature would be REopt-style **"probability that the house survives an outage of X hours starting at a random time"**, or survival under real queue schedules (Yasno groups), with optional generator fallback.

### Gaps
- I found no open-source tool that explicitly outputs classical **LLP/LOLP** as a named metric alongside autonomy days. WillemVanM's unserved-energy fraction and PVGIS's empty-day % are the closest.
- I found no open-source tool that models **CV-phase charge taper** of LiFePO4/lead-acid in an off-grid SoC loop. SAM has a voltage model, but I could not confirm it limits charge current in a CV phase.

---

## Q3. Which tools size PV strings against inverter/MPPT voltage windows with temperature, and which do cable sizing / voltage drop?

### Takeaway
Several open-source projects check **cold Voc against max input voltage** and **hot Vmp against the MPPT minimum**:
- vocmax: NEC 690.7, using weather data and the SAPM/CEC models.
- grollie: NEC 690/705, multi-MPPT, Isc limits, 1.25× OCPD.
- pypv: automatic layouts per MPPT.
- KeshviEnterprise, zonzelf (PR), solair-core, wrolpi (PR).
- pblakez: ranked PpSs table for charge controllers.

**No open-source project found** offers dedicated DC/AC cable sizing with ampacity tables and voltage drop. pvlib only has `dc_ohms_from_percent` / `dc_ohmic_losses`. In this area solar_calc (ПУЭ ampacity, Cu/Al, temperature-dependent resistance, MC4 contact losses) is **ahead** of everything found.

### Cited Findings
- **vocmax.**
  - Calculates the maximum string length "consistent with the NEC 2017 690.7 standard".
  - Uses module parameters from the **CEC database** (converted to SAPM) or a manual parameter dict.
  - Options: ASHRAE AOI loss, **bifacial** (proportional or pvfactors), racking type, and **site weather data** (NSRDB sample) to compute the realistic maximum Voc instead of a "coldest temperature at 1000 W/m²" assumption.
  - Available as a web tool and on pip.
  - — [toddkarin/vocmax](https://github.com/toddkarin/vocmax); [PyPI](https://pypi.org/project/vocmax/)
- **grollie/solar-calculator.**
  - Per-string configuration with mixed panel models; each string is assigned to a specific MPPT of a specific inverter; multi-inverter.
  - Drag-and-drop **schematic editor**.
  - Component library (specific SunGold panels and hybrid inverters).
  - NEC validation: string Voc vs inverter max DC, Vmp vs MPPT range, MPPT Isc limits, NEC 690.8 ×1.25 OCPD sizing.
  - Per-MPPT Imp/Isc display.
  - — [README](https://github.com/grollie/solar-calculator)
- **pypv.** The inputs are a module (Pmax, Vmp, Imp, Voc, Isc, temperature coefficients) and an inverter with a **list of MPPTs**, each with min/max voltage, Isc and DC inputs, plus start voltage, max PV power, and target power with min/max temperatures. It returns the number of inverters and a layout per MPPT (e.g. 2×6 and 2×5) plus the DC/AC ratio. — [README](https://github.com/patrickpasquini/pypv)
- **zonzelf** (Next.js, Dutch, PR #76, "inverter-first sizing chain").
  - Voc corrected to the site's coldest temperature (NEC 690.7), with the series count **floored**.
  - Separate check of Vmp at **hot cell temperature = ambient + 30 °C** against the bottom of the MPPT window.
  - — [PR #76](https://github.com/vraaijmakers/zonzelf/pull/76)
- **wrolpi PR #778.** Off-grid solar calculator that checks string Voc on the coldest morning. The default is 25 °C below the coldest monthly average. — [PR #778](https://github.com/lrnselfreliance/wrolpi/pull/778)
- **pblakez/solar-string-calc.**
  - Inputs: battery voltage, panel W and Voc, controller max input V and W, cold-Voc margin, allowed PV oversize.
  - Output: a **ranked table of PpSs configurations** with controller utilisation.
  - The README admits it **ignores Isc, temperature coefficients and wire length**.
  - — [README](https://github.com/pblakez/solar-string-calc)
- **KeshviEnterprise Solar Plant Designer.** Optional electrical module with string sizing (cold-temperature Voc and hot-temperature Vmp checks), DC/AC ratio, MPPT and current checks, and a suggested string configuration. — [README](https://github.com/KeshviEnterprise/SolarProject)
- **solair-core.** `calculateTemperatureAdjustedVoc` for cold-weather Voc safety; controller and battery recommendation with autonomy days and `ambientTempMin`. — [README](https://github.com/Wooinxlkz/solair-core)
- **Cable sizing / voltage drop.** A dedicated search for GitHub solar wire-size or voltage-drop calculators returned only commercial or closed web calculators: dcwirecalculator.com (NEC 2023 / IEC 60364 ampacity and drop), engcal.online (string drop 1–2% target), solar-wind.co.uk, and others. The closest code was a DEV.to article with a JS snippet, and its printed example appears arithmetically wrong. — [dcwirecalculator](https://dcwirecalculator.com/solar-cable-size-calculator.html); [engcal](https://engcal.online/solar-string-voltage-drop); [DEV.to article](https://dev.to/chameerasampathkorea/demystifying-solar-wire-sizing-voltage-drop-a-transparent-engineering-guide-for-pv-installers-42c4)
- **pvlib wiring loss.** Only the `dc_ohms_from_percent` and `dc_ohmic_losses` helpers. — [pvsystem.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/pvsystem.py)

### Inferences
- Ideas solar_calc could borrow:
  1. Vmp_hot defined as **ambient + 30 °C** (zonzelf) or a NOCT/Faiman cell temperature at summer maximum, rather than a fixed value.
  2. **Site-statistics-based record cold** (vocmax uses hourly weather data; wrolpi uses coldest monthly mean minus 25 °C), possibly from PVGIS hourly temperatures for the chosen location.
  3. **Multi-MPPT / multi-array assignment** (grollie, pypv): for example, one hybrid inverter with 2 MPPTs fed by east and west strings.
  4. A **1.25× (NEC 690.8) / IEC 62548 fuse and cable current factor** shown explicitly.
- Cable sizing is a differentiator for solar_calc; no open-source tool matches it.

### Gaps
- I did not find any open-source tool implementing **IEC 62548 / IEC 60364-7-712** cable sizing for PV, or Ukrainian ПУЭ tables. I could not verify how commercial tools treat temperature-dependent resistance.

---

## Q4. What physics and models do they use that solar_calc does not?

### Takeaway
Compared with solar_calc's Haurwitz + Erbs + isotropic + ASHRAE IAM + NOCT + linear I-V on an "average day" basis, the reference tools (pvlib, SAM, PVGIS) use:
- **hourly or sub-hourly multi-year or TMY data** instead of monthly averages;
- **Perez / Hay-Davies anisotropic transposition**;
- **Ineichen / Simplified-Solis clear sky** with turbidity;
- **single-diode models** (CEC/De Soto/PVsyst) or the **Huld** model;
- **Faiman / SAPM / PVsyst cell temperature with wind** and thermal inertia;
- **inverter part-load efficiency curves** (Sandia, ADR, CEC);
- **diffuse IAM**, **spectral mismatch**, **snow loss** (Marion/NREL, Townsend), **soiling** (Kimber, HSU);
- **azimuth-dependent horizon profiles** and 3D/row shading;
- **bypass-diode partial-shading I-V** (PVMismatch);
- **bifacial** models;
- **battery ageing** (calendar and cycle) and thermal/voltage models (SAM, BLAST-Lite, SimSES);
- **stochastic weather** (Markov, synthetic clouds) and **Monte Carlo** uncertainty.

### Cited Findings
- **Transposition, decomposition, clear sky.**
  - pvlib transposition: Perez, Perez-Driesse, Hay-Davies, Reindl, Klucher, King.
  - pvlib decomposition: DISC, DIRINT, Erbs-Driesse, Boland, Orgill-Hollands, Louche.
  - pvlib clear sky: Ineichen with Linke turbidity, Simplified Solis, Bird.
  - — [irradiance.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/irradiance.py); [clearsky.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/clearsky.py)
- **IAM.** Physical (Fresnel), Martin-Ruiz, Schlick and SAPM, plus **diffuse IAM** (Marion integration, Martin-Ruiz diffuse, Schlick diffuse). — [iam.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/iam.py)
- **Cell temperature.** Faiman (wind-dependent), SAPM, PVsyst, Fuentes, NOCT-SAM, Ross, **Prilliman** (transient, thermal mass). — [temperature.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/temperature.py)
- **Module I-V.** Single-diode models (`calcparams_desoto/cec/pvsyst` + `singlediode`, Bishop88 for reverse bias) and the CEC/Sandia databases via `retrieve_sam`. PVGIS's **Huld** model is available as `pvarray.huld`. — [pvsystem.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/pvsystem.py); [singlediode.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/singlediode.py); [pvarray.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/pvarray.py)
- **Inverter efficiency curves.** pvlib Sandia / ADR / PVWatts models; SAM "Datasheet part-load efficiency curve". — [inverter.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/inverter.py); [SAM forum](https://sam.nrel.gov/forum/forum-general/2768-pv-modules-and-inverters-not-in-database)
- **Snow.**
  - pvlib: NREL (Marion) coverage and DC loss, and Townsend monthly snow loss.
  - SAM: removes the output of covered strings (10–45° tilt).
  - PVGIS 5.3: improved snow-covered panel modelling.
  - — [snow.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/snow.py); [NREL research-hub](https://research-hub.nrel.gov/en/publications/integration-validation-and-application-of-a-pv-snow-coverage-mode/); [ess-news](https://www.ess-news.com/2024/11/18/eu-upgrades-open-access-tool-to-assess-residential-solar-plus-storage-yield/)
- **Soiling.** pvlib HSU (rain and PM-driven) and Kimber; RdTools estimates soiling loss from measured data. — [soiling.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/soiling.py); [rdtools](https://github.com/NatLabRockies/rdtools)
- **Spectral.** Spectral factors from First Solar, SAPM, Caballero, PVSPEC, JRC, Polo; SPECTRL2. — [spectrum/](https://github.com/pvlib/pvlib-python/tree/main/pvlib/spectrum)
- **Horizon and shading.**
  - pvlib: `get_pvgis_horizon` (PVGIS DEM-based horizon profile by azimuth), masking angle, `shaded_fraction1d`, `direct_martinez` (shaded fraction to power loss with bypass diodes).
  - SAM: 3D Shade Calculator and GCR self-shading.
  - **solXpect:** for **each azimuth range** the user sets the minimum sun elevation and the **% shading** below it (e.g. building 100%, tree 60%).
  - **KeshviEnterprise:** 3D scene with live shadows, a seasonal shading table and inter-row shading.
  - — [iotools/pvgis.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/iotools/pvgis.py); [shading.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/shading.py); [SAM forum](https://sam.nrel.gov/forum/forum-general/1382-3d-shade-calculator-for-large-arrays.html); [solXpect README](https://github.com/woheller69/solxpect); [KeshviEnterprise](https://github.com/KeshviEnterprise/SolarProject)
- **Partial shading / mismatch.** PVMismatch models cell → module with bypass diodes → string → system I-V. — [PVMismatch](https://github.com/SunPower/PVMismatch)
- **Bifacial.** pvlib `infinite_sheds` / pvfactors / solarfactors / bifacial_radiance; vocmax also includes bifacial gain in the max-Voc calculation. — [bifacial/](https://github.com/pvlib/pvlib-python/tree/main/pvlib/bifacial); [solarfactors](https://github.com/pvlib/solarfactors); [vocmax](https://github.com/toddkarin/vocmax)
- **Battery ageing and physics.**
  - SAM: Li-ion capacity, voltage and lifetime models (NMC Smith 2017; LMO/LTO), a thermal model, and replacement scheduling. — [NREL 2025 workshop](https://docs.nrel.gov/docs/fy25osti/93555.pdf); [SAM battery](https://sam.nrel.gov/node/69635)
  - BLAST-Lite: cell degradation models; oversizing reduces degradation. — [BLAST-Lite](https://github.com/NatLabRockies/BLAST-Lite)
  - SimSES: half-cycle counting with calendar and cycle ageing (LFP Naumann). — [PyPI simses](https://pypi.org/project/simses/); [openmod wiki](https://wiki.openmod-initiative.org/wiki/SimSES)
  - battery_sim (Home Assistant): cycle counter and degradation factor that shrinks usable capacity. — [battery_sim](https://github.com/hif2k1/battery_sim)
  - bslib: measured AC/DC-coupled system efficiency parameters (Stromspeicher-Inspektion). — [bslib](https://github.com/FZJ-IEK3-VSA/bslib)
- **Module degradation.**
  - solarsim: panel degradation by system age, feeding into LCOE. — [solarsim](https://github.com/briancpotter/solarsim)
  - sunbeam60: "Output fade" of 0.5%/yr, NREL's field median. — [sunbeam60](https://github.com/sunbeam60/Solar-Panel-and-Battery-Calculator)
- **Time base and weather.**
  - Hourly 8760 or multi-year data: PVGIS hourly/TMY via pvlib; NASA POWER in MicroGridsPy and MiGUEL. — [iotools](https://github.com/pvlib/pvlib-python/tree/main/pvlib/iotools); [MicroGridsPy](https://github.com/SESAM-Polimi/MicroGridsPy-SESAM)
  - 1-minute optimisation in MicroGridsPy. — [MicroGridsPy](https://github.com/SESAM-Polimi/MicroGridsPy-SESAM)
  - Synthetic clouds with monthly variation (solarsim); Markov synthetic weather with PVGIS (meteosynth); two-stage stochastic scenarios (MicroGridsPy); Monte Carlo uncertainty (GreenInvest). — [solarsim](https://github.com/briancpotter/solarsim); [meteosynth](https://pypi.org/project/meteosynth/); [GreenInvest](https://github.com/mbax0009/GreenInvest-Pakistan)
  - SAM's bundled Sandia **LHS/stepwise** libraries support stochastic and uncertainty analysis. — [SAM README](https://github.com/NatLabRockies/SAM)
- **Stochastic loads.** RAMP: appliance-level windows and weekly frequency. WillemVanM: random duty cycles redrawn until the daily energy fits. BDEW H0 standard profile (demandlib). — [RAMP algorithm](https://rampdemand.readthedocs.io/en/latest/algorithm.html); [WillemVanM](https://github.com/WillemVanM/SolarBatterySimulator); [demandlib BDEW](https://demandlib.readthedocs.io/en/latest/bdew.html)

### Inferences
Highest-value physics upgrades for a Kyiv 1–30 kW system, in my judgement:
1. A **PVGIS hourly multi-year** (or TMY) mode. This captures real multi-day dark spells in Nov–Jan, which drive battery sizing.
2. **Snow loss.** Kyiv winters, at least the Townsend monthly model.
3. An **azimuth-dependent horizon** (PVGIS horizon API, plus user-drawn obstacles with transparency as in solXpect).
4. **Perez transposition** and a **diffuse IAM**. These matter for steep winter tilts and for east-west arrays.
5. **Inverter and MPPT part-load efficiency curves.**
6. **Battery calendar and cycle ageing**, giving year-N capacity.
7. A **single-diode (CEC) or Huld** module model in place of the linear I-V approximation. This improves low-light and Voc/Vmp-temperature accuracy.

### Gaps
- I could not open the full pvlib or SAM documentation pages (blocked), so the descriptions above come from function names in source and from forum/workshop summaries, not full technical references.
- I found no open-source tool modelling **LiFePO4 charging below 0 °C** or a cold-capacity derating table. solar_calc already does this, and I could not find whether SAM's thermal model blocks charging at low temperature.

---

## Q5. What UX and output features do they offer (economics, reports, maps, component databases, monitoring import)?

### Takeaway
The richest UX among small tools comes from browser apps: KeshviEnterprise (map, CAD, 3D, PDF, provenance labels), Hello Solar Planner (pass/fail/unverified checks, PDF/CSV report, local prices), sunbeam60 (share link, drawn tariffs, export limit) and GreenInvest (verdict, quote check, Monte Carlo). Economics with NPV, payback, LCOE and replacement costs is standard in SAM, REopt, MicroGridsPy, solarsim, grollie, Migelo and solair-core. Component databases (CEC modules and inverters, measured storage efficiency data) and **calibration against monitoring data** (Victron VRM, smart meters, per-string learned corrections) are common in the more serious tools.

### Cited Findings
- **Economics.**
  - grollie: BOM with itemised costs, 30% ITC, 25-year cash-flow chart, NPV. — [grollie](https://github.com/grollie/solar-calculator)
  - Migelo: ROI, NPV and payback with time-of-use prices, plus heatmaps. — [Migelo](https://github.com/Migelo/solar-battery-simulator)
  - solarsim: LCOE with discount rate, maintenance, component lifetimes and replacements. — [solarsim](https://github.com/briancpotter/solarsim)
  - MicroGridsPy: NPC/LCOE, variable fuel costs, CO2 objective. — [MicroGridsPy](https://github.com/SESAM-Polimi/MicroGridsPy-SESAM)
  - MiGUEL: LCOE, NPV, CO2. — [MiGUEL](https://github.com/pdb-94/miguel)
  - solair-core: ROI, payback, break-even year, LCOE, system size from monthly bill, CO2 offset. — [solair-core](https://github.com/Wooinxlkz/solair-core)
  - HTW PV_Calculator: optimises PV peak power and battery size for minimum LCOE. — [HTW](https://github.com/Thomas-HTW-Berlin/PV_Calculator)
- **Tariffs, grid charging and export.**
  - sunbeam60: hourly import and export tariffs (presets or drawn by hand), "Grid charging" below a price threshold, and an "Export limit" (default 3.68 kW, the UK G98 limit). — [sunbeam60](https://github.com/sunbeam60/Solar-Panel-and-Battery-Calculator)
  - Migelo: Slovenian 5-block transmission tariffs. — [Migelo](https://github.com/Migelo/solar-battery-simulator)
  - GreenInvest: national tariff schedule bands and TOU. — [GreenInvest](https://github.com/mbax0009/GreenInvest-Pakistan)
- **Reports and transparency.**
  - KeshviEnterprise:
    - PDF report covering project, location, layout, module and inverter data, irradiation, monthly table, losses, assumptions, warnings and disclaimer.
    - Every value is labelled **USER INPUT / CALCULATED / ESTIMATED / EXTERNAL DATA / ASSUMPTION / DEMO**.
    - **"How is this calculated?"** expanders next to each figure.
    - Loss waterfall, CSV/PNG chart export, JSON project import/export, undo/redo.
    - — [KeshviEnterprise](https://github.com/KeshviEnterprise/SolarProject)
  - Hello Solar Planner: report with assumptions, specification sources, costs and unresolved checks; PDF and CSV export; checks marked passed, failed or unverified. — [solarplanner](https://github.com/projecthelloworld-org/solarplanner)
  - MiGUEL: automatically generated PDF report. — [MiGUEL](https://github.com/pdb-94/miguel)
- **Maps and location.**
  - KeshviEnterprise: OpenStreetMap Nominatim search, click-to-pin, time zone and elevation lookup (Open-Meteo), and a choice of data provider (NASA POWER, PVGIS or PVWatts) with automatic fallback. — [KeshviEnterprise](https://github.com/KeshviEnterprise/SolarProject)
  - solXpect: Leaflet map and OpenStreetMap. — [solXpect](https://github.com/woheller69/solxpect)
  - Solario: satellite roof placement. — [Solario](https://github.com/sohelmd0188/SS-SunPower-Calculator-Solario)
- **Decision support.**
  - GreenInvest: "install / conditional / do-not-install" verdict, **installer quote checking**, sensitivity analysis, Monte Carlo uncertainty, outage-duration and protected-load checks. — [GreenInvest](https://github.com/mbax0009/GreenInvest-Pakistan)
  - WillemVanM: Pareto front of cost against reliability. — [WillemVanM](https://github.com/WillemVanM/SolarBatterySimulator)
- **Component databases.**
  - CEC module and inverter libraries in SAM and pvlib (`retrieve_sam`), and pvlib `read_panond` for PVsyst PAN/OND files. — [SAM forum](https://sam.nrel.gov/forum/forum-general/2768-pv-modules-and-inverters-not-in-database); [iotools/](https://github.com/pvlib/pvlib-python/tree/main/pvlib/iotools)
  - bslib: measured storage-system database. — [bslib](https://github.com/FZJ-IEK3-VSA/bslib)
  - grollie: specific hybrid inverters. — [grollie](https://github.com/grollie/solar-calculator)
  - Hello Solar Planner: selectable panel, battery and controller sizes with reference prices. — [solarplanner](https://github.com/projecthelloworld-org/solarplanner)
- **Monitoring import and calibration.**
  - WillemVanM: compares modelled specific yield with **Victron VRM** exports to check tilt, azimuth, time zone and derating. — [WillemVanM](https://github.com/WillemVanM/SolarBatterySimulator)
  - PV-Soft: virtual batteries from **smart-meter IR-reader** logs (openHAB/InfluxDB). — [PV-Soft](https://github.com/PV-Soft/Battery-Simulation)
  - battery_sim: virtual battery from Home Assistant import/export sensors. — [battery_sim](https://github.com/hif2k1/battery_sim)
  - ha-pvstrings: per-string pvlib model plus a learned correction. — [ha-pvstrings](https://github.com/doccodyblue/ha-pvstrings)
  - Helios-Forecast: self-correcting against measured production. — [Helios-Forecast](https://github.com/ReikanYsora/Helios-Forecast)
  - RdTools / pvanalytics: degradation, soiling and QC of measured data. — [rdtools](https://github.com/NatLabRockies/rdtools)
- **Forecast mode.** solXpect gives a 16-day hourly PV forecast from Open-Meteo, with an inverter cap, multiple orientations summed, albedo and a diffuse-efficiency parameter. — [solXpect](https://github.com/woheller69/solxpect)
- **Load entry.**
  - Appliance list with **motor surge** (Microgrid-Calculator, Solario, Hello Solar Planner "startup demand"). — [Microgrid-Calculator](https://github.com/sohaibiqbaal/Microgrid-Calculator); [Solario](https://github.com/sohelmd0188/SS-SunPower-Calculator-Solario); [solarplanner](https://github.com/projecthelloworld-org/solarplanner)
  - Hourly profile drawn with the mouse and scaled to annual kWh. — [sunbeam60](https://github.com/sunbeam60/Solar-Panel-and-Battery-Calculator)
  - Heat-pump add-on load. — [Migelo](https://github.com/Migelo/solar-battery-simulator)
- **Sharing and storage.** Share link (sunbeam60); projects in browser localStorage (Hello Solar Planner, KeshviEnterprise); copy configuration as Markdown (pblakez). — [sunbeam60](https://github.com/sunbeam60/Solar-Panel-and-Battery-Calculator); [pblakez](https://github.com/pblakez/solar-string-calc)
- **Ukraine outage data.** Yasno planned-outage calendar and next-outage sensors (Home Assistant). — [ha-yasno-outages](https://github.com/denysdovhan/ha-yasno-outages)

### Inferences
UX features that would add the most value to a PySide6 desktop app, in my judgement:
1. A **PDF report** with assumptions and warnings.
2. **"How is this calculated?" / provenance labels** on results.
3. **Saving and loading whole projects** (JSON already exists for profiles).
4. A **BOM with UAH prices** and payback.
5. A **map-based location picker with automatic PVGIS download** (DRcalc, hourly, horizon).
6. **Import of Deye/Victron/Solarman logs** for calibration of the "fact correction" factor.

### Gaps
- I did not verify the quality of the PDF and report output, or the accuracy of any small tool. Most small tools have no validation against measured data.

---

## Q6. Features and ideas these projects have that solar_calc v1.2.1 lacks

### Takeaway
solar_calc is already stronger than the small open-source calculators in four areas: DC wiring and ampacity, MPPT voltage-dependent efficiency, LiFePO4 cold-charge checks, and Ukrainian presets. It lags the serious tools in nine:
1. **Time base and weather realism:** hourly or multi-year data, stochastic weather.
2. **Reliability statistics:** days empty, unserved kWh, outage survival probability.
3. **Real outage schedules and generator backup.**
4. **Economics:** NPV, LCOE, two-zone tariffs, export.
5. **Battery ageing** and **CV taper.**
6. **Shading:** horizon profile, obstacles, snow.
7. **Multi-array / multi-MPPT** configurations.
8. **Optimisation:** cost against reliability.
9. **Calibration with monitoring data.**

### Cited Findings (feature → who has it)
1. **Hourly 8760 / multi-year simulation from PVGIS hourly (seriescalc) or TMY**, instead of 12 "average days" × 3 weather types. → pvlib `get_pvgis_hourly` / `get_pvgis_tmy`; MicroGridsPy and MiGUEL (NASA POWER); WillemVanM (PVGIS CSV import). — [pvlib iotools](https://github.com/pvlib/pvlib-python/tree/main/pvlib/iotools); [WillemVanM](https://github.com/WillemVanM/SolarBatterySimulator); [MicroGridsPy](https://github.com/SESAM-Polimi/MicroGridsPy-SESAM)
2. **Reliability metrics over many years:**
   - PVGIS-style monthly % days battery full or empty, average energy missing or not captured, SoC histogram. — [PVGIS sample](https://akkudoktor.net/uploads/short-url/7A4LUUstP0cmCIztnOrIBz8wdmQ.pdf)
   - WillemVanM-style unserved kWh per year, blackout hours per year, blackout events per year. — [WillemVanM](https://github.com/WillemVanM/SolarBatterySimulator)
3. **Outage survival probability.** Random outage start times, survival probability against duration, critical-load fraction. → REopt. — [REopt tutorial](https://www.nrel.gov/reopt/curriculum/videos/reopt-lite-tutorial-module-6-text)
4. **Real or scheduled grid outages as an input time series.**
   - MiGUEL `blackout_data` (CSV of grid availability per time step); Offgridders "grid with blackouts". — [MiGUEL](https://github.com/pdb-94/miguel); [Offgridders](https://github.com/rl-institut/offgridders)
   - Data source for Ukraine: Yasno outage calendar (ha-yasno-outages). — [ha-yasno-outages](https://github.com/denysdovhan/ha-yasno-outages)
5. **Generator backup:** diesel or petrol genset sizing, fuel use, partial-load efficiency, start/stop on SoC. → MicroGridsPy (MILP partial load), REopt (existing or optimised generator), Offgridders, MiGUEL (legacy). — [MicroGridsPy](https://github.com/SESAM-Polimi/MicroGridsPy-SESAM); [REopt.jl](https://github.com/NatLabRockies/REopt.jl)
6. **Stochastic weather / Monte Carlo.** → meteosynth (Markov chains + PVGIS), solarsim (synthetic clouds), GreenInvest (Monte Carlo), MicroGridsPy (two-stage stochastic). — [meteosynth](https://pypi.org/project/meteosynth/); [solarsim](https://github.com/briancpotter/solarsim); [GreenInvest](https://github.com/mbax0009/GreenInvest-Pakistan)
7. **Cost-optimal sizing.** Cheapest PV + battery for a reliability target with a Pareto front (WillemVanM); LP sizing of PV, battery and inverter (Microgrid-Calculator); batch heatmaps (Migelo); minimum-LCOE optimisation (HTW PV_Calculator). — [WillemVanM](https://github.com/WillemVanM/SolarBatterySimulator); [Microgrid-Calculator](https://github.com/sohaibiqbaal/Microgrid-Calculator); [Migelo](https://github.com/Migelo/solar-battery-simulator); [HTW](https://github.com/Thomas-HTW-Berlin/PV_Calculator)
8. **Economics beyond the tariff:** CAPEX/BOM, NPV, payback, LCOE with battery and inverter replacement, discount rate, degradation. → grollie, solarsim, solair-core, MicroGridsPy, SAM. — [grollie](https://github.com/grollie/solar-calculator); [solarsim](https://github.com/briancpotter/solarsim); [solair-core](https://github.com/Wooinxlkz/solair-core)
9. **Time-of-use / night tariff, grid charging below a price threshold, export / feed-in price, export limit.** → sunbeam60, Migelo, EMHASS, EOS. — [sunbeam60](https://github.com/sunbeam60/Solar-Panel-and-Battery-Calculator); [EMHASS](https://emhass.readthedocs.io/en/latest/); [EOS](https://github.com/Akkudoktor-EOS/EOS)
10. **Battery ageing.** Cycle counting, calendar and cycle fade, year-N capacity, replacement year; **voltage and thermal model**. → SAM, BLAST-Lite, SimSES, battery_sim. — [SAM workshop](https://docs.nrel.gov/docs/fy25osti/93555.pdf); [BLAST-Lite](https://github.com/NatLabRockies/BLAST-Lite); [SimSES](https://pypi.org/project/simses/); [battery_sim](https://github.com/hif2k1/battery_sim)
11. **Module degradation.** About 0.5%/yr (sunbeam60), age-based panel degradation (solarsim); pvdeg for physics-based degradation. — [sunbeam60](https://github.com/sunbeam60/Solar-Panel-and-Battery-Calculator); [pvdeg](https://pypi.org/project/pvdeg/)
12. **Snow loss** (Marion/NREL, Townsend) and **soiling models** (Kimber, HSU). → pvlib, SAM, PVGIS 5.3. — [snow.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/snow.py); [soiling.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/soiling.py)
13. **Horizon profile by azimuth** (PVGIS horizon API) and **obstacle shading with transparency** per azimuth sector (solXpect). Also 3D shading (SAM, KeshviEnterprise) and row-to-row / GCR self-shading. — [pvlib pvgis.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/iotools/pvgis.py); [solXpect](https://github.com/woheller69/solxpect); [SAM forum](https://sam.nrel.gov/forum/forum-general/1382-3d-shade-calculator-for-large-arrays.html)
14. **Partial shading with bypass diodes** (PVMismatch; pvlib `direct_martinez`). — [PVMismatch](https://github.com/SunPower/PVMismatch); [shading.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/shading.py)
15. **Better irradiance and module models:** Perez transposition, diffuse IAM, Ineichen clear sky, Faiman temperature with wind, single-diode (CEC) or Huld, spectral, bifacial. → pvlib. — [irradiance.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/irradiance.py); [pvarray.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/pvarray.py)
16. **Inverter efficiency curve** (part-load) instead of a constant value. → pvlib Sandia/ADR, SAM datasheet curve. — [inverter.py](https://github.com/pvlib/pvlib-python/blob/main/pvlib/inverter.py)
17. **Multiple arrays and MPPTs** (east-west, different tilts), with string-to-MPPT assignment and summing. → grollie, pypv, solXpect "show sum", ha-pvstrings. — [grollie](https://github.com/grollie/solar-calculator); [pypv](https://github.com/patrickpasquini/pypv); [solXpect](https://github.com/woheller69/solxpect)
18. **Site-statistics-based cold Voc** from weather records (vocmax), Vmp_hot at ambient + 30 °C (zonzelf), and an automatic ranked list of all viable S×P layouts per MPPT (pblakez, pypv). — [vocmax](https://github.com/toddkarin/vocmax); [zonzelf PR](https://github.com/vraaijmakers/zonzelf/pull/76); [pblakez](https://github.com/pblakez/solar-string-calc)
19. **Component databases:** CEC modules and inverters; import of PVsyst **.PAN/.OND** files (pvlib `read_panond`). — [iotools/](https://github.com/pvlib/pvlib-python/tree/main/pvlib/iotools)
20. **Appliance-based load builder with motor surge**, for inverter peak and surge sizing, and **critical-load** definition for outages. → Microgrid-Calculator, Hello Solar Planner, Solario, REopt. — [Microgrid-Calculator](https://github.com/sohaibiqbaal/Microgrid-Calculator); [solarplanner](https://github.com/projecthelloworld-org/solarplanner)
21. **Stochastic or standard load profiles** (RAMP, BDEW H0 via demandlib, LoadProfileGenerator), **measured meter-data import** (PV-Soft, Migelo CSV) and a **heat-pump load add-on** (Migelo). — [RAMP](https://pypi.org/project/rampdemand/); [demandlib](https://demandlib.readthedocs.io/en/latest/bdew.html); [PV-Soft](https://github.com/PV-Soft/Battery-Simulation)
22. **Calibration with monitoring data** (Victron VRM comparison, per-string learned correction, RdTools degradation and soiling). — [WillemVanM](https://github.com/WillemVanM/SolarBatterySimulator); [ha-pvstrings](https://github.com/doccodyblue/ha-pvstrings); [rdtools](https://github.com/NatLabRockies/rdtools)
23. **Forecast mode** (next 1–16 days from Open-Meteo): will the battery last through tomorrow's outage? → solXpect, EMHASS, EOS. — [solXpect](https://github.com/woheller69/solxpect)
24. **Reporting and UX:** PDF report, provenance labels, "how calculated" expanders, pass/fail/unverified check list, BOM with costs, project save/load, map picker, installer-quote check. → KeshviEnterprise, Hello Solar Planner, GreenInvest, imtona44. — [KeshviEnterprise](https://github.com/KeshviEnterprise/SolarProject); [solarplanner](https://github.com/projecthelloworld-org/solarplanner); [GreenInvest](https://github.com/mbax0009/GreenInvest-Pakistan); [imtona44](https://github.com/imtona44/solarcalc)
25. **DC-coupled versus AC-coupled storage efficiency chains** with measured device data (bslib / Stromspeicher-Inspektion). — [bslib](https://github.com/FZJ-IEK3-VSA/bslib)

### Inferences
Suggested priority for solar_calc, given a Kyiv 1–30 kW home hybrid or off-grid system and the outage context. This ordering is my judgement from the findings above.
1. **PVGIS hourly multi-year mode plus the PVGIS/WillemVanM reliability statistics** (items 1–2). This is the biggest realism gain for battery sizing, and pvlib's `get_pvgis_hourly` shows the API pattern.
2. **Outage-schedule input** (Yasno/DTEK queue windows, or a CSV of grid on/off per step) **plus REopt-style survival probability**, with a **generator option** (start SoC, fuel l/h) (items 3–5).
3. **Two-zone night tariff with grid charging**, plus **NPV/payback/LCOE with battery replacement and degradation** (items 8–11).
4. **Azimuth-dependent horizon (PVGIS horizon) with an obstacle table, and snow loss** (items 12–13).
5. **Inverter part-load curve, Perez/diffuse IAM, Faiman or Huld** (items 15–16), with low effort if pvlib is used as a dependency.
6. **Multi-array / multi-MPPT** and **ranked automatic string layouts** (items 17–18).
7. **PDF report with provenance and check list**, and a **BOM in UAH** (item 24).
8. **Calibration import** of Deye, Victron or Solarman CSV logs to fit the "fact correction" factor automatically (item 22).

Already covered by solar_calc, and rare or absent in open source:
- DC cable sizing with ПУЭ ampacity, Cu/Al and temperature-dependent resistance, plus contact losses;
- MPPT efficiency depending on Vin/Vbat, and headroom over battery voltage;
- LiFePO4 charging below 0 °C;
- cold capacity derating;
- string fuse rule for 3 or more strings;
- inverter idle-consumption share;
- the Ukrainian UI and presets.

### Gaps
- I did not inspect source code to confirm how each small tool implements its claims. Everything above is README-level evidence.
- Quantitative evidence is missing on how much "average day × 3 weather types" underestimates the battery or PV needed compared with multi-year hourly simulation for Kyiv. This would need a test run, for example solar_calc against PVGIS seriescalc for Kyiv.
- No Yasno/DTEK **historical** outage dataset suitable for Monte Carlo was found. ha-yasno-outages exposes planned schedules only.
