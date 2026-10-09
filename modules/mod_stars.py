"""mod_stars.py  v1.4.0
Яркие звёзды и фигуры созвездий для страницы «Небо» (видимые в Украине).
Координаты J2000: прямое восхождение (ч), склонение (°), звёздная величина.
Прецессия за 25 лет ≈0.35° — для картинки не важна. Положение — mod_astro.radec_altaz.

Журнал:
v1.4.0: перенесено из Smart_BMS 4.81 (star_catalog.py).
"""

# имя: (RA ч, Dec °, звёздная величина, подпись или "")
STARS = {
    # Большая Медведица
    "Dubhe": (11.062, 61.75, 1.8, ""), "Merak": (11.031, 56.38, 2.4, ""),
    "Phecda": (11.897, 53.69, 2.4, ""), "Megrez": (12.257, 57.03, 3.3, ""),
    "Alioth": (12.900, 55.96, 1.8, ""), "Mizar": (13.399, 54.93, 2.2, ""),
    "Alkaid": (13.792, 49.31, 1.9, ""),
    # Малая Медведица
    "Polaris": (2.530, 89.26, 2.0, "Полярная"),
    "Kochab": (14.845, 74.16, 2.1, ""), "Pherkad": (15.345, 71.83, 3.0, ""),
    "Yildun": (17.537, 86.59, 4.4, ""), "epsUMi": (16.766, 82.04, 4.2, ""),
    "zetUMi": (15.734, 77.79, 4.3, ""), "etaUMi": (16.292, 75.76, 5.0, ""),
    # Кассиопея
    "Caph": (0.153, 59.15, 2.3, ""), "Schedar": (0.675, 56.54, 2.2, ""),
    "gamCas": (0.945, 60.72, 2.2, ""), "Ruchbah": (1.430, 60.24, 2.7, ""),
    "Segin": (1.907, 63.67, 3.4, ""),
    # Лебедь
    "Deneb": (20.690, 45.28, 1.25, "Денеб"), "Sadr": (20.370, 40.26, 2.2, ""),
    "Gienah": (20.770, 33.97, 2.5, ""), "delCyg": (19.750, 45.13, 2.9, ""),
    "Albireo": (19.512, 27.96, 3.1, ""),
    # Лира
    "Vega": (18.616, 38.78, 0.03, "Вега"), "Sheliak": (18.835, 33.36, 3.5, ""),
    "Sulafat": (18.982, 32.69, 3.3, ""), "zetLyr": (18.746, 37.61, 4.3, ""),
    # Орёл
    "Altair": (19.846, 8.87, 0.77, "Альтаир"),
    "Tarazed": (19.771, 10.61, 2.7, ""), "Alshain": (19.922, 6.41, 3.7, ""),
    # Пегас + Андромеда
    "Markab": (23.079, 15.21, 2.5, ""), "Scheat": (23.063, 28.08, 2.4, ""),
    "Algenib": (0.220, 15.18, 2.8, ""), "Alpheratz": (0.140, 29.09, 2.1, ""),
    "Enif": (21.736, 9.88, 2.4, ""), "Mirach": (1.162, 35.62, 2.1, ""),
    "Almach": (2.065, 42.33, 2.1, ""),
    # Персей
    "Mirfak": (3.405, 49.86, 1.8, ""), "Algol": (3.136, 40.96, 2.1, "Алголь"),
    # Орион
    "Betelgeuse": (5.919, 7.41, 0.5, "Бетельгейзе"),
    "Rigel": (5.242, -8.20, 0.13, "Ригель"),
    "Bellatrix": (5.419, 6.35, 1.6, ""), "Mintaka": (5.533, -0.30, 2.2, ""),
    "Alnilam": (5.604, -1.20, 1.7, ""), "Alnitak": (5.679, -1.94, 1.8, ""),
    "Saiph": (5.796, -9.67, 2.1, ""), "Meissa": (5.585, 9.93, 3.4, ""),
    # Телец
    "Aldebaran": (4.599, 16.51, 0.85, "Альдебаран"),
    "Elnath": (5.438, 28.61, 1.65, ""), "Alcyone": (3.791, 24.11, 2.9,
                                                     "Плеяды"),
    "zetTau": (5.627, 21.14, 3.0, ""), "gamTau": (4.330, 15.63, 3.6, ""),
    "epsTau": (4.477, 19.18, 3.5, ""),
    # Близнецы
    "Castor": (7.577, 31.89, 1.6, "Кастор"), "Pollux": (7.755, 28.03, 1.15,
                                                        "Поллукс"),
    "Alhena": (6.629, 16.40, 1.9, ""), "Mebsuta": (6.732, 25.13, 3.0, ""),
    "Tejat": (6.383, 22.51, 2.9, ""), "Wasat": (7.335, 21.98, 3.5, ""),
    # Большой и Малый Пёс
    "Sirius": (6.752, -16.72, -1.46, "Сириус"),
    "Mirzam": (6.378, -17.96, 2.0, ""), "Adhara": (6.977, -28.97, 1.5, ""),
    "Wezen": (7.140, -26.39, 1.8, ""), "Aludra": (7.402, -29.30, 2.4, ""),
    "Procyon": (7.655, 5.22, 0.34, "Процион"),
    "Gomeisa": (7.453, 8.29, 2.9, ""),
    # Возничий
    "Capella": (5.278, 46.00, 0.08, "Капелла"),
    "Menkalinan": (5.992, 44.95, 1.9, ""), "thAur": (5.995, 37.21, 2.6, ""),
    "iotAur": (4.950, 33.17, 2.7, ""),
    # Лев
    "Regulus": (10.140, 11.97, 1.35, "Регул"),
    "Denebola": (11.818, 14.57, 2.1, ""), "Algieba": (10.333, 19.84, 2.0, ""),
    "Zosma": (11.235, 20.52, 2.6, ""), "Chertan": (11.237, 15.43, 3.3, ""),
    "etaLeo": (10.122, 16.76, 3.5, ""), "Adhafera": (10.278, 23.42, 3.4, ""),
    "epsLeo": (9.764, 23.77, 3.0, ""),
    # Дева, Волопас, Северная Корона
    "Spica": (13.420, -11.16, 0.98, "Спика"),
    "Arcturus": (14.261, 19.18, -0.05, "Арктур"),
    "Izar": (14.750, 27.07, 2.4, ""), "Muphrid": (13.911, 18.40, 2.7, ""),
    "Seginus": (14.535, 38.31, 3.0, ""), "Nekkar": (15.032, 40.39, 3.5, ""),
    "delBoo": (15.258, 33.31, 3.5, ""), "Alphecca": (15.578, 26.71, 2.2, ""),
    # Скорпион
    "Antares": (16.490, -26.43, 1.0, "Антарес"),
    "Dschubba": (16.006, -22.62, 2.3, ""), "Acrab": (16.091, -19.81, 2.6, ""),
    "piSco": (15.981, -26.11, 2.9, ""), "tauSco": (16.598, -28.22, 2.8, ""),
    "epsSco": (16.836, -34.29, 2.3, ""), "muSco": (16.864, -38.05, 3.0, ""),
    "Shaula": (17.560, -37.10, 1.6, ""), "Sargas": (17.622, -43.00, 1.9, ""),
    "kapSco": (17.708, -39.03, 2.4, ""),
    # Стрелец («чайник»)
    "KausAus": (18.403, -34.38, 1.8, ""), "Nunki": (18.921, -26.30, 2.0, ""),
    "Ascella": (19.043, -29.88, 2.6, ""), "KausMed": (18.350, -29.83, 2.7, ""),
    "KausBor": (18.466, -25.42, 2.8, ""), "Alnasl": (18.097, -30.42, 3.0, ""),
    "phiSgr": (18.761, -26.99, 3.2, ""), "tauSgr": (19.116, -27.67, 3.3, ""),
    # Геркулес
    "zetHer": (16.688, 31.60, 2.8, ""), "etaHer": (16.715, 38.92, 3.5, ""),
    "piHer": (17.251, 36.81, 3.2, ""), "epsHer": (17.005, 30.93, 3.9, ""),
    # одиночные яркие
    "Fomalhaut": (22.961, -29.62, 1.16, "Фомальгаут"),
    "DenebKaitos": (0.727, -17.99, 2.0, ""),
    "Hamal": (2.120, 23.46, 2.0, ""),
}

