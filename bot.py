import json
import os
import random
import time

import requests
import tweepy
from dotenv import load_dotenv

# HTTP headers
headers = {
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "User-Agent": "VoyagerBot (+https://github.com/Trizlet/VoyagerBot)",
}

# Configuration
tries = 3
debug_msg = False  # Enable debug output
remove_img = True  # Remove downloadeded images after use
post_confirm = True  # Enable/Disable tweeting
image_mode = "calib"  # "raw", "calib", or "both"

# Map modes to filename
match image_mode:
    case "raw":
        modes = ["_RAW.JPG"]
    case "calib":
        modes = ["_CALIB.JPG"]
    case "both":
        modes = ["_RAW.JPG", "_CALIB.JPG"]
    case _:
        raise ValueError(f"Unknown image_mode: {image_mode}")

# Paths and auth
base_path = os.path.dirname(os.path.realpath(__file__))
auth_path = os.path.join(base_path, "auth.env")
load_dotenv(auth_path)

consumer_key = os.getenv("CONSUMER_KEY")
consumer_secret = os.getenv("CONSUMER_SECRET")
access_token = os.getenv("ACCESS_TOKEN")
access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

session = requests.Session()
session.headers.update(headers)


def auth_v1(key, secret, token, token_secret) -> tweepy.API:
    a = tweepy.OAuthHandler(key, secret)
    a.set_access_token(token, token_secret)
    return tweepy.API(a)


def auth_v2(key, secret, token, token_secret) -> tweepy.Client:
    return tweepy.Client(
        consumer_key=key,
        consumer_secret=secret,
        access_token=token,
        access_token_secret=token_secret,
        wait_on_rate_limit=True,
    )


api_v1 = auth_v1(consumer_key, consumer_secret, access_token, access_token_secret)
client_v2 = auth_v2(consumer_key, consumer_secret, access_token, access_token_secret)

for attempt in range(tries):
    try:
        # Load metadata
        data_path = os.path.join(base_path, "data.json")
        with open(data_path) as f:
            meta = json.load(f)

        selection = random.randint(0, meta["limit"])
        page = meta["page"][selection]
        id, target, date_ts, filter, host = page
        date = date_ts.split("T")[0]

        # Fetch image list
        response = session.get(
            f"https://opus.pds-rings.seti.org/opus/api/files/{id}.json"
            "?types=vgiss_raw_browse,vgiss_cleaned_browse,vgiss_calib_browse,vgiss_geomed_browse"
        )
        response.raise_for_status()
        imgs = response.json()["data"][id]

        downloaded = []

        # Download selected image types
        for group in imgs.values():
            for url in group:
                url_upper = url.upper()

                # RAW
                if "_RAW.JPG" in modes and url_upper.endswith("_RAW.JPG"):
                    dst = os.path.join(base_path, "RAW.JPG")
                    with open(dst, "wb") as f:
                        f.write(session.get(url).content)
                    downloaded.append(dst)

                # CALIB
                if "_CALIB.JPG" in modes and url_upper.endswith("_CALIB.JPG"):
                    dst = os.path.join(base_path, "CALIB.JPG")
                    with open(dst, "wb") as f:
                        f.write(session.get(url).content)
                    downloaded.append(dst)

        # Compose tweet
        text = (
            f"{host}\n\nTarget: {target}\nFilter: {filter}\n" f"Date: {date}\nOPUS Image ID: {id}"
        )

        if debug_msg:
            print(text)

        # Post
        if post_confirm:
            media_ids = [  # Upload media
                api_v1.media_upload(path).media_id_string for path in downloaded
            ]
            if media_ids:
                client_v2.create_tweet(text=text, media_ids=media_ids)  # Post tweet
                if debug_msg:
                    print("\nTweeted!")

        time.sleep(2)

        # Cleanup
        if remove_img:
            for path in downloaded:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
            if debug_msg:
                print("\nRemoved downloaded images.")

    except (KeyError, requests.HTTPError) as e:
        if attempt < tries - 1:
            time.sleep(10)
            continue
        if debug_msg:
            print("ERROR:", e)
        raise
    break
