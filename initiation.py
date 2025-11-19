"""
LED Controller with Network Status and Data Logging
Monitors network connectivity and logs data on button press
"""

import RPi.GPIO as GPIO
import time
import configparser
import socket
import os
from datetime import datetime
from pathlib import Path


class LEDController:
    """Main controller class for LED operations and network monitoring"""

    def __init__(self, config_file='config.ini'):
        """Initialize the LED Controller with configuration"""
        self.config = self._load_config(config_file)
        self._setup_gpio()
        self.network_connected = False

    def _load_config(self, config_file):
        """Load configuration from INI file"""
        config = configparser.ConfigParser()

        # Create default config if not exists
        if not os.path.exists(config_file):
            self._create_default_config(config_file)

        config.read(config_file)
        return config

    def _create_default_config(self, config_file):
        """Create a default configuration file"""
        config = configparser.ConfigParser()

        config['GPIO_PINS'] = {
            'pin_red': '17',
            'pin_green': '27',
            'pin_blue': '22',
            'button_pin': '18',
            'status_led': '23',  # LED to glow when button pressed
            'success_led': '24',  # LED for successful file write
            'error_led': '25'  # LED for file write errors
        }

        config['LED_BEHAVIOR'] = {
            'network_check_blinks': '5',  # Blink x times if no network
            'blink_duration': '0.5',  # Duration of each blink in seconds
            'error_blinks': '3',  # Blink error LED x times on failure
            'sequence_duration': '10',  # Duration of button press sequence
            'max_retries': '3',  # Maximum number of retries after initial attempt
            'retry_delay': '2'  # Delay between retry attempts (seconds)
        }

        config['FILE_SETTINGS'] = {
            'save_directory': './data_logs',
            'file_prefix': 'TEST_DATA',
            'file_extension': '.txt'
        }

        config['NETWORK'] = {
            'check_interval': '5',  # Check network every 5 seconds
            'test_host': '8.8.8.8',  # Google DNS for connectivity test
            'test_port': '53'
        }

        with open(config_file, 'w') as f:
            config.write(f)

        print(f"Default configuration created: {config_file}")

    def _setup_gpio(self):
        """Setup GPIO pins based on configuration"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Get pin numbers from config
        self.pin_red = self.config.getint('GPIO_PINS', 'pin_red')
        self.pin_green = self.config.getint('GPIO_PINS', 'pin_green')
        self.pin_blue = self.config.getint('GPIO_PINS', 'pin_blue')
        self.button_pin = self.config.getint('GPIO_PINS', 'button_pin')
        self.status_led = self.config.getint('GPIO_PINS', 'status_led')
        self.success_led = self.config.getint('GPIO_PINS', 'success_led')
        self.error_led = self.config.getint('GPIO_PINS', 'error_led')

        # Setup LED pins as output
        GPIO.setup(self.pin_red, GPIO.OUT)
        GPIO.setup(self.pin_green, GPIO.OUT)
        GPIO.setup(self.pin_blue, GPIO.OUT)
        GPIO.setup(self.status_led, GPIO.OUT)
        GPIO.setup(self.success_led, GPIO.OUT)
        GPIO.setup(self.error_led, GPIO.OUT)

        # Setup button pin as input with pull-up
        GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Initialize all LEDs to OFF
        self.set_rgb_color(False, False, False)
        GPIO.output(self.status_led, GPIO.LOW)
        GPIO.output(self.success_led, GPIO.LOW)
        GPIO.output(self.error_led, GPIO.LOW)

    def set_rgb_color(self, r, g, b):
        """Set RGB LED color"""
        GPIO.output(self.pin_red, GPIO.HIGH if r else GPIO.LOW)
        GPIO.output(self.pin_green, GPIO.HIGH if g else GPIO.LOW)
        GPIO.output(self.pin_blue, GPIO.HIGH if b else GPIO.LOW)

    def check_network_connectivity(self):
        """Check if network (WiFi/Ethernet) is connected"""
        try:
            host = self.config.get('NETWORK', 'test_host')
            port = self.config.getint('NETWORK', 'test_port')

            # Create socket and try to connect
            socket.setdefaulttimeout(3)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            sock.close()
            return True
        except (socket.error, socket.timeout):
            return False

    def indicate_network_status(self):
        """Show network status using green LED"""
        was_connected = self.network_connected
        self.network_connected = self.check_network_connectivity()

        # Update LED based on network status
        if self.network_connected:
            # Continuous green for connected
            self.set_rgb_color(False, True, False)
            if self.network_connected != was_connected or was_connected is False:
                print("Network connected - Ready!")
        else:
            # Red for disconnected
            self.set_rgb_color(True, False, False)
            if self.network_connected != was_connected or was_connected is False:
                print("Network disconnected")

    def write_data_file(self):
        """Write data file with current timestamp and ADS data"""
        try:
            # Get file settings from config
            save_dir = self.config.get('FILE_SETTINGS', 'save_directory')
            file_prefix = self.config.get('FILE_SETTINGS', 'file_prefix')
            file_extension = self.config.get('FILE_SETTINGS', 'file_extension')

            # Create directory if it doesn't exist
            Path(save_dir).mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{file_prefix}_{timestamp}{file_extension}"
            filepath = os.path.join(save_dir, filename)

            # Write data to file
            with open(filepath, 'w') as f:
                f.write(f"ADS Data Log\n")
                f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Network Status: {'Connected' if self.network_connected else 'Disconnected'}\n")
                f.write(f"\n--- TEST Data ---\n")
                f.write(f"Sample data\n")

            print(f"Data file created successfully: {filepath}")
            return True

        except Exception as e:
            print(f"Error writing data file: {e}")
            return False

    def handle_button_press(self):
        """Handle button press event with retry logic"""
        print("Button pressed! Processing...")

        max_retries = self.config.getint('LED_BEHAVIOR', 'max_retries')
        retry_delay = self.config.getint('LED_BEHAVIOR', 'retry_delay')
        blink_duration = self.config.getfloat('LED_BEHAVIOR', 'blink_duration')

        # Turn on status LED
        GPIO.output(self.status_led, GPIO.HIGH)
        time.sleep(0.5)

        # Initial attempt (attempt 0)
        print("Initial attempt to write data file...")
        success = self.write_data_file()

        if success:
            print("File written successfully on first attempt!")
            # Turn off status LED
            GPIO.output(self.status_led, GPIO.LOW)

            # Glow success LED continuously
            GPIO.output(self.success_led, GPIO.HIGH)
            time.sleep(2)  # Keep it on for 2 seconds
            GPIO.output(self.success_led, GPIO.LOW)
            return True

        # If initial attempt failed, retry X times
        for retry in range(1, max_retries + 1):
            print(f"Initial attempt failed. Retry {retry} of {max_retries}...")

            # Blink error LED 'retry' number of times to show which retry
            for _ in range(retry):
                GPIO.output(self.error_led, GPIO.HIGH)
                time.sleep(blink_duration)
                GPIO.output(self.error_led, GPIO.LOW)
                time.sleep(blink_duration)

            # Wait before retrying
            print(f"Waiting {retry_delay} seconds before retry...")
            time.sleep(retry_delay)

            # Try to write data file
            success = self.write_data_file()

            if success:
                print(f"File written successfully on retry {retry}!")
                # Turn off status LED
                GPIO.output(self.status_led, GPIO.LOW)

                # Glow success LED continuously
                GPIO.output(self.success_led, GPIO.HIGH)
                time.sleep(2)  # Keep it on for 2 seconds
                GPIO.output(self.success_led, GPIO.LOW)
                return True

        # Turn off status LED
        GPIO.output(self.status_led, GPIO.LOW)

        # If all retries failed, show continuous red LED
        print(f"Initial attempt + {max_retries} retries all failed. File write unsuccessful.")
        self.set_rgb_color(True, False, False)  # Continuous RED
        GPIO.output(self.error_led, GPIO.HIGH)  # Keep error LED on

        return False

    def file_write_mode(self):
        """File write mode - waits for button press and writes file"""
        print("File Write Mode: Waiting for button press...")

        button_pressed_last = False
        file_written = False

        while not file_written:
            # Check button state
            button_state = GPIO.input(self.button_pin)

            # Detect button press (with simple debouncing)
            if button_state == GPIO.LOW and not button_pressed_last:
                file_written = self.handle_button_press()
                button_pressed_last = True

                # Exit the loop after handling button press
                # (either success or all retries failed)
                break
            elif button_state == GPIO.HIGH:
                button_pressed_last = False

            time.sleep(0.1)

        if file_written:
            print("File write completed successfully.")
        else:
            print("File write failed after all retries. Check the error LED.")
            # Keep the program running for a few seconds to show the error state
            time.sleep(5)

        return file_written

    def run(self):
        """Main run loop - clean entry point"""
        print("LED Controller Started")

        try:
            self.indicate_network_status()
            self.file_write_mode()

            print("Program completed. Exiting...")

        except KeyboardInterrupt:
            print("\nScript interrupted by user.")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up GPIO pins"""
        GPIO.cleanup()
        print("GPIO cleaned up. Exiting.")


if __name__ == "__main__":
    controller = LEDController('initiation_config.ini')
    controller.run()
