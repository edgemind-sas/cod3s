from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI

class DataBase:
    client: AsyncIOMotorClient = None

db = DataBase()


DATABASE_URL = "mongodb://rootuser:rootpass@localhost:27017/mydatabaseTest1?authSource=admin"



def get_database() -> AsyncIOMotorClient:
    return db.client.mydatabaseTest1 

def connect_to_mongo():
    db.client = AsyncIOMotorClient(DATABASE_URL)
    print("Connected to MongoDB")

def close_mongo_connection():
    db.client.close()
    print("Disconnected from MongoDB")

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    close_mongo_connection()
