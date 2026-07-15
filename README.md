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
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 52999 --reload
```

Truy cập:

- `http://127.0.0.1:52999/history/vote`
- `http://127.0.0.1:52999/history/attendance`
- `http://127.0.0.1:52999/history/discuss`
- `http://127.0.0.1:52999/docs`

## Chạy bằng Docker Desktop

Project có sẵn:

- [Dockerfile](/Volumes/external/Projects 2/Voting/Dockerfile:1)
- [docker-compose.yml](/Volumes/external/Projects 2/Voting/docker-compose.yml:1)
- [docker-compose.host.yml](/Volumes/external/Projects 2/Voting/docker-compose.host.yml:1) (Linux host network)

Chạy (bridge network):

```bash
docker compose up -d --build
```

### Tự chạy khi bật Docker Desktop (Windows)

Compose **không** có nút “auto start project”, nhưng có 2 lớp:

#### A. Container tự restart khi Docker engine lên (đơn giản)

1. `restart: always` (đã bật trong `docker-compose.yml`)
2. Chạy **một lần**:
   ```powershell
   docker compose up -d --build
   ```
3. Docker Desktop → **Settings → General** → bật **Start Docker Desktop when you sign in**
4. **Không** `docker compose down` khi tắt máy (down xóa container → không auto lên lại). Chỉ tắt Docker Desktop / shutdown PC.

Lần sau Docker Desktop start → `voting-api` + `voting-history-listener` tự chạy lại.

#### B. Task Scheduler ép `compose up` mỗi lần đăng nhập (chắc hơn)

1. Sửa path trong [`scripts/start-voting-api.ps1`](scripts/start-voting-api.ps1):
   ```powershell
   $ComposeDir = "D:\path\to\voting-api"
   ```
2. PowerShell **Run as Administrator** — tạo task:
   ```powershell
   $script = "D:\path\to\voting-api\scripts\start-voting-api.ps1"
   $action = New-ScheduledTaskAction -Execute "powershell.exe" `
     -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
   $trigger = New-ScheduledTaskTrigger -AtLogOn
   Register-ScheduledTask -TaskName "StartVotingApiDocker" `
     -Action $action -Trigger $trigger -Description "docker compose up voting-api when user logs on"
   ```
3. Script đợi Docker engine sẵn sàng (tối đa 5 phút) rồi `docker compose up -d`.
4. Log: `%USERPROFILE%\Documents\voting-api-docker-start.log`

### Docker Desktop Windows + Redis trong WSL2

Đây là setup phổ biến: **host Python work**, Docker bị `Timeout connecting to server`.

**Lý do:** container Docker không vào được network WSL như process Windows/WSL. Phải đi qua **Windows localhost port forward**.

**Bước 1 — Redis trong WSL bind mọi interface**

Trong WSL (`redis.conf` hoặc khi start):

```bash
# redis-server với bind 0.0.0.0 (hoặc comment bind 127.0.0.1)
redis-cli CONFIG SET protected-mode no
# kiểm tra đang listen
ss -lntp | grep 6379
```

**Bước 2 — Kiểm tra từ Windows (PowerShell)**

```powershell
Test-NetConnection 127.0.0.1 -Port 6379
```

Phải `TcpTestSucceeded : True` (WSL2 localhost forwarding).

**Bước 3 — `.env` cho Docker** (copy từ `.env.example`)

```env
SOURCE_REDIS_URL=redis://host.docker.internal:6379/0
HISTORY_REDIS_URL=redis://host.docker.internal:6379/1
MONITOR_CHANNEL=voting_monitor_channel_6
```

**Không** dùng `redis://127.0.0.1:6379` trong container (127.0.0.1 = chính container).  
**Không** trông chờ `10.192.x.x` từ Docker nếu Redis chỉ chạy local WSL.

**Bước 4 — Chạy lại**

```bash
docker compose down
docker compose up -d --build
docker compose logs -f listener
```

Log OK sẽ có `Redis ping ok` / subscribe channel.

**Bước 5 — Test từ trong container**

```bash
docker compose exec listener python -c "from redis import Redis; print(Redis.from_url('redis://host.docker.internal:6379/0', socket_connect_timeout=5).ping())"
```

Phải in `True`.

#### Nếu vẫn timeout / lỗi connect

| Check | Action |
|---|---|
| Redis chỉ bind `127.0.0.1` trong WSL | Đổi bind `0.0.0.0` |
| Windows không thấy port 6379 | Restart WSL: `wsl --shutdown`, start Redis lại |
| Docker Desktop cũ | Bật **WSL2 integration** cho distro đang chạy Redis |
| Redis remote LAN từ WSL (không local) | Container vẫn khó VPN; chạy listener trên host hoặc Linux `docker-compose.host.yml` |
| `unknown command HELLO` | Redis cũ + redis-py mới. Code dùng `protocol=2` (RESP2). **Rebuild image**: `docker compose up -d --build` |

Service được tạo:

- `api`: FastAPI trên cổng `52999`
- `listener`: process listen monitor channel và ghi history

Dừng:

```bash
docker compose down
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
