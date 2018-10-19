import json
import os
import email.parser
import email.policy
import paho.mqtt.client as mqtt
from aiosmtpd.controller import Controller


def on_connect(client, userdata, flags, rc):
    """
    Handles subscribing to topics when a connection to MQTT is established
    :return: None
    """
    print("Connected with result code "+str(rc), flush=True)


class TelegraphHandler:
    def __init__(self, mqtt: mqtt.Client):
        self.mqtt = mqtt

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if address != 'post@home.misell.cymru':
            return '553 invalid email'
        envelope.rcpt_tos.append(address)
        return '250 OK'

    async def handle_DATA(self, server, session, envelope):
        print('Message from %s' % envelope.mail_from)
        print('Message for %s' % envelope.rcpt_tos)
        print('Message data:\n')
        print(envelope.content.decode('utf8', errors='replace'))
        print('End of message', flush=True)

        message = email.parser.BytesParser(policy=email.policy.default).parsebytes(envelope.content)

        data = json.dumps({
            "subject": message["subject"],
            "from": message["from"],
            "message": message.get_body().get_content()
        })
        self.mqtt.publish("printer/print", data)

        return '250 Message accepted for delivery'


if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect

    client.connect(os.getenv("MQTT_SERVER", "172.30.2.3"), 1883, 60)

    controller = Controller(TelegraphHandler(client), hostname='0.0.0.0', port=25)
    controller.start()
    print("SMTP server started", flush=True)
    while True:
        try:
            client.loop()
        except (KeyboardInterrupt, SystemExit):
            print("Bye!", flush=True)
            break
    controller.stop()
