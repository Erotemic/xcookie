#!/bin/bash
flake8 ./xcookie --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 ./tests --count --select=E9,F63,F7,F82 --show-source --statistics
