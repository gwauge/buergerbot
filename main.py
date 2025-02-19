from datetime import date
import os
from playwright.sync_api import sync_playwright, ElementHandle

from lib import logger, parse_german_date

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


def handle_free_days(
    free_days: list[ElementHandle],
    month_str: str,
    year: int
):
    global dates
    if free_days:
        logger.info("Found %d free days in %s %d",
                    len(free_days), month_str, year)

        for free_day in free_days:
            day = grab_day(free_day)
            free = grab_number_of_appointments(free_day)
            dates[parse_german_date(day, month_str, year)] = free
            logger.info("\tDay: %d | Free: %d", day, free)


def run():

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=(os.getenv("HEADLESS") or "1") == "1")
        context = browser.new_context()
        page = context.new_page()

        # navigate to the website
        page.goto("https://egov.potsdam.de/tnv/?START_OFFICE=buergerservice")

        # click "Termin vereinbaren"
        page.click("button#action_officeselect_termnew_prefix1333626470")
        page.wait_for_load_state("networkidle")

        # Select type of appointment by setting number of people
        page.select_option("select#id_1337591470", value="1")

        # Confirm and continue
        page.click("button#action_concernselect_next")
        page.wait_for_load_state("networkidle")

        # Continue again by pressing "Weiter"
        page.click("button#action_concerncomments_next")
        page.wait_for_load_state("networkidle")

        # click through months
        while True:
            # grab monthtable0
            monthtable0 = page.query_selector("table#monthtable0")
            month_str, year_str = monthtable0\
                .query_selector("caption")\
                .inner_text().split(" ")
            year = int(year_str)

            # check for free days inside
            free_days = monthtable0.query_selector_all(".ekolCalendar_ButtonDayFreeX")
            handle_free_days(free_days, month_str, year)

            # repeat for monthtable1
            monthtable1 = page.query_selector("table#monthtable1")
            month_str, year_str = monthtable1\
                .query_selector("caption")\
                .inner_text().split(" ")

            # check for free days inside
            free_days = monthtable1.query_selector_all(".ekolCalendar_ButtonDayFreeX")
            handle_free_days(free_days, month_str, year)

            if not free_days:
                continue_button = page.query_selector("button:has-text('Vorwärts')")
                if not continue_button:
                    logger.error("No 'Vorwärts' button found")
                    break

                # check if button is disabled
                if continue_button.get_attribute("disabled") is not None:
                    logger.debug("Reached lasted month")
                    break

                continue_button.click()
                page.wait_for_load_state("networkidle")

        browser.close()


if __name__ == "__main__":
    run()
