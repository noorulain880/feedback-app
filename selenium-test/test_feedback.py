"""
Selenium test for the Feedback Board.

Opens the deployed app and verifies web elements, then tests the main
features end to end: validation error, add an entry (course, type, rating),
helpful vote, edit, category filter, sort dropdown, rating-by-course chart
and delete.

Usage:
    py selenium-test\\test_feedback.py http://<load-balancer-dns>
"""
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5001"
    unique = f"Selenium User {int(time.time())}"

    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 10)

    def body_text():
        return driver.find_element(By.TAG_NAME, "body").text

    def entry_present():
        return unique in body_text()

    def find_item():
        return driver.find_element(
            By.XPATH,
            f"//li[contains(@class,'feedback-item')][.//strong[text()='{unique}']]",
        )

    try:
        # 1. Open the app and verify the form elements exist
        driver.get(base_url)
        print(f"Opened {base_url}")
        wait.until(EC.presence_of_element_located((By.NAME, "name")))
        wait.until(EC.presence_of_element_located((By.ID, "course")))
        wait.until(EC.presence_of_element_located((By.ID, "category")))
        wait.until(EC.presence_of_element_located((By.ID, "rating")))
        wait.until(EC.presence_of_element_located((By.NAME, "message")))
        wait.until(EC.presence_of_element_located((By.ID, "submit-btn")))
        print("PASS 1: name, course, type, rating, message and submit are present.")

        # 2. Validation: submitting an empty form shows an error
        driver.find_element(By.ID, "submit-btn").click()
        error = wait.until(EC.presence_of_element_located((By.ID, "form-error")))
        assert "required" in error.text.lower(), "Expected validation error"
        print("PASS 2: empty form is rejected with an error message.")

        # 3. Add an entry: DevOps course, Bug type, rating 4
        driver.find_element(By.NAME, "name").send_keys(unique)
        Select(driver.find_element(By.ID, "course")).select_by_value("DevOps")
        Select(driver.find_element(By.ID, "category")).select_by_value("Bug")
        Select(driver.find_element(By.ID, "rating")).select_by_value("4")
        driver.find_element(By.NAME, "message").send_keys(
            "Entry created by the automated Selenium test.")
        driver.find_element(By.ID, "submit-btn").click()
        wait.until(EC.presence_of_element_located((By.ID, "feedback-list")))
        assert entry_present(), "New entry not found in the list"
        print("PASS 3: new entry saved and shown in the list.")

        # 4. Helpful vote increments the counter
        before = int(find_item().find_element(By.CLASS_NAME, "helpful-count").text)
        find_item().find_element(By.CLASS_NAME, "helpful-btn").click()
        wait.until(
            lambda d: int(find_item().find_element(
                By.CLASS_NAME, "helpful-count").text) == before + 1
        )
        print("PASS 4: helpful vote counter incremented.")

        # 5. Edit the entry (message and rating)
        find_item().find_element(By.CLASS_NAME, "edit-btn").click()
        wait.until(EC.presence_of_element_located((By.ID, "save-btn")))
        message = driver.find_element(By.NAME, "message")
        message.clear()
        message.send_keys("Edited by the Selenium test.")
        Select(driver.find_element(By.ID, "rating")).select_by_value("2")
        driver.find_element(By.ID, "save-btn").click()
        wait.until(EC.presence_of_element_located((By.ID, "feedback-list")))
        assert "Edited by the Selenium test." in body_text(), "Edit was not saved"
        print("PASS 5: entry edited and changes are shown.")

        # 6. Filter by category: visible under Bug, hidden under Praise
        driver.find_element(By.ID, "filter-Bug").click()
        wait.until(EC.presence_of_element_located((By.ID, "feedback-list")))
        assert entry_present(), "Entry missing under the Bug filter"
        driver.find_element(By.ID, "filter-Praise").click()
        wait.until(EC.url_contains("category=Praise"))
        assert not entry_present(), "Entry should not appear under Praise"
        print("PASS 6: category filter works.")

        # 7. Sort dropdown: switch through every option, list must stay valid
        driver.find_element(By.ID, "filter-All").click()
        wait.until(EC.presence_of_element_located((By.ID, "feedback-list")))
        for key in ["oldest", "rating", "helpful", "newest"]:
            Select(driver.find_element(By.ID, "sort")).select_by_value(key)
            wait.until(lambda d: Select(
                d.find_element(By.ID, "sort")).first_selected_option
                .get_attribute("value") == key)
            wait.until(EC.presence_of_element_located((By.ID, "feedback-list")))
            assert entry_present(), f"Entry missing when sorted by {key}"
        print("PASS 7: sort dropdown works for all four options.")

        # 8. Rating by course chart shows the DevOps course
        chart = wait.until(EC.presence_of_element_located((By.ID, "course-chart")))
        assert "DevOps" in chart.text, "DevOps missing from the chart"
        assert "entry" in chart.text or "entries" in chart.text, \
            "Entry count missing from the chart"
        print("PASS 8: rating-by-course chart is shown.")

        # 9. Delete the entry
        find_item().find_element(By.CLASS_NAME, "delete-btn").click()
        wait.until(lambda d: unique not in body_text())
        print("PASS 9: entry deleted.")

        print("ALL TESTS PASSED.")
        time.sleep(3)  # keep the browser visible briefly for the screenshot

    finally:
        driver.quit()


if __name__ == "__main__":
    main()