import jinja2
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import selenium.webdriver.firefox.firefox_binary
import selenium.common.exceptions
import paho.mqtt.client as mqtt
from pyvirtualdisplay import Display

binary = selenium.webdriver.firefox.firefox_binary.FirefoxBinary('/home/benjamin/firefox/firefox')
fp = webdriver.FirefoxProfile('/home/benjamin/.mozilla/firefox/volp2y1k.dev-edition-default/')
template = jinja2.Template("""
<html>
    <head>
        <title>Shopping List</title>
        
        <style>
            li {
              font-size: 30px;
              font-family: sans-serif;
            }
        </style>
    </head>
    <body>
        <ul>
            {% for item in items %}
                <li>{{ item }}</li>
            {% endfor %}
        </ul>
    </body>
</html>
""")


def on_connect(client, userdata, flags, rc):
    """
    Handles subscribing to topics when a connection to MQTT is established
    :return: None
    """
    print("Connected with result code "+str(rc))
    client.subscribe("printer/shopping-list")


def get_shopping_list(driver):
    driver.get("https://shoppinglist.google.com/lists/default")
    print("Got page", flush=True)

    list_items = []

    try:
        shopping_list = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "shoppingList"))
        )
        print("Got list", flush=True)
        shopping_list = shopping_list.find_element_by_class_name("activeItems")
        shopping_list = shopping_list.find_elements_by_class_name("activeItem")
        for item in shopping_list:
            list_items.append(item.find_element_by_class_name("title").text)
    finally:
        return template.render(items=list_items)


def on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
    print("Printing shopping list", flush=True)
    try:
        shopping_list = get_shopping_list(userdata)
    except selenium.common.exceptions.WebDriverException as e:
        print(e)
        return

    data = json.dumps({
        "subject": "Shopping List",
        "message": shopping_list
    })

    client.publish("printer/print", data)


if __name__ == "__main__":
    display = Display(visible=0, size=(800, 600))
    display.start()
    print("Setup display", flush=True)
    driver = webdriver.Firefox(fp, firefox_binary=binary)
    print("Got driver", flush=True)

    client = mqtt.Client(userdata=driver)
    client.on_connect = on_connect
    client.message_callback_add("printer/shopping-list", on_message)

    client.connect(os.getenv("MQTT_SERVER", "172.30.2.3"), 1883, 60)

    while True:
        try:
            client.loop()
        except (KeyboardInterrupt, SystemExit):
            print("Bye!")
            break

    driver.close()
    display.stop()
