#!/bin/bash

DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/venv/bin/python" "$DIR/app_gui.py"
