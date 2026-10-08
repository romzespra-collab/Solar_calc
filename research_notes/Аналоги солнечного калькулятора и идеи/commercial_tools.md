# Commercial and free (closed-source / web) PV + battery design tools: feature survey and checklist vs solar_calc v1.2.1

Scope: small home PV + battery (off-grid / hybrid / backup), 1-30 kW PV, LiFePO4, hybrid inverters, Ukraine/Europe, state as of Oct 2026.

Method note (applies to all sections): direct page fetching was blocked by the network egress proxy for almost every vendor domain (pvsyst.com, valentin-software.com, homerenergy.com, sma.de, victronenergy.com, JRC, Ukrainian installer sites). All findings below come from web-search result extracts of the cited pages (mostly the vendors' own help/manual pages), not from reading the full pages. Where only third-party or forum sources were available this is flagged.

Legend used in the checklist: Y = documented, P = partial / simplified / only in some editions, - = not found or explicitly absent, ? = could not verify.

---

## Q1. What does each tool offer (inputs, models, outputs) for a home PV + battery system?

### Takeaway
Engineering simulators (PVsyst, SAM, HOMER, PV*SOL, PVGIS) all run at least hourly simulations over a full year or multi-year series, with dedicated battery models (SOC, efficiency, ageing) and outage/generator logic; vendor tools (SMA, Fronius, Huawei, SolarEdge) are free but lock you to one brand and focus on string validation, self-consumption/self-sufficiency and sales reports; consumer and Ukrainian online calculators are mostly "daily Wh x days / (V x DoD x eff)" formulas or monthly-average yield plus payback.

### Cited Findings

#### PVsyst (desktop, commercial; v8.x current)
- Stand-alone pre-sizing inputs: required autonomy (days), required loss-of-load probability (PLOL), battery voltage; the battery is sized for the requested autonomy "accounting for a PV production corresponding to the worst n-days sequence in the year"; monthly table includes required back-up energy — [PVsyst stand-alone preliminary design](https://www.pvsyst.com/help/preliminary-design/stand-alone-system-presizing/stand-alone-system-preliminary-design.html); [PVsyst presizing results](https://www.pvsyst.com/help-pvsyst7/dimensisole_results.htm)
- Pre-sizing uses monthly solar input and "doesn't transmit its values to your system, except for some defaults"; the detailed hourly simulation with real components is the actual check; PVsyst advises starting with a battery close to the (over-evaluated) pre-size and says "It is usually preferable to oversize the PV" because battery cost dominates — [PVsyst stand-alone tutorial v7](https://www.pvsyst.com/pdf/pdf-tutorials/pvsyst-7/pvsyst-tutorial-v7-standalone-en.pdf); [Stand-alone system procedure](https://www.pvsyst.com/help/project-design/stand-alone-systems-definition/stand-alone-system-procedure.html)
- Hidden parameter "SOC minimum threshold" for pre-sizing (forum suggestion to set 30% to cap DoD at 70%; old thread) — [PVsyst forum](https://forum.pvsyst.com/topic/143-stand-alone-systems-pre-sizing/)
- Stand-alone simulation variables: E_Load, E_User, missing energy (load minus energy supplied), solar fraction (E_Solar/E_Load where E_Solar = E_User - E_BkUp), back-up genset energy, run time, fuel consumption, loss-of-load duration — [PVsyst simulation variables: stand alone](https://www.pvsyst.com/help/project-design/results/simulation-variables-stand-alone-system.html). A v7.2.5 sample report defines SolFrac = EUsed/ELoad instead (version difference) — [PVsyst 7.2.5 sample report](https://bdd.pseau.org/outils/ouvrages/ebml_wet_simulation_report_of_solar_powered_chlorination_system_for_mazraat_yachouaa_station_2021.pdf)
- Battery ageing in reports: "Cycles SOW 80.0 to 68.2 %, Static SOW 80.0 to 71.3 %" (state of wear from cycling and from age) — [PVsyst 7.2.5 sample report](https://bdd.pseau.org/outils/ouvrages/ebml_wet_simulation_report_of_solar_powered_chlorination_system_for_mazraat_yachouaa_station_2021.pdf); battery ageing / number-of-cycles parameters in the battery database — [PVsyst battery ageing](https://www.pvsyst.com/help/battery_ageing.htm)
- Charge controller thresholds: genset starts when battery empty and solar insufficient, stops on SOC hysteresis; back-up-on threshold must be above load-disconnect threshold (forum example: genset start/stop 15%/45%, user moved to 30%/55%) — [PVsyst controller thresholds](https://www.pvsyst.com/help-pvsyst7/controller_thresholds.htm); [PVsyst forum genset](https://forum.pvsyst.com/viewtopic.php?t=5109)
- Grid-connected with storage strategies: self-consumption, weak-grid support (needs hourly load profile plus an hourly grid availability/unavailability profile; re-injection of PV surplus configurable), peak shaving and power shifting (grid-oriented, no load profile); battery never exports to grid in self-consumption/weak-grid modes — [PVsyst grid systems with storage](https://www.pvsyst.com/help/project-design/grid-connected-system-definition/grid-systems-with-storage/index.html); [Power shifting](https://www.pvsyst.com/help/project-design/grid-connected-system-definition/grid-systems-with-storage/power-shifting-storage.html)
- Battery model tracks SOC, voltage, losses and ageing ("State of Wear") as function of charge/discharge rate, temperature, depth of discharge — [PVsyst poster on grid-tied storage](https://www.pvsyst.com/pdf/company/publications/posters/simulation_of_grid_tied_pv_systems_with_battery_storage_in_pvsyst.pdf); [PVsyst BESS glossary](https://www.pvsyst.com/help/glossary/pv-system/bess.html)
- Detailed losses: wiring (ohmic, a single global R for the array), module quality, mismatch, soiling, thermal, unavailability; DC ohmic losses and AC losses after inverter are separate — [PVsyst v8 grid tutorial](https://www.pvsyst.com/pdf/pdf-tutorials/pvsyst-8/pvsyst-tutorial-v8-grid-connected-en.pdf); [PVsyst ohmic loss](https://pvsyst.com/help/index.html?ohmic_loss.htm=); [Array losses general](https://www.pvsyst.com/help/project-design/array-and-system-losses/array-losses-general-considerations.html)
- Default mismatch 1% (lowered from 2% in v6); module quality loss default = 1/4 of tolerance spread; Monte-Carlo ageing mismatch tool — [PVsyst mismatch](https://www.pvsyst.com/help/project-design/array-and-system-losses/array-mismatch-losses/index.html); [Module quality](https://www.pvsyst.com/help/project-design/array-and-system-losses/module-quality-losses.html); [Ageing / module degradation](https://www.pvsyst.com/help/project-design/array-and-system-losses/ageing-pv-modules-degradation/index.html)
- Near shading via 3D scene; three electrical-shading modes (2D analytic, approximate by strings/partitions, module layout); far shading from a horizon profile — [PVsyst electrical shading mismatch](https://www.pvsyst.com/help/project-design/shadings/calculation-and-model/electrical-shading-mismatch-loss.html)
- Inverter efficiency: single curve vs input power (up to 8 points, linear interpolation) or three curves at different input voltages with quadratic interpolation on real input voltage; Euro/CEC weighted averages — [PVsyst inverter efficiency model](https://www.pvsyst.com/help/physical-models-used/grid-inverter/inverter-model-efficiency.html); [Euro/CEC efficiency](https://www.pvsyst.com/help/component-database/grid-inverters/grid-inverters-main-interface/grid-inverters-efficiency-curve/european-or-cec-efficiency.html)
- Report includes a loss diagram (waterfall from POA irradiance to AC output) — [third-party guide to the PVsyst loss diagram](https://heavendesigns.in/blog/pvsyst-loss-diagram-interpretation-guide/)
- 2025 patch notes (third-party patch library): 8.0.15 heterogeneous SolarEdge optimizer strings; 8.0.20 fixed a power-shifting storage energy-balance warning — [patch library](https://adaptiva.com/patch-library/1000006321_patch_for_pvsyst)

#### PVGIS (JRC, free web + API; 5.3 production, PVGIS 6 in beta)
- Off-grid (SHS) tool: Off-grid tab and non-interactive `api/SHScalc`; inputs: PV peak power, battery capacity in Wh (nominal full-to-empty), discharge cutoff % (default 40% for lead-acid, e.g. 20% for Li-ion), consumption per day in Wh, optional 24 hourly fractions (sum = 1) repeated every day; default profile puts most consumption in the evening — [PVGIS off-grid tool](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-tools/grid-pv-systems_en); [PVGIS 5 user manual](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en)
- Off-grid model: hour-by-hour over the time series; PV surplus to battery; when full, energy counted as not captured — [PVGIS off-grid tool (5)](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-tools/grid-pv-systems_en)
- Off-grid outputs: % days with full battery (f_f), % days with empty battery, average energy not captured (E_lost), average energy missing, monthly values of each, and a 10-value histogram of battery charge state — [PVGIS off-grid tool](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-tools/grid-pv-systems_en)
- PVGIS applies a static percentage loss to the whole system (forum observation) — [DIY Solar Forum](https://diysolarforum.com/threads/multi-array-performance-calculator.54631/)
- Grid-connected: default 14% system loss (cabling, inverter, soiling/snow), module ageing NOT included; built-in DEM horizon (GRASS r.horizon, SRTM/GTOPO30) or user horizon file read clockwise from north — [PVGIS 5.3 release](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-releases/pvgis-53_en); [PVGIS user manual](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en)
- Grid-connected "PV electricity price": PV system cost, interest %/yr, lifetime yrs; fixed-rate annuity (mortgage-like) LCOE with built-in O&M of 2%/yr of initial cost; API returns it only with pvprice=1 — [PVGIS grid-connected](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-tools/grid-connected-pv_en)
- Data: PVGIS 5.3 uses SARAH-3 and ERA5 2005-2023; ERA5 hourly ~0.28 deg global, used for temperature/wind everywhere; TMY generator from SARAH3/NSRDB/ERA5 — [PVGIS 5.3 release](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-releases/pvgis-53_en); [PVGIS TMY](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-tools/pvgis-typical-meteorological-year-tmy-generator_en)
- Hourly series via API (pvlib `get_pvgis_hourly` with `usehorizon`, `userhorizon`, `loss`, `pvcalculation`) — [pvlib docs](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.iotools.get_pvgis_hourly.html)
- PVGIS 6 (beta as of 2026): rewritten in Python (FastAPI, CLI, code on code.europa.eu), multi-section systems, bifacial modules, several solar-position algorithms, improved tilt/azimuth optimisation, SARAH-3 + ERA5/ERA5-Land 2014-2024 (one page says 2013-2024), MCP interface for AI agents in development; yields within 15 kWh/kWp of 5.3 — [About PVGIS 6](https://photovoltaic-geographic-information-system.ec.europa.eu/en/about-pvgis-6); [PVGIS status report 2025](https://publications.jrc.ec.europa.eu/repository/handle/JRC145327); [PVGIS 6 dataset report](https://publications.jrc.ec.europa.eu/repository/handle/JRC145834)

#### NREL SAM (free desktop + PySAM; docs now at sam.nlr.gov / natlabrockies.github.io)
- Battery: capacity fade split into calendar and cycling, replacements computed from performance; outage simulation answers "Will this system adequately provide backup during an outage?" — [NREL "How to Model Batteries" slides](https://docs.nrel.gov/docs/fy25osti/93555.pdf)
- Degradation-aware price-signal dispatch using 24-h PV/load forecasts, degradation data and utility rates; behind-the-meter batteries modelled as unable to export (in that version) — [NREL 2021 paper](https://docs.nrel.gov/docs/fy21osti/79575.pdf)
- Grid outage page: critical load as % of load or kW array; outage times specified by user, or "Calculate hours of autonomy for a hypothetical outage"; based on REopt resilience — [SAM Grid Outage help](https://samrepo.nrelcloud.org/help/grid_outage.html); [SAM forum](https://sam.nrel.gov/forum/forum-general/3903-autonomy-outage-probability-output-metrics.html)
- PV: CEC and Sandia module libraries, CEC inverter database with Sandia-type empirical inverter model, user datasheet entry; single inverter type per run — [SAM inverter help](https://samrepo.nlr.gov/help/pv_inverter.html); [SAM forum DB](https://sam.nrel.gov/forum/forum-general/2768-pv-modules-and-inverters-not-in-database.html)
- Detailed PV model has 3D shade calculator, snow loss model (needs snow depth data), sub-hourly simulation; degradation linear (since 2021), applied to DC in lifetime mode — [SAM PV technical reference update](https://docs.nrel.gov/docs/fy18osti/67399.pdf); [SAM degradation help](https://samrepo.nrelcloud.org/help/degradation.html); [SAM release notes](https://natlabrockies.github.io/SAM/doc/reference/release_notes.html)
- Weather: NSRDB download inside SAM incl. sub-hourly files; time resolution inferred from row count (35,040 rows = 15 min) — [SAM location and resource](https://samrepo.nrelcloud.org/help/pv_location_and_resource.html); [SAM weather data](https://sam.nlr.gov/weather-data)

#### HOMER Pro / HOMER Grid (UL Solutions, commercial)
- Optimises all component combinations, ranks feasible systems by net present cost (capex, replacements, O&M, fuel, financing); sensitivity analysis over resource/price ranges — [HOMER Pro](https://www.homerenergy.com/products/pro/index.html); [HOMER Pro student guide 3.14.4](https://www.saarcenergy.org/wp-content/uploads/2021/11/HOMER-Pro-Foundations-Student-Training-Guide-ver20211125.pdf)
- Capacity shortage constraint (e.g. 5% annual = ~438 h); any unmet load makes a system infeasible unless max annual capacity shortage > 0 — [HOMER capacity shortage](https://www.homerenergy.com/products/pro/docs/3.15/capacity_shortage.html); [Unmet load](https://homerenergy.com/products/pro/docs/latest/unmet_load.html)
- Battery models: idealized, kinetic (two-tank), and Modified Kinetic Battery Model (Advanced Storage module): series resistance, temperature effects, calendar + cycle degradation with rainflow counting, based on NREL BLAST; lifetime fade only in multi-year mode; storage degradation tables and augmentation in newer releases — [HOMER Advanced Storage](https://homerenergy.com/homer-pro/advanced-storage); [MKBM](https://www.homerenergy.com/products/pro/docs/3.15/modified_kinetic_battery_model.html); [Storage FAQs](https://homerenergy.com/docs/knowledgebase/article/storage-faqs/); [HOMER Pro releases](https://homerenergy.com/homer-pro/releases)
- Outputs: renewable fraction, renewable penetration, unmet load and fraction, excess electricity, generator fuel and hours; time step configurable down to 1 min for imported data — [Renewable fraction](https://homerenergy.com/products/pro/docs/latest/_renewable_fraction.html); [Electrical outputs](https://homerenergy.com/products/pro/docs/latest/electrical_outputs.html); [Unmet load fraction](https://homerenergy.com/products/pro/docs/latest/unmet_load_fraction.html)
- HOMER Grid: library of 50,000+ US tariffs, demand-charge limiting, TOU arbitrage, resilience module (extra simulation of a user-specified outage window, outage cost folded into COE/NPC), no stochastic reliability analysis — [HOMER Grid](https://homerenergy.com/homer-grid); [How HOMER Grid models resilience](https://homerenergy.com/products/grid/docs/latest/how_homer_grid_models_resilience.html); [Demand response](https://homerenergy.com/products/grid/docs/latest/demand_response.html)

#### PV*SOL / PV*SOL premium (Valentin, commercial; 2026 edition released Nov 2025)
- Component DB counts conflict across sources: a 2025-era listing surfaced by search says "over 26,000 PV modules, 7,500 inverters, 5,500 battery systems" (exact listing not identified); a download site cites 12,500+ batteries for 2026 and a review cites 16,000 — treat as order-of-magnitude only — [PV*SOL premium page](https://valentin-software.com/en/products/pvsol-premium/); [Filehippo listing](https://filehippo.com/download_pvsol-premium-2025/); [review](https://www.heavengreenenergy.com/blog/pvsol-review)
- 3D design up to 7,500 mounted / 10,000 roof-parallel modules; shading simulation and shadow frequency; PVGIS climate data updated to SARAH3 (2025) — [PV*SOL premium 2025 news](https://valentin-software.com/en/product-news-blog-en/pvsol-premium-2025-available-now/)
- Off-grid: energy order PV -> load, battery down to min SOC, then generator; surplus PV charges to max SOC; generator controlled by SOC; load shedding by SOC thresholds in two time windows — [PV*SOL off-grid calculation](https://help.valentin-software.com/pvsol/en/calculation/offgrid-systems/); [Backup generator](https://help.valentin-software.com/pvsol/en/pages/backup-generator/)
- Off-grid battery sizing from an autonomy time and a design period (radiation basis), assumes max discharge to 20% of capacity, ~2 kWh battery per kW battery-inverter in cluster defaults — [PV*SOL system configuration](https://help.valentin-software.com/pvsol/en/pages/battery-inverter-and-battery/system-configuration/)
- Limitation (forum, ~19 months old): stand-alone tool supports only AC-coupled batteries; DC-coupled hybrid inverter off-grid must be faked as grid-connected with zero feed-in — [Valentin forum](https://forum.valentin-software.com/topic/10572-off-grid-system-with-battery)
- Circuit diagram auto-generated, string cable and AC/DC cable losses per inverter; cable plan with cut list (lengths, diameters) for roof-parallel arrays — [PV*SOL premium page via search](https://valentin-software.com/en/products/pvsol-premium/); [UK reseller](https://www.solardesign.co.uk/pvsol-premium.php)
- 2025: Renusol PV-Configurator interface (structural calc, mounting plan, parts list); DC-coupled batteries drawn on DC side of hybrid inverters; 2026: customer presentation export to PDF and DOCX — [Renusol](https://www.renusol.com/en/our-company/news/details/pv-sol-premium-2025-now-with-interface-to-renusol-pv-configurator-3-0/); [Solar Power World Nov 2025](https://www.solarpowerworldonline.com/2025/11/pvsol-adds-new-customer-presentation-feature-in-latest-software-update/)
- Forum note: PV*SOL accounts for inverter clipping when DC > AC, unlike some simple calculators — [GreenPowerTalk FAQ](https://greenpowertalk.tech/threads/faq-programi-rozraxunku-kalkuljatori.512/)

#### Victron tools (free)
- MPPT calculator (mppt.victronenergy.com): inputs series/strings, min and max site temperature, cable length and cross-section, panel Pmax/Voc/Isc/Vmp/Imp and V/I temperature coefficients; shows PV voltage at min temperature vs MPPT max, charge current, PV power ratio; wizard, share links, export, current/voltage graphs even when no MPPT matches — [Victron MPPT calculator](https://mppt.victronenergy.com/); [Victron Professional news](https://professional.victronenergy.com/news/detail/268/)
- Community reports: worked example 40.8 V Voc, -0.26%/K, -30 C gives 93.3 V for 2S; a case where calculator predicted 254 V at -20 C for a 250 V controller; doubts on Vmin formula — [Victron community](https://community.victronenergy.com/t/mppt-sizing-at-upper-voltage-limit/61861); [equation check](https://communityarchive.victronenergy.com/questions/304138/mmpt-calculator-equation-check.html)
- Victron Toolkit app: voltage drop for DC, AC 1-phase and 3-phase with safety warnings and list of matching cable sizes; LED code decoding; inverter/charger temperature derating; no battery sizing — [Introducing the Victron Toolkit app (2024)](https://www.victronenergy.com/blog/2024/09/04/introducing-the-victron-toolkit-app/); [Google Play](https://play.google.com/store/apps/details?id=nl.victronenergy.victronledapp)
- Victron off-grid page offers a "system planner" to roughly calculate solar array, battery and inverter size (inputs not verified) — [Victron off-grid home](https://www.victronenergy.com/markets/off-grid/family-home)

#### SMA Sunny Design (free web)
- Plans complete energy systems; key figures on self-consumption and self-sufficiency in a comparison of alternatives; UI shows degree of self-sufficiency and annual battery cycles; batteries for peak shaving + self-consumption "multi-use" (peak shaving in PRO tier) — [Sunny Design](https://www.sma.de/en/products/apps-software/sunny-design); [SMA Energy System Home design](https://manuals.sma.de/SI-HoMan-PL/en-US/3310319371.html)
- Cable sizing (detailed planning) calculates relative power loss for chosen cross-section; SMA recommends < 1% at rated operation; minimum cross-section configurable since v3.20 — [Sunny Design user manual](https://files.sma.de/downloads/SD3-SDW-BA-en-26.pdf)
- Checks: max system voltage per MPP tracker (v5.50), nominal power ratio, warning if max grid connection load exceeded (v5.60) — [Sunny Design user manual](https://files.sma.de/downloads/SD3-SDW-BA-en-26.pdf); [SMA blog oversizing](https://www.sma-sunny.com/en/7-reasons-why-you-should-oversize-your-pv-array-2/)
- Off-grid (Sunny Island) design guide: generator rating 80-120% of inverter output — [SMA off-grid design guide](https://files.sma.de/downloads/OffGrid-System-PL-en-27.pdf)

#### Fronius Solar.creator (free web)
- Automatic string sizing, shadow analysis, energy storage integration (BYD, Fronius Reserva); heating integration; PDF report with cost effectiveness and energy-balance optimisation — [Fronius Verto support](https://www.fronius.com/en/help-center/solar-energy/solar-inverters/support-verto); [Fronius Solar.creator FAQ](https://www.fronius.com/en/faq-online-tools/faq-solar-energy/solarcreator); [Fronius configurator](https://www.fronius.com/en-us/usa/solar-energy/installers-partners/products-solutions/monitoring-digital-tools/design-pv-system-solar-configurator)
- Battery sizing via self-sufficiency saturation (example: 12.6 kWh already reaches max self-sufficiency) — [Fronius AU blog 2026](https://blog.fronius.com/solar-energy-australia/2026/04/07/choosing-the-right-solar-battery-for-your-home/)

#### Huawei FusionSolar SmartDesign 2.0 (free web, Huawei-only)
- Satellite-view layout, auto module layout, auto inverter/optimizer/ESS selection and cabling from module count and target capacity ratio; residential limit 3 inverters (10 in Japan) — [SmartDesign manual: electrical design](https://support.huawei.com/enterprise/en/doc/EDOC1100257167/bc233624/electrical-design)
- ESS capacity design: choose planning objective, enter costs, one-click automatic ESS design comparing benefits for several capacities; TOU price input; "Support Power Backup" option after loads defined — [SmartDesign datasheet](https://solar.huawei.com/download?p=%2F-%2Fmedia%2FSolar%2Fdatasheet%2FFusionSolar_SmartDesign_2_0.pdf); [SmartDesign 2.0 PDF](https://okgroupsrl.com/wp-content/uploads/2025/10/Smart-design-2.0.pdf)
- Report: basic info, 3D overview + device list, electricity bill before/after PV or PV+ESS, monthly grid-power curve, economic benefits (payback), energy distribution, module layout — [SmartDesign: generating a report](https://support.huawei.com/enterprise/en/doc/EDOC1100257167/c42f7784/generating-a-report); [SmartDesign FAQ](https://support.huawei.com/enterprise/en/doc/EDOC1100257167/58e51a54/faqs)

#### SolarEdge Designer (free web, SolarEdge-only)
- Battery backup app note: user sets minimum hours of backup, % of total consumption available for backup, and backup power; hourly model starting from full usable capacity; minimum battery count to meet self-consumption and storage floors — [SolarEdge backup time application note](https://knowledge-center.solaredge.com/sites/kc/files/se-designer-battery-backup-time-application-note-eng.pdf)
- Continuous validation of voltage limits, string sizing, optimiser count, unbalanced strings; 3D roof model + tree shading; BOM and performance summary export; DXF export to AutoCAD for SLD; no native SLD or wire sizing (competitor reviews); DNV validation within 1% of PVsyst; P50 only — [SolarEdge Designer](https://www.solaredge.com/us/products/software-tools/designer); [What's new](https://marketing.solaredge.com/solaredge-designer-0-20); [SurgePV review](https://www.surgepv.com/reviews/solaredge); [Qbits review](https://qbitsenergy.com/blog/solaredge-designer-review/)

#### OpenSolar (free installer platform)
- Usable capacity = nameplate x max DoD; charge/discharge rate caps (excess PV exported); control schemes "Self-consumption (load-following)" (default) and "Minimize Grid Import Cost" (TOU) — [How OpenSolar models battery storage](https://support.opensolar.com/hc/en-us/articles/12382460685455-How-OpenSolar-Models-Battery-Energy-Storage); [Battery control scheme](https://support.opensolar.com/hc/en-us/articles/12447137853071-How-to-create-and-apply-a-battery-control-scheme)
- Battery Design Assistant: optional backup requirements by appliance list or continuous/peak kW; shows grid independence, self-consumption, savings; SAM methodology option; UK MCS MGD 003 self-consumption (cap 95%) — [Battery Design Assistant](https://support.opensolar.com/hc/en-us/articles/10632948081551-Battery-Design-Assistant-on-OpenSolar-UK-AU-US); [MCS calculator](https://support.opensolar.com/hc/en-us/articles/12362712299151-How-to-use-the-MCS-calculator)
- Auto-populated SLD with strings, inverters, batteries — [OpenSolar SLD](https://support.opensolar.com/hc/en-us/articles/12354314183567-How-to-use-the-Single-Line-Diagram-SLDs)

#### Aurora Solar (commercial SaaS)
- Backup duration in days for three tiers (essentials / appliances / whole home) from hourly load, hourly production, backed-up % of load, usable capacity and round-trip efficiency; reported as P90; backup reserve SOC (e.g. 20%) — [Aurora backup duration calculations](https://help.aurorasolar.com/hc/en-us/articles/360055738673-Backup-Duration-Calculations); [Work with storage](https://help.aurorasolar.com/hc/en-us/articles/21146255023891-How-to-Work-with-storage-in-Aurora)
- Energy arbitrage vs self-consumption (falls back to self-consumption if no monetary benefit); assumes 2%/yr battery capacity degradation — [Aurora energy arbitrage](https://help.aurorasolar.com/hc/en-us/articles/28998198908563-Understanding-Storage-Modeling-for-Energy-Arbitrage)
- Financials: payback, NPV, lifetime savings, LCOE, cashflow chart; hourly simulation against rate, net metering and export rules; panel degradation, rate escalation, incentives, financing — [Aurora financial analysis overview](https://help.aurorasolar.com/hc/en-us/articles/51752305485715-Financial-analysis-Overview)
- Circuit table: OCPD, conductor type, terminal temp rating, EGC size, conduit, length, voltage drop; SLD editor (Europe only per help) — [Aurora SLD editor](https://help.aurorasolar.com/hc/en-us/articles/44152078845843-Single-Line-Diagram-Editor); [Instant plan sets](https://help.aurorasolar.com/hc/en-us/articles/33543611295379-Instant-Plan-Sets)
- HelioScope (commercial) gained integrated BESS modeling in June 2026 — [pv magazine USA](https://pv-magazine-usa.com/2026/06/23/aurora-adds-integrated-storage-modeling-to-helioscope-commercial-solar-design-software/)

#### Deye / Growatt / Sofar
- No public Deye/Growatt/Sofar online design/sizing tool was found; Deye's string-sizing article asks users to send datasheets, min/max temperatures, roof layout and backup needs to Deye — [Deye blog](https://deye.com/blog/solar-string-sizing-how-voltage-and-temperature-affect-inverter-selection/); a glossary claims Growatt and Deye publish string sizing tools but without links (unverified) — [Qbits glossary](https://qbitsenergy.com/glossary/string-sizing/)
- Third-party Deye configuration guide: "weakest component sets the ceiling" (e.g. battery allows 135 A but cables 100 A -> set 100 A) — [Wattuneed Deye manual 2026](https://www.wattuneed.com/en/deye-hybrid-inverter-configuration-complete-engineering-manual-2026.htm)

#### Consumer off-grid calculators (US/EU brands)
- altE: battery = daily load x autonomy / DoD (example 10 kWh/day, 2 days, 50% DoD -> 40 kWh); lithium example 10 kWh x 1.2 (80% DoD) x 1.05 inefficiency = 12.6 kWh; inputs monthly kWh; sizes battery, PV watts, charge controller — [altE off-grid sizing calculator](https://www.altestore.com/pages/off-grid-solar-system-sizing-calculator)
- Renogy: appliance list with watts and hours/day, consumption box, recommended components, saved configurations with account — [Renogy calculator how-to](https://www.renogy.com/blogs/archive/solar-calculator-how-to)
- EcoFlow: consumption, backup duration, battery specs -> capacity and usable capacity — [EcoFlow blog](https://energy.ecoflow.com/us/blog/solar-battery-calculator); Bluetti guide divides by 0.90 for inverter loss and adds motor surge — [Bluetti guide](https://www.bluettipower.com/blogs/buying-guide/best-solar-generators-for-home-backup)
- Northern Arizona Wind & Sun / Backwoods load worksheets: watts x hours/day per appliance; design for December or the worst month; 3 days reserve, max 50% depletion (lead-acid) — [Backwoods worksheet](https://backwoodssolar.com/learning-center/off-grid-load-worksheet/); [NAWS load evaluation](https://www.solar-electric.com/learning-center/electrical-load-evaluation-calculation.html/)
- Wholesale Solar calculator: not found in search (see Gaps).

#### Ukrainian / Russian online calculators
- Ultrasolar (UA): inverter power, LiFePO4 capacity, BMS discharge current, autonomy time; includes starting currents; ready kits with prices — [Ultrasolar calculator](https://ultrasolar.com.ua/calculator-invertora-ta-batarey-lifepo4)
- Akvadim (UA shop): outage schedule input (e.g. 4 h off / 2 h on), inverter efficiency 90-92%, surge currents, Gel/AGM/LiFePO4 discharge specifics (shop claim) — [Akvadim backup calculator](https://akvadim.com.ua/calculator/backup-power)
- akumulyator.center, Powercom, LogicPower, Deps, Volter, RBC: inverter/UPS battery capacity or runtime from load W, hours, efficiency, system voltage — [akumulyator.center](https://akumulyator.center/invertori/akumulyator-dlya-invertora/); [Powercom](https://powercom.ua/kalkulyator-dlya-rozrahunku); [LogicPower](https://logicpower.ua/ua/calculator); [Volter](https://volter.ua/uk/kalkuljator-rascheta-vremeni-raboty-ibp/)
- Vistan Group (UA): region, tilt, Net Billing, battery 0/5/10/20/30/50 kWh; monthly and annual generation, consumption coverage, battery autonomy in hours, payback at household tariff 4.32 UAH — [Vistan calculator](https://vistan.group/calculator)
- Atmosfera (UA): needed power, savings over years, whether to buy a battery now or later; admits engineering calculation needs hourly modelling, seasonality, degradation, inverter limits — [Atmosfera calculator](https://www.atmosfera.ua/for-home/kalkulyator-sonyachnyh-stantsiy-dlya-domu); [Atmosfera article](https://www.atmosfera.ua/media/yak-rozrahuvati-sonyachnu-elektrostanciyu)
- Keyvolt, Xolar, SWE, Generacia, SolarMax: power, tariff, region (or average Ukrainian yield), cost, annual generation, savings, payback; SWE uses tilt and azimuth; Generacia states results are "NOT exact" — [Keyvolt](https://keyvolt.com.ua/calculator/); [Xolar](https://xolar.com.ua/kalkulyator/); [SWE](https://swe.kyiv.ua/calculator); [Generacia](https://generacia.energy/-kalkuljator/); [SolarMax](https://solarmax.in.ua/info/okupnist-ses)
- Sanlarix (UA): 5-step cost/payback calculator; commercial examples use grid 7 UAH/kWh vs net billing 3 UAH/kWh with NPV/IRR over 25 years — [Sanlarix calculator](https://sanlarix.com.ua/kalkulyator/); [Sanlarix industrial](https://sanlarix.com.ua/promyslova-ses-dlya-vyrobnycztva/)
- calculator.cec.in.ua (UA): map point or settlement -> PVGIS 6; annual, monthly-average and per-kW yield; compares orientations and tilts — [GreenPowerTalk thread](https://greenpowertalk.tech/threads/novij-ukrajinskij-kalkuljator-virobitku-sonjachnoji-stanciji-tochno-najkraschij.2304/)
- calculator.bdf.gov.ua (state Business Development Fund, KfW/EU program for SMEs): power, investment, mounting area, annual yield, savings UAH, payback, CO2 — [BDF calculator](https://calculator.bdf.gov.ua/)
- Russian: Reenergo (map location, panel power, daily consumption, battery parameters -> runtime without grid and sun; winter/summer appliance list), stk-svoydom (days of autonomy -> panels, battery, inverter, controller), Helios-house (assumes due south), Solarmsk (12/24/48 V LiFePO4/AGM, S x P layout), Betaenergy (warns winter shortfall, recommends generator) — [Reenergo](https://reenergo.ru/online-sun-calculator/); [stk-svoydom](https://stk-svoydom.ru/kalkulyatory/raschet-solnechnykh-batarej); [Helios-house](https://www.helios-house.ru/on-line-kalkulyator.html); [Solarmsk](https://solarmsk.ru/kalkulyatory-i-kp/); [Betaenergy](https://www.betaenergy.ru/calculator/)

### Inferences
- solar_calc already sits between the consumer/installer calculators and the engineering simulators: its DC-side electrical modelling (three DC cable segments, Cu/Al, temperature, contact quality, ПУЭ ampacity, MPPT efficiency vs Vin/Vbat, MPPT self-consumption, battery cold derating) is more detailed than anything found in PVsyst (single global R), Sunny Design (relative power loss only), Victron Toolkit (voltage drop only) or any online calculator.
- Its biggest modelling gap relative to PVsyst/PVGIS/SAM/HOMER is the time base: an "average day per month" cannot produce LOLP, SOC histograms, days-full/empty statistics, or realistic multi-day winter deficits, which all those tools derive from hourly multi-year or TMY series.
- PV*SOL's stand-alone module reportedly cannot model DC-coupled hybrid inverters off-grid; this is precisely the typical Ukrainian Deye/Must/Voltronic-style setup that solar_calc targets — a niche where solar_calc is structurally better suited.

### Gaps
- Could not open any vendor page in full (egress blocked); details rely on search extracts. Exact current UI fields for Sunny Design, Fronius Solar.creator, Victron system planner and PV*SOL 2026 were not verified.
- Wholesale Solar calculator, Sofar design tool, and Growatt/Deye official design tools: no reliable source found.
- PV*SOL battery ageing model in the current version: only a PV*SOL 5.0-era document mentions degradation; not confirmed for 2026.

---

## Q2. How do tools size batteries for autonomy and for backup during outages?

### Takeaway
Three families: (1) rule-of-thumb "days of autonomy x daily load / (DoD x efficiency)" (altE, consumer and UA/RU calculators, PVsyst/PV*SOL pre-sizing); (2) statistical reliability from hourly multi-year simulation — LOLP / unmet-load fraction / % days empty / SOC histogram (PVsyst, PVGIS SHS, HOMER); (3) outage-resilience simulation — user-defined outage windows or an outage starting at every hour of the year, with a critical-load fraction, reported as hours survived or probability (SAM/REopt, HOMER Grid, Aurora P90 days, SolarEdge minimum backup hours, PVsyst weak-grid availability profile, Akvadim outage schedule).

### Cited Findings
- PVsyst pre-sizing: autonomy days + PLOL target; battery sized for the worst n-day sequence; PLOL is % of time load not met (academic use: 2-10% typical for RE systems) — [PVsyst presizing](https://www.pvsyst.com/help/preliminary-design/stand-alone-system-presizing/stand-alone-system-preliminary-design.html); [Ali et al. study using PVsyst](https://pdfs.semanticscholar.org/d730/d261db206bddaee03a9d8062e197d3818c88.pdf)
- PVsyst simulation reports loss-of-load time fraction (sample: 0.1%) and missing energy — [PVsyst 7.2.5 sample report](https://bdd.pseau.org/outils/ouvrages/ebml_wet_simulation_report_of_solar_powered_chlorination_system_for_mazraat_yachouaa_station_2021.pdf)
- PVsyst weak-grid strategy uses an hourly grid availability profile to simulate scheduled/unscheduled outages — [PVsyst grid systems with storage](https://www.pvsyst.com/help/project-design/grid-connected-system-definition/grid-systems-with-storage/index.html)
- PVGIS SHS: % days battery full, % days empty, energy not captured, energy missing, SOC histogram (10 bins), monthly breakdown — [PVGIS off-grid](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-tools/grid-pv-systems_en)
- HOMER: maximum annual capacity shortage constraint, unmet load fraction — [HOMER capacity shortage](https://www.homerenergy.com/products/pro/docs/3.15/capacity_shortage.html)
- SAM/REopt: 8,760 outage cases (one starting at each hour) -> hours critical load sustained; example "72% probability of meeting the critical load during a 7-day outage"; critical load % strongly drives size — [REopt resilience tutorial](https://docs.nlr.gov/docs/fy20osti/76678.pdf); [SAM Grid Outage](https://samrepo.nrelcloud.org/help/grid_outage.html)
- HOMER Grid: extra simulation for user-specified outage period per design; no stochastic reliability — [HOMER Grid resilience](https://homerenergy.com/products/grid/docs/latest/how_homer_grid_models_resilience.html)
- Aurora: backup duration P90 (90% of days last longer) for three load tiers; backup reserve SOC — [Aurora backup duration](https://help.aurorasolar.com/hc/en-us/articles/360055738673-Backup-Duration-Calculations)
- SolarEdge Designer: min backup hours, % of consumption to back up, backup power; hourly simulation from full battery — [SolarEdge app note](https://knowledge-center.solaredge.com/sites/kc/files/se-designer-battery-backup-time-application-note-eng.pdf)
- PV*SOL off-grid: autonomy time + design period; discharge to 20% — [PV*SOL system configuration](https://help.valentin-software.com/pvsol/en/pages/battery-inverter-and-battery/system-configuration/)
- Huawei: ESS capacity recommendation by comparing economic benefit of several capacities under a planning objective (cost-driven, not reliability-driven) — [SmartDesign datasheet](https://solar.huawei.com/download?p=%2F-%2Fmedia%2FSolar%2Fdatasheet%2FFusionSolar_SmartDesign_2_0.pdf)
- Fronius/SMA: battery sized by self-sufficiency saturation; SMA example: battery capacity matters more than battery-inverter rating for self-sufficiency; smaller inverter acceptable if no backup needed — [Fronius AU blog](https://blog.fronius.com/solar-energy-australia/2026/04/07/choosing-the-right-solar-battery-for-your-home/); [SMA sizing blog](https://www.sma-sunny.com/en/sizing-a-storage-system-inverter-power-vs-battery-capacity/)
- Rule-of-thumb formula used by consumer tools: Ah = daily Wh x days / (V x DoD x ~0.9); autonomy 2-3 days typical, 5+ for cloudy climates; LiFePO4 80-90% DoD vs lead-acid 50% — [Off Grid Authority](https://offgridauthority.com/off-grid-solar-calculator/); [altE](https://www.altestore.com/pages/off-grid-solar-system-sizing-calculator); [wind-solar.ru](https://www.wind-solar.ru/blogs/blog/kak-rasschitat-solnechnye-batarei)
- UA: Akvadim models an outage schedule (hours off / hours on); Vistan reports autonomy in hours for chosen battery; Ultrasolar includes BMS discharge current and starting currents — [Akvadim](https://akvadim.com.ua/calculator/backup-power); [Vistan](https://vistan.group/calculator); [Ultrasolar](https://ultrasolar.com.ua/calculator-invertora-ta-batarey-lifepo4)
- Ukraine 2026 context: hourly outage schedules reintroduced in several regions on 8 Oct 2026; schedule format by queue (e.g. 1:00-2:00, 7:30-8:30, 13:30-14:30, 19:30-21:00); schedules not applied during emergency outages — [Telegraf Poltava schedule](https://www.telegraf.in.ua/blackout/na-poltavshhyni-8-zhovtnya-vymykatymut-svitlo-grafik-dlya-vsih-cherg.html); [alerts.org.ua](https://alerts.org.ua/)

### Inferences
- solar_calc's "no-grid/outage mode" covers the whole period; the competitive features to add are (a) a per-queue daily outage schedule mask (0/1 per hour or 10-min step) as in Akvadim / PVsyst weak-grid, (b) a critical-load fraction (SAM, Aurora, SolarEdge), and (c) a REopt-style "outage starting at every step" survival curve, reported as hours survived (P50/P90) per month — feasible even on solar_calc's current average-day basis, but much more credible on hourly series.
- PVGIS-style statistics (% days full / empty, energy not captured / missing, SOC histogram) are cheap to add once an hourly multi-year loop exists, and match what Ukrainian users ask ("will it last the winter?").

### Gaps
- No source found on how Wholesale Solar or Victron's system planner choose autonomy days; HOMER Grid's battery sizing optimiser internals not documented in the extracts.

---

## Q3. What economic outputs do the tools provide?

### Takeaway
All engineering simulators and installer platforms compute payback, NPV and LCOE with tariff structures; residential-focused tools add bill-before/after, self-consumption ratio and self-sufficiency; Ukrainian calculators compute simple payback with household tariff and (some) net billing. solar_calc has only flat-tariff grid cost.

### Cited Findings
- PVsyst: NPV, IRR, payback, ROI, LCOE; yearly cash-flow; tariffs: fixed feed-in, peak/off-peak by hour, full-year hourly CSV prices, separate self-consumption tariff with annual evolution (e.g. +2%/yr) — [PVsyst financial results](https://www.pvsyst.com/help-pvsyst7/financial_balance.htm); [PVsyst tariffs](https://www.pvsyst.com/help/tariffs.htm); [PVsyst economic optimisation with storage](https://www.pvsyst.com/pdf/company/publications/articles/economic_optimization_of_pv_systems_with_storage.pdf); [Canal Solar walkthrough](https://canalsolar.com.br/en/economic-analysis-of-a-photovoltaic-system-using-pvsyst/)
- PVGIS: LCOE only (cost, interest, lifetime, fixed 2% O&M) — [PVGIS grid-connected](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-tools/grid-connected-pv_en)
- SAM: value = bill without system minus bill with system under same rate; NPV, payback, LCOE from after-tax cash flows; net metering (monthly kWh, true-up, rollover) vs net billing (per time step, may make bill negative), sub-hourly buy/sell rates; battery replacements — [SAM help 2024.12.12](https://sam.nlr.gov/images/web_page_files/sam-help-2024-12-12.pdf); [SAM metering forum](https://sam.nrel.gov/forum/forum-general/4274-some-clarifications-with-sams-metering-billing.html); [SAM rates webinar](https://sam.nlr.gov/financial-models/images/webinar_files/sam-webinars-2017-electricity-rates.pdf)
- HOMER: NPC ranking, COE, replacements, fuel, outage costs (Grid) — [HOMER Pro](https://www.homerenergy.com/products/pro/index.html); [HOMER Grid resilience](https://homerenergy.com/products/grid/docs/latest/how_homer_grid_models_resilience.html)
- PV*SOL: NPV (capital value) method; amortisation period (not shown if > 30 years); LCOE per VDI 6025; feed-in reduced for degradation, P90 and negative-price hours; tariff DB for from-grid, feed-in and net-metering tariffs — [PV*SOL financial analysis calc](https://help.valentin-software.com/pvsol/en/calculation/financial-analysis/); [PV*SOL results financial analysis](https://help.valentin-software.com/pvsol/en/pages/results/financial-analysis/)
- Aurora: payback, NPV, lifetime savings, LCOE, cashflow; hourly bill simulation; panel degradation; rate escalation; financing — [Aurora financial analysis](https://help.aurorasolar.com/hc/en-us/articles/51752305485715-Financial-analysis-Overview)
- OpenSolar: price, incentives, cash/loan/lease, energy price inflation, analysis duration; TOU bill savings by period — [OpenSolar financial savings](https://support.opensolar.com/hc/en-us/articles/12486176749711); [OpenSolar bill savings](https://support.opensolar.com/hc/en-us/articles/5733939697679-How-OpenSolar-calculates-utility-bill-savings)
- Huawei: bill before/after, revenue, payback (warning: payback 0 means price/O&M missing) — [SmartDesign report](https://support.huawei.com/enterprise/en/doc/EDOC1100257167/c42f7784/generating-a-report); [SmartDesign FAQ](https://support.huawei.com/enterprise/en/doc/EDOC1100257167/58e51a54/faqs)
- SMA / Fronius: self-consumption and self-sufficiency KPIs, battery cycles/yr; Fronius report includes cost effectiveness — [Sunny Design](https://www.sma.de/en/products/apps-software/sunny-design); [Fronius FAQ](https://www.fronius.com/en/faq-online-tools/faq-solar-energy/solarcreator)
- SolarEdge Designer: ROI projections; third-party says finance is basic (payback/savings) — [SolarEdge Designer](https://www.solaredge.com/us/products/software-tools/designer); [apps.list.solar](https://apps.list.solar/tools/solaredge-designer/)
- Ukraine: net billing available since Jan 2024; surplus valued at day-ahead market price (~5-7 UAH/kWh cited for commercial), not guaranteed; household tariff 4.32 UAH/kWh used by Vistan — [pipl.ua net billing 2026](https://pipl.ua/article/elektroenergiya-2026-yak-pracyuye-net-billing-i-chi-vigidno-teper-staviti-sonyachni-paneli); [Sanlarix](https://sanlarix.com.ua/promyslova-ses-dlya-vyrobnycztva/); [Vistan](https://vistan.group/calculator)

### Inferences
- Minimum useful economics block for solar_calc: CAPEX by component (PV, inverter, battery, cables, install), tariff (flat + optional two-zone day/night TOU + net-billing export price), price escalation %, discount rate, horizon, battery replacement year/cost and PV degradation -> simple payback, discounted payback, NPV, LCOE/LCOS, plus "value of avoided outage hours" (optional user-specified UAH/h, analogous to HOMER Grid outage cost). Ukrainian two-zone household tariffs are common, but no source on 2026 zone prices was collected (see Gaps).
- Self-consumption ratio and self-sufficiency (autarky) are trivially derivable from existing solar_calc energy flows and are the headline KPIs of SMA/Fronius/OpenSolar.

### Gaps
- 2026 Ukrainian household two-zone/three-zone tariff values and current net-billing settlement rules for households were not researched in depth.

---

## Q4. What design checks and warnings do the tools perform?

### Takeaway
String voltage/current window checks (cold Voc vs max input, hot Vmp vs MPPT min, Isc vs input limit) are universal in vendor tools and Victron; DC/AC (nominal power) ratio and clipping are checked by SMA/Huawei and modelled by PV*SOL/SAM; cable checks range from a single loss % (PVsyst, SMA <1%) to full circuit tables with OCPD and voltage drop (Aurora); fuse/OCPD sizing appears only in Aurora-style permit tools. solar_calc covers string and cable checks well but lacks protection-device sizing and some vendor-type warnings.

### Cited Findings
- Victron MPPT calculator: PV voltage at min temperature vs MPPT max, charge current, PV power ratio; oversizing allowed as long as Isc rating and cold-voltage rules are respected; recommended array ~+20% over controller max input — [Victron MPPT calculator](https://mppt.victronenergy.com/); [community oversizing](https://communityarchive.victronenergy.com/questions/208560/mppt-oversizing-calculator.html)
- Victron Toolkit: voltage drop with "potential voltage drop safety issues" flagged — [Victron Toolkit blog](https://www.victronenergy.com/blog/2024/09/04/introducing-the-victron-toolkit-app/)
- SMA Sunny Design: warns if design exceeds inverter critical input parameters; module max system voltage per MPP tracker; nominal power ratio / dimensioning factor; grid connection load exceeded warning; cable power loss — [SMA blog](https://www.sma-sunny.com/en/7-reasons-why-you-should-oversize-your-pv-array-2/); [Sunny Design manual](https://files.sma.de/downloads/SD3-SDW-BA-en-26.pdf)
- SMA backup: DC cable from battery inverter to battery must withstand backup overload; Sunny Island 48 V example: 140 A at 5 kW, ~8.5 W/m loss for 50 mm2 — [SMA backup planning guide](https://d3yvy865gav9f.cloudfront.net/asset/851725204959/document_92lu2ap7156trajf4pb81fka35/SI-SBS-STPSE-Backup-PL-en-30.pdf); [Sunny Island manual](https://www.manualslib.com/manual/1578959/Sma-Sunny-Island-5048.html?page=32)
- SolarEdge Designer: voltage window, optimiser count, unbalanced strings, inverter loading checked continuously — [Qbits review](https://qbitsenergy.com/blog/solaredge-designer-review/)
- Huawei: auto device selection by target capacity ratio; inverter count limits — [SmartDesign electrical design](https://support.huawei.com/enterprise/en/doc/EDOC1100257167/bc233624/electrical-design)
- Aurora circuit table: OCPD, conductor, terminal temperature rating, EGC, conduit, length, voltage drop — [Aurora instant plan sets](https://help.aurorasolar.com/hc/en-us/articles/33543611295379-Instant-Plan-Sets)
- PVsyst: ohmic loss as % at STC (practitioner guidance <= ~2%); inverter overpower behaviour — [PVsyst ohmic loss](https://pvsyst.com/help/index.html?ohmic_loss.htm=); [PVsyst forum overpower](https://forum.pvsyst.com/viewtopic.php?t=3710)
- PV*SOL: string/AC/DC cable losses per inverter on the circuit diagram — [PV*SOL premium](https://valentin-software.com/en/products/pvsol-premium/)
- PVsyst stand-alone: genset start threshold must be above load-disconnect threshold — [PVsyst controller thresholds](https://www.pvsyst.com/help-pvsyst7/controller_thresholds.htm)
- SMA off-grid: generator 80-120% of Sunny Island power — [SMA off-grid design](https://files.sma.de/downloads/OffGrid-System-PL-en-27.pdf)
- Deye practice: charge/discharge current limit must be set to weakest component (battery BMS, cable) — [Wattuneed](https://www.wattuneed.com/en/deye-hybrid-inverter-configuration-complete-engineering-manual-2026.htm)
- Ultrasolar / Akvadim / Bluetti: starting (surge) power of motors/pumps/compressors considered when sizing inverter — [Ultrasolar](https://ultrasolar.com.ua/calculator-invertora-ta-batarey-lifepo4); [Bluetti guide](https://www.bluettipower.com/blogs/buying-guide/best-solar-generators-for-home-backup)
- Generic benchmarks: string conductor 1.25 x Isc (or 1.56 x Isc under NEC 690.8); voltage drop 2% DC array-to-inverter, ~1% AC — [SurgePV cable sizing](https://www.surgepv.com/blog/solar-cable-sizing-calculation)

### Inferences
- Checks solar_calc may be missing (to verify in code): fuse/breaker sizing for PV strings (when >2 strings in parallel), battery fuse/breaker vs cable ampacity and BMS current; inverter surge power vs load start-up; generator size window; inverter AC power vs peak load; DC/AC (PV/inverter) ratio warning and clipping energy for hybrid inverters with limited PV input power; warning when battery charge current limit < PV surplus (lost energy).
- solar_calc's MPPT efficiency vs Vin/Vbat and cable models allow a check none of the surveyed tools offer: MPPT-to-battery and battery-to-inverter voltage drop at peak inverter load (low-voltage cut-off triggered early) — worth keeping as a differentiator.

### Gaps
- Exact Sunny Design warning thresholds and texts were not available; whether OpenSolar performs Voc/MPPT validation is undocumented.

---

## Q5. What reporting and UX features are common?

### Takeaway
PDF report (with monthly tables, loss diagram, economics) is standard in every professional tool; installer platforms add 3D/satellite layout, BOM, SLD and customer proposals; vendor tools are free but brand-locked. solar_calc has text/CSV/PNG export and JSON profiles but no PDF, SLD, BOM or component database.

### Cited Findings
- PVsyst: simulation report with loss diagram, battery SOW, LOL, solar fraction — [PVsyst 7.2.5 sample report](https://bdd.pseau.org/outils/ouvrages/ebml_wet_simulation_report_of_solar_powered_chlorination_system_for_mazraat_yachouaa_station_2021.pdf)
- PV*SOL: customizable reports with layouts, circuit diagrams, economic summaries; 2026 customer presentation PDF/DOCX; Renusol mounting BOM — [Solar Power World](https://www.solarpowerworldonline.com/2025/11/pvsol-adds-new-customer-presentation-feature-in-latest-software-update/); [Renusol](https://www.renusol.com/en/our-company/news/details/pv-sol-premium-2025-now-with-interface-to-renusol-pv-configurator-3-0/)
- Huawei: customizable/exportable report with 3D overview and device list; ESS report "within 5 minutes in 5 steps" (vendor claim) — [SmartDesign report](https://support.huawei.com/enterprise/en/doc/EDOC1100257167/c42f7784/generating-a-report); [SmartDesign datasheet](https://solar.huawei.com/download?p=%2F-%2Fmedia%2FSolar%2Fdatasheet%2FFusionSolar_SmartDesign_2_0.pdf)
- Fronius: PDF report, emailed from project overview — [Fronius configurator](https://www.fronius.com/en-us/usa/solar-energy/installers-partners/products-solutions/monitoring-digital-tools/design-pv-system-solar-configurator)
- SolarEdge: layout, BOM, performance summary export; DXF — [SurgePV review](https://www.surgepv.com/reviews/solaredge); [What's new](https://marketing.solaredge.com/solaredge-designer-0-20)
- OpenSolar: proposals with up to four featured figures, battery price as line item, battery-only/retrofit proposals, auto SLD — [Featured figures](https://support.opensolar.com/hc/en-us/articles/13092835119759-Featured-Figures-in-the-Proposal); [Battery line item](https://support.opensolar.com/hc/en-us/articles/14173460956815-Showing-Battery-Pricing-as-a-Line-Item-on-Proposals); [OpenSolar SLD](https://support.opensolar.com/hc/en-us/articles/12354314183567-How-to-use-the-Single-Line-Diagram-SLDs)
- Aurora: web proposal, plan sets, SLD editor, LIDAR-assisted modelling and shade reports (Premium) — [Aurora pricing](https://aurorasolar.com/pricing/); [Aurora SLD editor](https://help.aurorasolar.com/hc/en-us/articles/44152078845843-Single-Line-Diagram-Editor)
- PVGIS: CSV/JSON outputs, API; PVGIS 6 adds CLI and planned MCP interface — [PVGIS off-grid](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-tools/grid-pv-systems_en); [About PVGIS 6](https://photovoltaic-geographic-information-system.ec.europa.eu/en/about-pvgis-6)
- SAM: PySAM scripting; CEC module/inverter CSV libraries usable via pvlib `retrieve_sam` — [SAM forum PySAM DB](https://sam.nlr.gov/forum/forum-general/3742-using-pv-module-and-inverter-database-in-pysam.html); [pvlib retrieve_sam](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.pvsystem.retrieve_sam.html)
- Victron MPPT calculator: share links, export/archive configs, setup wizard — [Victron Professional](https://professional.victronenergy.com/news/detail/268/)
- Renogy: save multiple configurations with account — [Renogy](https://www.renogy.com/blogs/archive/solar-calculator-how-to)
- Ukrainian forum users criticise vendor calculators for giving only a few headline numbers and ignoring DC > AC clipping — [GreenPowerTalk thread](https://greenpowertalk.tech/threads/novij-ukrajinskij-kalkuljator-virobitku-sonjachnoji-stanciji-tochno-najkraschij.2304/); [GreenPowerTalk FAQ](https://greenpowertalk.tech/threads/faq-programi-rozraxunku-kalkuljatori.512/)

### Inferences
- For a desktop PySide6 tool, the highest-value reporting additions are: a one-click PDF (inputs, monthly table, loss waterfall, battery SOC/days-empty stats, checks with pass/warn/fail, economics) and an auto-generated simple DC single-line diagram (PV strings -> fuse/breaker -> MPPT -> battery fuse -> inverter -> AC) with cable sizes from the existing cable model; plus a BOM table (panels, cables by section/length, fuses, connectors).
- A component database could be seeded from SAM/CEC libraries via pvlib (modules, inverters) plus a local JSON library of common Ukrainian-market hybrid inverters and LiFePO4 packs; full PAN/OND import is a stretch goal.

### Gaps
- Did not verify whether any free tool generates SLDs for low-voltage (48 V) DC-coupled off-grid systems specifically.

---

## Q6. Consolidated feature checklist, and what solar_calc v1.2.1 lacks

### Takeaway
Against 14 tool groups, solar_calc is strong on DC electrical detail, MPPT/battery modelling and orientation/wire optimisation tables, but lacks (in order of importance for Ukrainian home backup): hourly year/TMY simulation and reliability statistics, outage schedules with critical loads, economics (payback/NPV/LCOE, TOU, net billing), self-consumption/self-sufficiency KPIs, battery/PV degradation, generator, PDF report, protection device sizing, component database, and multi-point horizon.

### Cited Findings
Abbreviations: PVS = PVsyst; PVG = PVGIS; SAM; HOM = HOMER Pro/Grid; SOL = PV*SOL premium; VIC = Victron MPPT calc + Toolkit; SMA = Sunny Design; FRO = Fronius Solar.creator; HUA = Huawei SmartDesign; SE = SolarEdge Designer; OS = OpenSolar; AUR = Aurora; CON = consumer off-grid calculators (altE, Renogy, EcoFlow/Bluetti, load worksheets); UA = Ukrainian/Russian online calculators; OUR = solar_calc v1.2.1 (per feature list given in the brief). Sources for each cell are those cited in Q1-Q5 for that tool.

| # | Feature | PVS | PVG | SAM | HOM | SOL | VIC | SMA | FRO | HUA | SE | OS | AUR | CON | UA | OUR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Weather / time base** | | | | | | | | | | | | | | | | |
| 1 | Hourly full-year or multi-year series / TMY | Y | Y | Y | Y | P (PVGIS SARAH3 climate data) | - | ? | ? | ? | P | P (SAM option) | Y | - | P (cec.in.ua via PVGIS) | - |
| 2 | Sub-hourly step | ? | - | Y | Y | ? | - | ? | ? | ? | ? | ? | ? | - | - | P (10-min avg day) |
| 3 | Clear/average/overcast scenario days | ? | - | - | - | ? | - | ? | ? | ? | ? | ? | ? | - | - | Y |
| 4 | Worst n-day / multi-day weather sequence | Y (presizing) | Y (multi-year series) | P (full-year series) | P (full-year series) | P (design period) | - | ? | ? | ? | ? | ? | ? | - | - | P (N-day series) |
| **PV losses / models** | | | | | | | | | | | | | | | | |
| 5 | 3D near shading / scene | Y | - | Y | - | Y | - | ? | P (shadow analysis) | Y | Y | ? | Y | - | - | - |
| 6 | Horizon profile (multi-point / DEM) | Y | Y | ? | - | ? | - | ? | ? | ? | ? | ? | ? | - | P (via PVGIS) | P (one angle) |
| 7 | Module temperature model | Y | Y | ? | ? | ? | P (Voc vs temp) | ? | ? | ? | ? | ? | ? | - | - | Y |
| 8 | Inverter/MPPT efficiency curve (power and voltage) | Y | - | Y | - | ? | - | P | ? | ? | ? | ? | ? | - | - | P (MPPT vs Vin/Vbat; inverter constant) |
| 9 | Clipping / DC:AC ratio modelling | P (overpower) | - | Y | - | Y | Y (PV power ratio) | Y | ? | Y | P (inverter loading) | ? | ? | - | - | P (MPPT current/charge limit) |
| 10 | Mismatch, soiling, module quality | Y | P (single loss %) | ? | - | ? | - | ? | ? | ? | ? | ? | ? | - | - | Y |
| 11 | PV degradation over years | Y | - | Y | ? | Y | - | ? | ? | ? | ? | ? | Y | - | - | - |
| 12 | Snow loss | ? | P (inside loss %) | Y | - | ? | - | - | - | - | - | - | - | - | - | - |
| **Battery** | | | | | | | | | | | | | | | | |
| 13 | SOC, efficiency, DoD/cut-off, C-rate limits | Y | P (cut-off only) | Y | Y | Y | - | P | ? | ? | P | Y | Y | P | P | Y |
| 14 | Temperature (cold) effect on battery | P (ageing input) | - | ? | Y (MKBM) | ? | - | - | - | - | - | - | - | - | - | Y |
| 15 | Battery ageing (cycles / calendar / SOW) | Y | - | Y | Y | ? | - | P (cycles/yr) | - | - | - | - | P (2%/yr) | - | - | - |
| 16 | Battery replacement in lifetime | ? | - | Y | Y | ? | - | - | - | - | - | - | ? | - | - | - |
| **Load / dispatch** | | | | | | | | | | | | | | | | |
| 17 | 8760 hourly load import | Y | P (24 fractions/day) | Y | Y | P | - | ? | ? | P (loads set) | ? | ? | Y | - | - | P (monthly + 4 shapes) |
| 18 | Appliance list builder with surge power | - | - | - | - | - | - | - | - | - | - | Y | P (tiers) | Y | Y (Ultrasolar, Akvadim) | - |
| 19 | Self-consumption dispatch | Y | - | Y | Y | Y | - | Y | Y | Y | Y | Y | Y | - | P | Y (SBU-like) |
| 20 | TOU / arbitrage / peak-shaving dispatch | Y | - | Y | Y | ? | - | Y | ? | Y | ? | Y | Y | - | - | - |
| 21 | Backup generator (SOC start/stop, fuel, hours) | Y | - | ? | Y | Y | - | Y (Sunny Island) | - | - | - | - | - | - | P (advice only) | - |
| **Reliability / backup** | | | | | | | | | | | | | | | | |
| 22 | Days-of-autonomy sizing | Y | - | - | - | Y | - | - | - | - | - | - | Y (backup days) | Y | Y | P |
| 23 | LOLP / unmet-load fraction / missing energy | Y | Y | P (outage hours) | Y | ? | - | - | - | - | - | - | - | - | - | P (coverage %, grid kWh) |
| 24 | % days battery full/empty, SOC histogram | ? | Y | ? | ? | ? | - | - | - | - | - | - | - | - | - | - |
| 25 | Outage schedule / user outage windows | Y (weak grid) | - | Y | Y (Grid) | - | - | - | - | P (backup option) | Y (backup hours) | - | Y | - | Y (Akvadim) | P (whole-period no-grid) |
| 26 | Critical-load fraction | - | - | Y | ? | - | - | - | - | ? | Y | P (backup kW) | Y | - | - | - |
| 27 | Probabilistic outage survival (P90 / every-hour start) | - | - | Y | - | - | - | - | - | - | - | - | Y (P90) | - | - | - |
| **Sizing / optimisation** | | | | | | | | | | | | | | | | |
| 28 | Optimisation / comparison of alternatives | P (presizing) | - | ? | Y | ? | Y (MPPT match) | Y | P (auto strings) | Y (ESS) | - | ? | ? | Y (simple) | P | Y (S x P options) |
| 29 | Sensitivity analysis | ? | - | ? | Y | ? | - | - | - | - | - | - | - | - | - | - |
| 30 | Tilt/azimuth optimisation | ? | Y | ? | - | ? | - | ? | ? | ? | ? | ? | ? | - | Y (SWE, cec.in.ua) | Y |
| **Electrical checks** | | | | | | | | | | | | | | | | |
| 31 | Cold Voc vs max input; Vmp vs MPPT window | ? | - | ? | - | ? | Y | Y | P (input limits) | ? | Y | ? | ? (3rd-party claim) | - | - | Y |
| 32 | Isc vs MPPT input current limit | ? | - | - | - | ? | Y | P | ? | ? | P | ? | ? | - | - | Y |
| 33 | Cable sizing / voltage drop / power loss | P (single R) | - | - | - | Y | Y (Toolkit, MPPT calc) | Y | ? | ? | - | ? | Y | - | - | Y (3 DC segments, ПУЭ) |
| 34 | Fuse / OCPD sizing | - | - | - | - | ? | - | ? | ? | ? | - | ? | Y | - | - | - |
| 35 | Inverter surge vs load start-up | - | - | - | - | - | - | - | - | - | - | Y (peak kW) | - | P | Y | - |
| 36 | Generator size check | ? | - | - | Y | Y | - | Y (80-120%) | - | - | - | - | - | - | - | - |
| **Economics** | | | | | | | | | | | | | | | | |
| 37 | Payback / NPV / LCOE | Y | P (LCOE only) | Y | Y | Y | - | ? | Y | Y | P | Y | Y | - | Y (payback; Sanlarix NPV/IRR) | - |
| 38 | TOU tariffs | Y | - | Y | Y | ? | - | ? | ? | Y | ? | Y | Y | - | - | - |
| 39 | Feed-in / net metering / net billing | Y | - | Y | P | Y | - | ? | ? | ? | ? | ? | Y | - | Y (Vistan) | - |
| 40 | Price escalation, discount rate | Y | P (interest) | Y | Y | Y | - | ? | ? | ? | ? | Y | Y | - | P | - |
| 41 | Self-consumption ratio & self-sufficiency KPIs | P | - | ? | P (renewable fraction) | Y | - | Y | Y | P (energy distribution) | ? | Y | ? | - | P (coverage) | P (coverage %) |
| 42 | Bill before/after | - | - | Y | ? | ? | - | ? | ? | Y | ? | Y | Y | - | P | P (grid cost) |
| **Reporting / UX** | | | | | | | | | | | | | | | | |
| 43 | PDF report | Y | ? | ? | ? | Y | - | ? | Y | Y | P (summary export) | Y (proposal) | Y (web proposal) | - | - | - |
| 44 | Loss diagram (waterfall) | Y | - | ? | - | ? | - | - | - | - | - | - | - | - | - | ? |
| 45 | Single-line / circuit diagram | - | - | - | - | Y | - | - | - | P (connection details) | - (DXF only) | Y | Y | - | - | - |
| 46 | BOM / parts list | - | - | - | - | Y (Renusol) | - | ? | ? | Y (device list) | Y | P (line items) | ? | Y (kits) | Y (kits with prices) | - |
| 47 | Component database | Y | - | Y (CEC) | ? | Y (26k/7.5k/5.5k+) | Y (Victron) | Y (SMA) | Y (Fronius) | Y (Huawei) | Y (SolarEdge) | ? | ? | P | P | P (presets) |
| 48 | CSV / data export | ? | Y | ? | ? | ? | Y (config export) | ? | ? | ? | ? | ? | ? | - | - | Y |
| 49 | Save / share projects | Y | - | Y | Y | Y | Y (links) | ? | Y | ? | ? | ? | ? | Y (Renogy) | - | Y (JSON) |
| 50 | API / scripting | - | Y | Y (PySAM) | - | - | - | - | - | - | - | - | - | - | - | - |
| 51 | 3D / satellite layout | Y | - | Y (3D shade calc) | - | Y | - | ? | ? | Y | Y | ? | Y | - | - | - |

### Inferences
Prioritised list of what solar_calc lacks (P1 = high value for Ukrainian 1-30 kW hybrid/backup users and feasible in a Python desktop app; P3 = low value or out of scope):

- P1 — Hourly year simulation from PVGIS TMY/hourly series (`seriescalc`/`tmy` API, same provider already used for DRcalc), keeping the existing 10-min average-day mode as "quick" mode. Unlocks rows 1, 4, 23, 24, 27 (PVGIS, PVsyst, SAM, HOMER all do this).
- P1 — Reliability statistics like PVGIS SHS: % days battery full / empty, energy not captured, missing energy, SOC histogram (10 bins), monthly; LOLP and unmet-load fraction like PVsyst/HOMER.
- P1 — Outage modelling for Ukraine: daily outage schedule per queue (hours off/on, e.g. Akvadim's "4 off / 2 on", PVsyst weak-grid availability profile), critical-load fraction (SAM/Aurora/SolarEdge), and "outage starting at every hour" survival curve with P50/P90 hours (SAM/REopt, Aurora).
- P1 — Self-consumption ratio and self-sufficiency KPIs (SMA, Fronius, OpenSolar) and battery cycles per year (SMA) — derived from existing flows, near-zero cost.
- P1 — Economics: CAPEX per component, payback (simple + discounted), NPV, LCOE, tariff escalation, two-zone TOU, net-billing export price, battery replacement; optional value of lost load (HOMER Grid outage cost analogue).
- P2 — Battery ageing: cycle counting (rainflow or equivalent full cycles) + calendar fade, end-of-life year (PVsyst SOW, HOMER MKBM/BLAST, SAM); PV degradation %/yr (PVsyst, SAM, Aurora, PV*SOL).
- P2 — Generator as a source in off-grid/outage mode: SOC start/stop thresholds (PVsyst/PV*SOL), run hours, fuel, sizing window 80-120% of inverter (SMA).
- P2 — PDF report with loss waterfall, monthly table, checks summary, economics; simple auto-generated DC single-line diagram and BOM (cables by section/length, fuses).
- P2 — Protection device sizing: string fuses / DC breakers / battery fuse vs cable ampacity and BMS current (Aurora circuit table analogue), plus inverter surge vs appliance start-up (Ultrasolar, Akvadim, OpenSolar peak kW).
- P2 — Appliance-list load builder (Renogy, OpenSolar, Reenergo winter/summer lists) feeding the existing hourly shapes.
- P2 — Multi-point horizon from PVGIS (`printhorizon`) or user file instead of a single elevation angle.
- P2 — Component database: seed from CEC libraries via pvlib `retrieve_sam`, plus curated Ukrainian-market hybrid inverters (Deye, Must, Victron) and LiFePO4 packs; inverter efficiency curve (vs load) instead of constant efficiency.
- P3 — PV x battery size matrix with cost objective / sensitivity (HOMER-style); snow loss (SAM); 3D shading, satellite layout, proposals/CRM (Aurora/OpenSolar/Huawei) — likely out of scope for a desktop engineering calculator.
- Differentiators to preserve: detailed DC cable model on three segments (Cu/Al, temperature, contacts, ПУЭ ampacity), MPPT efficiency vs Vin/Vbat and self-consumption, battery cold derating, low-light module behaviour, S x P option comparison, clear/average/overcast day scenarios, DC-coupled hybrid off-grid modelling (which PV*SOL's stand-alone module reportedly cannot do — [Valentin forum](https://forum.valentin-software.com/topic/10572-off-grid-system-with-battery)).

### Gaps
- Several checklist cells are "?" because vendor help pages could not be fetched; "?" means "not verified", not "absent" (e.g. PVsyst very likely exports CSV and optimises tilt, but no source was retrieved). The matrix is a lower bound for commercial/vendor tools.
- solar_calc column is based on the feature list supplied in the brief, not on reading the code; rows 18, 34, 35, 44 should be verified in the source.
- No quantitative comparison (e.g. yield difference solar_calc vs PVsyst/PVGIS for Kyiv) was performed.
