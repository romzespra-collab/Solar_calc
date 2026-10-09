# solar_calc.spec  v1.9.4 — PyInstaller, onefile, без консоли
# v1.9.4: + modules/mod_region.py (погода региона за 5 лет)
# v1.9.3: без изменений сборки, версия поднята вместе с программой
# v1.9.2: без изменений сборки, версия поднята вместе с программой
# v1.9.1: без изменений сборки, версия поднята вместе с программой
# v1.9.0: + modules/mod_constructor.py (конструктор станции), без mod_scheme
# v1.5.0: + файл полной базы панелей modules/panels_db.tsv.gz (datas)
# v1.4.0: + модули погоды, неба, астрономии, прогноза
# v1.3.0: программа разбита на модули: solar_calc.py, solar_calc_qt.py, modules/ — всё вшивается в EXE
# v1.2.1: без изменений сборки, версия поднята вместе с программой
# v1.2.0: без изменений сборки, версия поднята вместе с программой
# v1.1.0: без изменений сборки, версия поднята вместе с программой
# v1.0.0: первая версия
block_cipher = None

a = Analysis(
    ['solar_calc.pyw'],
    pathex=['.'],
    binaries=[],
    datas=[('modules/panels_db.tsv.gz', 'modules')],
    hiddenimports=['solar_calc', 'solar_calc_qt', 'modules.mod_base', 'modules.mod_panels', 'modules.mod_equipment',
                   'modules.mod_sun', 'modules.mod_fields', 'modules.mod_config', 'modules.mod_model',
                   'modules.mod_checks', 'modules.mod_pvgis', 'modules.mod_theme', 'modules.mod_widgets',
                   'modules.mod_page_settings', 'modules.mod_page_results', 'modules.mod_page_tools',
                   'modules.mod_astro', 'modules.mod_stars', 'modules.mod_weather', 'modules.mod_forecast',
                   'modules.mod_wx_draw', 'modules.mod_sky', 'modules.mod_page_sky', 'modules.mod_constructor', 'modules.mod_region'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngine',
              'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.QtMultimedia', 'PySide6.QtQuick',
              'PySide6.QtQml', 'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'tkinter'],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='solar_calc',
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
