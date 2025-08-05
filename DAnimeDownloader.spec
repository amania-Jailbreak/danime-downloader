# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 隠れたインポートを明示的に指定
hidden_imports = [
    'pywidevine',
    'pywidevine.cdm',
    'pywidevine.device',
    'pywidevine.pssh',
    'bs4',
    'requests',
    'tqdm',
    'xml.etree.ElementTree',
    'unicodedata',
    're',
    'json',
    'subprocess',
    'tempfile',
    'base64',
    'urllib.parse',
    'argparse',
    'time',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # README等のファイルをバンドルする場合
        ('README.md', '.'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 不要なモジュールを除外
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DAnimeDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # UPXで圧縮してサイズを削減
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # コンソールアプリケーション
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # アイコンファイルがあれば指定
)
