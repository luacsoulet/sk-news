# config_robot.py
import re

# RÉGLAGE UNIQUE ICI
HEADLESS_MODE = True  # Change en False pour voir les fenêtres

# LOGIQUE GOOGLE UNIQUE ICI
def handle_google_consent(page):
    if "google." in page.url:
        try:
            regex_consent = re.compile(r"Tout accepter|J'accepte|Accepter tout|Accept all", re.IGNORECASE)
            button = page.get_by_role("button", name=regex_consent)
            if button.count() > 0:
                button.first.click(timeout=5000, no_wait_after=True)
                print("✅ Google Consent cliqué via config.")
        except:
            pass