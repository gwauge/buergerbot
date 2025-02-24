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

from lib import logger, parse_german_date, telegram_send_photo

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


class UserQuestions:
    """
    A class used to represent user questions and personal data.

    Attributes
    ----------
    requests : dict[str, int]
        A dictionary to store user requests with string keys and integer values.
    personal_data : dict[str, any]
        A dictionary to store personal data with string keys and values of any type.

    Methods
    -------
    __init__():
        Initializes the UserQuestions class with empty dictionaries for requests and personal_data.
    """
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.requests: dict[str, int] = {}
        self.personal_data: PersonalData = PersonalData()

        self.requests: dict[str, int] = {}

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


# Start a separate event loop in a background thread
def start_event_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


def run(args: dict[str, any], user_questions: UserQuestions) -> bool:

    # Create a new event loop for the thread
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=start_event_loop, args=(loop,), daemon=True)
    thread.start()

    success = False

    # TODO: check if internet connection is available

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context()
        page = context.new_page()

        # navigate to the website
        page.goto(URL)

        # click "Termin vereinbaren"
        page.click("button#action_officeselect_termnew_prefix1333626470")
        page.wait_for_load_state("networkidle")

        # Select type of appointment by setting number of people
        # page.select_option("select#id_1335352852", value="1")
        for request_id, number in user_questions.requests.items():
            page.select_option(f"select#{request_id}", value=str(number))

        # Confirm and continue
        page.click("button#action_concernselect_next")
        page.wait_for_load_state("networkidle")

        # Continue again by pressing "Weiter"
        page.click("button#action_concerncomments_next")
        page.wait_for_load_state("networkidle")

        searching = True

        # click through months
        while searching:
            # grab monthtable0
            for table_name in ["monthtable0", "monthtable1"]:
                monthtable = page.query_selector(f"table#{table_name}")
                month_str, year_str = monthtable\
                    .query_selector("caption")\
                    .inner_text().split(" ")
                year = int(year_str)

                # check for free days inside
                free_days = monthtable.query_selector_all(".ekolCalendar_ButtonDayFreeX")
                if not free_days:
                    continue

                free_day = free_days[0]  # select first free day
                searching = False  # found free day, stop search

                # get day and number of appointments
                day = grab_day(free_day)
                free = grab_number_of_appointments(free_day)
                dates[parse_german_date(day, month_str, year)] = free

                # log free day by using local date format: month, day year in local language
                logger.debug("%s %d, %d: %d appointments available",
                            month_str, day, year, free)

                # book appointment
                if args.disable_booking:
                    continue

                # click on the day
                free_day.click()
                page.wait_for_load_state("networkidle")

                # Select the first available time slot
                time_select = page.query_selector("#ekolcalendartimeselectbox")

                # get first non empty option value
                options = time_select.query_selector_all("option")
                value = next(option.get_attribute("value") for option in options if option.get_attribute("value") != "")

                # parse time from unix timestamp
                timestamp = int(value)
                time_str = time.strftime('%H:%M', time.localtime(timestamp / 1000))
                logger.debug("Selecting first availale time: %s", time_str)

                # select the time
                time_select.select_option(value=value)

                # click "Ok" button
                ok_button = page.query_selector("button:has-text('Ok')")
                ok_button.click()
                page.wait_for_load_state("networkidle")

                # while #cssconstants_captcha_image exists
                while page.query_selector("#cssconstants_captcha_image"):

                    # enter personal data
                    page.query_selector("#anrede").select_option(value=user_questions.personal_data.foa.value)
                    page.query_selector("input#vorname").fill(user_questions.personal_data.first_name)
                    page.query_selector("input#nachname").fill(user_questions.personal_data.last_name)
                    page.query_selector("input#telefon").fill(user_questions.personal_data.phone)
                    page.query_selector("input#email").fill(user_questions.personal_data.email)

                    # TODO: generate new captcha when receiving /new

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
                success = True
                logger.info("Successfully booked appointment for %s %d, %d at %s",
                            month_str, day, year, time_str)

            if searching:
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

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel("DEBUG")

    # logger.info("Book via: %s", URL)
    try:
        user_questions = UserQuestions(args)
        logger.debug("Selected request types: %s", user_questions.requests)

        if args.periodic:
            tries = 0

            while not run(args, user_questions) and (args.tries == 0 or tries < args.tries):
                tries += 1
                logger.debug(
                    "[Attempt %d] Unsuccessful. Sleeping for %02d:%02d minutes until next attempt.",
                    tries,
                    args.minutes,
                    args.seconds)
                time.sleep(args.minutes * 60 + args.seconds)
        else:
            run(args, user_questions)

    except KeyboardInterrupt:
        logger.debug("Exiting...")
    except ZeroDivisionError:
        pass
