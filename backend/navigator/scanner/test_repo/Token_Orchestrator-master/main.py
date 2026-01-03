import time
import heapq
import random
from typing import Dict,Optional
from fastapi import FastAPI,HTTPException
import asyncio
from pydantic import BaseModel
import uuid

#configurations acc to ps
KEY_LIFETIME_SECONDS=5*60
BLOCK_AUTO_RELEASE_SEC=60
CLEANUP_INTERVAL=1.0

app=FastAPI(title="Token Orchestrator")

#pydantic model KeyInfo for story key data
class keyInfo(BaseModel):
    id:str
    key:str
    created_at:float
    expires_at:float
    is_blocked:bool
    blocked_until:Optional[float]=None

keys:Dict[str,keyInfo]={}       #dict for storing created keys
available:set=set()               #for storing available keys
expiry_heap=[]                    #min-heap for managing key expirations
blocked_set=set()               #for storing blocked keys

def _now()->float:
    return time.time()  #current timestamp

def push_expiry(id:str,expires_at:float):
    heapq.heappush(expiry_heap,(expires_at,id))

def create_random_key_string()->str:
    return uuid.uuid4().hex

def add_key_record(id:str,key_str:str):
    now=_now()
    expires_at=now+KEY_LIFETIME_SECONDS
    info=keyInfo(
        id=id,
        key=key_str,
        created_at=now,
        expires_at=expires_at,
        is_blocked=False,
        blocked_until=None,
    )
    keys[id]=info
    available.add(id)
    push_expiry(id,expires_at)

def remove_key(id:str):
    if id in keys:
        keys.pop(id)
    available.discard(id)
    blocked_set.discard(id)

async def background_cleanup():
    while True:
        now=_now()
        
        #expiry of keys
        while expiry_heap and expiry_heap[0][0]<=now:
            expires_at,id=heapq.heappop(expiry_heap)
            info=keys.get(id)
            if not info:
                continue
            if info.expires_at!=expires_at:
                continue
            remove_key(id)

        #auto-unblocking keys
        to_unblock=[]
        for id in list (blocked_set):
            info=keys.get(id)
            if not info:
                blocked_set.discard(id)
                continue
            if info.blocked_until and info.blocked_until<=now:
                to_unblock.append(id)

        #making them available
        for id in to_unblock:
            info=keys.get(id)
            if info:
                info.is_blocked=False
                info.blocked_until=None
                blocked_set.discard(id)
                if info.expires_at>now:
                    available.add(id)
    
    await asyncio.sleep(CLEANUP_INTERVAL)

#creating and posting keys 
@app.post("/keys",status_code=201)
def create_key():
    id=uuid.uuid4().hex
    key_str=create_random_key_string()
    add_key_record(id,key_str)
    return{"id":id,"key":key_str}

#fetching keys 
@app.get("/keys")
def get_available_key():
    if not available:
        raise HTTPException(status_code=404,detail="No keys available")
    id =random.choice(list(available))
    info=keys.get(id)
    if not info:
        available.discard(id)
        raise HTTPException(status_code=404,detail="No keys available")
    now=_now()
    info.is_blocked=True
    info.blocked_until=now+BLOCK_AUTO_RELEASE_SEC
    blocked_set.add(id)
    available.discard(id)
    return{"id":info.id,"key":info.key}

#fetching keys with specific id
@app.get("/keys/{id}")
def get_keys_info(id:str):
    info=keys.get(id)
    if not info:
        raise HTTPException(status_code=404,detail="Key not found")
    return{
        "id":info.id,
        "isBlocked":info.is_blocked,
        "blockedUntil":info.blocked_until,
        "createdAt":info.created_at,
        "expriesAt":info.expires_at
    }

#deleting keys with specific id    
@app.delete("/keys/{id}")
def delete_key(id:str):
    if id not in keys:
        raise HTTPException(status_code=404,detail="Key not found")
    remove_key(id)
    return {"status":"Deleted","id":id}

#manually unblocking key after usage while there expiry hasn't reached    
@app.put("/keys/{id}")
def unblock_key(id:str):
    info=keys.get(id)
    if not info:
        raise HTTPException(status_code=404,detail="Key not found")
    info.is_blocked=False
    info.blocked_until=None
    blocked_set.discard(id)
    if info.expires_at>_now():
        available.add(id)
    return{"status":"unblocked","id":id}

#keeping key alive by extending its expiry time    
@app.put("/keepalive/{id}")
def keepalive_key(id:str):
    info=keys.get(id)
    if not info:
        raise HTTPException(status_code=404,detail="Key not found")
    new_expiry=_now()+KEY_LIFETIME_SECONDS
    info.expires_at=new_expiry
    push_expiry(id,new_expiry)
    if not info.is_blocked:
        available.add(id)
    return{"status":"kept-alive","id":id,"expriesAt":new_expiry}