import json
import os
import random
import time

import requests
import tweepy
from dotenv import load_dotenv

tries = 4

auth = os.path.dirname(os.path.realpath(__file__)) + "/auth.env"
load_dotenv(auth)

consumer_key = os.getenv('CONSUMER_KEY')
consumer_secret = os.getenv('CONSUMER_SECRET')
access_token = os.getenv('ACCESS_TOKEN')
access_token_secret = os.getenv('ACCESS_TOKEN_SECRET')


def auth_v1(
    consumer_key, consumer_secret, access_token, access_token_secret
) -> tweepy.API:
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    return tweepy.API(auth)

def auth_v2(
    consumer_key, consumer_secret, access_token, access_token_secret
) -> tweepy.Client:
    return tweepy.Client(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        return_type=requests.Response,
        wait_on_rate_limit=True,
    )

for i in range(tries):
    try:
        api_v1 = auth_v1(
            consumer_key, consumer_secret, access_token, access_token_secret
        )
        client_v2 = auth_v2(
            consumer_key, consumer_secret, access_token, access_token_secret
        )

        path = os.path.dirname(os.path.realpath(__file__)) + "/data.json"
        with open(path) as fd:
            metadataJSON = json.load(fd)

        selection = random.randint(0, metadataJSON["limit"])

        id = metadataJSON["page"][selection][0]
        target = metadataJSON["page"][selection][1]
        date = metadataJSON["page"][selection][2].split("T")[0]
        filter = metadataJSON["page"][selection][3]
        host = metadataJSON["page"][selection][4]

        chosen = requests.get(
            f"https://opus.pds-rings.seti.org/opus/api/files/{id}.json?types=vgiss_raw_browse,vgiss_cleaned_browse,vgiss_calib_browse,vgiss_geomed_browse"
        )

        if chosen.status_code == 200:
            chosenJSON = json.loads(chosen.content)
            for item in chosenJSON["data"][id]:
                for img in chosenJSON["data"][id][item]:
                    if str(img).upper().endswith("_RAW.JPG") or str(
                        img
                    ).upper().endswith("_CALIB.JPG"):
                        # print(img)
                        response = requests.get(img)
                        destination = (
                            os.path.dirname(os.path.realpath(__file__))
                            + "/"
                            + img.rsplit("_", 1)[-1]
                        )
                        with open(destination, "wb") as f:
                            f.write(response.content)
            text2post = f"{host}\n\nTarget: {target}\nFilter: {filter}\nDate: {date}\nOPUS Image ID: {id}"
           # print(text2post)
            path1 = os.path.dirname(os.path.realpath(__file__)) + "/RAW.JPG"
            path2 = os.path.dirname(os.path.realpath(__file__)) + "/CALIB.JPG"
            media_id1 = api_v1.media_upload(path1).media_id_string
            media_id2 = api_v1.media_upload(path2).media_id_string
            client_v2.create_tweet(text=text2post, media_ids=[media_id2])
            #client_v2.create_tweet(text=text2post, media_ids=[media_id2, media_id1])
           # print("Tweeted!")
            time.sleep(2)
            os.remove(os.path.dirname(os.path.realpath(__file__)) + "/RAW.JPG")
            os.remove(os.path.dirname(os.path.realpath(__file__)) + "/CALIB.JPG")
           # print("Removed images, script complete.")
    except KeyError:
        if i < tries - 1:  # i is zero indexed
            time.sleep(10)
            continue
        else:
            #print("ERROR")
            raise
    break

