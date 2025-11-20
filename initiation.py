import RPi.GPIO as GPIO
import time
import configparser
import socket
import os
from datetime import datetime
from pathlib import Path
import subprocess


class LEDController:
    """Main controller class for LED operations and network monitoring"""

    def __init__(self, config_file='config.ini'):
        self.config = self._load_config(config_file)
        self._setup_gpio()
        self.network_connected = False

        # Pre-generate filename and content once per button press
        self.file_content = ""
        self.filename = ""

    def _load_config(self, config_file):
        config = configparser.ConfigParser()
        if not os.path.exists(config_file):
            self._create_default_config(config_file)
        config.read(config_file)
        return config

    def _create_default_config(self, config_file):
        config = configparser.ConfigParser()

        config['GPIO_PINS'] = {
            'pin_red': '17',
            'pin_green': '27',
            'pin_blue': '22',
            'button_pin': '18',
            'status_led': '23',
            'success_led': '24',
            'error_led': '25'
        }

        config['LED_BEHAVIOR'] = {
            'network_check_blinks': '5',
            'blink_duration': '0.5',
            'error_blinks': '3',
            'sequence_duration': '10',
            'max_retries': '3',
            'retry_delay': '2'
        }

        config['FILE_SETTINGS'] = {
            'save_directory': './data_logs',
            'file_prefix': 'TEST_DATA',
            'file_extension': '.txt'
        }

        config['NETWORK'] = {
            'check_interval': '5',
            'test_host': '8.8.8.8',
            'test_port': '53'
        }

        config['REMOTE'] = {
            'remoteUser': 'Sanjib',
            'IP': '192.168.1.116',
            'location': 'Documents/gsk_LIAL_Initiation-Device/logFromPi'
        }

        with open(config_file, 'w') as f:
            config.write(f)
        print(f"Default configuration created: {config_file}")

    def _setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # GPIO pins
        self.pin_red = self.config.getint('GPIO_PINS', 'pin_red')
        self.pin_green = self.config.getint('GPIO_PINS', 'pin_green')
        self.pin_blue = self.config.getint('GPIO_PINS', 'pin_blue')
        self.button_pin = self.config.getint('GPIO_PINS', 'button_pin')
        self.status_led = self.config.getint('GPIO_PINS', 'status_led')
        self.success_led = self.config.getint('GPIO_PINS', 'success_led')
        self.error_led = self.config.getint('GPIO_PINS', 'error_led')

        # Output pins
        for pin in [self.pin_red, self.pin_green, self.pin_blue,
                    self.status_led, self.success_led, self.error_led]:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

        # Button input
        GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def set_rgb_color(self, r, g, b):
        GPIO.output(self.pin_red, GPIO.HIGH if r else GPIO.LOW)
        GPIO.output(self.pin_green, GPIO.HIGH if g else GPIO.LOW)
        GPIO.output(self.pin_blue, GPIO.HIGH if b else GPIO.LOW)

    def check_network_connectivity(self):
        try:
            host = self.config.get('NETWORK', 'test_host')
            port = self.config.getint('NETWORK', 'test_port')
            sock = socket.create_connection((host, port), timeout=3)
            sock.close()
            return True
        except (socket.error, socket.timeout):
            return False

    def indicate_network_status(self):
        was_connected = self.network_connected
        self.network_connected = self.check_network_connectivity()
        if self.network_connected:
            self.set_rgb_color(False, True, False)
            if not was_connected:
                print("Network connected - Ready!")
        else:
            self.set_rgb_color(True, False, False)
            if was_connected or not was_connected:
                print("Network disconnected")

    def _prepare_file(self):
        """Generate filename and content once"""
        save_dir = self.config.get('FILE_SETTINGS', 'save_directory')
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_prefix = self.config.get('FILE_SETTINGS', 'file_prefix')
        file_extension = self.config.get('FILE_SETTINGS', 'file_extension')
        self.filename = f"{file_prefix}_{timestamp}{file_extension}"
        self.local_filepath = os.path.join(save_dir, self.filename)

        self.file_content = (
            f"TEST Data Log\n"
            f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Network Status: {'Connected' if self.network_connected else 'Disconnected'}\n"
            f"\n--- TEST Data ---\n"
            f"Sample data\n"
        )

    def write_file(self, write2NetworkDrive=False):
        """Write file locally and optionally to network"""
        try:
            # Write local file
            with open(self.local_filepath, 'w') as f:
                print(f"File path: {self.local_filepath}")
                f.write(self.file_content)

            if write2NetworkDrive:
                # Read remote info
                remote_user = self.config.get('REMOTE', 'remoteUser', fallback='Sanjib')
                remote_ip = self.config.get('REMOTE', 'IP', fallback='192.168.1.116')
                remote_location = self.config.get('REMOTE', 'location',
                                                  fallback='Documents/gsk_LIAL_Initiation-Device/logFromPi')

                scp_command = [
                    "scp",
                    self.local_filepath,
                    f"{remote_user}@{remote_ip}:{remote_location}/{self.filename}"
                ]

                try:
                    subprocess.run(scp_command, check=True, timeout=4)
                    GPIO.output(self.success_led, GPIO.HIGH)
                    time.sleep(2)
                    GPIO.output(self.success_led, GPIO.LOW)
                    print(f"File copied to network: {remote_ip}:{remote_location}/{self.filename}")
                except subprocess.TimeoutExpired:
                    print("SCP command timed out")
                    self._blink_error_led()
                    return False
                except subprocess.CalledProcessError:
                    print("Unable to write to network drive")
                    self._blink_error_led()
                    return False
            return True

        except Exception as e:
            print(f"Error writing file: {e}")
            self._blink_error_led()
            return False

    def _blink_error_led(self, times=None):
        """Blink error LED in case of failure"""
        blink_duration = self.config.getfloat('LED_BEHAVIOR', 'blink_duration', fallback=0.5)
        if times is None:
            times = self.config.getint('LED_BEHAVIOR', 'error_blinks', fallback=3)
        for _ in range(times):
            GPIO.output(self.error_led, GPIO.HIGH)
            time.sleep(blink_duration)
            GPIO.output(self.error_led, GPIO.LOW)
            time.sleep(blink_duration)

    def handle_button_press(self, write2NetworkDrive=False):
        """Handle button press and write file"""
        print("Button pressed! Processing...")
        self._prepare_file()

        max_retries = self.config.getint('LED_BEHAVIOR', 'max_retries', fallback=3)
        retry_delay = self.config.getint('LED_BEHAVIOR', 'retry_delay', fallback=2)

        GPIO.output(self.status_led, GPIO.HIGH)
        time.sleep(0.5)

        for attempt in range(max_retries + 1):
            success = self.write_file(write2NetworkDrive=write2NetworkDrive)
            if success:
                GPIO.output(self.status_led, GPIO.LOW)
                return True
            print(f"Attempt {attempt + 1} failed, retrying in {retry_delay}s...")
            self._blink_error_led(times=attempt + 1)
            time.sleep(retry_delay)

        GPIO.output(self.status_led, GPIO.LOW)
        print("All attempts failed")
        self.set_rgb_color(True, False, False)  # RED
        return False

    def file_write_mode(self, write2NetworkDrive=False):
        """Wait for button press and write file"""
        print("File Write Mode: Waiting for button press...")
        button_pressed_last = False
        while True:
            button_state = GPIO.input(self.button_pin)
            if button_state == GPIO.LOW and not button_pressed_last:
                time.sleep(0.01)
                success = self.handle_button_press(write2NetworkDrive=write2NetworkDrive)
                button_pressed_last = True
                return success
            elif button_state == GPIO.HIGH:
                button_pressed_last = False
            time.sleep(0.1)

    def run(self, write2NetworkDrive=False):
        print("LED Controller Started")
        try:
            self.indicate_network_status()
            self.file_write_mode(write2NetworkDrive=write2NetworkDrive)
            print("Program completed. Exiting...")
        except KeyboardInterrupt:
            print("\nScript interrupted by user.")
        finally:
            self.cleanup()

    def cleanup(self):
        GPIO.cleanup()
        print("GPIO cleaned up. Exiting.")


if __name__ == "__main__":
    # Create controller with config file
    controller = LEDController('/usr/local/projects/initiation_config.ini')

    # Run controller, set write2NetworkDrive=True to copy files to network
    controller.run(write2NetworkDrive=True)
