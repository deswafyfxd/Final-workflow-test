name: Check Workflow Status

on:
  schedule:
    - cron: '0 23 * * *'

jobs:
  check_status:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout repository
      uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.x'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install requests

    - name: Run script
      run: python your_script.py
      env:
        DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK }}
