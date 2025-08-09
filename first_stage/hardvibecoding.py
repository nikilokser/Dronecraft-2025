from skyros.drone import Drone

#подтянуть айдишники дронов в craft_patterns вместо айдишников 1-4 плюс в аргумент функции 
def process_qr_data(qr_data):
    #данные для направления на координаты дронов для разных предметов
    craft_patterns = {
        "0": {  # Кирка  02DDSS
            "1": {"x": -1, "y": 1, "z": 1}, #id 801 D
            "2": {"x": 0, "y": 1, "z": 1},  #id 802 D
            "3": {"x": 0, "y": 0, "z": 1},  #id 803 S
            "4": {"x": 0, "y": -1, "z": 1}  #id 804 ? = S
        },
        "1": {  # Топор  17DDDS
            "1": {"x": -1, "y": 1, "z": 1},  #id 801 D
            "2": {"x": 0, "y": 1, "z": 1}, #id 802 D
            "3": {"x": 0, "y": 0, "z": 1}, #id 803 S
            "4": {"x": -1, "y": 0, "z": 1}   #id 804 ? = D
        },
        "2": {  # Булава  24DDDS
            "1": {"x": 1, "y": 1, "z": 1},  #id 801 D
            "2": {"x": 0, "y": 1, "z": 1},  #id 802 D
            "3": {"x": -1, "y": -1, "z": 1},  #id 803 S
            "4": {"x": 1, "y": 0, "z": 1}   #id 804 ? = D
        }
    }

    #парсим строку из QR-кода
    craft_type = qr_data[0]  # Первый символ — тип предмета
    positions = craft_patterns.get(craft_type, {})

    return positions

#инициализация
qr_data = "24DDDS"
targets = process_qr_data(qr_data)
print(targets)

