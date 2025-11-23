import time
from mfrc522 import SimpleMFRC522
import requests

RFID_USERS = {
 219154493860: "Guna",
 609489756334: "Jeyaboopathi",
 56870281259: "Varsha",
 126737162529: "Madhumita",
 402470248785 : "Kaviya"
 

}

reader = SimpleMFRC522()

def notify_flask(rfid, user_name):
 url = "http://localhost:5000/rfid_scanned"
 data = {"rfid": rfid, "username": user_name}
 try:
 requests.post(url, json=data)
 except Exception as e:
 print("Failed to notify Flask:", e)

def main():
 try:
 print("Place your RFID card near the reader...")
 while True:
 rfid, _ = reader.read()
 rfid = int(rfid)
 user_name = RFID_USERS.get(rfid, "Unknown")
 print(f"Scanned Name: {user_name}")
 print(f"Scanned UID: {rfid}")
 notify_flask(rfid, user_name)
 # time.sleep(2) 
 except KeyboardInterrupt:
 print("Exiting...")
 finally:
 import RPi.GPIO as GPIO
 GPIO.cleanup()

if __name__ == "__main__":
 main()
