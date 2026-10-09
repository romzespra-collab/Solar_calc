"""mod_panels.py  v1.9.8
База солнечных панелей: паспорт STC + температурные коэффициенты, «производитель → серия → мощность».
Полная база — panels_db.tsv.gz рядом (CEC/NREL SAM 2026.7.3 — 21 тыс. моделей, 250+ производителей,
+ паспорта популярных серий, которых в CEC нет). Ниже — ручные паспорта (сверены с datasheet), они главнее
файла; их ключи не меняются (старые настройки открываются как были).
«≈ не проверено» в описании — значения из каталога, не из паспорта.

Журнал:
v1.9.8: +6 паспортов — топ продаж в Украине, которых не было: LONGi LR8-66HGD-615M, LR7-72HTH-615M,
        LR5-54HIH-410M; JA JAM54D41-460/LR; Jinko JKM380N-6TL3-V; ReneSola RS6-580N.
v1.9.7: повреждённый (не обрезанный) panels_db.tsv.gz — zlib.error больше не валит запуск, остаются встроенные.
v1.5.0: полная база из файла panels_db.tsv.gz (CEC + паспорта серий); серии (PANEL_SERIES) — для выбора
        «производитель → серия → мощность»; поиск по базе (окно 🔎 FindDialog).
v1.3.0: вынесено из solar_calc.pyw v1.2.1; база «производитель → модель» (PANEL_DB):
        96 моделей — Jinko, LONGi, JA Solar, Trina, Canadian Solar, Risen, Astronergy, AIKO,
        Tongwei, DAH Solar, Huasun, Sunova, Yingli, Leapton, Ulica Solar, Abi-Solar, Q CELLS, REC,
        Maxeon, Victron, Axioma Energy.
"""

import gc
import gzip
import re
import zlib
from pathlib import Path

from .mod_base import log, presets_of


def _p(pmax, vmp, imp, voc, isc, gamma, bvoc, noct=45, lowlight=97):
    return dict(pmax=pmax, vmp=vmp, imp=imp, voc=voc, isc=isc, gamma=gamma, bvoc=bvoc, noct=noct, lowlight=lowlight)


