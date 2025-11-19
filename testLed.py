import RPi.GPIO as GPIO
import time

# Pin Definitions (BCM numbering)
PIN_RED = 17
PIN_GREEN = 27
PIN_BLUE = 22
BUTTON_PIN = 18  # GPIO where your button is connected

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# LED pins as output
GPIO.setup(PIN_RED, GPIO.OUT)
GPIO.setup(PIN_GREEN, GPIO.OUT)
GPIO.setup(PIN_BLUE, GPIO.OUT)

# Button pin as input with internal pull-up resistor
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print("LED setup complete. Waiting for 5 button presses...")

def set_color(r, g, b):
    """Helper function to set R, G, B pins HIGH or LOW based on boolean input."""
    GPIO.output(PIN_RED, GPIO.HIGH if r else GPIO.LOW)
    GPIO.output(PIN_GREEN, GPIO.HIGH if g else GPIO.LOW)
    GPIO.output(PIN_BLUE, GPIO.HIGH if b else GPIO.LOW)

def blink_sequence(duration_sec=5):
    """Blink the RGB LEDs in sequence for duration_sec seconds."""
    start_time = time.time()
    while time.time() - start_time < duration_sec:
        set_color(True, False, False)   # Red
        time.sleep(0.5)
        set_color(False, True, False)   # Green
        time.sleep(0.5)
        set_color(False, False, True)   # Blue
        time.sleep(0.5)
        set_color(True, True, True)     # White
        time.sleep(0.5)
    set_color(False, False, False)      # Turn off LEDs

try:
    press_count = 0
    max_press_count = 2
    while press_count < max_press_count:
        # Wait for button press (LOW because using pull-up)
        GPIO.wait_for_edge(BUTTON_PIN, GPIO.FALLING)
        press_count += 1
        print(f"Button pressed {press_count} time(s)! Blinking LEDs...")
        blink_sequence(duration_sec=5)

    print(f"{max_press_count} button presses completed. Exiting...")

except KeyboardInterrupt:
    print("\nScript interrupted by user.")

finally:
    GPIO.cleanup()
    print("GPIO cleaned up. Exiting.")
