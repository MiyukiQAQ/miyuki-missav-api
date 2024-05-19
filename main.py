from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import json_util
from pydantic import BaseModel
import json
import requests
from lxml import etree
from downloader import downloader
import time
from datetime import datetime
import threading

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}

app = FastAPI()
uri = 'mongodb://miyuki:xxxx@192.168.0.123:27017/miyuki'
client = MongoClient(uri)
db = client['miyuki']

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def parse_json(data):
    return json.loads(json_util.dumps(data))


def download_from_queue():
    download_queue_collection = db["download_queue"]
    download_status_collection = db["download_status"]
    while True:
        download_infos = download_queue_collection.find()
        for download_info in download_infos:
            url = download_info['url']
            serial = download_info['serial']
            query = {"serial": serial}
            download_status = {
                'serial': serial,
                'url': url,
                'status': 'downloading',
                'startTime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'endTime': None
            }
            update_data = {"$set": download_status}
            download_status_collection.update_one(query, update_data, upsert=True)
            try:
                flag = downloader.download_from_url(url)
                if flag:
                    download_status['status'] = 'complete'
                else:
                    download_status['status'] = 'error'
            except Exception as e:
                download_status['status'] = 'error'
            finally:
                download_status['endTime'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                download_status_collection.update_one(query, update_data, upsert=True)
                download_queue_collection.delete_one(query)
        time.sleep(15)


threading.Thread(target=download_from_queue).start()


def get_movie_from_url(url):
    response = requests.get(url=url, headers=headers)
    if response.status_code == 200:
        root = etree.HTML(response.text)
        releaseDate = (root.xpath('//span[contains(text(), "Release date:")]')[0]).getparent().xpath('span[@class="font-medium"]/text()')[0]
        serial = (root.xpath('//span[contains(text(), "Code:")]')[0]).getparent().xpath('span[@class="font-medium"]/text()')[0]
        title = (root.xpath('//span[contains(text(), "Title:")]')[0]).getparent().xpath('span[@class="font-medium"]/text()')[0]
        actress = (root.xpath('//span[contains(text(), "Actress:")]')[0]).getparent().xpath('a/text()')[0]
        description = root.xpath('//meta[@property="og:description"]')[0].get('content')
        return {
            'releaseDate': releaseDate,
            'serial': serial,
            'title': title,
            'actress': actress,
            'description': description
        }
    else:
        return None


@app.on_event("shutdown")
async def shutdown():
    await client.close()


@app.get("/api/movies")
async def movies():
    movie_collection = db["movie"]
    movies = movie_collection.find({}, {'_id': 0})
    return parse_json(movies)


@app.get("/api/downloadstatus")
async def movies():
    download_status_collection = db["download_status"]
    download_status_list = download_status_collection.find({}, {'_id': 0})
    return parse_json(download_status_list)


class Url(BaseModel):
    url: str


@app.post("/api/movie/url")
async def post_movie(urlbody: Url):
    url = urlbody.url
    movie = get_movie_from_url(url)
    movie["url"] = url
    movie["collected"] = False
    movie["playlist"] = None
    movie["type"] = None
    movie_collection = db["movie"]
    query = {"serial": movie['serial']}
    update_data = {"$set": movie}
    movie_collection.update_one(query, update_data, upsert=True)
    moviedata = movie_collection.find({"serial": {"$eq": movie['serial']}}, {'_id': 0})
    return parse_json(moviedata)


@app.delete("/api/movie/{serial}")
async def delete_movie(serial: str):
    movie_collection = db["movie"]
    movie_collection.delete_one({"serial": {"$eq": serial}})
    return True


def time_wait():
    time.sleep(10)


@app.post("/api/movie/{serial}/download")
async def download_movie(serial: str, background_tasks: BackgroundTasks):
    movie_collection = db["movie"]
    movie = movie_collection.find_one({"serial": {"$eq": serial}})
    url = movie["url"]
    download_queue_collection = db["download_queue"]
    download_info = {
        "serial": serial,
        "url": url
    }
    query = {"serial": serial}
    update_data = {"$set": download_info}
    download_queue_collection.update_one(query, update_data, upsert=True)
    return True