# (ключ, производитель, модель, паспорт: Pmax Вт, Vmp В, Imp А, Voc В, Isc А, γ %/°C, βVoc %/°C, NOCT/NMOT °C,
#  КПД при 200 Вт/м² %, описание)
_CURATED = [
    ("p100", "Типовые", "100 Вт, 36 ячеек (12 В)", _p(100, 18.0, 5.56, 21.6, 6.0, -0.40, -0.30, 47, 96), "моно/поли 36 ячеек"),
    ("p300", "Типовые", "Поли 300 Вт, 60 ячеек", _p(300, 32.6, 9.20, 39.8, 9.70, -0.40, -0.30, 45, 96), "поликристалл 60 ячеек"),
    ("p410", "Типовые", "Моно 410 Вт, 108 полуяч.", _p(410, 31.4, 13.06, 37.6, 13.90, -0.35, -0.27, 45, 97), "моно PERC 108 полуячеек"),
    ("p550", "Типовые", "Моно 550 Вт, 144 полуяч.", _p(550, 41.96, 13.11, 49.9, 13.98, -0.34, -0.27, 45, 97), "моно PERC 144 полуячейки"),
    ("p670", "Типовые", "Моно 670 Вт, 132 яч. 210 мм", _p(670, 38.3, 17.50, 45.9, 18.60, -0.34, -0.26, 45, 97), "моно 132 полуячейки 210 мм"),
    ("jinko_jkm275pp60", "Jinko", "275 Вт · JKM275PP-60 (Eagle 60P)", _p(275, 32, 8.61, 39.1, 9.15, -0.4, -0.3, 45, 96),
     "60 поли 156 mm · 1650×992×40 мм · 19 кг · NOCT 45°C · паспорт ✓"),
    ("jinko_jkm280pp60", "Jinko", "280 Вт · JKM280PP-60 (Eagle 60P)", _p(280, 32.3, 8.69, 39.4, 9.2, -0.4, -0.3, 45, 96),
     "60 поли 156 mm · 1650×992×40 мм · 19 кг · NOCT 45°C · паспорт ✓"),
    ("jinko_jkm330pp72", "Jinko", "330 Вт · JKM330PP-72 (Eagle 72P)", _p(330, 37.8, 8.74, 46.9, 9.14, -0.4, -0.3, 45, 96),
     "72 поли 156 mm · 1956×992×40 мм · 26.5 кг · NOCT 45°C · паспорт ✓"),
    ("jinko_jkm440n54hl4rbdv", "Jinko", "440 Вт · JKM440N-54HL4R-BDV (Tiger Neo 54HL4R-BDV)", _p(440, 32.4, 13.58, 38.98, 14.35, -0.29, -0.25, 45, 97.5),
     "108 полуячеек N-type TOPCon · двусторонняя · 1762×1134×30 мм · 22 кг · NOCT 45°C · паспорт ✓"),
    ("jinko_jkm445n54hl4rv", "Jinko", "445 Вт · JKM445N-54HL4R-V (Tiger Neo 54HL4R-V)", _p(445, 33.02, 13.48, 39.59, 13.93, -0.29, -0.25, 45, 97.5),
     "108 полуячеек N-type TOPCon · 1762×1134×30 мм · 21 кг · NOCT 45°C · паспорт ✓"),
    ("jinko_jkm450n54hl4rv", "Jinko", "450 Вт · JKM450N-54HL4R-V (Tiger Neo 54HL4R-V)", _p(450, 33.21, 13.55, 39.78, 14, -0.29, -0.25, 45, 97.5),
     "108 полуячеек N-type TOPCon · 1762×1134×30 мм · 21 кг · NOCT 45°C · паспорт ✓"),
    ("jinko_jkm580n72hl4bdv", "Jinko", "580 Вт · JKM580N-72HL4-BDV (Tiger Neo 72HL4-BDV)", _p(580, 43.88, 13.22, 52.5, 13.95, -0.29, -0.25, 45, 97.5),
     "144 полуячеек N-type TOPCon · двусторонняя · 2278×1134×30 мм · 32 кг · NOCT 45°C · паспорт ✓"),
    ("jinko_jkm580n72hl4v", "Jinko", "580 Вт · JKM580N-72HL4-V (Tiger Neo 72HL4-V)", _p(580, 43.35, 13.38, 52.31, 14.01, -0.29, -0.25, 45, 97.5),
     "144 полуячеек N-type TOPCon · 2278×1134×30 мм · 27 кг · NOCT 45°C · паспорт ✓"),
    ("jinko590", "Jinko", "590 Вт · JKM590N-72HL4-BDV (Tiger Neo 72HL4-BDV)", _p(590, 44.17, 13.36, 52.9, 14.07, -0.29, -0.25, 45, 97.5),
     "144 полуячеек N-type TOPCon · двусторонняя · 2278×1134×30 мм · 32 кг · NOCT 45°C · паспорт ✓"),
    ("jinko_jkm625n66hl4mbdv", "Jinko", "625 Вт · JKM625N-66HL4M-BDV (Tiger Neo 66HL4M-BDV)", _p(625, 40.88, 15.29, 49.28, 16.14, -0.29, -0.25, 45, 97.5),
     "132 полуячеек N-type TOPCon (G12R) · двусторонняя · 2382×1134×30 мм · 32.4 кг · NOCT 45°C · паспорт ✓"),
    ("jinko_jkm630n78hl4bdv", "Jinko", "630 Вт · JKM630N-78HL4-BDV (Tiger Neo 78HL4-BDV)", _p(630, 47.7, 13.21, 57.08, 13.86, -0.29, -0.25, 45, 97.5),
     "156 полуячеек N-type TOPCon · двусторонняя · 2465×1134×30 мм · 34 кг · NOCT 45°C · паспорт ✓"),
    ("jinko_jkm710n66hl5bdv", "Jinko", "710 Вт · JKM710N-66HL5-BDV (Tiger Neo 3.0 66HL5-BDV)", _p(710, 40.65, 17.47, 48.73, 18.53, -0.29, -0.25, 45, 97.5),
     "132 полуячеек N-type TOPCon (G12) · двусторонняя · 2384×1303×33 мм · 37.5 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr460hph370m", "LONGi", "370 Вт · LR4-60HPH-370M (Hi-MO 4m LR4-60HPH)", _p(370, 34.4, 10.76, 40.9, 11.52, -0.35, -0.27, 45, 97),
     "120 полуячеек моно PERC (166 mm) · 1755×1038×35 мм · 19.5 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr554hth430m", "LONGi", "430 Вт · LR5-54HTH-430M (Hi-MO 6 Explorer LR5-54HTH)", _p(430, 32.84, 13.1, 39.13, 14.15, -0.29, -0.23, 45, 97.5),
     "108 полуячеек моно HPBC · 1722×1134×30 мм · 20.8 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr554hth435m", "LONGi", "435 Вт · LR5-54HTH-435M (Hi-MO 6 Explorer LR5-54HTH)", _p(435, 33.04, 13.17, 39.33, 14.22, -0.29, -0.23, 45, 97.5),
     "108 полуячеек моно HPBC · 1722×1134×30 мм · 20.8 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr554hth440m", "LONGi", "440 Вт · LR5-54HTH-440M (Hi-MO 6 Explorer LR5-54HTH)", _p(440, 33.24, 13.24, 39.53, 14.3, -0.29, -0.23, 45, 97.5),
     "108 полуячеек моно HPBC · 1722×1134×30 мм · 20.8 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr472hph450m", "LONGi", "450 Вт · LR4-72HPH-450M (Hi-MO 4m LR4-72HPH)", _p(450, 41.5, 10.85, 49.3, 11.6, -0.35, -0.27, 45, 97),
     "144 полуячеек моно PERC (166 mm) · 2094×1038×35 мм · 23.5 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr472hph455m", "LONGi", "455 Вт · LR4-72HPH-455M (Hi-MO 4m LR4-72HPH)", _p(455, 41.7, 10.92, 49.5, 11.66, -0.35, -0.27, 45, 97),
     "144 полуячеек моно PERC (166 mm) · 2094×1038×35 мм · 23.5 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr754hvh475m", "LONGi", "475 Вт · LR7-54HVH-475M (Hi-MO X10 Explorer LR7-54HVH)", _p(475, 33.16, 14.33, 40.18, 15.03, -0.26, -0.2, 45, 97.5),
     "108 полуячеек N-type HPBC 2.0 · 1800×1134×30 мм · 21.6 кг · NOCT 45°C · паспорт ✓"),
    ("longi480", "LONGi", "480 Вт · LR7-54HVH-480M (Hi-MO X10 Explorer LR7-54HVH)", _p(480, 33.28, 14.43, 40.29, 15.13, -0.26, -0.2, 45, 97.5),
     "108 полуячеек N-type HPBC 2.0 · 1800×1134×30 мм · 21.6 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr754hvh485m", "LONGi", "485 Вт · LR7-54HVH-485M (Hi-MO X10 Explorer LR7-54HVH)", _p(485, 33.4, 14.53, 40.4, 15.23, -0.26, -0.2, 45, 97.5),
     "108 полуячеек N-type HPBC 2.0 · 1800×1134×30 мм · 21.6 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr572hth575m", "LONGi", "575 Вт · LR5-72HTH-575M (Hi-MO 6 Explorer LR5-72HTH)", _p(575, 43.91, 13.1, 52.06, 14.14, -0.29, -0.23, 45, 97.5),
     "144 полуячеек моно HPBC · 2278×1134×35 мм · 27.5 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr572htd580m", "LONGi", "580 Вт · LR5-72HTD-580M (Hi-MO 6 Guardian LR5-72HTD)", _p(580, 43.85, 13.23, 52.3, 14.13, -0.29, -0.23, 45, 97.5),
     "144 полуячеек моно HPBC · двусторонняя · 2278×1134×35 мм · 32.6 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr572hth580m", "LONGi", "580 Вт · LR5-72HTH-580M (Hi-MO 6 Explorer LR5-72HTH)", _p(580, 44.06, 13.17, 52.21, 14.2, -0.29, -0.23, 45, 97.5),
     "144 полуячеек моно HPBC · 2278×1134×35 мм · 27.5 кг · NOCT 45°C · паспорт ✓"),
    ("longi585", "LONGi", "585 Вт · LR5-72HTH-585M (Hi-MO 6 Explorer LR5-72HTH)", _p(585, 44.21, 13.24, 52.36, 14.27, -0.29, -0.23, 45, 97.5),
     "144 полуячеек моно HPBC · 2278×1134×35 мм · 27.5 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr772hgd610m", "LONGi", "610 Вт · LR7-72HGD-610M (Hi-MO 7 LR7-72HGD)", _p(610, 44.34, 13.76, 52.44, 14.65, -0.28, -0.23, 45, 97.5),
     "144 полуячеек N-type HPDC · двусторонняя · 2382×1134×30 мм · 33.5 кг · NOCT 45°C · паспорт ✓"),
    ("longi_lr772hgd620m", "LONGi", "620 Вт · LR7-72HGD-620M (Hi-MO 7 LR7-72HGD)", _p(620, 44.55, 13.92, 52.66, 14.81, -0.28, -0.23, 45, 97.5),
     "144 полуячеек N-type HPDC · двусторонняя · 2382×1134×30 мм · 33.5 кг · NOCT 45°C · паспорт ✓"),
    # v1.9.8: топ продаж в Украине (hotline / ek.ua / prom / OLX, осень 2026), которых не было в базе
    ("longi_lr866hgd615m", "LONGi", "615 Вт · LR8-66HGD-615M (Hi-MO 7 LR8-66HGD)", _p(615, 40.71, 15.11, 48.58, 16.0, -0.28, -0.23, 45, 97.5),
     "132 полуячейки N-type HPDC (182×210 мм) · двусторонняя · 2382×1134×30 мм · 33.5 кг · NOCT ≈45°C · паспорт ✓"),
    ("longi_lr772hth615m", "LONGi", "615 Вт · LR7-72HTH-615M (Hi-MO X6 Max LR7-72HTH)", _p(615, 44.33, 13.88, 52.57, 14.87, -0.28, -0.23, 45, 97.5),
     "144 полуячейки N-type HPBC · NOCT 45°C · паспорт ✓"),
    ("longi_lr554hih410m", "LONGi", "410 Вт · LR5-54HIH-410M (Hi-MO 5m LR5-54HIH)", _p(410, 31.25, 13.12, 37.25, 13.88, -0.34, -0.265, 45, 97),
     "108 полуячеек моно PERC · 1722×1134×30 мм · 21.3 кг · NOCT 45°C · паспорт ✓"),
    ("jasolar_jam54d41460lr", "JA Solar", "460 Вт · JAM54D41-460/LR (DeepBlue 4.0 Pro JAM54D41/LR)", _p(460, 33.68, 13.66, 40.6, 14.43, -0.29, -0.25, 45, 97.5),
     "108 полуячеек N-type Bycium+ (TOPCon) · двусторонняя · NOCT 45°C · паспорт ✓"),
    ("jinko_jkm380n6tl3v", "Jinko", "380 Вт · JKM380N-6TL3-V (Tiger Neo N-type 60TR)", _p(380, 34.77, 10.93, 42.77, 11.6, -0.34, -0.28, 45, 97.5),
     "120 полуячеек N-type TOPCon · чёрная рамка · NOCT 45°C · Isc ≈ не проверено"),
    ("renesola_rs6580n", "ReneSola", "580 Вт · RS6-580N (RS6-xxxN)", _p(580, 43.35, 13.38, 52.51, 14.01, -0.29, -0.25, 45, 97.5),
     "144 полуячейки N-type TOPCon · NOCT 45°C · Isc ≈ не проверено"),
    ("jasolar_jap60s01275sc", "JA Solar", "275 Вт · JAP60S01-275/SC (JAP60S01/SC)", _p(275, 31.34, 8.77, 38.38, 9.29, -0.4, -0.33, 45, 96),
     "60 поли 156.75 mm · 1650×991×35 мм · 18.2 кг · NOCT 45°C · паспорт ✓"),
    ("jasolar_jam60s10340mr", "JA Solar", "340 Вт · JAM60S10-340/MR (JAM60S10/MR)", _p(340, 34.73, 9.79, 41.55, 10.46, -0.35, -0.27, 45, 97),
     "120 полуячеек моно PERC (158.75 mm) · 1689×996×35 мм · 18.7 кг · NOCT 45°C · паспорт ✓"),
    ("jasolar_jam54d41440mb", "JA Solar", "440 Вт · JAM54D41-440/MB (DeepBlue 4.0 Pro JAM54D41/MB)", _p(440, 33.37, 13.18, 39.38, 13.85, -0.29, -0.25, 45, 97.5),
     "108 полуячеек N-type Bycium+ (TOPCon) · двусторонняя · 1722×1134×30 мм · 21.5 кг · NOCT 45°C · паспорт ✓"),
    ("jasolar_jam54d40445mb", "JA Solar", "445 Вт · JAM54D40-445/MB (DeepBlue 4.0 Pro JAM54D40/MB)", _p(445, 33.64, 13.23, 39.65, 13.9, -0.29, -0.25, 45, 97.5),
     "108 полуячеек N-type Bycium+ (TOPCon) · двусторонняя · 1722×1134×30 мм · 21.5 кг · NOCT 45°C · паспорт ✓"),
    ("jasolar_jam54d40450lb", "JA Solar", "450 Вт · JAM54D40-450/LB (DeepBlue 4.0 Pro JAM54D40/LB)", _p(450, 32.82, 13.71, 39.3, 14.48, -0.29, -0.25, 45, 97.5),
     "108 полуячеек N-type Bycium+ (TOPCon), 182x210 ячеек · двусторонняя · 1762×1134×30 мм · 22 кг · NOCT 45°C · паспорт ✓"),
    ("jasolar_jam72s20450mr", "JA Solar", "450 Вт · JAM72S20-450/MR (JAM72S20/MR)", _p(450, 41.52, 10.84, 49.7, 11.36, -0.35, -0.27, 45, 97),
     "144 полуячеек моно PERC (166 mm) · 2112×1052×35 мм · 24.5 кг · NOCT 45°C · паспорт ✓"),
    ("jasolar_jam72s20455mr", "JA Solar", "455 Вт · JAM72S20-455/MR (JAM72S20/MR)", _p(455, 41.82, 10.88, 49.85, 11.41, -0.35, -0.27, 45, 97),
     "144 полуячеек моно PERC (166 mm) · 2112×1052×35 мм · 24.5 кг · NOCT 45°C · паспорт ✓"),
    ("jasolar_jam72d40580mb", "JA Solar", "580 Вт · JAM72D40-580/MB (DeepBlue 4.0 Pro JAM72D40/MB)", _p(580, 44.02, 13.17, 51.95, 13.84, -0.3, -0.26, 45, 97.5),
     "144 полуячеек N-type Bycium+ (TOPCon) · двусторонняя · 2278×1134×30 мм · 31.8 кг · NOCT 45°C · паспорт ✓"),
    ("ja585", "JA Solar", "585 Вт · JAM72D40-585/GB (DeepBlue 4.0 Pro JAM72D40)", _p(585, 44.22, 13.23, 52.16, 13.89, -0.29, -0.25, 45, 97.5),
     "144 полуячеек N-type · двусторонняя · NOCT 45°C · паспорт из v1.2"),
    ("jasolar_jam72d40590mb", "JA Solar", "590 Вт · JAM72D40-590/MB (DeepBlue 4.0 Pro JAM72D40/MB)", _p(590, 44.43, 13.28, 52.37, 13.94, -0.3, -0.26, 45, 97.5),
     "144 полуячеек N-type Bycium+ (TOPCon) · двусторонняя · 2278×1134×30 мм · 31.8 кг · NOCT 45°C · паспорт ✓"),
    ("jasolar_jam66d45615lb", "JA Solar", "615 Вт · JAM66D45-615/LB (DeepBlue 4.0 Pro JAM66D45/LB)", _p(615, 39.96, 15.39, 48.3, 16.1, -0.29, -0.25, 45, 97.5),
     "132 полуячеек N-type Bycium+ (TOPCon) · двусторонняя · 2382×1134×30 мм · 33.1 кг · NOCT 45°C · паспорт ✓"),
    ("jasolar_jam66d45620lb", "JA Solar", "620 Вт · JAM66D45-620/LB (DeepBlue 4.0 Pro JAM66D45/LB)", _p(620, 40.21, 15.42, 48.5, 16.13, -0.29, -0.25, 45, 97.5),
     "132 полуячеек N-type Bycium+ (TOPCon) · двусторонняя · 2382×1134×30 мм · 33.1 кг · NOCT 45°C · паспорт ✓"),
    ("trina_tsm275pd05", "Trina", "275 Вт · TSM-275PD05 (Honey TSM-PD05)", _p(275, 31.1, 8.84, 38.5, 9.25, -0.41, -0.32, 44, 96),
     "60 поли 156 mm · 1650×992×35 мм · 18.6 кг · NOCT 44°C · паспорт ✓"),
    ("trina_tsm440neg9r28", "Trina", "440 Вт · TSM-440NEG9R.28 (Vertex S+ NEG9R.28)", _p(440, 44, 10.01, 52.2, 10.67, -0.3, -0.24, 43, 97.5),
     "144 ячеек (разрез.) (2x72) N-type i-TOPCon (210R) · 1762×1134×30 мм · 21 кг · NOCT 43°C · паспорт ✓"),
    ("trina_tsm445neg9r28", "Trina", "445 Вт · TSM-445NEG9R.28 (Vertex S+ NEG9R.28)", _p(445, 44.3, 10.05, 52.6, 10.71, -0.3, -0.24, 43, 97.5),
     "144 ячеек (разрез.) (2x72) N-type i-TOPCon (210R) · 1762×1134×30 мм · 21 кг · NOCT 43°C · паспорт ✓"),
    ("trina_tsm570de19r", "Trina", "570 Вт · TSM-570DE19R (Vertex DE19R)", _p(570, 38.5, 14.79, 45.8, 15.85, -0.34, -0.25, 43, 97),
     "132 полуячеек моно PERC (210R) · 2384×1134×35 мм · 29.1 кг · NOCT 43°C · паспорт ✓"),
    ("trina575", "Trina", "575 Вт · TSM-575DE19R (Vertex DE19R)", _p(575, 38.8, 14.83, 46.1, 15.9, -0.34, -0.25, 43, 97),
     "132 полуячеек моно PERC (210R) · 2384×1134×35 мм · 29.1 кг · NOCT 43°C · паспорт ✓"),
    ("trina_tsm615neg19rc20", "Trina", "615 Вт · TSM-615NEG19RC.20 (Vertex N NEG19RC.20)", _p(615, 41.1, 14.98, 49.3, 15.89, -0.29, -0.24, 43, 97.5),
     "132 полуячеек N-type i-TOPCon (210R) · двусторонняя · 2382×1134×30 мм · 33 кг · NOCT 43°C · паспорт ✓"),
    ("trina_tsm620neg19rc20", "Trina", "620 Вт · TSM-620NEG19RC.20 (Vertex N NEG19RC.20)", _p(620, 41.4, 14.99, 49.6, 15.91, -0.29, -0.24, 43, 97.5),
     "132 полуячеек N-type i-TOPCon (210R) · двусторонняя · 2382×1134×30 мм · 33 кг · NOCT 43°C · паспорт ✓"),
    ("trina_tsm695neg21c20", "Trina", "695 Вт · TSM-695NEG21C.20 (Vertex N NEG21C.20)", _p(695, 40.3, 17.25, 48.3, 18.28, -0.3, -0.24, 43, 97.5),
     "132 полуячеек N-type i-TOPCon (G12) · двусторонняя · 2384×1303×33 мм · 38.3 кг · NOCT 43°C · паспорт ✓"),
    ("trina_tsm700neg21c20", "Trina", "700 Вт · TSM-700NEG21C.20 (Vertex N NEG21C.20)", _p(700, 40.5, 17.29, 48.6, 18.32, -0.3, -0.24, 43, 97.5),
     "132 полуячеек N-type i-TOPCon (G12) · двусторонняя · 2384×1303×33 мм · 38.3 кг · NOCT 43°C · паспорт ✓"),
    ("canadiansolar_cs6k275p", "Canadian Solar", "275 Вт · CS6K-275P (CS6K-P)", _p(275, 31, 8.88, 38, 9.45, -0.41, -0.31, 45, 96),
     "60 поли 156 mm · 1650×992×40 мм · 18.2 кг · NOCT 45°C · паспорт ✓"),
    ("canadiansolar_cs6k280p", "Canadian Solar", "280 Вт · CS6K-280P (CS6K-P)", _p(280, 31.3, 8.95, 38.2, 9.52, -0.41, -0.31, 45, 96),
     "60 поли 156 mm · 1650×992×40 мм · 18.2 кг · NOCT 45°C · паспорт ✓"),
    ("canadiansolar_cs6u330p", "Canadian Solar", "330 Вт · CS6U-330P (MaxPower CS6U-P)", _p(330, 37.2, 8.88, 45.6, 9.45, -0.41, -0.31, 45, 96),
     "72 поли 156 mm · 1960×992×40 мм · 22.4 кг · NOCT 45°C · паспорт ✓"),
    ("canadiansolar_cs6248td445", "Canadian Solar", "445 Вт · CS6.2-48TD-445 (TOPHiKu6 CS6.2-48TD)", _p(445, 44.6, 9.98, 52.7, 10.61, -0.29, -0.25, 41, 97.5),
     "144 ячеек (разрез.) (2x72) N-type TOPCon · 1762×1134×30 мм · 24.6 кг · NMOT 41°C · паспорт ✓"),
    ("canadiansolar_cs6248td450", "Canadian Solar", "450 Вт · CS6.2-48TD-450 (TOPHiKu6 CS6.2-48TD)", _p(450, 44.8, 10.05, 52.9, 10.68, -0.29, -0.25, 41, 97.5),
     "144 ячеек (разрез.) (2x72) N-type TOPCon · 1762×1134×30 мм · 24.6 кг · NMOT 41°C · паспорт ✓"),
    ("canadiansolar_cs6w580tbag", "Canadian Solar", "580 Вт · CS6W-580TB-AG (TOPBiHiKu6 CS6W-TB-AG)", _p(580, 43.1, 13.46, 52.2, 13.93, -0.29, -0.25, 41, 97.5),
     "144 полуячеек N-type TOPCon · двусторонняя · 2278×1134×30 мм · 32.3 кг · NMOT 41°C · паспорт ✓"),
    ("canadiansolar_cs6w585tbag", "Canadian Solar", "585 Вт · CS6W-585TB-AG (TOPBiHiKu6 CS6W-TB-AG)", _p(585, 43.3, 13.52, 52.4, 14, -0.29, -0.25, 41, 97.5),
     "144 полуячеек N-type TOPCon · двусторонняя · 2278×1134×30 мм · 32.3 кг · NMOT 41°C · паспорт ✓"),
    ("canadiansolar_cs7n695tbag", "Canadian Solar", "695 Вт · CS7N-695TB-AG (TOPBiHiKu7 CS7N-TB-AG)", _p(695, 39.8, 17.47, 47.7, 18.44, -0.29, -0.25, 41, 97.5),
     "132 полуячеек N-type TOPCon (G12) · двусторонняя · 2384×1303×33 мм · 37.8 кг · NMOT 41°C · паспорт ✓"),
    ("canadiansolar_cs7n700tbag", "Canadian Solar", "700 Вт · CS7N-700TB-AG (TOPBiHiKu7 CS7N-TB-AG)", _p(700, 40, 17.51, 47.9, 18.49, -0.29, -0.25, 41, 97.5),
     "132 полуячеек N-type TOPCon (G12) · двусторонняя · 2384×1303×33 мм · 37.8 кг · NMOT 41°C · паспорт ✓"),
    ("risen_rsm726330p", "Risen", "330 Вт · RSM72-6-330P (RSM72-6)", _p(330, 38.1, 8.7, 46.3, 9.25, -0.39, -0.32, 45, 96),
     "72 поли 156 mm · 1956×992×40 мм · 22 кг · NOCT 45°C · паспорт ✓"),
    ("risen_rsm1089435n", "Risen", "435 Вт · RSM108-9-435N (RSM108-9 N-type)", _p(435, 33.15, 13.13, 39.47, 14, -0.3, -0.25, 44, 97.5),
     "108 полуячеек N-type TOPCon · 1722×1134×30 мм · 22 кг · NOCT 44°C · паспорт ✓"),
    ("risen_rsm1089440n", "Risen", "440 Вт · RSM108-9-440N (RSM108-9 N-type)", _p(440, 33.34, 13.18, 39.67, 14.06, -0.3, -0.25, 44, 97.5),
     "108 полуячеек N-type TOPCon · 1722×1134×30 мм · 22 кг · NOCT 44°C · паспорт ✓"),
    ("risen_rsm1328700bhdg", "Risen", "700 Вт · RSM132-8-700BHDG (Hyper-ion RSM132-8 BHDG)", _p(700, 41.78, 16.77, 49.83, 17.82, -0.24, -0.22, 43, 97.5),
     "132 полуячеек N-type HJT (G12) · двусторонняя · 2384×1303×35 мм · 40.5 кг · NMOT 43°C · паспорт ✓"),
    ("astronergy_chsm54nhc440", "Astronergy", "440 Вт · CHSM54N-HC-440 (ASTRO N5s CHSM54N-HC)", _p(440, 32.61, 13.49, 38.8, 14.3, -0.29, -0.25, 41, 97.5),
     "108 полуячеек N-type TOPCon · 1722×1134×30 мм · 21.3 кг · NMOT 41°C · паспорт ✓"),
    ("astronergy_chsm72ndgfbh580", "Astronergy", "580 Вт · CHSM72N(DG)/F-BH-580 (ASTRO N5 CHSM72N/F-BH)", _p(580, 43.11, 13.45, 51.3, 14.28, -0.29, -0.25, 41, 97.5),
     "144 полуячеек N-type TOPCon · двусторонняя · 2278×1134×30 мм · 32.1 кг · NMOT 41°C · паспорт ✓"),
    ("aiko_aikoa455mah54mw", "AIKO", "455 Вт · AIKO-A455-MAH54Mw (Neostar 2P ABC MAH54Mw)", _p(455, 34.56, 13.17, 41, 14.22, -0.26, -0.22, 45, 97.5),
     "108 полуячеек N-type ABC (back contact) · 1757×1134×30 мм · 21.5 кг · NOCT 45°C · паспорт ✓"),
    ("aiko_aikoa460mah54mw", "AIKO", "460 Вт · AIKO-A460-MAH54Mw (Neostar 2P ABC MAH54Mw)", _p(460, 34.62, 13.29, 41.06, 14.25, -0.26, -0.22, 45, 97.5),
     "108 полуячеек N-type ABC (back contact) · 1757×1134×30 мм · 21.5 кг · NOCT 45°C · паспорт ✓"),
    ("aiko_aikoa465mah54mw", "AIKO", "465 Вт · AIKO-A465-MAH54Mw (Neostar 2P ABC MAH54Mw)", _p(465, 34.68, 13.41, 41.12, 14.29, -0.26, -0.22, 45, 97.5),
     "108 полуячеек N-type ABC (back contact) · 1757×1134×30 мм · 21.5 кг · NOCT 45°C · паспорт ✓"),
    ("aiko_aikoa615mah72mw", "AIKO", "615 Вт · AIKO-A615-MAH72Mw (Comet 2N ABC MAH72Mw)", _p(615, 44.98, 13.68, 54.29, 14.44, -0.26, -0.22, 45, 97.5),
     "144 полуячеек N-type ABC (back contact) · 2323×1134×33 мм · 27.7 кг · NOCT 45°C · паспорт ✓"),
    ("tongwei_twmnd54hs440", "Tongwei", "440 Вт · TWMND-54HS440 (TNC TWMND-54HS)", _p(440, 33.6, 13.1, 39.45, 13.77, -0.28, -0.24, 45, 97.5),
     "108 полуячеек N-type TNC (TOPCon) · 1722×1134×30 мм · 20.5 кг · NOCT 45°C · паспорт ✓"),
    ("tongwei_twmnd72hd575", "Tongwei", "575 Вт · TWMND-72HD575 (TNC TWMND-72HD)", _p(575, 43.08, 13.35, 51.44, 14.25, -0.3, -0.25, 45, 97.5),
     "144 полуячеек N-type TNC (TOPCon) · двусторонняя · 2278×1134×30 мм · 32.7 кг · NOCT 45°C · паспорт ✓"),
    ("tongwei_twmnd72hs580", "Tongwei", "580 Вт · TWMND-72HS580 (TNC TWMND-72HS)", _p(580, 45.03, 12.88, 52.8, 13.5, -0.3, -0.25, 45, 97.5),
     "144 полуячеек N-type TNC (TOPCon) · 2278×1134×35 мм · 27.8 кг · NOCT 45°C · паспорт ✓"),
    ("dahsolar_dhn54x16dgbw440", "DAH Solar", "440 Вт · DHN-54X16/DG(BW)-440 (DHN-54X16/DG)", _p(440, 32.9, 13.37, 38.4, 13.96, -0.3, -0.25, 45, 97.5),
     "108 полуячеек N-type TOPCon · 1722×1134×30 мм · 24 кг · NOCT 45°C · паспорт ✓"),
    ("dahsolar_dhn72x16dg580", "DAH Solar", "580 Вт · DHN-72X16/DG-580 (DHN-72X16/DG)", _p(580, 43.6, 13.3, 51.4, 14.14, -0.29, -0.25, 45, 97.5),
     "144 полуячеек N-type TOPCon · двусторонняя · 2279×1134×30 мм · 31.2 кг · NOCT 45°C · паспорт ✓"),
    ("huasun_hs182b108ds430", "Huasun", "430 Вт · HS-182-B108DS430 (G10 HS-182-B108DS)", _p(430, 33.49, 12.84, 40.3, 13.3, -0.26, -0.24, 45, 97.5),
     "108 полуячеек N-type HJT (M10) · двусторонняя · 1722×1134×30 мм · 26 кг · NOCT 45°C · паспорт ✓"),
    ("huasun_hs210b132ds705", "Huasun", "705 Вт · HS-210-B132DS705 (Himalaya G12 HS-210-B132DS)", _p(705, 42.25, 16.69, 50.29, 17.49, -0.26, -0.24, 45, 97.5),
     "132 полуячеек N-type HJT (G12) · двусторонняя · 2384×1303×35 мм · 38.7 кг · NOCT 45°C · паспорт ✓"),
    ("sunova_ss44054mdht", "Sunova", "440 Вт · SS-440-54MDH(T) (Tangra S SS-54MDH)", _p(440, 33.48, 13.15, 39.03, 13.73, -0.3, -0.28, 45, 97.5),
     "108 полуячеек N-type TOPCon · 1722×1134×30 мм · 21.5 кг · NOCT 45°C · паспорт ✓"),
    ("yingli_yl550d49e1500v12", "Yingli", "550 Вт · YL550D-49e 1/2 (YLM-J 3.0 PRO)", _p(550, 42, 13.1, 49.82, 13.97, -0.35, -0.27, 45, 97),
     "144 полуячеек моно PERC (M10) · 2278×1134×30 мм · 28 кг · NOCT 45°C · паспорт ✓"),
    ("leapton_lp182182m54nb440w", "Leapton", "440 Вт · LP182*182-M-54-NB-440W (LP182*182-M-54-NB)", _p(440, 32.05, 13.73, 38.87, 14.27, -0.3, -0.25, 41, 97.5),
     "108 полуячеек N-type TOPCon · двусторонняя · 1722×1134×30 мм · 24 кг · NOCT 41°C · паспорт ✓"),
    ("leapton_lp182182m54nh450w", "Leapton", "450 Вт · LP182*182-M-54-NH-450W (LP182*182-M-54-NH)", _p(450, 32.35, 13.91, 39.17, 14.44, -0.3, -0.25, 41, 97.5),
     "108 полуячеек N-type TOPCon · 1722×1134×30 мм · 21 кг · NOCT 41°C · паспорт ✓"),
    ("ulicasolar_ul450m108bhvn", "Ulica Solar", "450 Вт · UL-450M-108BHVN (UL-M-108BHVN)", _p(450, 33.22, 13.55, 39.78, 14, -0.29, -0.25, 43, 97.5),
     "108 полуячеек N-type TOPCon · 1762×1134×30 мм · 22 кг · NOCT 43°C · паспорт ✓"),
    ("ulicasolar_ul550m144hv", "Ulica Solar", "550 Вт · UL-550M-144HV (UL-M-144HV)", _p(550, 41.9, 13.13, 50, 13.75, -0.34, -0.27, 43, 97),
     "144 полуячеек моно PERC (M10) · 2279×1134×35 мм · 27.5 кг · NOCT 43°C · паспорт ✓"),
    ("ulicasolar_ul580m144adgn", "Ulica Solar", "580 Вт · UL-580M-144ADGN (UL-M-144ADGN)", _p(580, 44.02, 13.18, 52.52, 13.95, -0.29, -0.25, 43, 97.5),
     "144 полуячеек N-type TOPCon · двусторонняя · 2278×1134×30 мм · 30.6 кг · NOCT 43°C · паспорт ✓"),
    ("abisolar_ab42554mhc", "Abi-Solar", "425 Вт · AB425-54MHC (AB-54MHC)", _p(425, 31.7, 13.41, 38.3, 14.12, -0.3, -0.25, 44, 97),
     "108 полуячеек моно (M10) · 1722×1134×30 мм · 24.5 кг · NOCT 44°C · паспорт ✓"),
    ("abisolar_ab44072mhc", "Abi-Solar", "440 Вт · AB440-72MHC (AB-72MHC)", _p(440, 40.97, 10.74, 50.08, 11.33, -0.37, -0.29, 44, 97),
     "144 полуячеек моно PERC (166 mm) · 2108×1046×35 мм · 24 кг · NOCT 44°C · паспорт ✓"),
    ("qcells_qpeakduomg11s415", "Q CELLS", "415 Вт · Q.PEAK DUO M-G11S+ 415 (Q.PEAK DUO M-G11S+)", _p(415, 31.05, 13.37, 37.14, 13.99, -0.34, -0.27, 43, 97),
     "108 полуячеек моно Q.ANTUM DUO Z (PERC) · 1722×1134×30 мм · 21.1 кг · NMOT 43°C · паспорт ✓"),
    ("qcells_qtronblkmg2440", "Q CELLS", "440 Вт · Q.TRON BLK M-G2+ 440 (Q.TRON BLK M-G2+)", _p(440, 33.33, 13.2, 39.88, 13.9, -0.3, -0.24, 43, 97.5),
     "108 полуячеек N-type Q.ANTUM NEO (TOPCon) · 1722×1134×30 мм · 21.2 кг · NMOT 43°C · паспорт ✓"),
    ("qcells_qpeakduomlg11s500", "Q CELLS", "500 Вт · Q.PEAK DUO ML-G11S 500 (Q.PEAK DUO ML-G11S)", _p(500, 37.66, 13.28, 45.35, 13.94, -0.34, -0.27, 43, 97),
     "132 полуячеек моно Q.ANTUM DUO Z (PERC) · 2092×1134×30 мм · 25.7 кг · NMOT 43°C · паспорт ✓"),
    ("qcells_qpeakduomlg11s505", "Q CELLS", "505 Вт · Q.PEAK DUO ML-G11S 505 (Q.PEAK DUO ML-G11S)", _p(505, 37.87, 13.34, 45.38, 13.97, -0.34, -0.27, 43, 97),
     "132 полуячеек моно Q.ANTUM DUO Z (PERC) · 2092×1134×30 мм · 25.7 кг · NMOT 43°C · паспорт ✓"),
    ("rec_rec420aapurer", "REC", "420 Вт · REC420AA Pure-R (Alpha Pure-R)", _p(420, 50, 8.4, 59.4, 8.88, -0.24, -0.24, 44, 97.5),
     "80 полуячеек N-type HJT (G12) · 1730×1118×30 мм · 21.5 кг · NMOT 44°C · паспорт ✓"),
    ("rec_rec430aapurer", "REC", "430 Вт · REC430AA Pure-R (Alpha Pure-R)", _p(430, 50.5, 8.52, 59.7, 8.91, -0.24, -0.24, 44, 97.5),
     "80 полуячеек N-type HJT (G12) · 1730×1118×30 мм · 21.5 кг · NMOT 44°C · паспорт ✓"),
    ("maxeon_sprmax6440", "Maxeon", "440 Вт · SPR-MAX6-440 (Maxeon 6)", _p(440, 40.49, 10.87, 48.21, 11.58, -0.29, -0.23, 43, 97.5),
     "66 N-type Maxeon Gen 6 IBC · 1872×1032×40 мм · 20.9 кг · NOCT 43°C · паспорт ✓"),
    ("victron_spm040401200", "Victron", "40 Вт · BlueSolar 40W-12V Mono (BlueSolar Monocrystalline series 4a)", _p(40, 18.3, 2.19, 22.45, 2.4, -0.45, -0.35, 45, 96),
     "SPM040401200 · 36 моно · 425×668×25 мм · 3.1 кг · NOCT 45°C · паспорт ✓"),
    ("victron_spm040901200", "Victron", "90 Вт · BlueSolar 90W-12V Mono (BlueSolar Monocrystalline series 4a)", _p(90, 19.6, 4.59, 24.06, 5.03, -0.45, -0.35, 45, 96),
     "SPM040901200 · 36 моно · 780×668×30 мм · 6.1 кг · NOCT 45°C · паспорт ✓"),
    ("victron_spm041151200", "Victron", "115 Вт · BlueSolar 115W-12V Mono (BlueSolar Monocrystalline series 4a)", _p(115, 19, 6.04, 23.32, 6.61, -0.45, -0.35, 45, 96),
     "SPM041151200 · 36 моно · 1015×668×30 мм · 8 кг · NOCT 45°C · паспорт ✓"),
    ("victron_spm041501200", "Victron", "150 Вт · BlueSolar 150W-12V Mono (BlueSolar Monocrystalline series 4a)", _p(150, 18.2, 8.25, 22.3, 8.69, -0.45, -0.35, 45, 96),
     "SPM041501200 · 36 моно · 1485×668×30 мм · 11 кг · NOCT 45°C · паспорт ✓"),
    ("victron_spm041751200", "Victron", "175 Вт · BlueSolar 175W-12V Mono (BlueSolar Monocrystalline series 4a)", _p(175, 19.4, 9.03, 23.7, 9.89, -0.45, -0.35, 45, 96),
     "SPM041751200 · 36 моно · 1485×668×30 мм · 11 кг · NOCT 45°C · паспорт ✓"),
    ("axiomaenergy_ax200m", "Axioma Energy", "200 Вт · AX-200M (AX-M)", _p(200, 18.1, 11.05, 21.6, 11.87, -0.38, -0.3, 45, 97),
     "64 моно (2 parallel strings) · 1378×770×35 мм · 10.7 кг · NOCT 45°C · ≈ не проверено"),
]

