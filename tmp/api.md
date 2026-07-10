curl ^"http://127.0.0.1:8000/history/vote^" ^
  -H ^"Accept-Language: en-US,en;q=0.9^" ^
  -H ^"Connection: keep-alive^" ^
  -H ^"Referer: http://127.0.0.1:8000/docs^" ^
  -H ^"Sec-Fetch-Dest: empty^" ^
  -H ^"Sec-Fetch-Mode: cors^" ^
  -H ^"Sec-Fetch-Site: same-origin^" ^
  -H ^"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0^" ^
  -H ^"accept: application/json^" ^
  -H ^"sec-ch-ua: ^\^"Not;A=Brand^\^";v=^\^"8^\^", ^\^"Chromium^\^";v=^\^"150^\^", ^\^"Microsoft Edge^\^";v=^\^"150^\^"^" ^
  -H ^"sec-ch-ua-mobile: ?0^" ^
  -H ^"sec-ch-ua-platform: ^\^"Windows^\^"^"
response:
[
    {
        "vote_index": 1,
        "started_at": "2026-07-10T11:41:26.143465+07:00",
        "ended_at": "2026-07-10T11:41:31.324596+07:00",
        "duration_seconds": 5,
        "items": []
    },
    {
        "vote_index": 2,
        "started_at": "2026-07-10T12:45:29.062734+07:00",
        "ended_at": "2026-07-10T12:46:01.527208+07:00",
        "duration_seconds": 32,
        "items": [
            {
                "delegate_id": 1215,
                "delegate_name": "Phạm Quí Tiên",
                "delegate_address": "",
                "delegate_group_name": "10. Đơn Vị Bầu Cử Số 10",
                "delegate_street": "",
                "delegate_street_number": "",
                "delegate_city": "",
                "result": "Bo phieu trang"
            },
        ]
    }
]

curl ^"http://127.0.0.1:8000/history/attendance^" ^
  -H ^"Accept-Language: en-US,en;q=0.9^" ^
  -H ^"Connection: keep-alive^" ^
  -H ^"Referer: http://127.0.0.1:8000/docs^" ^
  -H ^"Sec-Fetch-Dest: empty^" ^
  -H ^"Sec-Fetch-Mode: cors^" ^
  -H ^"Sec-Fetch-Site: same-origin^" ^
  -H ^"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0^" ^
  -H ^"accept: application/json^" ^
  -H ^"sec-ch-ua: ^\^"Not;A=Brand^\^";v=^\^"8^\^", ^\^"Chromium^\^";v=^\^"150^\^", ^\^"Microsoft Edge^\^";v=^\^"150^\^"^" ^
  -H ^"sec-ch-ua-mobile: ?0^" ^
  -H ^"sec-ch-ua-platform: ^\^"Windows^\^"^"

[
    {
        "attendance_index": 1,
        "started_at": "2026-07-10T12:39:51.704000+07:00",
        "ended_at": "2026-07-10T12:39:59.605881+07:00",
        "duration_seconds": 7,
        "present": [
            {
                "delegate_id": 1215,
                "delegate_name": "Phạm Quí Tiên",
                "delegate_address": "",
                "delegate_group_name": "10. Đơn Vị Bầu Cử Số 10",
                "delegate_street": "",
                "delegate_street_number": "",
                "delegate_city": "",
                "result": "Bo phieu trang"
            }
],
        "missing": [
            {
                "delegate_id": 1103,
                "delegate_name": "Bùi Tuấn Anh",
                "delegate_address": "",
                "delegate_group_name": "06. Đơn Vị Bầu Cử Số 6",
                "delegate_street": "",
                "delegate_street_number": "",
                "delegate_city": ""
            }
        ]
    }
]