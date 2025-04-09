#!/bin/sh
git pull
conda update -n base -c defaults conda
conda activate genius
conda update --all -y
python --version
python -m pip install --upgrade pip
pip install --upgrade -r requirements.txt