DB_FILE = Path(__file__).resolve().parent / "panels_db.tsv.gz"
TYPICAL = "Типовые"
_TECH = {"mono": "моно", "poly": "поли", "thin": "тонкоплёночная", "cdte": "CdTe тонкоплёночная", "cigs": "CIGS",
         "asi": "a-Si"}


def _slug(s):
    return re.sub(r"[^0-9a-z]", "", s.lower())


def series_of(code, pmax):
    """Модель → шаблон серии: мощность в названии заменяется на «xxx» (RSM72-6-330P → RSM72-6-xxxP)."""
    ps = str(int(round(pmax)))
    m = list(re.finditer(r"(?<!\d)" + ps + r"(?!\d)", code))
    if not m:
        return code
    mm = m[-1] if len(m) > 1 and not code.startswith(ps) else m[0]
    return code[:mm.start()] + "xxx" + code[mm.end():]


def _natural(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


_COLS = ("key", "brand", "family", "series", "code", "pmax", "vmp", "imp", "voc", "isc", "gamma", "bvoc", "noct",
         "lowlight", "tech", "cells", "bif", "size", "src", "ct", "wt", "nk", "url")
_PK = ("pmax", "vmp", "imp", "voc", "isc", "gamma", "bvoc", "noct", "lowlight")


def _info_file(tech, cells, bif, size, src, ct, wt, nk, noct):
    parts = [ct or _TECH.get(tech, tech)]
    if cells and cells != "0":
        parts.append(f"{cells} яч." if src == "ds" else f"{cells} яч. последовательно")
    if bif == "1":
        parts.append("двусторонняя")
    if size:
        parts.append(size.replace("x", "×") + " мм")
    if wt:
        parts.append(f"{wt} кг")
    parts.append(f"{nk or 'NOCT'} {noct}°C")
    parts.append("паспорт ✓" if src == "ds" else "база CEC 2026.7.3")
    return " · ".join(parts)


def _load_file():
    """panels_db.tsv.gz → {ключ: [производитель, семейство, серия, модель, паспорт, описание]}.
    Нет файла — пусто (останутся ручные паспорта)."""
    out = {}
    try:
        with gzip.open(DB_FILE, "rt", encoding="utf-8") as f:
            head = f.readline().rstrip("\n").split("\t")
            if tuple(head) != _COLS:
                raise ValueError("другой формат файла")
            n = len(_COLS)
            for line in f:
                v = line.rstrip("\n").split("\t")
                if len(v) != n:
                    continue
                (key, brand, fam, ser, code, pm, vmp, imp, voc, isc, gm, bv, noct, ll,
                 tech, cells, bif, size, src, ct, wt, nk, _url) = v
                try:
                    p = dict(zip(_PK, map(float, (pm, vmp, imp, voc, isc, gm, bv, noct, ll))))
                except ValueError:
                    continue
                if p["pmax"] > 0:
                    out[key] = [brand, fam, ser, code, p, _info_file(tech, cells, bif, size, src, ct, wt, nk, noct)]
    except (OSError, EOFError, ValueError, zlib.error) as e:
        log.warning(f"⚠ база панелей {DB_FILE.name} не прочитана ({e}) — только встроенные модели")
    return out


def _build():
    """→ (база {ключ: (производитель, модель, паспорт, описание)}, {ключ: серия}) — по порядку выбора."""
    recs = _load_file()
    for key, brand, name, p, info in _CURATED:
        if brand == TYPICAL:
            recs[key] = [brand, "", "Типовые панели", name, p, info]
            continue
        m = re.match(r"\s*[\d.]+\s*Вт\s*·\s*(.+?)(?:\s+\(([^()]*)\))?\s*$", name)
        code, fam = (m.group(1), m.group(2) or "") if m else (name, "")
        old = None                                       # та же модель из файла: как есть / без «(…)», ±«W» в конце
        for c in (code, re.sub(r"\([^)]*\)", "", code)):
            base = _slug(brand) + "_" + _slug(c)
            for k in (base, base + "w", base[:-1] if base.endswith("w") else None):
                if old is None and k in recs:
                    old = recs.pop(k)
        if old is not None:
            recs[key] = [brand, old[1] or fam, old[2], old[3], p, info]
        else:
            recs[key] = [brand, fam, series_of(code, p["pmax"]), code, p, info]
    # подпись серии: «семейство · шаблон», одна на серию
    fam_of = {}
    for brand, fam, ser, *_ in recs.values():
        if fam and (brand, ser) not in fam_of:
            fam_of[(brand, ser)] = fam
    labels, nat, rows = {}, {}, []
    for key, (brand, fam, ser, code, p, info) in recs.items():
        bs = (brand, ser)
        label = labels.get(bs)
        if label is None:
            f = fam_of.get(bs, "")
            label = ser if brand == TYPICAL or not f or _slug(f) in _slug(ser) else f"{f} · {ser}"
            labels[bs] = label
            nat[bs] = _natural(ser)                      # порядок серий — по названию модели, не по семейству
        name = code if brand == TYPICAL else f"{p['pmax']:g} Вт · {code}"
        rows.append((brand != TYPICAL, brand.lower(), nat[bs], p["pmax"], code, key, brand, label, name, p, info))
    rows.sort()
    db = {r[5]: (r[6], r[8], r[9], r[10]) for r in rows}
    return db, {r[5]: r[7] for r in rows}


_gc = gc.isenabled()
gc.disable()                      # 21 тыс. записей: без сборщика мусора загрузка в разы быстрее
try:
    PANEL_DB, PANEL_SERIES = _build()
finally:
    if _gc:
        gc.enable()

PANEL_PRESETS = presets_of(PANEL_DB, "Своя панель")
