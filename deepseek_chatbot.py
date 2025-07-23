import os
import time
import sys
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc
from markdownify import markdownify as md


class DeepSeekChatBot:
    """
    DeepSeek chatbot with reliable response text extraction
    """

    APP_URL = "https://chat.deepseek.com/"
    USER_DATA_PATH = Path(os.environ.get("LOCALAPPDATA")) / r'Google\Chrome\User Data\Default'

    def __init__(self):
        # Initialize with visible browser
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={self.USER_DATA_PATH}")
        options.add_argument("--disable-blink-features=AutomationControlled")

        self.driver = uc.Chrome(
            options=options,
            headless=False,
            use_subprocess=True,
        )

        self.driver.get(self.APP_URL)
        self._wait_for_login()
        self.is_our_first_chat = True

    def _wait_for_login(self):
        """Wait for chat input to appear"""
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "textarea#chat-input")))
            if len(sys.argv) == 0:
                print("✓ Ready to chat")
        except TimeoutException:
            print("Please login manually within 2 minutes...")
            WebDriverWait(self.driver, 120).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "textarea#chat-input")))
            print("✓ Login successful")

    def send_message(self, prompt):
        """Send message and return only the AI response text"""
        # Count existing replies before sending
        if self.is_our_first_chat:
            num_history_replies = 0
        else:
            history_replies = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "ds-markdown")))
            num_history_replies = len(history_replies)

        # Send the message
        input_box = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "textarea#chat-input")))

        # Handle multi-line prompts
        prompt_escaped = prompt.replace("\n", Keys.SHIFT + Keys.ENTER + Keys.SHIFT)
        input_box.clear()
        input_box.send_keys(prompt_escaped)
        input_box.send_keys(Keys.ENTER)
        if len(sys.argv) == 0:
            print(f"You: {prompt}")

        # Wait for and return the response
        response = self._get_latest_reply(num_history_replies)
        self.is_our_first_chat = False
        return response

    def _get_latest_reply(self, num_history_replies):
        """
        Retrieves the latest reply from the chat after sending a prompt.

        Args:
            num_history_replies: Number of existing replies before sending our message

        Returns:
            str: The cleaned response text
        """
        if len(sys.argv) == 0:
            print("Waiting for response...", end="", flush=True)

        # Wait for new reply to appear
        latest_reply = None
        maximum_trials = 60  # Max 60 seconds to wait for new reply
        for _ in range(maximum_trials):
            try:
                all_replies = self.driver.find_elements(By.CLASS_NAME, "ds-markdown")
                if len(all_replies) > num_history_replies:
                    latest_reply = all_replies[num_history_replies]
                    break
            except Exception:
                pass
            time.sleep(1)

        if latest_reply is None:
            raise TimeoutException("No new reply detected")

        # Wait until the reply stops changing
        previous_html = ""
        stable_count = 0
        stability_threshold = 3  # Need 3 consecutive stable checks

        for _ in range(maximum_trials):
            try:
                current_html = latest_reply.get_attribute('innerHTML')
                if current_html == previous_html:
                    stable_count += 1
                    if stable_count >= stability_threshold:
                        print("\r" + " " * 50 + "\r", end="")  # Clear waiting message
                        lines = [line.strip() for line in md(current_html).strip().split('\n') if line.strip()]
                        return '\n'.join(lines)

                else:
                    stable_count = 0
                    previous_html = current_html
            except Exception:
                pass  # Ignore stale element exceptions
            time.sleep(0.5)
        if len(sys.argv) == 0:
            print("\r" + " " * 50 + "\r", end="")  # Clear waiting message
        raise TimeoutException("Response did not stabilize")


    def close(self):
        """Close the browser"""
        self.driver.quit()


if __name__ == "__main__":
    bot = None
    try:
        # Force flush output buffers immediately
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)

        bot = DeepSeekChatBot()

        if len(sys.argv) > 1:
            msg = ' '.join(sys.argv[1:])
            response = bot.send_message(msg)
            print(response, flush=True)  # Explicit flush
        else:
            print("Enter your message (press Ctrl+C to exit):", flush=True)
            while True:
                msg = input("You: ")
                if msg.lower() in ('exit', 'quit'):
                    break
                response = bot.send_message(msg)
                print(f"AI: {response}\n", flush=True)  # Explicit flush

    except KeyboardInterrupt:
        print("\nExiting...", flush=True)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr, flush=True)
    finally:
        if bot:
            bot.close()
