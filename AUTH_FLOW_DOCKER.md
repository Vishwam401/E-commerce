# Auth Flow (Docker + Restfox) - Easy Guide

Yeh guide first-time Docker setup ke saath auth flow test karne ke liye hai.

## 1) First-Time Setup (Docker)

1. Project root open karo: `D:\PROJECTS\E-Commerce`
2. Ensure `.env.docker` present ho (DB + secret values)
3. Containers build + run karo:

```powershell
docker-compose up -d --build
```

4. Check services up hain:

```powershell
docker-compose ps
```

Expected: `api` and `db` both running.

## 2) API URL kaunsi use karni hai?

Current host mapping ke hisaab se API URL:

- `http://127.0.0.1:8001`

Note: `8001` isliye use kar rahe hain taaki local `8000` conflicts avoid ho.

## 3) Restfox se Auth test kaise karein

### A) Health check
- Method: `GET`
- URL: `http://127.0.0.1:8001/`

### B) Register
- Method: `POST`
- URL: `http://127.0.0.1:8001/auth/register`
- Header: `Content-Type: application/json`
- Body:

```json
{
  "email": "demo_user1@example.com",
  "username": "demo_user1",
  "password": "Password123!"
}
```

Expected: `201 Created`

### C) Login
- Method: `POST`
- URL: `http://127.0.0.1:8001/auth/login`
- Header: `Content-Type: application/x-www-form-urlencoded`
- Body type: Form URL Encoded
  - `username=demo_user1@example.com`
  - `password=Password123!`

Expected: `200` + `access_token`

## 4) Common Errors (quick samjho)

- `422 missing`
  - Usually koi required field missing hai (`email/username/password`)
  - Body format galat ho sakta hai

- `409 User with this email already exists`
  - Same email se dobara register kar rahe ho

- `409 Username or email already exists`
  - Username duplicate hai

- `500 Internal server error while creating user`
  - Request wrong server/port pe ja rahi ho sakti hai
  - Ya backend exception hua (logs check karo)

Logs check command:

```powershell
docker-compose logs api --tail 120
```

## 5) Daily restart commands

```powershell
docker-compose up -d
docker-compose restart api
docker-compose down
```

## 6) Future me add karna ho (refresh token, Redis, caching)

Jab tum next auth features add karoge, is guide me yeh sections add karna:

1. `Refresh Token Flow`
   - login pe `access_token` + `refresh_token`
   - `/auth/refresh` endpoint

2. `Redis Token/Caching`
   - token blacklist / session store
   - OTP/cache use-cases

3. `Restfox Examples`
   - protected routes with `Authorization: Bearer <token>`

Bas iss file ko update karte rehna, easy reference ban jayega.
