import json
import logging
import sys
from pyzbar import pyzbar
import cv2
import rospy
import time
from clover.srv import SetLEDEffect
from std_srvs.srv import Trigger

from skyros.drone import Drone

set_effect = rospy.ServiceProxy('led/set_effect', SetLEDEffect)
land = rospy.ServiceProxy('land', Trigger)

stream_url = "http://192.168.1.88:8080/stream?topic=/qr_detected_images"

number_of_drones = 3

b_data = ""
drones_ready = []
qr_found = False


def setup_logger(verbose=False, quiet=False):
    """Set up simple CLI logger"""
    level = logging.DEBUG if verbose else (logging.WARNING if quiet else logging.INFO)
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    
    return logging.getLogger()

setup_logger()

slave_target = None

def handle_message(msg):
    global slave_target
    print(f"Received: {msg}")
    
    try:
        data = json.loads(msg)
        if data.get("t") == "fc":  # flight_command
            # Check if this message is for this specific drone
            target_drone_id = data.get("d")
            if target_drone_id == drone.drone_id:
                # Parse coordinates for this drone
                slave_target = {
                    "x": data.get("x", 0),
                    "y": data.get("y", 0),
                    "z": data.get("z", 1)
                }
                logging.info(f"Slave {drone.drone_id} got target: {slave_target}")
    except Exception:
        if "point" in msg:
            drones_ready.append(msg.split()[0] if msg.split()[0] not in drones_ready else None)
            logging.error(msg)

            old_number_drones_ready = len(set(drones_ready))
            if len(set(drones_ready)) != old_number_drones_ready:
                logging.info(f"{len(set(drones_ready))} is arrived to point")
            else:
                logging.info(f"Waiting for drones arriving {drones_ready}")
        elif "all drones ready" in msg:
            set_effect(effect='flash', r=0, g=255, b=0)
        else:
            logging.warning(f"Failed to parse JSON: {msg}")


