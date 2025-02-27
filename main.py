#!/usr/bin/env python
import argparse
import enum
import threading
import time
from datetime import date
import os
import json
import asyncio

from playwright.sync_api import sync_playwright, ElementHandle
import yaml
from cerberus import Validator

from lib import logger, parse_german_date, telegram_send_photo, config_schema

URL = "https://egov.potsdam.de/tnv/?START_OFFICE=buergerservice"
dates: dict[date, int] = {}


def grab_day(button: ElementHandle) -> int:
    div = button.query_selector("div.ekolCalendar_DayNumberInRange")
    if div:
        return int(div.inner_text())
    raise Exception("No day found")


def grab_number_of_appointments(button: ElementHandle) -> int:
    div = button.query_selector("div.ekolCalendar_FreeTimeContainer")
    if div:
        return int(div.inner_text().split(" ")[0])
    raise Exception("No number of appointments found")


class FormOfAddress(enum.Enum):
    M = "herr"
    F = "frau"
    BLANK = "x"
    COMPANY = "firma"


class PersonalData:
    foa: FormOfAddress
    first_name: str
    last_name: str
    phone: str
    email: str


class Configuration:
    """
    A class used to represent the configuration of the bot.

    Attributes
    ----------
    requests : dict[str, int]
        A dictionary to store user requests with string keys and integer values.
    personal_data : dict[str, any]
        A dictionary to store personal data with string keys and values of any type.
    earliest_date : date | None
        The earliest date for appointments.
    latest_date : date | None
        The latest date for appointments.
    exclude_dates : list[date]
        A list of dates to exclude from the search.
    weekdays : dict[str, list[dict[str, str]]]
        A dictionary to store the available time slots for each
        weekday with string keys and lists of dictionaries
        with string keys and values.

    Methods
    -------
    __init__():
        Initializes the Configuration class.
    """
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.requests: dict[str, int] = {}
        self.personal_data: PersonalData = PersonalData()
        self.earliest_date: date | None = args.earliest_date
        self.latest_date: date | None = args.earliest_date
        self.exclude_dates: list[date] = []
        self.weekdays: dict[str, list[dict[str, str]]] = {}

        self.periodic = args.periodic
        self.minutes = args.minutes
        self.seconds = args.seconds

        self.requests: dict[str, int] = {}

        if args.no_interactive and args.config:
            self.parse_config()
        else:
            self.ask_personal_data()
            self.ask_request_types()

    def ask_personal_data(self):
        while True:
            if not args.no_interactive:
                print("Please enter your personal data:")

            # FOA
            foa = (args.foa.value if args.foa else None) or os.getenv("FOA")
            # check if form of address is valid
            if args.no_interactive and (foa is None or foa == ""):
                logger.error("--no-interactive requires a valid form of address. Please pass a valid form of address through the --foa argument or the FOA environment variable.")
                raise SystemExit(1)
            elif foa not in FormOfAddress._value2member_map_:
                logger.error("Invalid form of address found in args or environment variable. Please enter a valid form of address.")
                while True:
                    foa = input("Form of address (herr, frau, x, firma): ")
                    try:
                        self.personal_data.foa = FormOfAddress._value2member_map_[foa]
                        break
                    except KeyError:
                        logger.error("Invalid form of address. Please try again.")
            else:
                self.personal_data.foa = FormOfAddress._value2member_map_[foa]
                print(f"Form of address: {foa}")

            # first name
            first_name = args.first_name or os.getenv("FIRST_NAME")
            if args.no_interactive and (first_name is None or first_name == ""):
                logger.error("--no-interactive requires a valid first name. Please pass a valid first name through the --first-name argument or the FIRST_NAME environment variable.")
                raise SystemExit(1)
            elif first_name is None or first_name == "":
                while True:
                    first_name = input("First name: ")
                    if first_name:
                        self.personal_data.first_name = first_name
                        break
                    else:
                        logger.error("First name cannot be empty. Please try again.")
            else:
                self.personal_data.first_name = first_name
                print(f"First name: {first_name}")

            # last name
            last_name = args.last_name or os.getenv("LAST_NAME")
            if args.no_interactive and (last_name is None or last_name == ""):
                logger.error("--no-interactive requires a valid last name. Please pass a valid last name through the --last-name argument or the LAST_NAME environment variable.")
                raise SystemExit(1)
            elif last_name is None or last_name == "":
                while True:
                    last_name = input("Last name: ")
                    if last_name:
                        self.personal_data.last_name = last_name
                        break
                    else:
                        logger.error("Last name cannot be empty. Please try again.")
            else:
                self.personal_data.last_name = last_name
                print(f"Last name: {last_name}")

            # phone
            phone = args.phone or os.getenv("PHONE")
            if args.no_interactive and (phone is None or phone == ""):
                logger.error("--no-interactive requires a valid phone number. Please pass a valid phone number through the --phone argument or the PHONE environment variable.")
                raise SystemExit(1)
            elif phone is None or phone == "":
                while True:
                    phone = input("Phone number: ")
                    if phone:
                        self.personal_data.phone = phone
                        break
                    else:
                        logger.error("Phone number cannot be empty. Please try again.")
            else:
                self.personal_data.phone = phone
                print(f"Phone number: {phone}")

            # email
            email = args.email or os.getenv("EMAIL")
            if args.no_interactive and (email is None or email == ""):
                logger.error("--no-interactive requires a valid email address. Please pass a valid email address through the --email argument or the EMAIL environment variable.")
                raise SystemExit(1)
            elif email is None or email == "":
                while True:
                    email = input("Email address: ")
                    if email:
                        self.personal_data.email = email
                        break
                    else:
                        logger.error("Email address cannot be empty. Please try again.")
            else:
                self.personal_data.email = email
                print(f"Email address: {email}")

            if args.no_interactive or input("Is this correct? (y/n): ").lower() == "y":
                break

    def ask_request_types(self):
        # if no interactive mode is enabled, use request types from arguments
        if args.no_interactive:
            if not args.request:
                logger.error("No request types specified")
                raise SystemExit(1)

            for request_id, number in args.request:
                self.requests[request_id] = int(number)

        # if interactive mode is enabled, ask user for request types
        else:
            # read in request types from request-types.json
            request_types: dict[str, str] = {}
            with open("request-types.json", "r") as file:
                request_types = json.load(file)

            # ask user to select request type and number of people
            while True:
                while True:
                    print("Please select the type of request you would like to add:")
                    items = list(request_types.items())
                    for i, (request_id, request_name) in enumerate(items):
                        # skip already selected requests
                        if request_id in self.requests:
                            continue
                        print(f"\t{i + 1:2}: {request_name}")

                    while True:
                        try:  # check if user input is valid
                            selected_request = items[int(input("Enter the number of the request type: ")) - 1]
                            selected_number = int(input("Enter the number of people: "))
                            break
                        except (ValueError, IndexError):
                            logger.error("Invalid input. Please try again.")

                    print(f"You have selected: '{selected_request[1]}' for {selected_number} people")

                    if input("Is this correct? (y/n): ").lower() == "y":
                        self.requests[selected_request[0]] = selected_number
                        break

                if input("Would you like to add another request? (y/n): ").lower() != "y":
                    break

    def parse_config(self):
        if not os.path.exists(args.config):
            logger.error("Config file not found")
            raise SystemExit(1)

        with open(args.config, "r") as file:
            config_dict = yaml.safe_load(file)

        validator = Validator(config_schema)
        config = validator.validated(config_dict)
        if not config:
            logger.error(
                "The configuration file contains errors:\n%s",
                json.dumps(validator.errors, indent=4))
            exit(1)

        if config.get("periodic"):
            self.periodic = True
            self.minutes = int(config["periodic"].split(":")[-2])
            self.seconds = int(config["periodic"].split(":")[-1])

        self.personal_data.foa = FormOfAddress._value2member_map_[config["personal_data"]["foa"]]
        self.personal_data.first_name = config["personal_data"]["first_name"]
        self.personal_data.last_name = config["personal_data"]["last_name"]
        self.personal_data.phone = config["personal_data"]["phone"]
        self.personal_data.email = config["personal_data"]["email"]

        for request in config["requests"]:
            self.requests[request["id"]] = request["number_of_people"]

        for weekday, times in config["weekdays"]["available"].items():
            # select whole day if empty
            if not times and weekday not in config["weekdays"]["unavailable"]:
                self.weekdays[weekday] = [{"from": "00:00", "to": "23:59"}]
            else:
                self.weekdays[weekday] = times

        if config.get("dates"):
            if config["dates"].get("earliest"):
                self.earliest_date = date.fromisoformat(config["dates"]["earliest"])
            if config["dates"].get("latest"):
                self.latest_date = date.fromisoformat(config["dates"]["latest"])

            if config["dates"].get("exclude"):
                self.exclude_dates = [date.fromisoformat(d) for d in config["dates"]["exclude"]]

    def __str__(self):
        s = ""
        if self.periodic:
            s += "Periodic: {}\n".format(self.periodic)

        s += "Personal data:\n\tFOA: {}\n\tFirst name: {}\n\tLast name: {}\n\tPhone: {}\n\tEmail: {}\n".format(
            self.personal_data.foa.value,
            self.personal_data.first_name,
            self.personal_data.last_name,
            self.personal_data.phone,
            self.personal_data.email)

        s += "\nRequests:\n"
        for request_id, number in self.requests.items():
            s += f"\t{request_id}: {number}\n"

        s += "\nWeekdays:\n"
        for weekday, times in self.weekdays.items():
            s += f"\t{weekday}: {times}\n"

        s += "\nEarliest date: {}\nLatest date: {}\n".format(self.earliest_date, self.latest_date)

        s += "\nExcluded dates:\n"
        for d in self.exclude_dates:
            s += f"\t{d}\n"

        return s


