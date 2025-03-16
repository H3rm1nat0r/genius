#!/bin/sh
git pull
conda activate genius
conda update --all -y
python --version
python -m pip install --upgrade pip
pip install --upgrade -r requirements.txt
# pip freeze > requirements.txt 
pip freeze | awk -F "==" '{ print $1 }' > requirements.txt 
