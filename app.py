import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, render_template, jsonify, request, Response
from flask_socketio import SocketIO
import time
import base64
import cv2
import requests
import RPi.GPIO as GPIO

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("gcreds.json", scope)
client = gspread.authorize(creds)
SHEET_ID = "1ejcnFzCEQYoXXFTbVLVcmzwz_0bdznm0g6UPNQC_fOI"
sheet = client.open_by_key(SHEET_ID).sheet1

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
WEB_APP_URL = 'https://script.google.com/macros/s/AKfycbzGVP5JTXSYelAUMcKN4yKQn--wXULtizhrCCTHKZmtnqXPGasBC8QGggZKKq6XjdIE/exec'

# GPIO LED Setup
GPIO.setmode(GPIO.BCM)
led_pins = [5, 6, 13, 19, 26, 1,12, 16, 20, 21]
for pin in led_pins:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Component to LED Mapping
component_to_led = {
    "uln2003": 0,        # GPIO 5
    "load cell": 1,      # GPIO 6
    "dc pump": 2,        # GPIO 13
    "helical gear motor": 3,  # GPIO 19
    "battery": 4,          # GPIO 26
    "relay": 5,          # GPIO 1
    "stepper": 6,        # GPIO 12
    "gear motor": 7,     # GPIO 16
    "servo": 8,  # GPIO 20
    "lora": 9,         # GPIO 21
                    
}

def capture_image():
    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    ret, frame = cam.read()
    cam.release()
    if ret:
        _, buffer = cv2.imencode('.jpg', frame)
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
        return jpg_as_text
    return None

def load_inventory():
    data = sheet.get_all_values()
    items = {}
    for row in data[1:]:
        try:
            qty = int(row[2])
            total_used = int(row[3]) if len(row) > 3 and row[3].isdigit() else 0
            last_updated = row[4] if len(row) > 4 else ""
            items[row[1]] = {
                'name': row[1],
                'quantity': qty,
                'total_used': total_used,
                'last_updated': last_updated
            }
        except (ValueError, IndexError):
            continue
    return items

inventory = load_inventory()

@app.route("/voice-command", methods=["POST"])
def voice_command():
    try:
        data = request.get_json()
        component = data.get("component", "").lower()

        if component in component_to_led:
            idx = component_to_led[component]
            if idx < len(led_pins):
                pin = led_pins[idx]
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(5)
                GPIO.output(pin, GPIO.LOW)
                return jsonify({"status": "success", "message": f"LED for {component} triggered"}), 200
            else:
                return jsonify({"status": "error", "message": "Invalid LED index"}), 400
        else:
            return jsonify({"status": "error", "message": "Component not recognized"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/camera')
def camera():
    return render_template('camera.html')

@app.route('/capture', methods=['POST'])
def capture():
    image_data = request.form.get('imageData')
    if image_data:
        response = requests.post(WEB_APP_URL, data={'imageData': image_data})
        if response.status_code == 200:
            link = response.json().get("link", "")
            return jsonify({"success": True, "link": link})
    return jsonify({"success": False})

@app.route('/inventory')
def inventory_page():
    username = request.args.get('username', '')
    rfid = request.args.get('rfid', '')
    return render_template('item.html', username=username, rfid=rfid)

@app.route('/rfid')
def rfid_page():
    return render_template('rfid.html')

@socketio.on('update_quantity')
def update_quantity(data):
    global inventory, last_rfid_user
    item_name = data['box_id']
    change = int(data['change'])
    user = last_rfid_user.get("username", "Unknown")
    uid = last_rfid_user.get("rfid", "NA")
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    all_data = sheet.get_all_values()
    for idx, row in enumerate(all_data[1:], start=2):
        if row[1] == item_name:
            current_qty = int(row[2])
            total_used = int(row[3]) if len(row) > 3 and row[3].isdigit() else 0
            new_qty = max(0, current_qty + change)
            new_total_used = total_used + abs(change) if change < 0 else max(0, total_used - abs(change))
            last_update = time.strftime("%Y-%m-%d %H:%M:%S")
            sheet.update_cell(idx, 3, new_qty)
            sheet.update_cell(idx, 4, new_total_used)
            sheet.update_cell(idx, 5, last_update)
            break

    inventory = load_inventory()
    socketio.emit('update_inventory', {item_name: inventory[item_name]})

    usage_log = client.open_by_key(SHEET_ID).worksheet("UsageLog")
    usage_log.append_row([user, uid, item_name, change, now])

    # LED glow when item updated


@app.route("/get_inventory", methods=["GET"])
def get_inventory():
    fresh_inventory = load_inventory()
    return jsonify(list(fresh_inventory.values()))

@socketio.on('update_boxes')
def handle_update_boxes(data):
    socketio.emit('update_boxes', data)

last_rfid_user = {}

@app.route("/rfid_scanned", methods=["POST"])
def rfid_scanned():
    global last_rfid_user
    data = request.json
    last_rfid_user = {"rfid": data["rfid"], "username": data["username"]}
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    usage_log = client.open_by_key(SHEET_ID).worksheet("UsageLog")
    usage_log.append_row([data["username"], data["rfid"], "", now])
    return "OK"

@app.route('/last_rfid')
def last_rfid():
    return jsonify(last_rfid_user)

@app.route('/clear_rfid', methods=['POST'])
@app.route('/clear_last_rfid', methods=['POST'])
def clear_rfid():
    global last_rfid_user
    last_rfid_user = {}
    return jsonify({"status": "cleared"})

@app.route('/save_photo', methods=['POST'])
def save_photo():
    data = request.get_json()
    img_data = data['image'].split(",")[1]
    filename = f"user_photo_{int(time.time())}.png"
    with open(f"photos/{filename}", "wb") as fh:
        fh.write(base64.b64decode(img_data))
    return jsonify({"status": "ok", "filename": filename})

def gen_frames():
    cap = cv2.VideoCapture(0)
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("Server running at: http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
