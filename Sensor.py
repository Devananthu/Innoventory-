
import RPi.GPIO as GPIO
import time
import socketio
import threading

# ---------- CONFIGURATION ----------
SELECTOR_PINS = [17, 27, 22, 23] # GPIO pins used to select the channel https://docs.google.com/spreadsheets/d/1ejcnFzCEQYoXXFTbVLVcmzwz_0bdznm0g6UPNQC_fOI/edit?gid=0#gid=0
SIGNAL_PIN = 24 # GPIO pin used to read the signal from the multiplexer
NUM_CHANNELS = 16 # Number of channels in the multiplexer

# Mapping channels to item names or box labels
BOX_MAPPING = {
 0: "ULN2003", 1: "Load cell", 2: "DC Pump", 3: "Helical Gear motor",
 4: "Cells", 5: "Relay", 6: "Stepper motor", 7: "LoRa",
 8: "Gear motor", 9: "Servo motor", 
}

# ---------- GPIO SETUP ----------
GPIO.setmode(GPIO.BCM) 
GPIO.setwarnings(False)
for pin in SELECTOR_PINS:
 GPIO.setup(pin, GPIO.OUT)
GPIO.setup(SIGNAL_PIN, GPIO.IN)

# ---------- SOCKET.IO CLIENT ----------
sio = socketio.Client()

def connect_socket():
 """Connect to the Flask-SocketIO server."""
 try:
 sio.connect('http://localhost:5000') # Adjust if running on a different server
 print("✅ Socket.IO connected.")
 except socketio.exceptions.ConnectionError as e:
 print(f"Socket.IO connection failed: {e}")

# ---------- CHANNEL READING ----------
def read_channels():
 """Reads all channels of the multiplexer and detects open boxes."""
 channel_values = []
 for channel in range(NUM_CHANNELS):
 # Set multiplexer selector pins
 for i, pin in enumerate(SELECTOR_PINS):
 GPIO.output(pin, (channel >> i) & 1)

 time.sleep(0.01) # Allow signal to stabilize
 channel_state = GPIO.input(SIGNAL_PIN)
 channel_values.append(channel_state)

 # Box is considered "open" when signal is HIGH (True)
 open_boxes = [BOX_MAPPING[i] for i, state in enumerate(channel_values) if state]
 return open_boxes

# ---------- MONITORING THREAD ----------
def monitor_inventory():
 """Continuously monitor the inventory and send updates via Socket.IO."""
 prev_open_boxes = set()
 while True:
 open_boxes = set(read_channels())
 if open_boxes != prev_open_boxes:
 if sio.connected:
 sio.emit('update_boxes', {'open_boxes': list(open_boxes)})
 print(f"📦 Inventory update sent: {open_boxes}")
 else:
 print("⚠️ Socket.IO not connected. Attempting reconnect...")
 connect_socket()
 prev_open_boxes = open_boxes
 #time.sleep(1)

# ---------- MAIN ----------
if __name__ == '__main__':
 try:
 connect_socket()

 if sio.connected:
 # Start monitoring in a background thread
 monitor_thread = threading.Thread(target=monitor_inventory, daemon=True)
 monitor_thread.start()

 # Keep the main thread alive
 while True:
 time.sleep(1)
 else:
 print("Unable to start inventory monitoring. Socket.IO not connected.")

 except KeyboardInterrupt:
 print("\n🧹 Cleaning up GPIO...")
 GPIO.cleanup()
 print("👋 Program terminated.")
