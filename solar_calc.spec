# solar_calc.spec  v1.11.8 — PyInstaller, onefile, без консоли
# v1.11.8: без изменений сборки (модуль gh_update 1.4.3), версия поднята
# v1.11.7: без изменений сборки (модуль gh_update 1.4.2), версия поднята
# v1.11.6: без изменений сборки (Python 3.12+, PySide6 ≥ 6.10.1, gh_update 1.4.1), версия поднята
# v1.11.5: без изменений сборки (модуль gh_update 1.4.0 — обновление только Python), версия поднята
# v1.11.4: без изменений сборки (модуль gh_update 1.3.3), версия поднята
# v1.11.3: без изменений сборки (модуль gh_update 1.2.0), версия поднята
# v1.11.2: без изменений сборки (модуль gh_update 1.1.3), версия поднята
# v1.11.1: без изменений сборки (модуль gh_update 1.1.1), версия поднята
# v1.11.0: + modules/gh_update.py, gh_update_qt.py, gh_update_help.py (обновление с GitHub)
# v1.10.0: без изменений сборки (новые модули mod_green, mod_page_green вшиваются сами), версия поднята
# Более ранние версии — в истории git.
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
                   'modules.mod_wx_draw', 'modules.mod_sky', 'modules.mod_page_sky', 'modules.mod_constructor', 'modules.mod_region',
                   'modules.gh_update', 'modules.gh_update_qt', 'modules.gh_update_help'],
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
