# Open-source home energy management, battery dispatch, solar forecast, inverter monitoring and Ukrainian outage-schedule projects: what solar_calc v1.2.1 can learn from them

Research date: 2026-10-08. Method: web search (many search results summarised GitHub READMEs, docs sites, PyPI and HA community threads). Direct fetches worked only for pypi.org and raw.githubusercontent.com. The egress proxy blocked readthedocs, github.io, dou.ua, open-meteo.com, doc.forecast.solar and community.openhab.org, and ecosyste.ms star counts could not be read. Popularity numbers are therefore sparse (see Gaps). The web-search budget ran out before the last EMHASS-detail query.

Reference point: **solar_calc v1.2.1** (PySide6 desktop app, Kyiv defaults). It simulates an average day of each month in 10-min steps for 3 weather types and has PV, MPPT, battery, inverter and load models. Grid modes are "grid available" and "no grid / outages", with one flat tariff. It does **not** model real outage schedules, TOU tariffs, grid charging, export or net billing, forecasts, degradation, a generator, monitoring-data import or payback.

---

## Q0. Catalogue: which relevant projects exist, on what platform, how active, and with which concrete features?

### Takeaway
The useful projects fall into seven groups:
- **Optimisers/planners:** EMHASS, Predbat, evcc, Akkudoktor-EOS, batcontrol, OpenEMS, plus the commercial Ukrainian Yasno Power "Автопілот".
- **Simulators:** HA battery_sim.
- **Forecast integrations:** Forecast.Solar, Solcast, Open-Meteo Solar Forecast.
- **Inverter bridges:** Deye/Sunsynk via Solarman/Modbus, Voltronic/Axpert via mpp-solar, Must via ESPHome, Growatt, Victron VRM, SolarAssistant.
- **Ukrainian outage-schedule tools:** ha-yasno-outages, ha-svitlo-yeah, svitlo_live, outage-data-ua and the Yasno blackout-service wrappers.
- **Degradation libraries:** BLAST-Lite, PySAM, SimSES.

Most of them are Python. Most are Home Assistant (HA) add-ons or custom integrations, not desktop apps.

### Cited Findings

**A. Optimisers / dispatch planners**

