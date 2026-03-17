curl -X 'POST' \
  'http://0.0.0.0:8000/api/v1/auth/login' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "email": "test@example.com",
  "password": "test123456"
}'

返回
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOGUzZGEzNi00MGJhLTRhMjctOGUxOC05ZjdjMmE3NDE5MmYiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJ0ZW5hbnRfaWQiOiI3ZTczY2EwYS0wMWMyLTRmYjYtODg5MC03MzZjYzUwYmM3MWYiLCJyb2xlIjoidGVuYW50X2FkbWluIiwiZXhwIjoxNzczNzMxMTczLCJ0eXBlIjoiYWNjZXNzIn0.yIH16yvRK-VdOwdUewaUzbT3Csad-qkjwxKL7l1lpiU",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwOGUzZGEzNi00MGJhLTRhMjctOGUxOC05ZjdjMmE3NDE5MmYiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJ0ZW5hbnRfaWQiOiI3ZTczY2EwYS0wMWMyLTRmYjYtODg5MC03MzZjYzUwYmM3MWYiLCJyb2xlIjoidGVuYW50X2FkbWluIiwiZXhwIjoxNzc0MzM0MTczLCJ0eXBlIjoicmVmcmVzaCIsImp0aSI6IjRlNmUxMDJiLTYxNGEtNGE3MS1iYjU1LTMzYzY5YTRlNzczYyJ9.rhKucN48dPvhKP2o1aQYLoSViCnkdqT1DV53FzdKWc8",
    "token_type": "bearer",
    "expires_in": 1800
  },
  "request_id": null
}

curl -X 'GET' \
  'http://0.0.0.0:8000/api/v1/auth/me' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer <access_token>'

在http://0.0.0.0:8000/docs 页面点击右上角 Authorize，输入 access_token（无需手动加 Bearer 前缀）

报错

{
  "detail": [
    {
      "type": "missing",
      "loc": [
        "header",
        "authorization"
      ],
      "msg": "Field required",
      "input": null
    }
  ]
}