from mastodon import Mastodon
import os
import json
import time
import paho.mqtt.client as mqtt


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.connected_flag = True
        print("connected OK Returned code=", rc)
    else:
        print("Bad connection Returned code= ", rc)


def map_attachment(attachment):
    if attachment["type"] != "image":
        return ''
    alt_text = attachment['description'] if attachment['description'] is not None else attachment["text_url"]
    return f"<img src=\"{attachment['url']}\" alt=\"{alt_text}\" />"


def map_status(mention):
    attachments = ''.join(map(map_attachment, mention["status"]["media_attachments"]))
    emojis = mention["status"]["emojis"]
    message = str(mention["status"]["content"])

    for emoji in emojis:
        message = message.replace(f":{emoji['shortcode']}:",
                                  f"<img src = \"{emoji['url']}\" alt=\":{emoji['shortcode']}:\" "
                                  f"style=\"width: 1em\" />")

    toot_from = mention["account"]["display_name"]
    message = message + attachments

    print(f"New toot from {toot_from}", flush=True)
    print(message, flush=True)

    return {
        "subject": "Toot" if mention["status"]["spoiler_text"] == '' else mention["status"]["spoiler_text"],
        "from": toot_from,
        "message": message,
    }


if __name__ == "__main__":
    client = mqtt.Client()

    client.on_connect = on_connect
    client.connected_flag = False

    client.connect(os.getenv("MQTT_SERVER", "172.30.2.3"), 1883, 60)

    mastodon = Mastodon(
        client_id='masto_clientcred.secret',
        access_token='masto_usercred.secret',
        api_base_url='https://masto.misell.cymru',
        ratelimit_method='pace',
        ratelimit_pacefactor=0.7
    )

    try:
        with open("masto_last_notif_id", "r") as f:
            last_notif_id = f.read().strip()
    except FileNotFoundError:
        last_notif_id = None

    while True:
        time.sleep(1)
        client.loop()
        if client.connected_flag:
            notifs = mastodon.notifications(since_id=last_notif_id)
            if len(notifs) > 0:
                last_notif_id = notifs[0]['id']
                with open("masto_last_notif_id", "w") as f:
                    f.write(str(last_notif_id))
                mentions = filter(lambda n: n['type'] == 'mention', notifs)
                messages = map(map_status, mentions)
                messages = map(lambda m: json.dumps(m), messages)

                for m in messages:
                    client.publish("printer/print", m)
