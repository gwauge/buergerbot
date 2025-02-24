#!/bin/bash

# activate virtual environment
source .venv/bin/activate

# uninstall dependencies
playwright uninstall
pip uninstall -r requirements.txt

echo "Successfully uninstalled all dependencies"
