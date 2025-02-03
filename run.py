import platform
import time
import logging
from typing import Dict, Any, List

from hexss import json_load, json_update, check_packages

check_packages('numpy', 'opencv-python', 'Flask', 'mss', 'PyAutoGUI', install=True)

import pyautogui
import mss
from hexss import get_hostname
from hexss.network import get_all_ipv4, close_port
from hexss.threading import Multithread
import numpy as np
from flask import Flask, render_template, Response, request, redirect, url_for
import cv2
from datetime import datetime

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def display_capture(data: Dict[str, Any]) -> None:
    with mss.mss() as sct:
        while data['play']:
            try:
                screenshot = sct.grab(sct.monitors[1])
                image = np.array(screenshot)
                data['display_capture'] = image
            except Exception as e:
                logging.error(f"Error in display capture: {e}")
                time.sleep(1)


def get_data(data: Dict[str, Any], quality=100) -> np.ndarray:
    frame = data['display_capture']

    encode_param = [cv2.IMWRITE_JPEG_QUALITY, quality]  # Adjust quality (0-100)
    ret, buffer = cv2.imencode('.jpg', frame, encode_param)
    return buffer


@app.after_request
def add_cache_headers(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video')
def get_video():
    data = app.config['data']
    quality = request.args.get('quality', default=30, type=int)

    def generate():
        while data['play']:
            buffer = get_data(app.config['data'], quality)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.1)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/mouse', methods=['POST'])
def handle_mouse():
    position = request.json
    x = position.get('x')
    y = position.get('y')
    event_type = position.get('type')

    print(f"Received {event_type} at position - X: {x}, Y: {y}")

    # Dispatch event types
    if event_type == 'left-click-down':
        pyautogui.mouseDown(x=x * 1920, y=y * 1080, button='left')
    elif event_type == 'left-click-up':
        pyautogui.mouseUp(x=x * 1920, y=y * 1080, button='left')
    elif event_type == 'right-click-down':
        pyautogui.mouseDown(x=x * 1920, y=y * 1080, button='right')
    elif event_type == 'right-click-up':
        pyautogui.mouseUp(x=x * 1920, y=y * 1080, button='right')
    elif event_type == 'middle-click-down':
        pyautogui.mouseDown(x=x * 1920, y=y * 1080, button='middle')
    elif event_type == 'middle-click-up':
        pyautogui.mouseUp(x=x * 1920, y=y * 1080, button='middle')
    elif event_type == 'scroll-up':
        pyautogui.moveTo(x * 1920, y * 1080)
        pyautogui.scroll(500)  # Simulate scroll up
    elif event_type == 'scroll-down':
        pyautogui.moveTo(x * 1920, y * 1080)
        pyautogui.scroll(-500)  # Simulate scroll down
    elif event_type == 'mouse-move':
        pyautogui.moveTo(x * 1920, y * 1080)  # Simulate mouse move

    return {"message": "Event received successfully"}, 200


@app.route('/keyboard', methods=['POST'])
def handle_keyboard():
    data = request.json
    event_type = data.get('eventType')  # 'keydown' or 'keyup'
    key = data.get('key')  # The actual key pressed (e.g., "a", "Enter")
    code = data.get('code')  # The physical code (e.g., "KeyA", "Enter")

    print(f"Received {event_type} event for key: {key}, code: {code}")

    if event_type == 'keydown':
        try:
            pyautogui.keyDown(key)
        except Exception as e:
            logging.error(f"Error in keydown simulation: {e}")

    elif event_type == 'keyup':
        try:
            pyautogui.keyUp(key)
        except Exception as e:
            logging.error(f"Error in keyup simulation: {e}")

    return {"message": "Keyboard event processed"}, 200


def run_server(data: Dict[str, Any]) -> None:
    app.config['data'] = data
    ipv4 = data['config']['ipv4']
    port = data['config']['port']

    for ipv4_ in {'127.0.0.1', *get_all_ipv4(), get_hostname()}:
        logging.info(f"Running on http://{ipv4_}:{port}")

    app.run(host=ipv4, port=port, debug=False)


def run():
    data = {
        'play': True,
        'config': json_load('camera_server_config.json', {
            "ipv4": '0.0.0.0',
            "port": 2003
        }),
        'display_capture': np.full((480, 640, 3), (50, 50, 50), dtype=np.uint8)
    }
    close_port(data['config']['ipv4'], data['config']['port'], verbose=False)

    m = Multithread()

    m.add_func(display_capture, args=(data,))
    m.add_func(run_server, args=(data,), join=False)

    m.start()
    try:
        while data['play']:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        data['play'] = False
        m.join()


if __name__ == "__main__":
    run()
