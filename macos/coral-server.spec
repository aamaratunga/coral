# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for building the Coral server into a standalone macOS binary.

Usage:
    cd <coral-repo>
    pyinstaller macos/coral-server.spec

Or use the build script:
    ./macos/scripts/build-server.sh
"""

import os
import importlib
import pathlib

block_cipher = None

# Root of the coral repo
repo_root = os.path.abspath(os.path.join(SPECPATH, '..'))
src_dir = os.path.join(repo_root, 'src')
coral_pkg = os.path.join(src_dir, 'coral')

# Collect all coral submodules for hidden imports
hidden_imports = [
    # Core
    'coral',
    'coral.web_server',
    'coral.config',
    'coral.launch',
    'coral.tray',
    # Agents
    'coral.agents',
    'coral.agents.base',
    'coral.agents.claude',
    'coral.agents.gemini',
    # API routes
    'coral.api',
    'coral.api.live_sessions',
    'coral.api.history',
    'coral.api.system',
    'coral.api.tasks',
    'coral.api.schedule',
    'coral.api.uploads',
    'coral.api.webhooks',
    'coral.api.themes',
    'coral.api.templates',
    'coral.api.board_remotes',
    # Store
    'coral.store',
    'coral.store.connection',
    'coral.store.sessions',
    'coral.store.git',
    'coral.store.tasks',
    'coral.store.schedule',
    'coral.store.webhooks',
    'coral.store.remote_boards',
    # Tools
    'coral.tools',
    'coral.tools.session_manager',
    'coral.tools.tmux_manager',
    'coral.tools.log_streamer',
    'coral.tools.pulse_detector',
    'coral.tools.jsonl_reader',
    'coral.tools.cron_parser',
    'coral.tools.run_callback',
    'coral.tools.utils',
    'coral.tools.update_checker',
    'coral.tools.icon_cli',
    # Background tasks
    'coral.background_tasks',
    'coral.background_tasks.session_indexer',
    'coral.background_tasks.auto_summarizer',
    'coral.background_tasks.git_poller',
    'coral.background_tasks.idle_detector',
    'coral.background_tasks.scheduler',
    'coral.background_tasks.webhook_dispatcher',
    'coral.background_tasks.board_notifier',
    'coral.background_tasks.remote_board_poller',
    # Hooks
    'coral.hooks',
    'coral.hooks.task_state',
    'coral.hooks.agentic_state',
    'coral.hooks.utils',
    'coral.hooks.message_check',
    # Message board
    'coral.messageboard',
    'coral.messageboard.store',
    'coral.messageboard.api',
    'coral.messageboard.app',
    'coral.messageboard.cli',
    # Dependencies
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'aiosqlite',
    'jinja2',
    'jinja2.ext',
    'fastapi',
    'starlette',
    'starlette.responses',
    'starlette.websockets',
    'httpx',
    'multipart',
    'multipart.multipart',
    'email.mime.multipart',
    'email.mime.text',
]

# Data files to include in the bundle
datas = [
    # Templates
    (os.path.join(coral_pkg, 'templates'), 'coral/templates'),
    # Static assets
    (os.path.join(coral_pkg, 'static'), 'coral/static'),
    # Bundled themes
    (os.path.join(coral_pkg, 'bundled_themes'), 'coral/bundled_themes'),
    # Protocol docs
    (os.path.join(coral_pkg, 'PROTOCOL.md'), 'coral'),
    # Message board agent guide
    (os.path.join(coral_pkg, 'messageboard', 'AGENT_GUIDE.md'), 'coral/messageboard'),
]

a = Analysis(
    [os.path.join(coral_pkg, 'web_server.py')],
    pathex=[src_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'PIL',
        'cv2',
        'torch',
        'tensorflow',
        'rumps',  # Not needed in bundled mode
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
    [],
    exclude_binaries=True,
    name='coral-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    target_arch='arm64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='coral-server',
)
