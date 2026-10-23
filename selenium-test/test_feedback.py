import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"

    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 10)

    try:
        # 1. Open the app
        driver.get(base_url)
        print(f"Opened {base_url}")

        # 2. Verify the form's "name" input element is present
        name_input = wait.until(EC.presence_of_element_located((By.NAME, "name")))
        print("Found the 'name' input element.")

        # 3. Verify the submit button is present
        submit_btn = wait.until(EC.presence_of_element_located((By.ID, "submit-btn")))
        print("Found the submit button.")

        # 4. Fill in the form and submit (end-to-end check)
        name_input.send_keys("Selenium Test User")
        message_input = driver.find_element(By.NAME, "message")
        message_input.send_keys("This feedback was submitted by an automated Selenium script.")
        submit_btn.click()

        # 5. Wait for the page to reload and verify the new entry appears
        wait.until(EC.presence_of_element_located((By.ID, "feedback-list")))
        time.sleep(1)
        page_text = driver.find_element(By.ID, "feedback-list").text
        assert "Selenium Test User" in page_text, "Submitted feedback not found in the list!"
        print("New feedback entry verified in the list. TEST PASSED.")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()