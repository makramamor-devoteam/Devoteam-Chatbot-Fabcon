#!/bin/bash
python3 -m gunicorn app:app -c gunicorn.conf.py --bind=0.0.0.0:$PORT
