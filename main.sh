#!/bin/bash

clear

# 1. Buat virtual environment
python3 -m venv venv

# 2. Aktifkan virtual environment
source venv/bin/activate

# 3. Jalankan script python
python -u main.py