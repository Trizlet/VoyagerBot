import json
import os
import random
import time

import requests
import tweepy
from dotenv import load_dotenv

# HTTP headers and config (can be adjusted as needed)
HEADERS = {
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "User-Agent": "VoyagerBot (+https://github.com/Trizlet/VoyagerBot)",
}

TRIES = 3
DEBUG_MSG = False
REMOVE_IMG = True
POST_CONFIRM = True
IMAGE_MODE = "calib"  # "raw", "calib", or "both"


def get_modes(image_mode):
    match image_mode:
        case "raw":
            return ["_RAW.JPG"]
        case "calib":
            return ["_CALIB.JPG"]
        case "both":
            return ["_RAW.JPG", "_CALIB.JPG"]
        case _:
            raise ValueError(f"Unknown image_mode: {image_mode}")


def load_auth(base_path):
    auth_path = os.path.join(base_path, "auth.env")
    load_dotenv(auth_path)
    return (
        os.getenv("CONSUMER_KEY"),
        os.getenv("CONSUMER_SECRET"),
        os.getenv("ACCESS_TOKEN"),
        os.getenv("ACCESS_TOKEN_SECRET"),
    )


def auth_v1(key, secret, token, token_secret) -> tweepy.API:
    auth = tweepy.OAuthHandler(key, secret)
    auth.set_access_token(token, token_secret)
    return tweepy.API(auth)


def auth_v2(key, secret, token, token_secret) -> tweepy.Client:
    return tweepy.Client(
        consumer_key=key,
        consumer_secret=secret,
        access_token=token,
        access_token_secret=token_secret,
        wait_on_rate_limit=True,
    )


def load_metadata(data_path):
    with open(data_path) as f:
        return json.load(f)


def select_page(meta):
    selection = random.randint(0, meta["limit"])
    return meta["page"][selection]


def download_images(session, imgs, modes, base_path):
    downloaded = []
    for group in imgs.values():
        for url in group:
            url_upper = url.upper()
            for mode in modes:
                if url_upper.endswith(mode):
                    dst = os.path.join(base_path, mode.lstrip("_"))
                    with open(dst, "wb") as f:
                        f.write(session.get(url).content)
                    downloaded.append(dst)
    return downloaded


def compose_tweet(host, target, filter, date, id):
    return f"{host}\n\nTarget: {target}\nFilter: {filter}\nDate: {date}\nOPUS Image ID: {id}"


def cleanup_files(paths):
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def main():
    base_path = os.path.dirname(os.path.realpath(__file__))
    session = requests.Session()
    session.headers.update(HEADERS)
    modes = get_modes(IMAGE_MODE)
    keys = load_auth(base_path)
    api_v1 = auth_v1(*keys)
    client_v2 = auth_v2(*keys)

    for attempt in range(TRIES):
        try:
            meta = load_metadata(os.path.join(base_path, "data.json"))
            page = select_page(meta)
            id, target, date_ts, filter, host = page
            date = date_ts.split("T")[0]

            response = session.get(
                f"https://opus.pds-rings.seti.org/opus/api/files/{id}.json"
                "?types=vgiss_raw_browse,vgiss_cleaned_browse,vgiss_calib_browse,vgiss_geomed_browse"
            )
            response.raise_for_status()
            imgs = response.json()["data"][id]

            downloaded = download_images(session, imgs, modes, base_path)

            text = compose_tweet(host, target, filter, date, id)

            if DEBUG_MSG:
                print(text)

            if POST_CONFIRM:
                media_ids = [
                    api_v1.media_upload(path).media_id_string for path in downloaded
                ]
                if media_ids:
                    client_v2.create_tweet(text=text, media_ids=media_ids)
                    if DEBUG_MSG:
                        print("\nTweeted!")

            time.sleep(2)

            if REMOVE_IMG:
                cleanup_files(downloaded)
                if DEBUG_MSG:
                    print("\nRemoved downloaded images.")

        except (KeyError, requests.HTTPError) as e:
            if attempt < TRIES - 1:
                time.sleep(10)
                continue
            if DEBUG_MSG:
                print("ERROR:", e)
            raise
        break


if __name__ == "__main__":
    main()
