# History APIs

## Mục tiêu

Tài liệu này mô tả 3 API:

- `GET /history/vote`
- `GET /history/attendance`
- `GET /history/discuss`

Các API này không đọc trực tiếp toàn bộ dữ liệu thô từ app `voting/` tại thời điểm request. Thay vào đó:

1. Một listener riêng subscribe Redis monitor channel do app `voting/` publish.
2. Listener chuẩn hóa dữ liệu lịch sử và lưu sang một Redis DB riêng cho history.
3. API chỉ đọc dữ liệu đã chuẩn hóa từ Redis history DB.

Thiết kế này giúp:

- tách API đọc lịch sử khỏi app `voting/`
- lưu được `started_at`, `ended_at`, `duration_seconds`
- tránh phụ thuộc vào UI state của app `voting/`

---

## Thành phần chính

### 1. App nguồn `voting/`

App `voting/` publish event lên nhiều monitor channels qua:

- [voting/main.py](/Volumes/external/Projects 2/Voting/voting/main.py:966)

Config channel mặc định nằm ở:

- [voting/config.py](/Volumes/external/Projects 2/Voting/voting/config.py:15)

Trong đó channel chính dùng cho listener hiện tại là:

- `voting_monitor_channel`

### 2. Listener chuẩn hóa history

Listener nằm ở:

- [app/vote_history_listener.py](/Volumes/external/Projects 2/Voting/app/vote_history_listener.py:1)

Nhiệm vụ:

- subscribe monitor channel
- bắt lifecycle `SET_START` và `SET_STOP`
- bắt event `GENERAL_VOTING_RESULT`
- refresh delegate directory từ key nguồn `voting_result`
- lưu dữ liệu history sang Redis DB riêng
- tự reconnect khi Redis/pubsub lỗi
- chống crash khi gặp payload lỗi
- recover active session dang dở sau khi process restart

### 3. API đọc history

FastAPI app nằm ở:

- [app/main.py](/Volumes/external/Projects 2/Voting/app/main.py:1)

Loader đọc history nằm ở:

- [app/vote_history_api.py](/Volumes/external/Projects 2/Voting/app/vote_history_api.py:1)

---

## Redis và cấu hình

Config hiện tại nằm ở:

- [app/config.py](/Volumes/external/Projects 2/Voting/app/config.py:1)

### Redis nguồn

Redis nguồn là nơi app `voting/` đang ghi dữ liệu vận hành:

- `SOURCE_REDIS_URL`
- mặc định: `redis://localhost:6379/0`

Key nguồn:

- `SOURCE_VOTING_RESULT_KEY`
- mặc định: `voting_result`

### Redis history

Redis history là nơi listener lưu dữ liệu đã chuẩn hóa:

- `HISTORY_REDIS_URL`
- mặc định: `redis://localhost:6379/1`

Các key chính:

- `HISTORY_VOTE_KEY`
- mặc định: `vote_history`
- `HISTORY_ATTENDANCE_KEY`
- mặc định: `attendance_history`
- `HISTORY_DISCUSS_KEY`
- mặc định: `discuss_history`
- `ACTIVE_VOTE_KEY`
- mặc định: `vote_history_active`
- `ACTIVE_ATTENDANCE_KEY`
- mặc định: `attendance_history_active`
- `ACTIVE_DISCUSS_KEY`
- mặc định: `discuss_history_active`
- `DELEGATE_DIRECTORY_KEY`
- mặc định: `delegate_directory`

### Monitor channel

- `MONITOR_CHANNEL`
- mặc định: `voting_monitor_channel`

---

## Dữ liệu lấy từ app `voting/`

### 1. Event monitor

Listener đọc event monitor do app `voting/` publish.

Các event quan trọng:

- `SET_START`
- `SET_STOP`
- `GENERAL_VOTING_RESULT`

### 2. Key nguồn `voting_result`

Listener dùng key `voting_result` làm fallback/snapshot nguồn để enrich thông tin đại biểu.

Shape dữ liệu nguồn hiện tại:

```json
{
  "contact": {
    "1200": {
      "Id": 1200,
      "Name": "Nguyen Duy Chinh",
      "GroupName": "10. Don Vi Bau Cu So 10",
      "Street": "",
      "StreetNumber": "",
      "City": ""
    }
  },
  "contact_missing": [],
  "vote": {
    "ATTENDANCE": [
      {
        "1200": "diemdanh"
      }
    ],
    "VOTE": [
      {
        "1103": "Tan thanh"
      }
    ]
  }
}
```

---

## Delegate directory

Listener duy trì một delegate directory trong Redis history:

- key: `delegate_directory`

Mục đích:

- map `delegate_id` sang thông tin hiển thị
- tái sử dụng cho cả vote history và attendance history