with Drone(network_id=0x12, wifi_channel=10, tx_power=11, uart_port="/dev/ttyAMA1") as drone:
    drone.set_custom_message_callback(handle_message)

    # Send start json message to other drones
    start_message = {
        "status": "start",
        "info": {
            "drone_id": drone.drone_id,
        }
    }
    drone.broadcast_custom_message(json.dumps(start_message))

    # Wait for other drones to start
    if drone.wait_for_drones(n=number_of_drones-1, timeout=60.0):
        # Get network status with detailed info
        status = drone.get_network_status()

        # Show detailed drone info
        for drone_id, details in status["drone_details"].items():
            pos = details["position"]
            logging.info(
                f"  drone_{drone_id}: pos=({pos['x']:.1f},{pos['y']:.1f},{pos['z']:.1f}) "
            )
        drone.wait(1)

    # Take off

    drone.takeoff(z=1.5)
    drone.wait(5)
    
    # Master drone logic: drone with lowest ID becomes master
    discovered_drones = drone.get_discovered_drones()
    all_drones = discovered_drones | {drone.drone_id}
    master_drone_id = min(all_drones)
    
    if drone.drone_id == master_drone_id:
        logging.info(f"Drone {drone.drone_id} is MASTER - controlling swarm")
        
        # Master sends individual coordinates to each drone

        # Master flies to its position
        drone.navigate_with_avoidance(x=0, y=-1.0, z=3)

        cap = cv2.VideoCapture(stream_url)

        if cap.isOpened():
            logging.info("Stream successfully opened")
            qr_found = False
            start_time = time.time()  # Записываем время начала
            timeout = 5  # Таймаут в секундах
            
            while True:
                # Проверяем, не прошло ли 10 секунд
                if time.time() - start_time > timeout:
                    logging.warning(f"QR detection timeout after {timeout} seconds")
                    break
                
                ret, frame = cap.read()
                if ret:
                    
                    barcodes = pyzbar.decode(frame)
                    for barcode in barcodes:
                        b_data = barcode.data.decode('utf-8')

                        if b_data:
                            logging.info(f"QR with data: {b_data}")
                            qr_found = True
                            break
                    if qr_found:
                        break    
                else:
                    logging.error("Stream empty")
                    break
            cap.release()

            if b_data == "":
                drone.navigate_with_avoidance(x=-1, y=1.0, z=3)
                cap = cv2.VideoCapture(stream_url)

                if cap.isOpened():
                    logging.info("Stream successfully opened")
                    qr_found = False
                    start_time = time.time()  # Записываем время начала
                    timeout = 5  # Таймаут в секундах
                    
                    while True:
                        # Проверяем, не прошло ли 10 секунд
                        if time.time() - start_time > timeout:
                            logging.warning(f"QR detection timeout after {timeout} seconds")
                            break
                        
                        ret, frame = cap.read()
                        if ret:
                            
                            barcodes = pyzbar.decode(frame)
                            for barcode in barcodes:
                                b_data = barcode.data.decode('utf-8')

                                if b_data:
                                    logging.info(f"QR with data: {b_data}")
                                    qr_found = True
                                    break
                            if qr_found:
                                break    
                        else:
                            logging.error("Stream empty")
                            break
                    cap.release()

            discovered_drones = drone.get_discovered_drones()
        
        # Send coordinates to each drone separately
        for target_drone_id in discovered_drones:
            # Different coordinates for each drone
            if b_data == "37DDS":
                coordinates = {
                    111: {"x": 0, "y": 1, "z": 2},
                    126: {"x": 0, "y": 0, "z": 2}
                }.get(target_drone_id, {"x": 0, "y": 0, "z": 1})
            
            # Compact format for individual drone
                flight_command = {
                    "t": "fc",  # flight_command
                    "m": drone.drone_id,  # master_id
                    "d": target_drone_id,  # target drone id
                    "x": coordinates["x"],
                    "y": coordinates["y"],
                    "z": coordinates["z"]
                }
            
                json_msg = json.dumps(flight_command)
                logging.info(f"Master sending to drone {target_drone_id}: {json_msg} ({len(json_msg)} chars)")
                
                for i in range(20):
                    drone.broadcast_custom_message(json_msg)
                    drone.wait(0.4)

            if b_data == "30DSS":
                coordinates = {
                    111: {"x": 0, "y": 0, "z": 2},
                    126: {"x": 0, "y": -1, "z": 2}
                }.get(target_drone_id, {"x": 0, "y": 0, "z": 1})
            
            # Compact format for individual drone
                flight_command = {
                    "t": "fc",  # flight_command
                    "m": drone.drone_id,  # master_id
                    "d": target_drone_id,  # target drone id
                    "x": coordinates["x"],
                    "y": coordinates["y"],
                    "z": coordinates["z"]
                }
            
                json_msg = json.dumps(flight_command)
                logging.info(f"Master sending to drone {target_drone_id}: {json_msg} ({len(json_msg)} chars)")
                
                for i in range(20):
                    drone.broadcast_custom_message(json_msg)
                    drone.wait(0.4)
            
        if b_data == "37DDS":
            drone.navigate_with_avoidance(x=-1, y=1.0, z=3)
        elif b_data == "30DSS":
            drone.navigate_with_avoidance(x=0, y=1.0, z=3)

        while len(set(drones_ready)) < number_of_drones-1:
            pass
            
        drone.broadcast_custom_message("all drones ready")
        logging.info("All drones are ready, led turns on")
        set_effect(effect='flash', r=0, g=255, b=0)

        drone.wait(3)


    else:
        logging.info(f"Drone {drone.drone_id} is SLAVE - waiting for master commands")
        
        # Wait for master commands and execute them
        drone.wait(5)  # Wait for master to send commands


        while slave_target == None:
            pass 

        if slave_target:
            logging.info(f"Slave {drone.drone_id} flying to: {slave_target}")
            drone.navigate_with_avoidance(
                x=slave_target["x"], 
                y=slave_target["y"], 
                z=slave_target["z"]
            )
        else:
            logging.warning(f"Slave {drone.drone_id} no target received, flying to default")
            drone.navigate_with_avoidance(x=0.0, y=0.0, z=1.0)
            

        while len(set(drones_ready)) < number_of_drones-1:
            drone.broadcast_custom_message(f"{drone.drone_id} point")
            drone.wait(0.4)

        set_effect(effect='flash', r=0, g=255, b=0)

        drone.wait(3)

        while qr_found == False:
            pass

    # Broadcast message to other drones
    # drone.broadcast_custom_message(f"Hello from drone_{drone.drone_id}!")

    # Land
    land()
    drone.wait(1)
    land()
    drone.wait(1)
    land()
    drone.wait(1)
    land()
    drone.wait(10)

