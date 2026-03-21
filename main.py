# main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import init_db
import models  
from scheduler import start_scheduler, stop_scheduler

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()          
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(lifespan=lifespan)