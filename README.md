# Automatic appointment booking for Bürgerservice Potsdam

This script automatically books an appointment at the Bürgerservice Potsdam. It uses the Playwright headless browser automation library to (periodically) check for available appointments and book one as soon as it is available. Since booking requires solving a captcha, it sends a screenshot of the captcha to the user via Telegram. The user then has about 5 minutes to solve the captcha and send the solution back to the bot. The bot will then automatically fill out the form and book the appointment.

## Disclaimer
This script is provided as is and is intended for educational purposes only. Use at your own risk. The author is not responsible for any damage caused by the use of this script.

## Requirements
- Telegram bot token (see [here](https://core.telegram.org/bots#6-botfather))

## Use with Docker (recommended)

### Docker Compose
1. Create `compose.yaml` file. See [compose.yaml](compose.yaml) for an example.
2. Fill in `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` environment variables or create a `.env` file.
3. Create a `config.yaml` file. See [config.yaml.example](config.yaml.example) for an example and [Configuration](#configuration) for a detailed explanation of the configuration options.
4. Run the Docker container:
  ```bash
  docker compose up
  ```

### Use pre-built image
1. Create a `config.yaml` file. See [config.yaml.example](config.yaml.example) for an example and [Configuration](#configuration) for a detailed explanation of the configuration options.
2. Run image:
  ```bash
  docker run \
    -it --rm \
    -e TELEGRAM_TOKEN=YOUR_TELEGRAM
    -e TELEGRAM_CHAT_ID=YOUR_CHAT_ID
    -v ./config.yaml:/app/config.yaml \
    ghcr.io/gwauge/buergerbot:latest
  ```

### Build image manually
1. Clone the repository
2. Build the Docker image:
  ```bash
  docker build -t buergerbot .
  ```
1. Copy `.env.example` to `.env` and fill in the required information, specifically:
   - `TELEGRAM_TOKEN`: Your Telegram bot token
   - `TELEGRAM_CHAT_ID`: Your Telegram chat ID
2. Copy `config.yaml.example` to `config.yaml`. See `config.yaml.example` for an example. Also see [Configuration](#configuration) for a detailed explanation of the configuration options.
3. Run the Docker container:
  ```bash
  docker run \
    -it --rm \
    --env-file .env \
    -v ./config.yaml:/app/config.yaml \
    buergerbot
  ```
  It is important to pass the `.env` and `config.yaml` files to the containerm as they contain the necessary configuration and it won't run properly without them.

## Use without Docker
### Dependencies
See `requirements.txt` for a list of required packages.

### Installation
1. Clone the repository
2. Run `install.sh` to create a virtual environment and install the required packages
3. Copy `.env.example` to `.env` and fill in the required information

### Usage
1. Run `source venv/bin/activate` to activate the virtual environment
2. Run `./main.py` to start the script. See `./main.py --help` for available options.
   - `--periodic`: Will periodically check for appointments.
   - `--minutes` & `--seconds`: Control period between checks.
   - `--request {REQUEST_ID} {NUM}`: Use in combination with `--no-interactive` to book an appointment without user interaction. See `request-types.json` for possible request types.

## Configuration
An example configuration file is provided in `config.yaml.example`.

### Periodic
Can be set by providing a time interval in the format `MM:SS`. The script will then check for available appointments every `MM` minutes and `SS` seconds.

### Personal data
The following personal data is required to book an appointment:
- `first_name`: Your first name
- `last_name`: Your last name
- `email`: Your email address
- `phone`: Your phone number
- `foa`: Your form of address. Possible values are `herr`, `frau`, or `firma`.

### Request types
A single appointment can contain multiple request types. The `request_types` section should contain a list of these types.

Each request type should contain the following field:
- `id`: The request type ID. This can be found by inspecting the website.

Optionally, a request type can also contain the following field:
- `number_of_people`: The number of people for this request type. Default is 1.

### Weekdays
The `weekdays` section should contain a key for each weekday that you would like to specify availability for. Each availability entry should contain the following keys:
- `from`: The start time of the availability in the format `HH:MM`.
- `to`: The end time of the availability in the format `HH:MM`.

All other times during that time are considered unavailable.
If a weekday is not specified, the script will assume that you are available all day.

### Dates
Inside the `dates` section, you can optionally specify a list of dates to be excluded in the format `YYYY-MM-DD` under the key `exclude`.
Further, you can specify `earliest` and `latest` dates to book an appointment. If these are not specified, the script will book the first available appointment, that fits the specified requirements.

## Roadmap
- [ ] Fix log levels to avoid memory issues
  - [ ] Use logfile
  - [ ] Only log INFO and higher to console
  - [ ] Only log WARNING and higher to Telegram
- [x] Dockerize the project
- [x] Add support for earliest/latest booking date/time
- [x] Add support for detailed weekday/time selection, e.g. Wednesday 10:00-12:00, Thursday 14:00-16:00
- [x] Add `configuration.yaml` for selecting the appointment type, earliest/latest booking date/time, detailed weekday/time selection and passing personal data
- [x] Automatically build and push Docker image to Docker Hub & GHCR
- [x] Add Docker compose example

## Contributing
Feel free to contribute to this project by opening an issue or a pull request.
