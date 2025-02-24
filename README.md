# Automatic appointment booking for Bürgerservice Potsdam

This script automatically books an appointment at the Bürgerservice Potsdam. It uses the Playwright headless browser automation library to (periodically) check for available appointments and book one as soon as it is available. Since booking requires solving a captcha, it sends a screenshot of the captcha to the user via Telegram. The user then has about 5 minutes to solve the captcha and send the solution back to the bot. The bot will then automatically fill out the form and book the appointment.

## Requirements
- Telegram bot token (see [here](https://core.telegram.org/bots#6-botfather))
- Python venv >= 3.12

## Installation
1. Clone the repository
2. Run `install.sh` to create a virtual environment and install the required packages
3. Copy `.env.example` to `.env` and fill in the required information
4. Run `uninstall.sh` to remove the virtual environment and uninstall playwright.

## Usage
1. Run `source venv/bin/activate` to activate the virtual environment
2. Run `./main.py` to start the script. See `./main.py --help` for available options.
   - `--periodic`: Will periodically check for appointments.
   - `--minutes` & `--seconds`: Control period between checks.
   - `--request {REQUEST_ID} {NUM}`: Use in combination with `--no-interactive` to book an appointment without user interaction. See `request-types.json` for possible request types.

## Disclaimer
This script is provided as is and is intended for educational purposes only. Use at your own risk. The author is not responsible for any damage caused by the use of this script.

## Roadmap
- [ ] Fix log levels to avoid memory issues
  - [ ] Use logfile
  - [ ] Only log INFO and higher to console
  - [ ] Only log WARNING and higher to Telegram
- [ ] Dockerize the project
- [ ] Add support for earliest/latest booking date/time
- [ ] Add support for detailed weekday/time selection, e.g. Wednesday 10:00-12:00, Thursday 14:00-16:00
- [ ] Add `configuration.yaml` selecting the appointment type, earliest/latest booking date/time, detailed weekday/time selection and passing personal data
- [ ] Convert to standalone Telegram bot, that accepts users requests and books appointments automatically

## Contributing
Feel free to contribute to this project by opening an issue or a pull request.
