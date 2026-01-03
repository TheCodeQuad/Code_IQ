The problem statment was as follows:
---------------------------------------------

Design a server capable of generating, assigning, and managing API keys with specific functionalities. The server should offer various endpoints for interaction:
An endpoint to create new keys. Each generated key has a life of 5 minutes after which it gets deleted automatically if keep-alive operation is not run for that key (More details mentioned below).
An endpoint to retrieve an available key, ensuring the key is randomly selected and not currently in use. This key should then be blocked from being served again until its status changes. If no keys are available, a 404 error should be returned.
An endpoint to unblock a previously assigned key, making it available for reuse.
An endpoint to permanently remove a key from the system.
An endpoint for key keep-alive functionality, requiring clients to signal every 5 minutes to prevent the key from being deleted.
Automatically release blocked keys within 60 seconds if not unblocked explicitly.
Constraints:
Ensuring efficient key management without the need to iterate through all keys for any operation. The complexity of endpoint requests should be aimed at O(log n) or O(1) for scalability and efficiency.

---------------------------------------

## How to Use the Orchestrator

The orchestrator provides a REST API for managing API keys. Below are the available endpoints and example usages:

### 1. Create a New Key
**Endpoint:** `POST /keys`

**Description:** Generates a new API key. The key is valid for 5 minutes unless kept alive.

**Example (using curl):**
```sh
curl -X POST http://localhost:8000/keys
```
**Response:**
```json
{
	"id": "<key_id>",
	"key": "<key_string>"
}
```

### 2. Get an Available Key
**Endpoint:** `GET /keys`

**Description:** Retrieves a random available key and blocks it for 60 seconds or until manually unblocked.

**Example:**
```sh
curl http://localhost:8000/keys
```
**Response:**
```json
{
	"id": "<key_id>",
	"key": "<key_string>"
}
```

### 3. Get Key Info by ID
**Endpoint:** `GET /keys/{id}`

**Description:** Returns the status and metadata for a specific key.

**Example:**
```sh
curl http://localhost:8000/keys/<key_id>
```
**Response:**
```json
{
	"id": "<key_id>",
	"isBlocked": true,
	"blockedUntil": 1694440000.0,
	"createdAt": 1694439700.0,
	"expriesAt": 1694440000.0
}
```

### 4. Unblock a Key
**Endpoint:** `PUT /keys/{id}`

**Description:** Manually unblocks a key before its auto-release time, making it available for reuse.

**Example:**
```sh
curl -X PUT http://localhost:8000/keys/<key_id>
```
**Response:**
```json
{
	"status": "unblocked",
	"id": "<key_id>"
}
```

### 5. Delete a Key
**Endpoint:** `DELETE /keys/{id}`

**Description:** Permanently removes a key from the system.

**Example:**
```sh
curl -X DELETE http://localhost:8000/keys/<key_id>
```
**Response:**
```json
{
	"status": "Deleted",
	"id": "<key_id>"
}
```

### 6. Keep a Key Alive
**Endpoint:** `PUT /keepalive/{id}`

**Description:** Extends the key's expiry by another 5 minutes from the current time.

**Example:**
```sh
curl -X PUT http://localhost:8000/keepalive/<key_id>
```
**Response:**
```json
{
	"status": "kept-alive",
	"id": "<key_id>",
	"expriesAt": 1694440300.0
}
```

---
**Note:**
- Blocked keys are auto-released after 60 seconds if not unblocked manually.
- All endpoints return JSON responses.
- Replace `<key_id>` and `<key_string>` with actual values from your API responses.