### Nguồn dữ liệu directory

Directory được refresh từ `voting_result.contact`.

Hiện tại monitor event điểm danh không mang full contact data, nên source tin cậy nhất vẫn là:

- `contact.Name`
- `contact.GroupName`
- `contact.Street`
- `contact.StreetNumber`
- `contact.City`

### Quy tắc build địa chỉ

Mỗi delegate trong directory giữ đồng thời:

- `delegate_group_name`
- `delegate_street`
- `delegate_street_number`
- `delegate_city`
- `delegate_address`

Trong đó:

- `delegate_address` là chuỗi ghép từ `Street`, `StreetNumber`, `City`
- nếu thiếu thì để chuỗi rỗng `""`
- `GroupName` không được nhét vào `delegate_address`
- `GroupName` giữ riêng ở `delegate_group_name`

Ví dụ:

```json
{
  "1200": {
    "delegate_id": 1200,
    "delegate_name": "Nguyen Duy Chinh",
    "delegate_address": "",
    "delegate_group_name": "10. Don Vi Bau Cu So 10",
    "delegate_street": "",
    "delegate_street_number": "",
    "delegate_city": ""
  }
}
```

---

## API 1: `GET /history/vote`

### Mục đích

Trả lịch sử biểu quyết đã được chuẩn hóa theo từng lượt.

### Cách dữ liệu được tạo

Listener xử lý như sau:

1. Nhận `SET_START` với `display=VOTE`
2. Tạo active vote session mới
3. Nhận `GENERAL_VOTING_RESULT` với `display=VOTE`
4. Đọc `voting_results` và `meeting_voting_options`
5. Map `delegate_id -> result`
6. Nhận `SET_STOP` với `display=VOTE`
7. Gắn `ended_at`, tính `duration_seconds`
8. Enrich bằng delegate directory
9. Append vào key `vote_history`

### Dữ liệu vote lấy từ đâu

Từ monitor event:

- `payload.voting_results`
- `payload.meeting_voting_options.VOTE`

Listener dùng `voting_option_id` để map sang tên kết quả như:

- `Tan thanh`
- `Khong tan thanh`
- `Bo phieu trang`

### Time vote lấy từ đâu

Không lấy từ timer event của app `voting/`.

Hiện tại time được suy ra từ:

- `started_at`: lúc listener nhận `SET_START` cho `display=VOTE`
- `ended_at`: lúc listener nhận `SET_STOP` cho `display=VOTE`
- `duration_seconds`: hiệu số giữa `ended_at` và `started_at`

### Live vs completed

Listener **upsert** session vào `vote_history` liên tục:

- `SET_START` / live results → `status: "in_progress"`, `ended_at: null`
- `SET_STOP` → cùng `vote_index` được cập nhật, có `ended_at` / `duration_seconds`, bỏ `status` (hoặc status recover)

API `GET /history/vote` đọc key history nên **thấy data ngay khi đang vote**, không cần chờ Stop.

### Response mẫu

```json
[
  {
    "vote_index": 1,
    "started_at": "2026-07-09T11:15:03+07:00",
    "ended_at": "2026-07-09T11:16:22+07:00",
    "duration_seconds": 79,
    "items": [
      {
        "delegate_id": 1103,
        "delegate_name": "Bui Tuan Anh",
        "delegate_address": "12 Tran Hung Dao, Ha Noi",
        "delegate_group_name": "06. Don Vi Bau Cu So 6",
        "delegate_street": "12 Tran Hung Dao",
        "delegate_street_number": "",
        "delegate_city": "Ha Noi",
        "result": "Tan thanh"
      },
      {
        "delegate_id": 1104,
        "delegate_name": "Trinh Quang Anh",
        "delegate_address": "",
        "delegate_group_name": "11. Don Vi Bau Cu So 11",
        "delegate_street": "",
        "delegate_street_number": "",
        "delegate_city": "",
        "result": "Khong tan thanh"
      }
    ]
  }
]
```

### Redis key API đọc

- `vote_history`

### Khi key chưa tồn tại

API trả **200** với list rỗng:

```json
[]
```

---

## API 2: `GET /history/attendance`

### Mục đích

Trả lịch sử điểm danh theo từng lượt, gồm:

- danh sách `present`
- danh sách `missing`
- thời gian bắt đầu/kết thúc

### Cách dữ liệu được tạo

Listener xử lý như sau (khớp app `voting/` hiện tại):

