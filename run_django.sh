#!/bin/bash
# Django admin panelni ishga tushirish skripti

cd "$(dirname "$0")/src/config"
python manage.py runserver

