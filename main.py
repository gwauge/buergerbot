#!/usr/bin/env python
import time
from datetime import date
import os

from playwright.sync_api import sync_playwright, ElementHandle

from lib import logger, parse_german_date

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


def run(args: dict[str, any]):

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
        page.select_option("select#id_1335352852", value="1")

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
                if free_days:
                    for free_day in free_days:
                        searching = False

                        day = grab_day(free_day)
                        free = grab_number_of_appointments(free_day)
                        dates[parse_german_date(day, month_str, year)] = free

                        # log free day by using local date format: month, day year in local language
                        logger.info("%s %d, %d: %d appointments available",
                                    month_str, day, year, free)

                        # book appointment
                        if args.disable_booking:
                            continue

                        # click on the day
                        free_day.click()
                        page.wait_for_load_state("networkidle")

                        # Select the first available time slot
                        time_select = page.query_selector("#ekolcalendartimeselectbox")
                        options = time_select.query_selector_all("option")
                        for option in options:
                            value = option.get_attribute("value")
                            if value != "":
                                # parse time from unix timestamp
                                timestamp = int(value)
                                time_str = time.strftime('%H:%M', time.localtime(timestamp / 1000))
                                logger.info("Selecting first availale time: %s", time_str)

                                # select the time
                                time_select.select_option(value=value)

                                # click continue button
                                ok_button = page.query_selector("button:has-text('Ok')")
                                ok_button.click()

            # if not free_days:
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

        # if there is an appointment available, send url
        if dates:
            logger.info("Book via: %s", URL)

    # TODO: fix
    # hacky way to force application to shut down
    if not args.periodic:
        raise ZeroDivisionError("done")


if __name__ == "__main__":
    import argparse

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

    # control period of time to check
    parser.add_argument(
        "--minutes",
        type=int,
        default=5,
        help="Recheck every x minutes"
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

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel("DEBUG")

    try:
        if args.periodic:
            while True:
                run(args)
                logger.debug(
                    "Sleeping for %d minute%s until next attempt",
                    args.minutes,
                    "s" if args.minutes == 1 else "")
                time.sleep(args.minutes * 60)
        else:
            run(args)
            logger.debug("Done")

    except KeyboardInterrupt:
        logger.debug("Exiting...")
    except ZeroDivisionError:
        pass
