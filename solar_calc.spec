# solar_calc.spec  v1.2.0 — PyInstaller, onefile, без консоли
# v1.2.0: без изменений сборки, версия поднята вместе с программой
# v1.1.0: без изменений сборки, версия поднята вместе с программой
# v1.0.0: первая версия
block_cipher = None

a = Analysis(
    ['solar_calc.pyw'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