1. Nhận `SET_START` với `display=ATTENDANCE` → tạo active session (`started_at`)
2. Nhận `GENERAL_VOTING_RESULT` với `display=ATTENDANCE` → cache live `present_delegates` + `contact_missing` (nếu có)
3. Nhận `SET_STOP` với `display=ATTENDANCE` → **chốt history** từ payload:
   - `present` ← `payload.present_delegates`
   - `missing` ← `payload.contact_missing`
   - `ended_at` ← thời điểm nhận event
4. Nhận `SET_CLEAR` với `display=ATTENDANCE` → xóa active + toàn bộ `attendance_history`
5. (Fallback) `CONTACT_MISSING_EVENT` nếu active session còn mở — dùng `present_delegates` hoặc alias `contact_voted`

### Dữ liệu attendance lấy từ đâu

Nguồn chính từ **monitor events** do app `voting/` publish (không phụ thuộc mở màn CONTACT_MISSING):

| Event | Fields |
|---|---|
| `SET_START(ATTENDANCE)` | `present_delegates`, `contact_missing` (thường rỗng/all) |
| `GENERAL_VOTING_RESULT(ATTENDANCE)` | `present_delegates`, `contact_missing`, `online`, `total` |
| `SET_STOP(ATTENDANCE)` | `present_delegates`, `contact_missing` — **chốt history** |
| `SET_CLEAR(ATTENDANCE)` | snapshot lists + xóa data màn |
| `CONTACT_MISSING_EVENT` | `contact_voted` (= present), `contact_missing` — fallback |

App `voting/` cũng ghi snapshot Redis key `attendance_result` (source DB); listener history **ưu tiên monitor payload**.

### Time attendance lấy từ đâu

- `started_at`: `SET_START(display=ATTENDANCE)`
- `ended_at`: `SET_STOP(display=ATTENDANCE)` (hoặc timestamp `CONTACT_MISSING_EVENT` nếu fallback)
- `duration_seconds`: hiệu số `ended_at - started_at`

### Response mẫu

```json
[
  {
    "attendance_index": 1,
    "started_at": "2026-07-09T10:15:03+07:00",
    "ended_at": "2026-07-09T10:16:22+07:00",
    "duration_seconds": 79,
    "present": [
      {
        "delegate_id": 1200,
        "delegate_name": "Nguyen Duy Chinh",
        "delegate_address": "",
        "delegate_group_name": "10. Don Vi Bau Cu So 10",
        "delegate_street": "",
        "delegate_street_number": "",
        "delegate_city": "",
        "result": "diemdanh"
      }
    ],
    "missing": [
      {
        "delegate_id": 1103,
        "delegate_name": "Bui Tuan Anh",
        "delegate_address": "12 Tran Hung Dao, Ha Noi",
        "delegate_group_name": "06. Don Vi Bau Cu So 6",
        "delegate_street": "12 Tran Hung Dao",
        "delegate_street_number": "",
        "delegate_city": "Ha Noi"
      }
    ]
  }
]
```

### Redis key API đọc

- `attendance_history`

### Khi key chưa tồn tại

API trả **200** với list rỗng:

```json
[]
```

---

## API 3: `GET /history/discuss`

### Mục đích

Trả lịch sử thảo luận theo từng phiên, gồm:

- danh sách `waiting` (đang chờ phát biểu)
- danh sách `talking` (đang phát biểu)
- timeline `events` khi mic đổi trạng thái
- thời gian bắt đầu/kết thúc

### Cách dữ liệu được tạo

Listener xử lý như sau:

1. Nhận `SET_START` với `display=DISCUSS` (hoặc `CHAT`)
2. Tạo active discuss session
3. Nhận `MIC_STATE_CHANGED_IN_RUNNING_MEETING` → cập nhật `waiting`/`talking` và append event
4. Nhận `SET_STOP` với `display=DISCUSS` → chốt `ended_at`, append vào `discuss_history`
5. Nhận `SET_CLEAR` với `display=DISCUSS` → xóa active + toàn bộ `discuss_history`

### Dữ liệu discuss lấy từ đâu

Từ monitor event mic:

- `payload.waiting` / `payload.talking` (chuỗi `"id*/*display"`)
- `payload.waiting_delegates` / `payload.talking_delegates` (ưu tiên nếu có)
- `payload.state` (`Request` / `On` / `Off` / `MicResetEvent`)

### Response mẫu

```json
[
  {
    "discuss_index": 1,
    "display": "DISCUSS",
    "started_at": "2026-07-09T14:00:00+07:00",
    "ended_at": "2026-07-09T14:10:00+07:00",
    "duration_seconds": 600,
    "waiting": [
      {"delegate_id": 1103, "display": "Bui Tuan Anh"}
    ],
    "talking": [
      {"delegate_id": 1200, "display": "Nguyen Duy Chinh"}
    ],
    "events": [
      {
        "at": "2026-07-09T14:01:00+07:00",
        "state": "On",
        "waiting": [{"delegate_id": 1103, "display": "Bui Tuan Anh"}],
        "talking": [{"delegate_id": 1200, "display": "Nguyen Duy Chinh"}]
      }
    ]
  }
]
```