# Start a separate event loop in a background thread
def start_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def run(args: dict[str, any], config: Configuration) -> bool:

    # Create a new event loop for the thread
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=start_event_loop, args=(loop,), daemon=True)
    thread.start()

    success = False

    # TODO: check if internet connection is available

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chromium", headless=args.headless)
        context = browser.new_context()
        page = context.new_page()

        # navigate to the website
        page.goto(URL)

        # click "Termin vereinbaren"
        page.click("button#action_officeselect_termnew_prefix1333626470")
        page.wait_for_load_state("networkidle")

        # Select type of appointment by setting number of people
        # page.select_option("select#id_1335352852", value="1")
        for request_id, number in config.requests.items():
            page.select_option(f"select#{request_id}", value=str(number))

        # Confirm and continue
        page.click("button#action_concernselect_next")
        page.wait_for_load_state("networkidle")

        # Continue again by pressing "Weiter"
        page.click("button#action_concerncomments_next")
        page.wait_for_load_state("networkidle")

        # click through months
        while not success:
            # grab monthtable0
            for table_name in ["monthtable0", "monthtable1"]:
                monthtable = page.query_selector(f"table#{table_name}")
                month_str, year_str = monthtable\
                    .query_selector("caption")\
                    .inner_text().split(" ")
                year = int(year_str)

                # check for free days inside
                free_days = monthtable.query_selector_all(".ekolCalendar_ButtonDayFreeX")

                # free_day = free_days[0]  # select first free day
                for free_day in free_days:
                    # get day and number of appointments
                    day = grab_day(free_day)
                    free = grab_number_of_appointments(free_day)
                    parsed_date = parse_german_date(day, month_str, year)
                    dates[parsed_date] = free

                    # check if date is between earliest and latest date
                    if config.earliest_date and parsed_date < config.earliest_date:
                        # logger.debug("Skipping %s %d, %d as it is before the earliest date", month_str, day, year)
                        continue
                    if config.latest_date and parsed_date > config.latest_date:
                        # logger.debug("Skipping %s %d, %d and later days", month_str, day, year)
                        break

                    if parsed_date in config.exclude_dates:
                        break

                    # get weekday from parsed_date in lower case
                    weekday = parsed_date.strftime("%A").lower()
                    month_str_localized = parsed_date.strftime("%B")

                    # log free day by using local date format: month, day year in local language
                    logger.debug("%s %d, %d: %d appointments available",
                                 month_str_localized, day, year, free)

                    # book appointment
                    if args.disable_booking:
                        continue

                    # click on the day
                    free_day.click()
                    page.wait_for_load_state("networkidle")

                    # Select the first available time slot
                    time_select = page.query_selector("#ekolcalendartimeselectbox")

                    # find first time slot, which satiesfies the requirements
                    options = time_select.query_selector_all("option")
                    value = None
                    for option in options:
                        option_value = option.get_attribute("value")
                        if option_value:
                            option_time = time.strftime('%H:%M', time.localtime(int(option_value) / 1000))
                            for time_slot in config.weekdays[weekday]:
                                if time_slot["from"] <= option_time <= time_slot["to"]:
                                    value = option_value
                                    break
                        if value:
                            break
                    if not value:
                        logger.error("No suitable time slot found for %s %d, %d", month_str, day, year)
                        continue

                    # parse time from unix timestamp
                    time_str = time.strftime('%H:%M', time.localtime(int(value) / 1000))
                    logger.warning("Booking appointment for %s %d, %d at %s",
                                   month_str, day, year, time_str)

                    # select the time
                    time_select.select_option(value=value)

                    # click "Ok" button
                    ok_button = page.query_selector("button:has-text('Ok')")
                    ok_button.click()
                    page.wait_for_load_state("networkidle")

                    # enter personal data
                    page.query_selector("#anrede").select_option(value=config.personal_data.foa.value)
                    page.query_selector("input#vorname").fill(config.personal_data.first_name)
                    page.query_selector("input#nachname").fill(config.personal_data.last_name)
                    page.query_selector("input#telefon").fill(config.personal_data.phone)
                    page.query_selector("input#email").fill(config.personal_data.email)

                    # while #cssconstants_captcha_image exists
                    while page.query_selector("#cssconstants_captcha_image"):

                        # create captacha screenshot
                        captcha = page.locator("#cssconstants_captcha_image")
                        captcha.wait_for(state="visible")
                        image_bytes = captcha.screenshot()

                        # wait for captcha to be solved
                        future = asyncio.run_coroutine_threadsafe(telegram_send_photo(image_bytes), loop)
                        captcha_answer = future.result()

                        if not captcha_answer:
                            break

                        # enter captcha
                        page.query_selector("#captcha_userinput").fill(captcha_answer)

                        page.wait_for_timeout(2 * 1000)  # TODO: remove

                        # click "Weiter"
                        page.query_selector("button#action_userdata_next").click()
                        page.wait_for_load_state("networkidle")

                    # handle confirmation
                    page.query_selector("button#action_confirm_next").click()
                    page.wait_for_load_state("networkidle")

                    if page.query_selector("#cssconstantspageheader").inner_text() != "Terminvereinbarung":
                        logger.error("Booking appointment failed")
                        success = True  # a little hacky, should be renamed to "done" or similar
                        break

                    # get Aufrufnummer, Terminnummer & Änderungspin
                    aufrufnr = page.query_selector("div.blockcontentdatagrid:nth-child(6) > div:nth-child(3) > div.MDG_value").inner_text()
                    terminnr = page.query_selector("div.blockcontentdatagrid:nth-child(6) > div:nth-child(4) > div.MDG_value").inner_text()
                    aenderungspin = page.query_selector("div.blockcontentdatagrid:nth-child(6) > div:nth-child(5) > div.MDG_value").inner_text()

                    # take screenshot of appointment confirmation and save to file
                    form = page.locator("#idekolcontainer")
                    form.wait_for(state="visible")
                    form.screenshot(path="buchung.png")

                    success = True
                    logger.info("Successfully booked appointment for %s %d, %d at %s\n\tAufrufnummer: %s\n\tTerminnummer: %s\n\tÄnderungspin: %s",
                                month_str_localized, day, year, time_str,
                                aufrufnr, terminnr, aenderungspin)
                    break

                if success:
                    break

            if not success:
                continue_button = page.query_selector("button:has-text('Vorwärts')")
                if not continue_button:
                    logger.error("No 'Vorwärts' button found")
                    break

                # check if button is disabled
                if continue_button.get_attribute("disabled") is not None:
                    break

                continue_button.click()
                page.wait_for_load_state("networkidle")

        browser.close()
        p.stop()

    # Clean up the event loop thread (optional)
    loop.call_soon_threadsafe(loop.stop)
    thread.join()
    loop.close()

    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get appointment for Potsdam Bürgerservice")

    # run application headless
    parser.add_argument(
        "--headless",
        action="store_true",
        default=(os.getenv("HEADLESS") or "1") == "1",
        help="Run the application headless. Overwrites environment variable HEADLESS."
    )

    # make periodic
    parser.add_argument(
        "--periodic",
        action="store_true",
        default=False,
        help="Run the application periodically"
    )

    # add maximum tries
    parser.add_argument(
        "--tries",
        type=int,
        default=0,
        help="Maximum number of tries. 0 for infinite."
    )

    # control period of time to check
    parser.add_argument(
        "--minutes",
        type=int,
        default=5,
        help="Recheck every x minutes. Can be used with --seconds"
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=0,
        help="Recheck every x seconds. Can be used with --minutes"
    )

    parser.add_argument(
        "--disable-booking",
        action="store_true",
        default=False,
        help="If checked, do not actually book any appointments"
    )

    # make application verbose
    parser.add_argument(
        "--verbose",
        action="store_false",
        help="Make application verbose"
    )

    # skip questions
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        default=False,
        help="Skip all questions"
    )

    # specify config file
    parser.add_argument(
        "--config",
        type=str,
        help="Specify path to a YAML config file. Requires --no-interactive."
    )

    # specify personal data
    parser.add_argument(
        "--foa",
        type=FormOfAddress,
        help="Specify the form of address (herr, frau, x, firma). Required when using --no-interactive."
    )
    parser.add_argument(
        "--first-name",
        type=str,
        help="Specify the first name. Required when using --no-interactive."
    )
    parser.add_argument(
        "--last-name",
        type=str,
        help="Specify the last name. Required when using --no-interactive."
    )
    parser.add_argument(
        "--phone",
        type=str,
        help="Specify the phone number. Required when using --no-interactive."
    )
    parser.add_argument(
        "--email",
        type=str,
        help="Specify the email address. Required when using --no-interactive."
    )

    # specify request types
    parser.add_argument(
        "--request",
        action="append",
        nargs=2,
        metavar=("ID", "NUMBER"),
        help="Specify the request ID and number of people. Can be used multiple times. Required when using --no-interactive."
    )

    # specify the earliest date
    parser.add_argument(
        "--earliest-date",
        type=lambda s: date.fromisoformat(s),
        help="Specify the earliest date for appointments in YYYY-MM-DD format. Appointments before this date will be skipped."
    )

    # specify the latest date
    parser.add_argument(
        "--latest-date",
        type=lambda s: date.fromisoformat(s),
        help="Specify the latest date for appointments in YYYY-MM-DD format. Appointments after this date will be skipped."
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel("DEBUG")

    try:
        config = Configuration(args)
        logger.debug("Configuration:\n%s", config)

        if config.periodic:
            tries = 0

            while not run(args, config) and (args.tries == 0 or tries < args.tries):
                tries += 1
                logger.debug(
                    "[Attempt %d] Unsuccessful. Sleeping for %02d:%02d minutes until next attempt.",
                    tries,
                    config.minutes,
                    config.seconds)
                time.sleep(config.minutes * 60 + config.seconds)
        else:
            run(args, config)

    except KeyboardInterrupt:
        logger.debug("Exiting...")