# созвездие: (подпись, [(звезда, звезда), ...])
FIGURES = {
    "UMa": ("Большая Медведица", [
        ("Dubhe", "Merak"), ("Merak", "Phecda"), ("Phecda", "Megrez"),
        ("Megrez", "Dubhe"), ("Megrez", "Alioth"), ("Alioth", "Mizar"),
        ("Mizar", "Alkaid")]),
    "UMi": ("Малая Медведица", [
        ("Polaris", "Yildun"), ("Yildun", "epsUMi"), ("epsUMi", "zetUMi"),
        ("zetUMi", "Kochab"), ("Kochab", "Pherkad"), ("Pherkad", "etaUMi"),
        ("etaUMi", "zetUMi")]),
    "Cas": ("Кассиопея", [
        ("Caph", "Schedar"), ("Schedar", "gamCas"), ("gamCas", "Ruchbah"),
        ("Ruchbah", "Segin")]),
    "Cyg": ("Лебедь", [
        ("Deneb", "Sadr"), ("Sadr", "Albireo"), ("delCyg", "Sadr"),
        ("Sadr", "Gienah")]),
    "Lyr": ("Лира", [
        ("Vega", "zetLyr"), ("zetLyr", "Sheliak"), ("Sheliak", "Sulafat"),
        ("Sulafat", "zetLyr")]),
    "Aql": ("Орёл", [("Tarazed", "Altair"), ("Altair", "Alshain")]),
    "Peg": ("Пегас", [
        ("Markab", "Scheat"), ("Scheat", "Alpheratz"),
        ("Alpheratz", "Algenib"), ("Algenib", "Markab"), ("Markab", "Enif")]),
    "And": ("Андромеда", [("Alpheratz", "Mirach"), ("Mirach", "Almach")]),
    "Per": ("Персей", [("Mirfak", "Algol")]),
    "Ori": ("Орион", [
        ("Betelgeuse", "Bellatrix"), ("Bellatrix", "Mintaka"),
        ("Betelgeuse", "Alnitak"), ("Mintaka", "Alnilam"),
        ("Alnilam", "Alnitak"), ("Mintaka", "Rigel"), ("Alnitak", "Saiph"),
        ("Meissa", "Betelgeuse"), ("Meissa", "Bellatrix")]),
    "Tau": ("Телец", [
        ("Aldebaran", "gamTau"), ("gamTau", "epsTau"), ("epsTau", "Elnath"),
        ("Aldebaran", "zetTau")]),
    "Gem": ("Близнецы", [
        ("Castor", "Mebsuta"), ("Mebsuta", "Tejat"), ("Pollux", "Wasat"),
        ("Wasat", "Alhena"), ("Castor", "Pollux")]),
    "CMa": ("Большой Пёс", [
        ("Sirius", "Mirzam"), ("Sirius", "Wezen"), ("Wezen", "Adhara"),
        ("Wezen", "Aludra")]),
    "CMi": ("Малый Пёс", [("Procyon", "Gomeisa")]),
    "Aur": ("Возничий", [
        ("Capella", "Menkalinan"), ("Menkalinan", "thAur"),
        ("thAur", "Elnath"), ("Elnath", "iotAur"), ("iotAur", "Capella")]),
    "Leo": ("Лев", [
        ("Regulus", "etaLeo"), ("etaLeo", "Algieba"), ("Algieba", "Adhafera"),
        ("Adhafera", "epsLeo"), ("Algieba", "Zosma"), ("Zosma", "Denebola"),
        ("Denebola", "Chertan"), ("Chertan", "Regulus"), ("Zosma", "Chertan")]),
    "Boo": ("Волопас", [
        ("Arcturus", "Izar"), ("Izar", "delBoo"), ("delBoo", "Nekkar"),
        ("Nekkar", "Seginus"), ("Seginus", "Arcturus"),
        ("Arcturus", "Muphrid")]),
    "Sco": ("Скорпион", [
        ("Acrab", "Dschubba"), ("Dschubba", "piSco"), ("Dschubba", "Antares"),
        ("Antares", "tauSco"), ("tauSco", "epsSco"), ("epsSco", "muSco"),
        ("muSco", "Sargas"), ("Sargas", "kapSco"), ("kapSco", "Shaula")]),
    "Sgr": ("Стрелец", [
        ("Alnasl", "KausMed"), ("KausMed", "KausAus"), ("KausAus", "Alnasl"),
        ("KausMed", "KausBor"), ("KausMed", "phiSgr"), ("KausBor", "phiSgr"),
        ("phiSgr", "Nunki"), ("Nunki", "tauSgr"), ("tauSgr", "Ascella"),
        ("Ascella", "phiSgr"), ("Ascella", "KausAus")]),
    "Her": ("Геркулес", [
        ("zetHer", "epsHer"), ("epsHer", "piHer"), ("piHer", "etaHer"),
        ("etaHer", "zetHer")]),
}

# красноватые/оранжевые звёзды (цвет точки)
WARM = {"Betelgeuse", "Antares", "Aldebaran", "Arcturus", "Pollux",
        "Kochab", "Dubhe", "Schedar", "Mirach", "Enif", "Scheat", "Hamal"}
BLUE = {"Rigel", "Spica", "Regulus", "Vega", "Sirius", "Bellatrix",
        "Alnilam", "Deneb", "Alcyone", "Shaula"}