### Redis key API đọc

- `discuss_history`

### Khi key chưa tồn tại

API trả **200** với list rỗng:

```json
[]
```

---

## Chạy hệ thống

### 1. Chạy listener

```bash
python3 -m app.vote_history_listener
```

Listener sẽ:

- subscribe `MONITOR_CHANNEL`
- đọc event từ Redis nguồn
- ghi history sang Redis history DB

### Hardening hiện có

Listener hiện đã có:

- `try/except` cho từng message
- validate monitor payload trước khi xử lý
- reconnect loop với exponential backoff khi Redis/pubsub lỗi
- recovery cho `vote_history_active`, `attendance_history_active` và `discuss_history_active`

Khi recover active session dang dở, listener sẽ chốt session đó vào history với:

- `status: "incomplete_recovered"`

### 2. Chạy API

```bash
python3 -m uvicorn app.main:app --reload
```

### 3. Gọi API

```bash
curl http://127.0.0.1:52999/history/vote
curl http://127.0.0.1:52999/history/attendance
curl http://127.0.0.1:52999/history/discuss
```

---

## Mapping dữ liệu từ app `voting/`

### Vote history

| Nguồn | Đích |
|---|---|
| `SET_START(display=VOTE)` | `started_at` |
| `SET_STOP(display=VOTE)` | `ended_at` |
| `GENERAL_VOTING_RESULT.payload.voting_results[].delegate_id` | `items[].delegate_id` |
| `GENERAL_VOTING_RESULT.payload.meeting_voting_options.VOTE` | `items[].result` |
| `voting_result.contact[id].Name` | `items[].delegate_name` |
| `voting_result.contact[id].GroupName` | `items[].delegate_group_name` |
| `voting_result.contact[id].Street/StreetNumber/City` | `items[].delegate_address`, `delegate_street`, `delegate_street_number`, `delegate_city` |

### Attendance history

| Nguồn | Đích |
|---|---|
| `SET_START(display=ATTENDANCE)` | `started_at` |
| `SET_STOP(display=ATTENDANCE)` | `ended_at` |
| `CONTACT_MISSING_EVENT.payload.present_delegates` | `present[]` (kèm `result="diemdanh"`) |
| `CONTACT_MISSING_EVENT.payload.contact_missing` | `missing[]` |
| `<contact_info>.Id` | `delegate_id` |
| `<contact_info>.Name` | `delegate_name` |
| `<contact_info>.GroupName` | `delegate_group_name` |
| `<contact_info>.Street/StreetNumber/City` | `delegate_address`, `delegate_street`, `delegate_street_number`, `delegate_city` |

---

## Giới hạn hiện tại

1. Vote time và attendance time hiện là thời điểm listener nhận lifecycle event, không phải timer nội bộ CoCon.

2. Attendance history được chốt khi nhận `CONTACT_MISSING_EVENT` (đến sau `SET_STOP(ATTENDANCE)`), không phải ngay lúc `SET_STOP`. Nếu một lượt attendance không có `CONTACT_MISSING_EVENT` theo sau thì session sẽ không được chốt vào history.

3. Vote vẫn phụ thuộc `voting_result.contact` để lấy delegate detail; nếu contact chưa cập nhật đúng thời điểm, vote history có thể thiếu một phần contact fields. Attendance thì không, vì lấy trực tiếp từ `present_delegates` / `contact_missing`.

---

## Kiểm thử hiện có

Test nằm ở:

- [tests/test_vote_history_api.py](/Volumes/external/Projects 2/Voting/tests/test_vote_history_api.py:1)
- [tests/test_vote_history_processor.py](/Volumes/external/Projects 2/Voting/tests/test_vote_history_processor.py:1)

Các nhóm test chính:

- vote history API
- attendance history API
- vote processor
- attendance processor
- delegate directory refresh

Lệnh verify:

```bash
python3 -m pytest tests/test_vote_history_api.py tests/test_vote_history_processor.py -q
python3 -m compileall app tests
```

---

## Gợi ý mở rộng

1. Nếu muốn time chính xác hơn, cần lưu thêm timer event hoặc raw event timestamp ở producer.

2. Nếu muốn bỏ phụ thuộc vào `voting_result` cho attendance, app `voting/` cần publish đầy đủ `delegate_id` và contact info trên monitor event điểm danh.

3. Nếu muốn query theo thời gian hoặc pagination, có thể đổi từ lưu JSON list sang Redis sorted set hoặc database quan hệ.
