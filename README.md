# Voting API

Python API và listener để dựng lịch sử `vote`, `attendance` và `discuss` từ app `voting`.

## Mục tiêu

Project này tách phần đọc lịch sử ra khỏi app `voting`.

Luồng chính:

1. Listener subscribe Redis monitor channel từ app `voting`
2. Listener chuẩn hóa dữ liệu history và lưu sang Redis DB riêng
3. FastAPI đọc dữ liệu history đã chuẩn hóa và trả qua API

## API hiện có

- `GET /history/vote`
- `GET /history/attendance`
- `GET /history/discuss`

Chi tiết response và mapping dữ liệu xem tại:

- [docs/history-apis.md](docs/history-apis.md)

## Cấu trúc

- `app/main.py`: FastAPI app
- `app/vote_history_listener.py`: listener nhận monitor events và ghi history
- `app/vote_history_api.py`: loader đọc dữ liệu history từ Redis
- `app/config.py`: cấu hình Redis keys, DB, monitor channel
- `tests/`: test cho API và processor

## Yêu cầu

- Python 3.9+
- Redis
- App `voting` đang publish monitor events

## Cài đặt

```bash
python3 -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m pip install -r requirements.txt
```

## Cấu hình

Các biến môi trường hỗ trợ:

- `SOURCE_REDIS_URL`
- `HISTORY_REDIS_URL`
- `SOURCE_VOTING_RESULT_KEY`
- `HISTORY_VOTE_KEY`
- `HISTORY_ATTENDANCE_KEY`
- `HISTORY_DISCUSS_KEY`
- `ACTIVE_VOTE_KEY`
- `ACTIVE_ATTENDANCE_KEY`
- `ACTIVE_DISCUSS_KEY`
- `DELEGATE_DIRECTORY_KEY`
- `MONITOR_CHANNEL`

Mặc định:

- `SOURCE_REDIS_URL=redis://localhost:6379/0`
- `HISTORY_REDIS_URL=redis://localhost:6379/1`
- `SOURCE_VOTING_RESULT_KEY=voting_result`
- `MONITOR_CHANNEL=voting_monitor_channel`

## Chạy listener

```bash
python3 -m app.vote_history_listener
```

Listener sẽ:

- listen `MONITOR_CHANNEL`
- lấy lifecycle event cho `VOTE`, `ATTENDANCE` và `DISCUSS`
- theo dõi mic events cho thảo luận (`waiting` / `talking`)
- đọc thêm snapshot `voting_result` (vote/attendance enrich)
- ghi dữ liệu history sang history Redis DB

## Chạy API

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Truy cập:

- `http://127.0.0.1:8000/history/vote`
- `http://127.0.0.1:8000/history/attendance`
- `http://127.0.0.1:8000/history/discuss`
- `http://127.0.0.1:8000/docs`

## Chạy bằng Docker Desktop

Project có sẵn:

- [Dockerfile](/Volumes/external/Projects 2/Voting/Dockerfile:1)
- [docker-compose.yml](/Volumes/external/Projects 2/Voting/docker-compose.yml:1)

Chạy:

```bash
docker compose up -d --build
```

Service được tạo:

- `api`: FastAPI trên cổng `8000`
- `listener`: process listen monitor channel và ghi history

Dừng:

```bash
docker compose down
```

Nếu muốn override Redis/channel trên Windows, tạo file `.env` cạnh `docker-compose.yml`:

```env
SOURCE_REDIS_URL=redis://10.192.202.210:6379/0
HISTORY_REDIS_URL=redis://10.192.202.210:6379/1
MONITOR_CHANNEL=voting_monitor_channel_6
```

## Verify

```bash
python3 -m pytest tests/test_vote_history_api.py tests/test_vote_history_processor.py -q
python3 -m compileall app tests
```

## Ghi chú

- `/history/vote` lấy `time` từ monitor events và enrich delegate data từ `voting_result.contact`
- `/history/attendance` lấy `time` từ `SET_START`/`SET_STOP`, còn `present`/`missing` lấy từ payload `SET_STOP(ATTENDANCE)` (`present_delegates` + `contact_missing`); live cache từ `GENERAL_VOTING_RESULT(ATTENDANCE)`; fallback `CONTACT_MISSING_EVENT.contact_voted`
- `delegate_address` là địa chỉ thật ghép từ `Street`, `StreetNumber`, `City`
- `delegate_group_name` được giữ riêng, không nhét vào `delegate_address`
