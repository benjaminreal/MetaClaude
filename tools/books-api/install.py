#!/usr/bin/env python3
"""Run only after approval: install candidate and register local book tools."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tomllib
from books_api import config, secure_dir

SOURCE=Path(__file__).resolve().parent
# Set METACLAUDE_PROJECT to the 31_MetaClaude repository root before running.
PROJECT=Path(os.environ['METACLAUDE_PROJECT']) if os.environ.get('METACLAUDE_PROJECT') else None
CANONICAL=PROJECT/'tools/books-api' if PROJECT else None
RUNTIME=Path.home()/'Library/Application Support/MetaClaude/books-api'
NAME='books-api'

def main():
    if PROJECT is None:raise SystemExit('Set METACLAUDE_PROJECT to the 31_MetaClaude repository root')
    if sys.version_info<(3,12):raise SystemExit('Python 3.12+ required')
    codex=shutil.which('codex');claude=shutil.which('claude')
    if not codex or not claude:raise SystemExit('Both harness CLIs required')
    codex_config=Path.home()/'.codex/config.toml'
    claude_config=Path.home()/'.claude.json'
    codex_data=tomllib.loads(codex_config.read_text())
    claude_data=json.loads(claude_config.read_text())
    if NAME in codex_data.get('mcp_servers',{}) or NAME in claude_data.get('mcpServers',{}):
        raise SystemExit('Name already registered; review before changing anything')
    if CANONICAL.exists():
        raise SystemExit('Canonical destination already exists; review before changing anything')
    settings_path=RUNTIME/'config.json'
    settings_before=settings_path.read_bytes() if settings_path.exists() else None
    if RUNTIME.exists():
        secure_dir(RUNTIME)
        if {p.name for p in RUNTIME.iterdir()}-{'config.json'}:
            raise SystemExit('Unexpected runtime files; review before changing anything')
        config(settings_path)
    subprocess.run([sys.executable,'-m','unittest','-v','test_books_api.py'],cwd=SOURCE,check=True)
    old_umask=os.umask(0o077)
    try:
        backup=Path.home()/'Library/Application Support/MetaClaude/backups'/('books-api-'+time.strftime('%Y%m%dT%H%M%S'))
        backup.mkdir(parents=True,mode=0o700)
        for path in [codex_config,claude_config]:
            shutil.copyfile(path,backup/(path.parent.name+'-'+path.name))
        CANONICAL.mkdir(parents=True)
        RUNTIME.mkdir(parents=True,exist_ok=True,mode=0o700)
        for name in ['books_api.py','test_books_api.py','install.py','README.md','PLAN.md']:
            shutil.copyfile(SOURCE/name,CANONICAL/name)
        shutil.copyfile(SOURCE/'books_api.py',RUNTIME/'books_api.py')
        # Preserve the owner's separately entered key byte-for-byte.
        if settings_before is None:
            settings_path.write_text(json.dumps({'country':'MX'},indent=2)+'\n')
        (RUNTIME/'state').mkdir(mode=0o700)
        python=str(Path(sys.executable).resolve())
        command=[python,str(RUNTIME/'books_api.py'),'serve']
        subprocess.run([codex,'mcp','add',NAME,'--',*command],check=True)
        subprocess.run([claude,'mcp','add','--scope','user','--transport','stdio',NAME,'--',*command],check=True)
        new_codex=tomllib.loads(codex_config.read_text())['mcp_servers'][NAME]
        new_claude=json.loads(claude_config.read_text())['mcpServers'][NAME]
        if new_codex.get('command')!=python or new_claude.get('command')!=python:
            raise SystemExit('Registered command mismatch; inspect backups')
        if new_codex.get('args')!=command[1:] or new_claude.get('args')!=command[1:]:
            raise SystemExit('Registered arguments mismatch; inspect backups')
        codex_after=tomllib.loads(codex_config.read_text())
        claude_after=json.loads(claude_config.read_text())
        old_node=codex_data.get('mcp_servers',{}).get('node_repl',{})
        new_node=codex_after.get('mcp_servers',{}).get('node_repl',{})
        if old_node.get('args')==[] and 'args' not in new_node:
            content=codex_config.read_text()
            marker='[mcp_servers.node_repl]\n'
            if content.count(marker)!=1:
                raise SystemExit('Cannot safely restore omitted node_repl.args')
            codex_config.write_text(content.replace(marker,marker+'args = []\n',1))
            codex_after=tomllib.loads(codex_config.read_text())
        codex_after['mcp_servers'].pop(NAME)
        claude_after['mcpServers'].pop(NAME)
        if codex_after!=codex_data or claude_after!=claude_data:
            raise SystemExit('Unrelated configuration changed; inspect backups')
        if settings_before is not None and settings_path.read_bytes()!=settings_before:
            raise SystemExit('Owner settings changed unexpectedly')
        receipt={'status':'installed_configuration_verified','fresh_session_tools':'UNVERIFIED','google_books':'CONFIGURED_UNVERIFIED' if config(settings_path).get('google_books_api_key') else 'UNCONFIGURED','open_library_live':'UNVERIFIED_AFTER_INSTALL','backup_dir':str(backup),'canonical':str(CANONICAL),'runtime':str(RUNTIME),'python':python,'owner_settings_preserved':settings_before is not None,'other_configuration_preserved':True,'sha256':hashlib.sha256((RUNTIME/'books_api.py').read_bytes()).hexdigest()}
        (RUNTIME/'install_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt,indent=2))
    finally:os.umask(old_umask)

if __name__=='__main__':main()