- **EMHASS (Energy Management for Home Assistant)**: github.com/davidusb-geek/emhass. MIT licence, Python >=3.10,<3.13. Latest PyPI release is 0.18.4 (27 Sep 2026); 0.18.3 came out on 10 Sep 2026, so the project is very active. "Uses a Linear Programming approach to optimize energy use, considering electricity prices, solar generation, and energy storage from batteries." — [PyPI emhass](https://pypi.org/project/emhass/)
  - Features: day-ahead and Model Predictive Control (MPC) optimisation; open-source HiGHS or commercial Gurobi/CPLEX solvers; configurable cost functions ("profit", "cost" minimisation, "self-consumption"). It runs as an HA add-on or a standalone Docker container. — [EMHASS docs](https://emhass.readthedocs.io/en/latest/), [Getting started](https://emhass.readthedocs.io/en/stable/section_getting_started.html)
  - Other docs content: thermal integration for water heaters and heat pumps, treated as thermal storage; a study case with 5 kWp PV, a 5 kWh battery and two deferrable loads; the optimisation engine "rewritten using CVXPY and vectorization". — [EMHASS docs](https://emhass.readthedocs.io/en/latest/)
  - Older versions used PVLib for PV modelling and PuLP for the LP. — [PyPI emhass 0.3.13](https://pypi.org/project/emhass/0.3.13)
  - Deferrable loads, such as an EV or boiler, are defined by nominal power, operating hours and start/end timesteps. Each load publishes `sensor.p_deferrableN` to HA. — [EMHASS docs](https://emhass.readthedocs.io/en/latest/)
- **Predbat (batpred)**: github.com/springfall2008/batpred; docs at springfall2008.github.io/batpred. "Home battery prediction and charging automation for Home Assistant". The Gentoo package targets Python 3.12–3.14. — [Gentoo ebuild](https://gpo.zugaina.org/AJAX/Ebuild/56604817/View)
  - A standalone launcher exists that runs it without HA. — [same source](https://gpo.zugaina.org/AJAX/Ebuild/56604817/View)
  - Free for self-hosting, with a managed cloud service available. A comparison article ranks it first for UK homes. — [diyai.io comparison](https://diyai.io/ai-tools/engineering/best-ai-home-energy-management-tools/)
  - Version numbers in 2026 issues run up to v8.46.x. — [HA community, Sigenergy + Predbat v8.46.3](https://community.home-assistant.io/t/sigenergy-predbat-v8-46-3-charge-rate-discharge-rate-and-charge-limit-entities-missing/1018499)
  - Features (details in Q1): 48 h plan in 30-min slots, recomputed every 5 min; Solcast/Open-Meteo/Forecast.Solar PV10/50/90; load from history or a neural network; battery and inverter losses; `metric_battery_cycle` virtual cycle cost; car charging; iBoost (solar diverter) modelling; plan card and web UI. — [Predbat docs: customisation](https://springfall2008.github.io/batpred/customisation/), [Plan card](https://springfall2008.github.io/batpred/predbat-plan-card/), [Web interface](https://springfall2008.github.io/batpred/web-interface/)
- **evcc**: docs.evcc.io. Its main job is EV charging, but it now covers home batteries.
  - Tariffs & forecasts: grid price, feed-in price, CO2 intensity, solar forecast and temperature forecast. A fixed price per kWh or dynamic tariffs are supported. — [evcc Tariffs & forecasts](https://docs.evcc.io/en/tariffs/)
  - "Cheap grid charging" with a price limit, and `chargesZones` for time-variable network charges (§14a). — [evcc Dynamic tariffs](https://docs.evcc.io/en/features/dynamic-prices/)
  - Planner modes are cheap, green (CO2) or standard, and solar is always preferred. — [evcc Charge planner](https://docs.evcc.io/en/features/plans/)
  - "Smart feed-in" throttles PV when exporting costs money. — [evcc Dynamic tariffs](https://docs.evcc.io/en/features/dynamic-prices/)
  - Experimental optimizer. Inputs: solar yield, prices, feed-in tariffs, outdoor temperature, consumption history, battery/vehicle state. Outputs: "battery control (hold, grid charging)". — [evcc Optimizer](https://docs.evcc.io/en/features/optimizer/)
  - Release 0.316 (Sept 2026) renamed "Solar" mode to "Smart" and added a Battery status page. — [evcc blog 2026-09-25](https://docs.evcc.io/en/blog/2026/09/25/highlights-smart-battery-solar-share/)
  - `prioritySoc` and `bufferSoc` split surplus between the home battery and the car. — [evcc blog 10/2023](https://docs.evcc.io/en/blog/2023/10/05/feature-highlights-10-2023/)
- **Akkudoktor-EOS**: a self-hosted server that computes schedules for batteries, EVs and household devices from configuration, measurements and forecasts. It does not control hardware itself; it integrates with HA, Node-RED and evcc. — [EOS docs intro](https://akkudoktor-eos.readthedocs.io/en/latest/akkudoktoreos/introduction.html)
  - Uses a **genetic algorithm**, so "non-linear battery degradation ... heat pumps with non-linear COP fields can be used directly". — [same source](https://akkudoktor-eos.readthedocs.io/en/latest/akkudoktoreos/introduction.html)
  - Runs either manually via `POST /optimize` or in automatic interval mode. — [EOS automatic optimization](https://akkudoktor-eos.readthedocs.io/en/latest/akkudoktoreos/optimauto.html)
  - Presented at FOSDEM 2026. — [FOSDEM 2026](https://fosdem.org/2026/schedule/event/akkudoktor-eos-energy-management-plans)
  - About 1,594 stars in a late-May 2026 snapshot. — [ecosyste.ms](https://ost.ecosyste.ms/projects/301397)
- **batcontrol**: github.com/MaStr/batcontrol, MIT licence. Charges the battery from the grid when prices are low and PV is insufficient, and avoids discharging in expensive periods.
  - Hardware: Fronius Gen24 (HTTP/Modbus) or any inverter behind an MQTT bridge.
  - Price sources: Tibber, aWATTar, evcc, EnergyForecast.de, or fixed zone tariffs such as Octopus.
  - PV sources: Forecast.Solar, Solar-Prognose.de, evcc, or the HA ML forecast.
  - A static tariff is enough for peak shaving. Installs via Docker, HA add-on or plain Python. — [batcontrol GitHub](https://github.com/MaStr/batcontrol)
  - Release 0.9.1; Python 3.14 support merged on 7 Oct 2026. — [Release 0.9.1](https://github.com/MaStr/batcontrol/releases/tag/0.9.1), [PR #444](https://github.com/MaStr/batcontrol/pull/444)
- **OpenEMS**: Java, AGPL-3.0, started in 2016. Architecture is Edge (on-site control), UI and Backend. Use cases include storage plus PV, EV chargers, heat pumps and time-of-use tariffs. — [ecosyste.ms OpenEMS](https://ost.ecosyste.ms/projects/79573)
  - FENECON and Fraunhofer ISE built a §14a / EEBus reference implementation (June 2026). — [Bayern Innovativ](https://www.bayern-innovativ.de/en/emagazine/detail/open-source-software-is-intended-to-simplify-network-management/)
  - Aimed more at commercial/industrial users than at hobbyists (inference from its architecture).
- **Yasno Power "Автопілот"** (commercial, free, Ukraine; not open source).
  - Automatically manages a home PV station and battery, taking into account a user-set **reserve %**, the **day/night tariff** and PV generation.
  - Currently supports **Deye** only; you connect it with the logger serial number or QR code. Data refreshes every 5 min.
  - You do not need to be a Yasno customer. — [kosht.media](https://kosht.media/v-ukraini-zapustyly-avtomatychne-keruvannia-domashnimy-batareiamy/), [finance.ua](https://news.finance.ua/ua/yasno-zapustyv-servis-dlya-keruvannya-domashnimy-sonyachnymy-stanciyamy)
  - Rationale quoted from Yasno marketing: without automation the battery may be "charged too early, before the lowest night price" or "the whole reserve spent during the day, leaving none for an outage". — [finance.ua (ru)](https://news.finance.ua/ru/yasno-zapustil-servis-dlya-upravleniya-domashnimi-solnechnymi-stanciyami)

**B. Simulators that replay real data**

- **battery_sim (hif2k1)**: an HA custom integration, MIT licence, that "allows you to model how much energy you would save with a home battery". — [GitHub hif2k1/battery_sim](https://github.com/hif2k1/battery_sim)
  - How it works: the virtual battery charges when the meter exports and discharges when it imports. It needs cumulative import and export kWh sensors.
  - Tariff can be a fixed number or a variable-rate sensor.
  - Outputs: total money saved, split into import savings and extra export earnings. — [HA community thread](https://community.home-assistant.io/t/custom-component-home-battery-storage-simulation-battery-sim-integration/740496)
  - Forks: dewi-ny-je, and Smartify (REST power polling; HA 2026.8+). — [Smartify fork](https://github.com/smartify-your-home/smartify_battery_sim), [dewi-ny-je fork](https://github.com/dewi-ny-je/battery_sim)

**C. Blueprints / automations relevant to outages and TOU tariffs**

- **AlexandrLisitsa/HomeSweetHome PR #14, "Charge the battery to full before a scheduled DTEK outage"** (PowMr inverter):
  - When DTEK publishes a schedule, HA checks whether the battery would be full in time.
  - The charge current is computed from the energy still needed, with a target of being full 30 min before the outage window.
  - The deadline is also held on the ESP, so a dead HA cannot leave the inverter on grid. — [PR #14](https://github.com/AlexandrLisitsa/HomeSweetHome/pull/14)
- **Home Energy Autopilot** (HA blueprint): charge when power is cheap and discharge when expensive, with a reserve floor and a charge ceiling. — [HA community](https://community.home-assistant.io/t/home-energy-autopilot-charge-your-battery-when-power-is-cheap-discharge-when-its-expensive-any-dynamic-tariff-any-battery/1016827)
- **Smartcharging-HA**: an optimal charging schedule from day-ahead prices plus a solar forecast. — [GitHub pwnypower/Smartcharging-HA](https://github.com/pwnypower/Smartcharging-HA)
- **SunSynk/Deye HA integration via the cloud API**: v1.6.0 raises the charge current when any HA price sensor drops below a threshold. — [HA community](https://community.home-assistant.io/t/sunsynk-deye-integration-using-api/1010154)
- **Deye Zero Feed-in Control V2** (blueprint, uses a Shelly meter). — [HA community](https://community.home-assistant.io/t/deye-zero-feed-in-control-v2/915744)

**D. Solar forecast integrations.** Details are in Q4. In short: HA core Forecast.Solar ([HA docs](https://www.home-assistant.io/integrations/forecast_solar/)); BJReplay/ha-solcast-solar ([GitHub](https://github.com/BJReplay/ha-solcast-solar)); rany2/ha-open-meteo-solar-forecast ([GitHub](https://github.com/rany2/ha-open-meteo-solar-forecast)), whose PyPI library is [open-meteo-solar-forecast](https://pypi.org/project/open-meteo-solar-forecast/).

**E. Inverter monitoring / data bridges.** Details are in Q3. They cover Deye (ha-solarman, kellerza/sunsynk, deye-modbus-ha, deye-inverter-mqtt, ESPHome), Voltronic/Axpert (mpp-solar, docker-voltronic-homeassistant), Must (several ESPHome/ESP32 bridges), Growatt (GroBro, OpenInverterGateway), Victron VRM, and SolarAssistant (an official open-source HA integration exists).

**F. Ukrainian outage-schedule projects.** Details are in Q2: ha-yasno-outages, ha-svitlo-yeah, svitlo_live, Lviv PowerOff, ha-dtek-monitor, outage-data-ua, OE_OUTAGE_DATA, electricityoff-api-kem/dniprocek, menstryo/svitlo, chernivtsi-outages, outage-stats, power-outage-schedule-card and others.

**G. Degradation models.** Details are in Q3b: NREL BLAST-Lite, PySAM BatteryStateful and TUM SimSES.

### Inferences
- No project found is a **sizing calculator** like solar_calc. All the optimisers are operational schedulers, working 24–48 h ahead on live data. Their *models* are what transfers: loss chains, cycle cost, tariff vectors, forecast percentiles, outage masks.
- EMHASS and Predbat are the closest analogues for the battery/tariff logic. battery_sim is the closest analogue for "replay real data through a virtual battery".

### Gaps
- GitHub star/fork counts could not be retrieved. The ecosyste.ms and GitHub pages were blocked by the proxy, and the GitHub MCP was excluded by instruction. Only EOS (~1,594 stars, May 2026) and ha-yasno-outages (~189 stars, ~27 forks, as read from an ambiguous listing) have numbers.
- OpenEMS's time-of-use optimiser could not be described from sources.

---

## Q1. Which projects simulate or optimise battery charge/discharge against tariffs, forecasts and outages, and what inputs/outputs do they use?

### Takeaway
- **EMHASS:** an LP/MPC over 24 h+. Inputs are PV forecast, load forecast, a per-step import price vector (`load_cost_forecast`) and an export price vector (`prod_price_forecast`). Outputs are battery power, grid power and deferrable-load schedules.
- **Predbat:** brute-force evaluation of charge/discharge windows over 48 h in 30-min slots. Inputs are PV10/50/90, load history and import/export rates, with explicit loss and cycle-cost parameters. Output is a plan table.
- **evcc, batcontrol and EOS:** simpler (evcc, batcontrol) or genetic (EOS) variants of the same idea.
- **Outages are handled only crudely:** a reserve/minimum SoC (Predbat, Yasno Autopilot), or ad-hoc HA automations that pre-charge before a scheduled outage. No project found builds Ukrainian outage schedules into its optimiser.

### Cited Findings

**EMHASS inputs and outputs**
- `load_cost_forecast` is "the price of the energy from the grid in the next 24 hours", in currency/kWh. `prod_price_forecast` is "the price at which you will sell your excess PV production in the next 24 hours". — [EMHASS forecast module](https://emhass.readthedocs.io/en/stable/forecasts.html), [Passing data](https://emhass.readthedocs.io/en/stable/passing_data.html)
- Runtime lists must cover every step of the horizon; a shorter list causes an error. — [EMHASS forecast module](https://emhass.readthedocs.io/en/latest/forecasts.html)
- `weight_battery_discharge`: "additional weight in currency/kWh applied in the cost function to battery discharge usage" (default 0.00). `battery_dynamic_max`/`_min`: the allowed variation of battery power per time step. — [EMHASS config](https://emhass.readthedocs.io/en/latest/config.html)
- A user config example sets `soc_init`, `soc_final`, `battery_charge_power_max` and `battery_discharge_power_max`. — [HA community EMHASS thread](https://community.home-assistant.io/t/emhass-an-energy-management-for-home-assistant/338126?page=170)
- A feature request asks to use the actual SoC as the optimisation start point. — [EMHASS issue #585](https://github.com/davidusb-geek/emhass/issues/585)
- A machine-readable schema of runtime parameters lives at `src/emhass/static/data/runtime_params.json`. — [EMHASS cookbook](https://emhass.readthedocs.io/en/latest/cookbook/battery_aware_runtime_params.html)
- A user builds `load_cost_forecast` from Nord Pool hourly prices. — [HA community](https://community.home-assistant.io/t/emhass-an-energy-management-for-home-assistant/338126?page=170)

**Predbat inputs, model and outputs**
- Inputs: historical house load, tariff rates, Solcast forecasts. It re-plans every 5 minutes over 48 h in 30-min blocks, costs every charge/discharge combination and picks the cheapest. — [HA community (Fox KH7 thread)](https://community.home-assistant.io/t/predbat-anyone-have-a-working-apps-yaml-example-for-fox-kh7-inverter/1015045)
- PV: the central 50% scenario from Solcast, Open-Meteo or Forecast.Solar, weighted toward the pessimistic 10% scenario.
  - With PV calibration on, PV10 and PV90 are scaled by the same factor as PV50.
  - Users tune `predbat_pv_scaling` and `predbat_load_scaling` by comparing against actuals.
  - The default PV10 load scaling is 1.1 (+10% load). — [Predbat customisation](https://springfall2008.github.io/batpred/customisation/), [FAQ](https://springfall2008.github.io/batpred/faq/)
- Load is predicted from history, or by a neural network that learns time-of-day and day-of-week patterns. Predbat also tracks actual vs predicted load and adjusts in real time. — [Predbat docs](https://springfall2008.github.io/batpred/what-does-predbat-do/)
- Losses: defaults are 3% charge, 3% discharge and 4% inverter.
  - A full cycle is modelled as charge loss × inverter loss × inverter loss × discharge loss.
  - Grid charging always incurs the AC→DC inverter loss.
  - A "calibration chart" helps tune losses until the model matches reality. — [Predbat FAQ](https://springfall2008.github.io/batpred/faq/), [customisation](https://springfall2008.github.io/batpred/customisation/)
- Battery charge power curve and battery temperature charge curve are configurable in apps.yaml (community sample; the author warns the temperature curve must be recalculated for your battery voltage). — [FoxESS community sample apps.yaml](https://foxesscommunity.com/viewtopic.php?p=13359)
- Predbat tries to build the battery discharge curve from sensor history and logs an error when it cannot. — [batpred issue #3685](https://github.com/springfall2008/batpred/issues/3685)
- Outages: the docs suggest raising the minimum reserve to keep extra charge ahead of a likely outage, then lowering it afterwards. This helps only if the inverter provides backup. — [Predbat customisation](https://springfall2008.github.io/batpred/customisation/)
- Reported bug: cost optimisation overrode the `best_soc_keep` minimum and discharged the battery to 14%. — [issue #3207](https://github.com/springfall2008/batpred/issues/3207)
- Inverter control maps plan states to inverter modes: Demand/Eco → Self-Use, Charging → Force Charge from grid, Freeze charging → Back-up (hold SoC). — [FoxESS community](https://foxesscommunity.com/viewtopic.php?p=13359)
- Car charging: `num_cars`, `car_charging_exclusive`, and filtering car energy out of load history. A PR adds "solar-first" car slots; its merge status is unverified. — [Predbat customisation](https://springfall2008.github.io/batpred/customisation/), [PR #5195](https://github.com/springfall2008/batpred/pull/5195)
- iBoost models excess solar diverted to hot water instead of exported. — [Predbat output data](https://springfall2008.github.io/batpred/output-data/)

**evcc, batcontrol, EOS and Yasno Autopilot**
- evcc optimizer inputs: solar yield, prices, feed-in tariffs, outdoor temperature (heating demand), household consumption history, current battery and vehicle state. Outputs: cost-optimal charging plans and battery hold or grid charging. — [evcc Optimizer](https://docs.evcc.io/en/features/optimizer/)
- batcontrol: forecasts of price, PV and consumption are fetched on separate timers. Decisions are to charge from grid when cheap and PV is short, or to block discharge in expensive hours. — [batcontrol](https://github.com/MaStr/batcontrol)
- EOS fitness function: minimise cost, maximise self-consumption or meet battery targets, evaluated by simulating each candidate schedule. — [EOS docs](https://akkudoktor-eos.readthedocs.io/en/latest/akkudoktoreos/introduction.html)
- Yasno Autopilot inputs: reserve %, day/night tariff, PV generation (Deye only). — [kosht.media](https://kosht.media/v-ukraini-zapustyly-avtomatychne-keruvannia-domashnimy-batareiamy/)
- No source confirmed that Yasno Autopilot uses outage schedules. — [same](https://kosht.media/v-ukraini-zapustyly-avtomatychne-keruvannia-domashnimy-batareiamy/)

**Outage-driven pre-charging (Ukraine)**
- The PowMr/DTEK PR computes the needed charge current so the battery is full 30 min before the scheduled outage. — [PR #14](https://github.com/AlexandrLisitsa/HomeSweetHome/pull/14)
- Deye TOU: without the "Grid charge" checkbox the inverter goes to grid but does not charge the battery. Seen in a search summary of these forum threads; the exact thread was not isolated. — [powerforum.co.za Deye TOU](https://powerforum.co.za/topic/11682-deye-time-of-use-settings/), [powerforum "Deye using grid and not battery"](https://powerforum.co.za/topic/32928-deye-using-grid-and-not-battery/)
- Solis analogy: an inverter cannot simply "hold" the battery; the only way is to switch it to charge mode. — [bentasker.co.uk](https://www.bentasker.co.uk/posts/blog/house-stuff/controlling-charge-schedules-with-homeassistant-and-soliscloud.html)
- A German HA/ESPHome automation turns a Deye off at night when battery voltage falls below 51.3 V (idle-draw saving). — [akkudoktor.net](https://akkudoktor.net/t/deye-nachts-ausschalten-wenn-akku-leer-ist-ha-esphome-ha-automatisierungen/14529)

### Inferences
- The common data model across planners is a **time-indexed vector per step**: PV forecast (P10/P50/P90), load forecast, import price, export price, grid availability, and min/max SoC. solar_calc already has 10-min steps, so adding per-step import-price, export-price and grid-available vectors fits its architecture directly.
- Predbat's explicit loss chain (charge × inverter² × discharge) and the cycle cost answer one question with simple arithmetic: does night grid charging at 2.16 UAH pay off against daytime 4.32 UAH? See Q5 for the Ukrainian tariff numbers.
- For Ukraine, grid charging matters mainly to have a full battery *before* a scheduled outage. TOU arbitrage is secondary. No reviewed optimiser treats "grid unavailable" as a hard constraint in its plan, so solar_calc would be ahead here if it did.

### Gaps
- The exact EMHASS list of PV-forecast methods and the peak/off-peak tariff parameters could not be confirmed: the search budget ran out and readthedocs was blocked.
- Predbat's official explanation of `battery_temperature_charge_curve` semantics was not retrieved.
- The `metric_battery_cycle` default is inconsistent between sources (FAQ says 1p; a config dump shows 0.5/1.0). — [Predbat FAQ](https://springfall2008.github.io/batpred/faq/), [issue #1035](https://github.com/springfall2008/batpred/issues/1035)

---

## Q2. Which Ukrainian projects handle outage schedules (queues/groups "черги", hourly schedules), and how are the schedules represented (data formats, APIs)?

### Takeaway
There are two de-facto machine-readable sources:
1. **DTEK website JSON**, mirrored by Baskerville42/outage-data-ua. It is per region, keyed by group "GPV1.1" and hour "1"–"24", with values `yes/no/maybe/first/second/mfirst/msecond`, which gives half-hour resolution.
2. **The undocumented Yasno blackout-service API**, keyed by region and DSO. It returns slots in minutes from midnight with types such as "Definite" and a status such as "ScheduleApplies".

HA integrations (ha-yasno-outages → ha-svitlo-yeah, svitlo_live) wrap these into calendars and "next outage" sensors. Groups are "1.1…6.2" (12 sub-queues), and DTEK has used 30-min resolution since Dec 2024.

### Cited Findings

**HA integrations**
- **denysdovhan/ha-yasno-outages**: uses the Yasno API; Kyiv and Dnipro. Provides a calendar of planned outages and time sensors for the next outage. — [GitHub](https://github.com/denysdovhan/ha-yasno-outages), [DOU list of UA HA integrations (updated 11 Aug 2026)](https://dou.ua/goto/iJBp)
  - Releases mention support for the Yasno "v2" API. — [releases](https://github.com/denysdovhan/ha-yasno-outages/releases)
  - Listing shows ~189 stars, ~27 forks, last commit 18 Aug 2026; the layout of that listing was ambiguous. — [goodfirstissue listing](https://goodfirstissue.org/denysdovhan?page=2)
  - Older entity names look like `calendar.yasno_power_today_kiev_group_2_1` and `..._tomorrow_...`. — [user automation dataset](https://gitea-s2i2s.isti.cnr.it/simone.gallo/AutomationDataset/src/branch/main/kuzin2006/automation-descriptions.json)
- **ALERTua/ha-svitlo-yeah** (fork of ha-yasno-outages). Sources by region: — [README](https://raw.githubusercontent.com/ALERTua/ha-svitlo-yeah/main/README.md)
  - Kyiv and Dnipro (DnEM, CEK): Yasno API.
  - Kyiv oblast, Dnipro and oblast, Odesa and oblast (DTEK): community JSON from **Baskerville42/outage-data-ua**.
  - Khmelnytskyi, Ivano-Frankivsk, Uzhhorod, Lviv, Ternopil, Chernihiv, Zaporizhzhia, Zhytomyr, Poltava and Rivne oblenergos: community JSON from **yaroslav2901/OE_OUTAGE_DATA**.
  - Vinnytsia: **gpv-voe-vinnytsia**.
  - Sumy: **E-Svitlo API**, using the personal-cabinet login.
- ha-svitlo-yeah entities and behaviour: — [README](https://raw.githubusercontent.com/ALERTua/ha-svitlo-yeah/main/README.md)
  - Sensors: Electricity (connected / planned_outage / emergency / unknown), Next Planned Outage, Next Scheduled Outage, Next Connectivity, Schedule Updated On, Schedule Data Changed On.
  - Two calendars (planned and scheduled outages), a refresh button, and the event `svitlo_yeah_data_changed`.
  - Polls every 15 min (not configurable). It keeps the last schedule across restarts, and keeps using DTEK data up to 2 days old.
  - The DTEK JSON copy "can lag" and "has no emergency outages".
  - Dnipro CEK groups are shown like «ЦЕК 1.1 (1001.1)».
- Release 0.8.0: times are always Kyiv time, unknown-state warnings, Kyiv Oblast setup, requires HA 2026.3+. — [release 0.8.0](https://github.com/ALERTua/ha-svitlo-yeah/releases/tag/0.8.0), [HA community thread](https://community.home-assistant.io/t/svitlo-yeah-power-outage-schedules-for-ukraine/955865)
- **chaichuk/svitlo_live** (and the vladmokryi repo of the same name): status and planned outages "based on data from svitlo.live and DTEK websites"; covers all non-occupied Ukraine.
  - Entities: binary electricity status, next grid connection, next outage, minutes to outage, and a calendar `calendar.svitlo_<region>_<queue>`.
  - Poltava data comes directly from poe.pl.ua. Other regions go through a proxy that aggregates DTEK/YASNO.
  - Releases add emergency-outage notifications, night quiet hours 23:00–05:00 and v2.6.0 entity-ID changes. — [chaichuk releases](https://github.com/chaichuk/svitlo_live/releases), [vladmokryi/svitlo_live](https://github.com/vladmokryi/svitlo_live), [DOU list](https://dou.ua/goto/iJBp)
- **Home Assistant Lviv PowerOff** (LvivOblEnergo via EnergyUA data) and **HA EnergyUA**; ha-lviv-poweroff is by Anatolii Stehnii. — [DOU list](https://dou.ua/goto/iJBp)
- **groove-max/ha-dtek-monitor**: HA integration for DTEK OEM (Odesa) outage status and schedules. — [GitHub](https://github.com/groove-max/ha-dtek-monitor)
- **strange-v/power-outage-schedule-card**: a Lovelace card. — [GitHub](https://github.com/strange-v/power-outage-schedule-card)
- An HA community thread lists Ukrainian HA integrations. — [HA community](https://community.home-assistant.io/t/ukrainian-home-assistant-integrations/776849)

**Data repositories and APIs**
- **Baskerville42/outage-data-ua**: "public data store of planned outages in Ukraine". Data is collected from provider web pages and stored unchanged as `data/<region>.json`; PNG charts go to `images/<region>/gpv-x-x.png`. — [GitHub](https://github.com/Baskerville42/outage-data-ua)
  - Sister project: **outage_ua_bot**, a Telegram bot that updates and pins schedules in channels every 5 min. — [outage_ua_bot](https://github.com/Baskerville42/outage_ua_bot)
- **Exact format of `data/kyiv.json`** (fetched 2026-10-08): — [raw kyiv.json](https://raw.githubusercontent.com/Baskerville42/outage-data-ua/main/data/kyiv.json)
  - Top-level keys: `regionId`, `lastUpdated`, `fact`, `preset`.
  - `fact.data[<unix day timestamp>]["GPV1.1"]["1".."24"]` = status; `fact.today` holds that day's timestamp, and `fact.update` is a string such as "08.10.2026 08:01".
  - `preset.sch_names` maps "GPV1.1" to "Черга 1.1".
  - `preset.time_zone["1"]` = ["00-01","00:00","01:00"].
  - `preset.data` is a weekly template: group → weekday "1".."7" → hour "1".."24".
  - `preset.time_type` legend: `yes` = power on, `no` = power off, `maybe` = possible outage, `first` = off during the first 30 min of the hour, `second` = off during the second 30 min, `mfirst`/`msecond` = possibly off in the first/second 30 min.
  - Excerpt: `"GPV1.1": {"1": "first", "2": "yes", "3": "yes", ...}`.
  - On outage-free days, Kyiv, Dnipro and Odesa publish an empty `fact`, but `preset` still lists all groups. — [search summary of outage-data-ua/related projects](https://github.com/Baskerville42/outage-data-ua)
- **Yasno blackout-service API (undocumented)**: `https://app.yasno.ua/api/blackout-service/public/shutdowns/regions/{regionId}/dsos/{dsoId}/planned-outages`.
  - IDs: Kyiv (DTEK KEM) is region 25, DSO 902; Dnipro is region 3, DSO 301 or 303.
  - Times are minutes from midnight. A wrapper returns only slots of type "Definite" when the status is "ScheduleApplies".
  - Dnipro queues are 1.1…6.2. The Kyiv wrapper README says "Нові черги: 1.1 … 60.1 (старих підгруп *.2 немає)", which is unusual and unverified.
  - One tracker polls with GitHub Actions every 5 min and writes `data/outages.json`.
  - Sources: [gzoreslav/electricityoff-api-kem](https://github.com/gzoreslav/electricityoff-api-kem), [gzoreslav/electricityoff-api-dniprocek](https://github.com/gzoreslav/electricityoff-api-dniprocek), [norivka.github.io](https://github.com/norivka/norivka.github.io)
- Older Yasno response shape: `dailySchedule` → "kiev" → today/tomorrow → groups keyed like "1.1". — [kuzin2006/yasno_hass](https://github.com/kuzin2006/yasno_hass)
- **menstryo/svitlo**: GitHub Pages republisher; Actions run every 10 min and publish `regions.json` and `schedule/<id>.json`. — [GitHub](https://github.com/menstryo/svitlo)
- **denysdovhan/chernivtsi-outages**: each group is an array of 24 hourly power states, served from raw.githubusercontent. — [GitHub](https://github.com/denysdovhan/chernivtsi-outages)
- Other projects:
  - **akrava/outage-stats**: Kyiv dashboard with heatmaps, group ranking and history. — [GitHub](https://github.com/akrava/outage-stats)
  - **banditByte/light-monitor-kyiv**: hourly Actions, using outage-data-ua plus Yasno. — [GitHub](https://github.com/banditByte/light-monitor-kyiv)
  - **chaichuk/UA-power-outages-monitor**. — [GitHub](https://github.com/chaichuk/UA-power-outages-monitor)
  - **elzadj/my-svitlo** (parses power status and load-shedding schedules). — [GitHub](https://github.com/elzadj/my-svitlo)
  - **stufyyyyn/energy-ua-bot** (Poltava). — [GitHub](https://github.com/stufyyyyn/energy-ua-bot)
  - **whoisridze/electricity-outage-checker**: PyPI CLI that looks up DTEK schedules by address. — [PyPI](https://pypi.org/project/electricity-outage-checker/)
  - **petrovoronov/svitlobot-monitor**: uses the SvitloBot API to report the on/off tendency for a DTEK group. — [Docker Hub mirror](https://dhub.cyberranges.com/r/petrovoronov/svitlobot-monitor)
  - **Rockbourne/blackout-ua**. — [GitHub](https://github.com/Rockbourne/blackout-ua)
  - GitHub topic "yasno". — [topic](https://github.com/topics/yasno)

**Schedule semantics from utilities and the press**
- DTEK Kyiv Regional Grids (Dec 2024): schedules moved to 30-min intervals, and each queue is split into sub-queues 1.1 and 1.2, 2.1 and 2.2, and so on. — [DTEK press](https://grids.dtek.com/en/media-center/press/onovlyuemo-grafiki-vidklyuchen-za-novim-pidkhodom-dlya-vsiei-kraini--dtek-kiivski-regionalni-elektrome)
- Schedules show 3 zones: guaranteed power, definitely off, and possible outage. A semi-grey block means 30 min without power. — [DTEK "Графіки відключень: де знайти"](https://grids.dtek.com/en/media-center/press/grafiki-vidklyuchen-de-znayti-ta-yak-koristuvatis)
- DTEK says schedule publication is automated and shared with its website, chatbot and partners "through an open API". No endpoint is documented. — [E.DSO DTEK case study (PDF)](https://www.edsoforsmartgrids.eu/content/uploads/2025/10/51.2025_e.dso-success-cases_dtek_there-will-be-light_final.pdf)
- January 2026: DTEK returned to hourly consumer schedules in the Kyiv region while emergency schedules also ran. — [Interfax-Ukraine](https://interfax.com.ua/news/general/1139482.html)
- Yasno CEO (Jan 2026): the country lives with "4.5–5 queues"; with 5 of 6 queues restricted, outages can exceed 16 h a day. — [UNN](https://unn.ua/en/news/ukraine-is-transitioning-to-45-5-queues-of-power-outages-with-possible-blackouts-lasting-up-to-16-hours-yasno-ceo), [Ukrainska Pravda](https://www.pravda.com.ua/eng/news/2026/01/19/8016816)
- The Yasno mobile app shows planned schedules and pushes notifications when today's or tomorrow's schedule changes. — [Google Play](https://play.google.com/store/apps/details?id=com.dsolutions.yasnomobile)
- A Kyiv developer built a service that exports outage schedules to smartphone calendars (ICS-style). — [DOU news](https://dou.ua/lenta/news/integrate-schedules-into-calendar/)

### Inferences
- The `outage-data-ua` format maps directly onto solar_calc's 10-min grid: each hour status expands to 6 steps.
  - `no` → 6 steps without grid; `first` → steps 1–3 off; `second` → steps 4–6 off.
  - `maybe`, `mfirst` and `msecond` → probability-weighted or worst-case options.
- The `preset` weekly template (group × weekday × hour) is effectively a **typical-week outage profile**. It is exactly what a monthly-average-day simulator can use as a "grid availability profile" for a chosen queue.
- The Yasno slot format (start/end in minutes) converts trivially to the same 10-min mask.
- solar_calc could ship a few built-in "scenario" masks, such as 2, 3, 4.5 or 5 of 6 queues off, or a 4h-on/4h-off rotation. That would cover offline use when live data is unavailable. This is a design inference, not something a reviewed project does.

### Gaps
- No official Yasno or DTEK API documentation exists. Endpoints are inferred from third-party code and may change.
- The yaroslav2901/OE_OUTAGE_DATA and gpv-voe-vinnytsia formats were not inspected; they are presumably similar to DTEK's.
- No Ukrenergo machine-readable source (national "number of queues" forecast) was found.
- No project was found that uses outage schedules to **size** a PV + battery system. Only operational pre-charge automations were found.

---

## Q3. Which projects estimate battery degradation / cycle cost (and with what models), and which import real inverter logs (Deye, Victron VRM, Solar Assistant, Growatt) usable for calibration?

### Takeaway
- **Degradation:** dispatch tools use a **flat virtual cost per kWh cycled**: Predbat `metric_battery_cycle` and EMHASS `weight_battery_discharge`. EOS can include non-linear degradation through its genetic algorithm. Physics or empirical **lifetime models** are available as Python libraries: NREL BLAST-Lite (LFP-Gr models, also used by SAM/REopt), PySAM BatteryStateful (LFPGraphite preset, calendar/cycle with rainflow) and TUM SimSES.
- **Real data:** local HA bridges exist for every inverter brand common in Ukraine (Deye, Must, Voltronic/Axpert, Growatt, Victron). Bulk-history routes are Solarman web export (6-month retention), the Victron VRM data-download API (CSV/XLS), SolarAssistant (local history, HA integration) and HA energy-export tools.

### Cited Findings

**Degradation and cycle cost**
- Predbat `metric_battery_cycle` is a "virtual cost" applied to every kWh charged and discharged. The docs example uses 3.5p. Per the FAQ, 2p adds 4p to using the battery, so charging at 20p equates to grid use at 30p. Higher values reduce cycling at the expense of energy cost. — [Predbat customisation](https://springfall2008.github.io/batpred/customisation/), [FAQ](https://springfall2008.github.io/batpred/faq/)
- A user's worked threshold: 15% loss plus a 0.5p cycle cost gives 17.75p, the price below which grid use beats cycling the battery. — [HA community](https://community.home-assistant.io/t/predbat-anyone-have-a-working-apps-yaml-example-for-fox-kh7-inverter/1015045)
- A user reported config: `metric_battery_cycle` 4–6 øre/kWh, `inverter_loss` 5%, `battery_loss` and `battery_loss_discharge` 4%. — [batpred issue #1035](https://github.com/springfall2008/batpred/issues/1035)
- EMHASS `weight_battery_discharge`: a currency/kWh penalty in the cost function, default 0. — [EMHASS config](https://emhass.readthedocs.io/en/latest/config.html)
- EOS: the genetic algorithm allows "non-linear battery degradation" in the simulated fitness. — [EOS docs](https://akkudoktor-eos.readthedocs.io/en/latest/akkudoktoreos/introduction.html)
- **NREL BLAST-Lite** ("Battery Lifetime Analysis and Simulation Tool – Lite"): simplified NREL lifetime models for many Li-ion designs, parameterised from lab data, available in Python or MATLAB. It is used by the System Advisor Model (SAM) and REopt. — [NLR/NREL page](https://www.nlr.gov/research/software/blast-lite--battery-lifetime-analysis-and-simulation-tool---lite), [GitHub NREL/BLAST-Lite](https://github.com/NREL/BLAST-Lite)
  - Install via PyPI (BLAST-Lite; v1.1.x is current). — [PyPI BLAST-Lite](https://pypi.org/project/BLAST-Lite/1.0.3/), [releases](https://github.com/NREL/BLAST-Lite/releases)
  - Example: `from blast import utils, models; cell = models.Lfp_Gr_250AhPrismatic(); cell.simulate_battery_life(utils.generate_example_data())`.
  - Models include a 250 Ah LFP-Gr prismatic cell (from a 2023 J. Energy Storage paper on cells from manufacturers producing >1 GWh/yr) and a Sony-Murata LFP-Gr cell. — [GitHub README](https://github.com/NREL/BLAST-Lite)
  - `degradation_scalar` makes fade faster or slower. Simulations can either conserve energy throughput (DoD grows with age) or keep SoC limits constant.
  - Caveats from the README: trained on 1–3 years of data, so treat results as qualitative; "expected life" under nominal conditions only; pack life is 20–30% shorter than cell life; warranty life is more conservative. — [GitHub README](https://github.com/NREL/BLAST-Lite)
- **PySAM BatteryStateful**: physical models only (thermal, voltage, capacity, lifetime), stepped one timestep at a time. Presets: "LFPGraphite", "LMOLTO", "LeadAcid", "NMCGraphite". — [PySAM BatteryStateful](https://nrel-pysam.readthedocs.io/en/latest/modules/BatteryStateful.html)
  - `life_model` options: 0 = calendar/cycle, 1 = NMC, 2 = LMO/LTO. `calendar_choice` options: none, LithiumIonModel (a, b, c, q0) or a loss table. `cycling_matrix` columns: DoD %, cycle number, capacity %. — [same](https://nrel-pysam.readthedocs.io/en/latest/modules/BatteryStateful.html)
  - The cycle/calendar model uses rainflow counting. — [NREL slides](https://docs.nrel.gov/docs/fy25osti/93555.pdf)
- **SimSES** (TU Munich): Python framework for techno-economic simulation of stationary storage. Degradation comes from "stress characterization" with pluggable aging models. — [PyPI simses](https://pypi.org/project/simses), [openmod wiki](https://wiki.openmod-initiative.org/wiki/SimSES)
  - A 20-year run at 5-min steps takes about 27 min. — [openmod wiki](https://wiki.openmod-initiative.org/wiki/SimSES)
  - The TUM dissertation's ~900-day LFP/C aging tests point to ~20–25% capacity loss and resistance increase over 20 years, depending strongly on storage and inverter sizing. — [TUM dissertation PDF](https://mediatum.ub.tum.de/doc/1434981/1434981.pdf)

**Real inverter data import**
- **Deye/Sunsynk**:
  - davidrapan/ha-solarman is the recommended local Solarman-logger integration; it replaced StephanJoubert/home_assistant_solarman. It works if the logger and firmware allow the local port and a model profile exists. — [marklabs.pl Deye guide](https://marklabs.pl/en/deye-home-assistant-connection-guide/), [StephanJoubert repo](https://github.com/StephanJoubert/home_assistant_solarman), [migration discussion](https://github.com/davidrapan/ha-solarman/discussions/61)
  - Other routes: kellerza/sunsynk (Python library + HA add-on), kbialek/deye-inverter-mqtt, Lewa-Reka/esphome-deye-inverter (Modbus RTU, monitoring + control). — [marklabs.pl](https://marklabs.pl/en/deye-home-assistant-connection-guide/)
  - Developer089/deye-modbus-ha: Modbus TCP, logger port 8899 or gateway port 502. The rusty-bit fork fixes writes with FC16 because Deye rejects FC06. iz3man has another variant. — [Developer089](https://github.com/Developer089/deye-modbus-ha), [rusty-bit](https://github.com/rusty-bit/deye-modbus-ha), [iz3man](https://github.com/iz3man/deye-modbus-ha)
  - The HA core "Solarman" integration (2026.4) does not support Deye. A user reports logger read/write only once every 5 s. — [marklabs.pl](https://marklabs.pl/en/deye-home-assistant-connection-guide/)
  - A DIY ESP32 Deye monitor is described on DOU. — [DOU](https://dou.ua/goto/Cqf1)
- **Voltronic/Axpert** (and rebrands):
  - ned-kelly/docker-voltronic-homeassistant (RS232/USB → MQTT). — [HA community](https://community.home-assistant.io/t/programmatically-read-data-from-your-solar-inverter-voltronic-axpert-mppsolar-pip-voltacon-effekta-etc-and-interface-with-home-assistant-via-mqtt-works-with-rs232-usb/119053)
  - jblance/mpp-solar: Python package with command libraries for PI18 and PI30 protocols; pip or Docker. — [PyPI mppsolar](https://pypi.org/project/mppsolar/)
  - bilalahmadj110/inverter-monitor: Flask dashboard with history and **CSV export**. — [GitHub](https://github.com/bilalahmadj110/inverter-monitor)
- **Must (PV18/PH18/PV1800)**:
  - vladyspavlov/esphome-must-inverter. — [GitHub](https://github.com/vladyspavlov/esphome-must-inverter)
  - kodav/must-esp32-bridge (RS485 → MQTT, slave ID 4, 19200 baud). — [GitHub](https://github.com/kodav/must-esp32-bridge)
  - taHC81/MUST-ESPhome. — [GitHub](https://github.com/taHC81/MUST-ESPhome)
  - mukaschultze/ha-must-inverter. — [GitHub](https://github.com/mukaschultze/ha-must-inverter)
  - fpvo/must-inverter-mon (Node.js; SQLite history; MQTT). — [GitHub](https://github.com/fpvo/must-inverter-mon)
  - andremiller/must-inverter-python-monitor (minimalmodbus). — [GitHub](https://github.com/andremiller/must-inverter-python-monitor/blob/main/inverter_modbus.py)
  - PH18 and PV18 register maps may differ: battery SoC at 44180 versus the 25xxx block. — [gist comment](https://gist.github.com/vladyspavlov/5ac21cb58923482eff8e7bbb2d0854b3)
- **Axioma**: the AXGRID AXIOMA Wi-Fi module offers Modbus TCP for local integration. — [iSolar product page](https://isolar.com.ua/en/product/wi-fi-modul-dlya-invertoriv-axgrid-axioma-energy)
- **Growatt / multi-brand**:
  - robertzaage/GroBro: decodes Growatt NEO/SPF and NOAH MQTT, local or with Growatt cloud. — [GitHub topic listings (search summary)](https://github.com/topics/solar?o=desc&s=updated)
  - mtrossbach/noah-mqtt, Openinvertergateway (ShineWiFi-S firmware) and davidsmfreire/shinemonitor-api (Growatt/SRNE/Voltronic). — [GitHub topics](https://github.com/topics/voltronic), [GitHub topics deye](https://github.com/topics/deye)
  - Solar2MQTT (multi-brand Modbus; unverified). — [pistack.xyz](https://www.pistack.xyz/posts/2026-06-07-self-hosted-solar-inverter-monitors-opendtu-ahoydtu-solar2mqtt/)
- **Solis**: hultenvp/solis-sensor (SolisCloud). — [GitHub discussion](https://github.com/hultenvp/solis-sensor/discussions/71)
- **SolarAssistant**: stores 10+ years of history locally on a 16 GB SD card. — [solar-assistant.io Deye page](https://solar-assistant.io/explore/deye)
  - An official open-source HA integration exists since 2026 (Solar-Assistant/ha_solar_assistant). — [marklabs.pl](https://marklabs.pl/en/deye-home-assistant-connection-guide/)
  - Users say they "can export data from SA", but the format is unverified. — [akkudoktor forum](https://akkudoktor.net/t/deye-12k-hybried-offline/18609?page=2)
- **Solarman cloud**: the app cannot export; use the web portal export at home.solarmanpv.com. Detailed daily data covers the past 6 months. — [Solarman help 1](https://helpcenter.solarmanpv.com/portal/en/kb/articles/can-i-view-daily-detailed-data-and-for-what-period), [Solarman help 2](https://helpcenter.solarmanpv.com/portal/en/kb/articles/i-cannot-view-inverter-data-older-than-6-months)
  - Logging intervals are about 5–10 min. Users report gaps when the logger goes offline, and the newer Sunsynk portal export is weak. — [akkudoktor forum](https://akkudoktor.net/t/deye-12k-hybried-offline/18609?page=2), [4x4community Sunsynk data download](https://www.4x4community.co.za/forum/showthread.php/359050-Sunsynk-data-download)
- **Victron VRM**: the REST endpoint `vrmapi.victronenergy.com/v2/installations/{idSite}/data-download` returns CSV/XLS. Large exports are generated in the background and emailed; users fetch ~7–8 days per request and merge the files. — [Victron community](https://communityarchive.victronenergy.com/questions/212832/vrm-data-history-download.html), [timeout thread](https://communityarchive.victronenergy.com/questions/24838/csv-download-from-vrm-portal-stopped-by-timeout-er.html)
  - Auth: log in, then send the token in an `X-Authorization` header. — [VRM API python example](https://communityarchive.victronenergy.com/questions/116134/vrm-api-python-example.html)
  - Python client: ocf-vrmapi. — [PyPI ocf-vrmapi](https://pypi.org/project/ocf-vrmapi)
  - An MCP server exposes CSV download with a 200-request rolling-window rate limit. — [glama victron-vrm-mcp](https://glama.ai/mcp/servers/gimi-q/victron-vrm-mcp/tools/vrm_download_installation_data)
- **Home Assistant history export**: LucaTNT/export-homeassistant-energy extracts solar production, self-consumption, import and export to Excel/SQLite. — [GitHub](https://github.com/LucaTNT/export-homeassistant-energy)
- **Calibration practice**:
  - Predbat users compare the forecast with actual generation (HA energy tab or inverter portal) and tune PV/load scaling. — [Predbat FAQ](https://springfall2008.github.io/batpred/faq/)
  - Forecast.Solar accepts today's actual kWh to correct today's forecast (Personal plan or higher). — [Forecast.Solar "actual"](https://doc.forecast.solar/actual)
  - battery_sim replays real import/export through a virtual battery. — [battery_sim](https://github.com/hif2k1/battery_sim)

### Inferences
- For solar_calc, the cheapest useful degradation feature is a **per-kWh cycle cost** plus an annual equivalent-full-cycle count from the existing simulation, as in Predbat and EMHASS.
- A stronger option is to feed solar_calc's yearly SoC time series into **BLAST-Lite `Lfp_Gr_250AhPrismatic`** or **PySAM `LFPGraphite`** to get capacity after N years. Either library is pip-installable, but BLAST-Lite adds dependencies (numpy/scipy) to a PySide6 exe build.
- The most practical calibration import format is a generic CSV mapper with timestamp, PV kW/kWh, load, battery SoC and grid import, plus presets for Solarman, VRM, SolarAssistant, HA export and Must/Voltronic monitor CSVs. From that, solar_calc can fit PV scaling (actual/predicted per month), the load profile shape, round-trip efficiency and inverter idle draw.

### Gaps
- The LFP calendar/cycle equations inside BLAST-Lite were not retrieved.
- SolarAssistant's CSV export menu and format were not confirmed.
- Deye Cloud (as opposed to Solarman) export features were not found.
- The `victron-vrm` async PyPI client was mentioned in search results, but its URL was not confirmed.

---

## Q4. Which solar-forecast APIs (Forecast.Solar, Solcast, Open-Meteo) are free and usable from a desktop app, and with what limits?

### Takeaway
Free options, in order of preference for a desktop app:
- **Open-Meteo** is the most generous: no key; free for non-commercial use under 10,000 calls/day, 5,000/h and 600/min; offers GTI irradiance and many weather models. The catch is non-commercial use only.
- **Forecast.Solar Public** needs no key but allows only 12 calls per rolling 60 min per IP, 1 plane, about 1 day ahead and hourly resolution. It also has handy `historic` and `clearsky` endpoints plus horizon/damping options.
- **Solcast Hobbyist** needs a user-owned API key: 10 requests per UTC day, 2 rooftop sites within 1 km, 30-min data, personal use only.

All three are usable for "next 1–3 days" planning. None replaces PVGIS for long-term monthly averages.

### Cited Findings

**Forecast.Solar**
- Public tier: free with no registration or API key; 12 calls per IP per rolling 60 min; 1 plane; +1 day; 1 h resolution. Personal tier: 60 calls per key, rising to 300 and 600 on higher plans. Forecasts update at most every 15 min. — [Forecast.Solar account models](https://doc.forecast.solar/account_models)
- A user with three planes "regularly hit the rate limits". — [HA community PVGIS thread](https://community.home-assistant.io/t/pvgis-integration/607155)
- Endpoints: `estimate` (today + days ahead by plan), `historic` (average production for a day from historical weather) and `clearsky` (theoretical maximum). — [Forecast.Solar API](https://doc.forecast.solar/api)
- Damping: a single value or `damping_morning`/`damping_evening`. — [Forecast.Solar damping](https://doc.forecast.solar/damping)
- Horizon: defaults to the PVGIS horizon; accepts comma-separated degrees; per plane up to 4; `0` disables it. — [Forecast.Solar API](https://doc.forecast.solar/api)
- Actual-production correction (Personal plan or higher) affects only the current day. — [Forecast.Solar actual](https://doc.forecast.solar/actual)
- Operational notes: multi-plane needs Personal Plus; quarterly maintenance returns HTTP 503; responses use local time unless `?time=utc`. — [Forecast.Solar API](https://doc.forecast.solar/api)
- Python async client: `forecast-solar` on PyPI (used by HA core). — [PyPI forecast-solar](https://pypi.org/project/forecast-solar/5.0.0/), [HA Forecast.Solar integration](https://www.home-assistant.io/integrations/forecast_solar/)
- A 2022 forum report says azimuth and kWp seemed ignored in `estimate/watthours`; resolution unknown. — [Forecast.Solar forum](https://forum.forecast.solar/discussion/11/api-estimate-watthours-seems-to-ignore-azimuth-and-kwp-parameters)

**Solcast**
- Hobbyist tier: 10 API requests per UTC day; up to 2 rooftop arrays within 1 km; live estimated actuals and forecasts at 30-min intervals; personal use. — [Solcast docs: hobbyist](https://docs.solcast.com.au/docs/section/rooftop-sites-hobbyist), [Solcast KB](https://kb.solcast.com.au/user-guide-for-solcast-hobbyist-toolkit-account)
- Older accounts had 50 calls/day. Solcast staff advise randomising call times. — [Solcast hobbyist FAQ](https://kb.solcast.com.au/home-hobbyists-faqs)
- HA integration BJReplay/ha-solcast-solar:
  - Sensors for estimate (P50), estimate10 and estimate90; a 14-day forecast with the first 7 days as sensors.
  - Hourly dampening factors 0–1 (automated, simple and granular modes).
  - A "hard limit" so forecasts do not exceed inverter maximum.
  - Not endorsed by Solcast. — [GitHub BJReplay](https://github.com/BJReplay/ha-solcast-solar)
- A companion add-on auto-tunes dampening with no extra Solcast calls; it needs an OpenWeatherMap key. — [HA community](https://community.home-assistant.io/t/solcast-solar-enhanced-built-in-history-automatic-pv-tuning-adaptive-shading-dampening-companion-to-ha-solcast-solar/1013094)

**Open-Meteo**
- Terms: free non-commercial use under 10,000 calls/day, 5,000/hour and 600/minute. Abusers may be blocked. Commercial use requires a paid plan (with API key), and paid plans are exempt from the automated rate limits. — [Open-Meteo terms](https://open-meteo.com/en/terms)
- The rany2 README also cites a 300,000/month cap. — [rany2/ha-open-meteo-solar-forecast](https://github.com/rany2/ha-open-meteo-solar-forecast)
- rany2/ha-open-meteo-solar-forecast is "based on the Forecast.Solar integration but makes use of the Open-Meteo API":
  - Refreshes every 30 min.
  - `damping_morning`/`damping_evening`.
  - `dc_efficiency`, typically ~0.93 (DC wiring, distinct from cell efficiency, which is in the cell-temperature model).
  - Horizon profile file (tab-separated azimuth/elevation, linear interpolation) with a partial-shading option.
  - Multiple arrays and inverter capacity.
  - Azimuth 0–360 with 0 = North. The PyPI library uses 0 = South. — [GitHub README](https://github.com/rany2/ha-open-meteo-solar-forecast), [PyPI open-meteo-solar-forecast](https://pypi.org/project/open-meteo-solar-forecast/)
- User reports: Open-Meteo forecasts are "better than Forecast.Solar (free tier) and on-par (if not slightly better) than Solcast" (anecdotal); some days are underestimated; the author added cloud compensation. — [HA community thread](https://community.home-assistant.io/t/open-meteo-solar-forecast/733073)
- Global tilted irradiance is available, and users compared 10 irradiance models against their production. — [Victron community](https://community.victronenergy.com/t/use-different-weather-model-for-solar-forecast/16998)
- evcc's Open-Meteo solar setup takes azimuth, tilt (declination) and kWp. — [evcc Open-Meteo](https://docs.evcc.io/en/tariffs/open-meteo/)
- The GMH224 fork adds a local weather source for offline forecasting. — [GMH224 fork](https://github.com/GMH224/ha-open-meteo-solar-forecast)
- A Solcast vs Open-Meteo comparison article exists. — [marklabs.pl](https://marklabs.pl/en/pv-forecast-home-assistant/)

**Predbat's use of forecasts**
- Predbat uses P50 with weighting toward P10, and derives PV10/PV90 from ensemble percentiles relative to the median. — [Predbat customisation](https://springfall2008.github.io/batpred/customisation/)

### Inferences
- **Open-Meteo is the best default** for a desktop app: no key, high limits, and GTI computed for the user's tilt/azimuth. The **non-commercial** clause matters if solar_calc is ever sold.
- **Forecast.Solar Public** works as a no-key fallback if solar_calc makes one call per plane per refresh and caches results. Its `historic` endpoint could also serve as an alternative "typical day" source.
- **Solcast** should be optional, with the user's own key, because of its 10-calls/day budget.
- Forecast percentiles (P10/P50/P90) map naturally onto solar_calc's existing "overcast / average / clear" triad.
- Horizon/shading (with the PVGIS horizon as default) and morning/evening damping are cheap model additions. The current app has temperature and wiring losses but no shading.

### Gaps
- Forecast.Solar's exact damping formula and the current Solcast terms beyond the hobbyist page were not retrieved.
- Open-Meteo's exact solar endpoint variable names were not verified, because the site was blocked.

---

## Q5. Which ideas do these projects have that solar_calc lacks and could reasonably adopt (with Ukrainian tariff context)?

### Takeaway
The highest-value additions for a Ukrainian PV + battery sizing tool:
1. A grid-availability mask from real or typical **outage schedules** (DTEK/Yasno formats).
2. **Pre-outage and night-tariff grid charging** with a target SoC and charge power.
3. **Two- and three-zone tariffs** (night ×0.5 / ×0.4).
4. **Separate charge, discharge and inverter losses** plus a **cycle-cost/degradation** estimate.
5. **Import of real monitoring CSV** for calibration (battery_sim-style replay).
6. Optional **short-term forecast mode** (Open-Meteo) with P10/P50/P90.
7. **Export / green-tariff** pricing and payback economics.

### Cited Findings (Ukrainian tariff and export context)
- Household base price is 4.32 UAH/kWh, extended to 31 Oct 2026. — [Fakty, Sept 2026](https://fakty.com.ua/ua/ukraine/ekonomika/20260901-tarif-na-svitlo-u-veresni-2026-roku-chi-zminyatsya-tsini-dlya-ukrayintsiv/)
  - Two-zone metering: night 23:00–07:00 at ×0.5 = 2.16 UAH/kWh; day ×1.0 = 4.32. Three-zone metering: night ×0.4 = 1.73. A multi-zone meter is required. — [same](https://fakty.com.ua/ua/ukraine/ekonomika/20260901-tarif-na-svitlo-u-veresni-2026-roku-chi-zminyatsya-tsini-dlya-ukrayintsiv/)
- **Conflict on the electric-heating discount.** Fakty (Sept 2026) mentions 2.64 UAH/kWh for up to 2,000 kWh/month from 1 Oct to 30 Apr. Thepage reports that from 1 May the government cancelled the heating discounts in favour of a single 4.32 price; that article's year is unclear. — [Fakty](https://fakty.com.ua/ua/ukraine/ekonomika/20260901-tarif-na-svitlo-u-veresni-2026-roku-chi-zminyatsya-tsini-dlya-ukrayintsiv/); contradicted by [thepage.ua](https://thepage.ua/ua/news/novi-pravila-oplati-svitla-detali-tarifiv-z-1-travnya)
- Green tariff for households: NEURC resolutions No. 497/498 of 31 Mar 2026 set new buy-back rates effective 1 Apr 2026. — [Ligazakon](https://biz.ligazakon.net/news/243225_nkrekp-zatverdila-nov-stavki-zelenogo-tarifu-na-ii-kvartal-2026-roku)
- Net billing: bill 9011 (later 9011-д) would replace the green tariff for new household PV. Surplus would be sold at market price and credited against consumption. Its adoption is not confirmed in the sources found. — [thepage.ua](https://thepage.ua/ua/news/kabmin-vnis-zakonoproyekt-pro-zaminu-zelenogo-tarifu-sistemoyu-net-billing), [Interfax GreenDeal](https://interfax.com.ua/news/greendeal/891148.html)
- Yasno Autopilot shows there is commercial demand for day/night-tariff-aware charging with a backup reserve in Ukraine. — [kosht.media](https://kosht.media/v-ukraini-zapustyly-avtomatychne-keruvannia-domashnimy-batareiamy/)

### Inferences: ideas list for solar_calc (each with the project it comes from)
1. **Outage schedule → grid-availability mask in the SoC simulation.** Import outage-data-ua JSON (`fact` for a specific day, `preset` for a typical week per group) or the Yasno slot JSON. Expand `yes/no/first/second/maybe/mfirst/msecond` into 10-min steps. Offer built-in synthetic patterns (e.g. "3 of 6 queues", "4.5–5 queues ≈16 h off") for offline use. Report "hours of house darkness per month" and "outage energy covered".
   - Sources: ha-svitlo-yeah, outage-data-ua, Yasno blackout-service wrappers, and the Yasno CEO's 16 h/day statement.
2. **Pre-outage grid charging.** Before each scheduled outage, charge from grid to a target SoC at a set charge power (or C-rate), finishing X min before the outage. This is the PowMr PR logic. Also add a "reserve SoC" that daytime self-consumption must not go below, as in Predbat `best_soc_keep` and the Yasno Autopilot reserve %.
3. **TOU / two- and three-zone tariffs and night grid charging.** Use a per-step import price vector (EMHASS `load_cost_forecast`) with presets for Ukrainian 2-zone (night ×0.5) and 3-zone (night ×0.4). Add an option to charge at night to SoC X%. Report cost by zone and the saving versus a flat tariff (Yasno Autopilot, batcontrol "fixed zone tariffs", evcc "cheap grid charging").
4. **Arbitrage sanity check with an explicit loss chain.** Replace one constant inverter efficiency with separate charge, discharge and inverter losses (Predbat defaults 3/3/4%). Compute the break-even night price including a cycle cost: `price_night / (η_ch·η_inv²·η_dis) + cycle_cost < price_day`.
5. **Battery degradation / cycle cost.** Option A: a per-kWh cycle cost (Predbat `metric_battery_cycle`, EMHASS `weight_battery_discharge`) plus annual equivalent full cycles. Option B: pass the simulated yearly SoC profile and temperature to BLAST-Lite `Lfp_Gr_250AhPrismatic` or PySAM `LFPGraphite` to estimate remaining capacity after 5/10 years, applying BLAST's 20–30% pack penalty. Then re-run coverage with the faded capacity.
6. **Charge-power taper and temperature curves.** Model reduced charge power near full SoC and in the cold, as in the Predbat `battery_charge_power_curve` and temperature curve. This refines the existing cold derating and C-rate.
7. **Export / green tariff / net billing / zero export.** Add an export price per kWh (EMHASS `prod_price_forecast`), an export limit or zero-export mode (Deye zero-feed-in blueprint, evcc smart feed-in), and import-savings versus export-earnings outputs (battery_sim).
8. **Real monitoring data import and calibration.** Accept CSV from Solarman web export, Victron VRM data-download, SolarAssistant/HA (export-homeassistant-energy), and Must/Voltronic monitor CSV.
   - (a) Fit monthly PV scaling and load scaling (Predbat).
   - (b) Replay real import/export history through a virtual battery to show the savings a battery of size X would have brought (battery_sim).
   - (c) Estimate idle draw and round-trip efficiency from night-time data.
9. **Load profile from history.** Replace or extend the 4 fixed hourly shapes with an imported hourly/weekday profile (Predbat learns from history or a neural network; evcc and EOS use consumption history).
10. **Short-term forecast mode (1–3 days).** "Will my battery last through tomorrow's outages?": Open-Meteo GTI (no key), Forecast.Solar Public (no key, 12/h), optional Solcast key. Show P10/P50/P90 (Predbat, BJReplay Solcast). Cache responses and respect the limits.
11. **Shading/horizon and morning/evening damping.** Horizon profile, defaulting to the PVGIS horizon (Forecast.Solar, rany2 Open-Meteo integration).
12. **Multiple PV planes (E/W, two roofs) and an inverter AC hard limit (clipping).** Forecast.Solar multi-plane, Open-Meteo multi-array, Solcast hard limit.
13. **Deferrable / diverted loads.** Boiler or water heater (iBoost) and EV as schedulable loads that soak up PV surplus (EMHASS, Predbat, evcc).
14. **Plan-table output.** A per-slot table and chart of SoC, grid import/export, cost and outage flags, like the Predbat plan card.
15. **Economics and payback.** Combine zone-tariff savings, export revenue, outage-hours avoided and degradation cost into an annual benefit and a simple payback figure. No reviewed open-source project does sizing payback for Ukraine; this is a design inference.

### Gaps
- None of the reviewed projects models a **generator** (fuel use, start rules) alongside PV + battery, so no prior art was found for that idea.
- It is unclear whether net billing for households is in force in Oct 2026; the status of bill 9011-д was not confirmed.
- The heating-discount conflict above is unresolved.
- No authoritative household green-tariff rate for rooftop solar in 2026 was retrieved, only that NEURC resolutions 497/498 exist.
