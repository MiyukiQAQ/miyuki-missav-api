from fastapi import FastAPI
from pymongo import MongoClient
from bson import json_util
import json

app = FastAPI()
uri = 'mongodb://miyuki:xxxx@192.168.0.123:27017/miyuki'
client = MongoClient(uri)
db = client['miyuki']



def parse_json(data):
    return json.loads(json_util.dumps(data))

@app.on_event("shutdown")
async def shutdown():
    await client.close()

@app.get("/api/movies")
async def movies():
    movie_collection = db["movie"]
    movies = movie_collection.find()
    return parse_json(movies)
