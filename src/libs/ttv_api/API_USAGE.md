# TangThuVien API notes (captured via Frida)

Nguon du lieu: log runtime tu app `com.book.truyen.tangthuvien`.

## 1) Base URL

- `https://nae.vn/ttv`
- API chinh: `https://nae.vn/ttv/ttv_apiv2/public/*`

## 2) Header thuong gap

Nhieu request cua app gui kem:

- `token: <token_hien_tai>`
- `userid: 0`
- `appname: ttv`
- `Content-Type: application/x-www-form-urlencoded` (voi POST)

## 3) Danh sach endpoint da bat duoc

### GET /ttv/android-v3.json

Muc dich: lay config app (version, force_update, store links...).

```bash
curl -s --compressed \
  'https://nae.vn/ttv/android-v3.json' \
  -H 'token: <TOKEN>' \
  -H 'userid: 0' \
  -H 'appname: ttv'
```

### GET /ttv/banner.json

Muc dich: lay du lieu banner.

```bash
curl -s --compressed \
  'https://nae.vn/ttv/banner.json' \
  -H 'token: <TOKEN>' \
  -H 'userid: 0' \
  -H 'appname: ttv'
```

### GET /ttv/ttv_apiv2/public/get_list_story_home

Muc dich: lay danh sach truyen tren trang home.

```bash
curl -s --compressed \
  'https://nae.vn/ttv/ttv_apiv2/public/get_list_story_home' \
  -H 'token: <TOKEN>' \
  -H 'userid: 0' \
  -H 'appname: ttv'
```

### POST /ttv/ttv_apiv2/public/get_token

Muc dich: xin token session cho app.

Payload (form-urlencoded):
- key form: `get_token`
- value JSON string, vi du:
  - `{"imei":"21bab69a53e003ff","token_adr":"fcm_ttv::...","token_ios":""}`

```bash
curl -s --compressed \
  'https://nae.vn/ttv/ttv_apiv2/public/get_token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'get_token={"imei":"<IMEI>","token_adr":"<FCM_TOKEN>","token_ios":""}'
```

### POST /ttv/ttv_apiv2/public/get_list_story

Muc dich: lay danh sach truyen theo mode (vi du `HotMonth`).

Payload (form-urlencoded):
- key form: `get_list_story`
- value JSON string, vi du:
  - `{"mode":"HotMonth","delta":"0","finish":"none","user_id":"0","hash":"<HASH>"}`

```bash
curl -s --compressed \
  'https://nae.vn/ttv/ttv_apiv2/public/get_list_story' \
  -H 'token: <TOKEN>' \
  -H 'userid: 0' \
  -H 'appname: ttv' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'get_list_story={"mode":"HotMonth","delta":"0","finish":"none","user_id":"0","hash":"<HASH>"}'
```

### POST /ttv/ttv_apiv2/public/get_list_chapter

Muc dich: lay danh sach chapter theo `id_story`.

Payload (form-urlencoded):
- key form: `get_list_chapter`
- value JSON string, vi du:
  - `{"id_story":"38963","delta":"0","all":"all","hash":"<HASH>"}`

```bash
curl -s --compressed \
  'https://nae.vn/ttv/ttv_apiv2/public/get_list_chapter' \
  -H 'token: <TOKEN>' \
  -H 'userid: 0' \
  -H 'appname: ttv' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'get_list_chapter={"id_story":"38963","delta":"0","all":"all","hash":"<HASH>"}'
```

### POST /ttv/ttv_apiv2/public/get_content_chapter

Muc dich: lay noi dung chapter.

Payload (form-urlencoded):
- key form: `get_content_chapter`
- value JSON string, vi du:
  - `{"id_chapter":"6912661","id_story":"38963","user_id":"0","hash":"<HASH>"}`

```bash
curl -s --compressed \
  'https://nae.vn/ttv/ttv_apiv2/public/get_content_chapter' \
  -H 'token: <TOKEN>' \
  -H 'userid: 0' \
  -H 'appname: ttv' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'get_content_chapter={"id_chapter":"6912661","id_story":"38963","user_id":"0","hash":"<HASH>"}'
```

## 4) Vi sao truoc do chi thay HASH?

- Ban da inject ca `hook_hash.js` + `hook_okhttp_body.js`.
- `hook_hash.js` log rat nhieu SHA/MD5 trong TLS => chiem het log.
- Filter host/path trong network hook truoc do qua chat nen API bi loc mat.

Hien tai da sua filter mac dinh de log API ra lai.

## 5) Cach bat API de de doc hon

Chi bat network hook (khong bat hash):

```bash
source .venv/bin/activate
.venv/bin/frida -H 127.0.0.1:27042 \
  -f com.book.truyen.tangthuvien \
  -l hook_okhttp_body.js \
  -o api_capture_only_network.log
```

Neu can hash moi them `-l hook_hash.js`.

## 6) Luu y quan trong

- Truong `hash` trong payload co kha nang duoc tinh dong (ky hoac bam theo secret trong app).
- Neu goi bang script ben ngoai, can reverse cach tao `hash` va cap nhat `token` hop le.
- Co the can cookie/session sau khi goi `get_token`.

## 7) Kiem chung: hash co bat buoc khong?

Da test truc tiep voi `get_list_chapter`:

- Co hash dung: server tra `{"status":1,"message":"succes", ...}`.
- Khong co hash: server tra trang bao tri (HTML).
- Co hash sai (`deadbeef`): server tra `{"status":0,"message":"Loi bao mat, hay khoi dong lai ung dung."}`.

Ket luan: hash la bat buoc va server co kiem tra gia tri hash.

## 8) Cach lay hash de su dung

### Cach nhanh nhat (khuyen dung): Lay hash dong tu app

Da tao san script [hook_trace_formbody.js](hook_trace_formbody.js) de hook `okhttp3.FormBody$Builder.add(...)`.
Script se in ra payload dang gui, trong do co truong `hash` day du.

Chay:

```bash
source .venv/bin/activate
.venv/bin/frida -H 127.0.0.1:27042 \
  -f com.book.truyen.tangthuvien \
  -l hook_trace_formbody.js \
  -o formbody_trace.log
```

Trong log se co dong dang:

```text
name  : get_list_chapter
value : {"id_story": "39346", "delta": "0","all": "all","hash":"4621fbdb..."}
```

Lay gia tri `hash` trong `value` roi dung lai khi goi API ngoai app.

### Tim vi tri code tao hash

`hook_trace_formbody.js` cung in stacktrace, giup tim duong di code:

- `com.book.truyen.tangthuvien.ui.read.ReadPresenter.onLoadChapter(...)`
- `com.book.truyen.tangthuvien.ui.read.ReadFrag.onLoadData(...)`
- `com.book.truyen.tangthuvien.ui.librarys.categories.StoriesPresenter.onLoadDataFirst(...)`

Tu cac class nay, ban co the tiep tuc hook sau hon (hoac decompile APK) de tim ham util tinh hash neu muon tu sinh hash 100% ben ngoai app.

## 9) Crawler khong can Frida (da tao san)

Da tao script: [crawler_ttv.py](crawler_ttv.py)

Script thuc hien flow:

1. `get_token`
2. `get_list_story`
3. `get_list_chapter`
4. `get_content_chapter` (tuy chon)

Va dung hash tu [haskmaker.py](haskmaker.py) theo cong thuc da verify.

Chay nhanh:

```bash
/home/wolf/CODE/Android/API/.venv/bin/python crawler_ttv.py --id-story 39346 --show-content
```

Tuy chinh:

```bash
/home/wolf/CODE/Android/API/.venv/bin/python crawler_ttv.py \
  --imei 21bab69a53e003ff \
  --token-adr 'fcm_ttv::test' \
  --mode HotMonth \
  --id-story 39346 \
  --show-content
```

## 10) Danh sach API tong hop (ban cung cap)

Danh sach duoi day la inventory endpoint de mo rong crawler. Khong phai tat ca da duoc verify input/hash.

- `/ttv/ttv_apiv2/public/get_comment`
- `/ttv/ttv_apiv2/public/get_content_chapter`
- `/ttv/ttv_apiv2/public/get_feed`
- `/ttv/ttv_apiv2/public/get_items`
- `/ttv/ttv_apiv2/public/get_json_story`
- `/ttv/ttv_apiv2/public/get_list_chapter`
- `/ttv/ttv_apiv2/public/get_list_story`
- `/ttv/ttv_apiv2/public/get_list_story_author`
- `/ttv/ttv_apiv2/public/get_list_story_converter`
- `/ttv/ttv_apiv2/public/get_list_story_home`
- `/ttv/ttv_apiv2/public/get_list_story_type`
- `/ttv/ttv_apiv2/public/get_notification`
- `/ttv/ttv_apiv2/public/get_rank_user`
- `/ttv/ttv_apiv2/public/get_search_story`
- `/ttv/ttv_apiv2/public/get_stories_follow`
- `/ttv/ttv_apiv2/public/get_suggest_story`
- `/ttv/ttv_apiv2/public/get_threads`
- `/ttv/ttv_apiv2/public/get_title`
- `/ttv/ttv_apiv2/public/get_token`
- `/ttv/ttv_apiv2/public/get_user_nomination`
- `/ttv/ttv_apiv2/public/get_user_shop_histories`
- `/ttv/ttv_apiv2/public/list_download`
- `/ttv/ttv_apiv2/public/login_ttv_app`
- `/ttv/ttv_apiv2/public/post_comment`
- `/ttv/ttv_apiv2/public/post_comment_error`
- `/ttv/ttv_apiv2/public/post_comment_v2`
- `/ttv/ttv_apiv2/public/post_fail`
- `/ttv/ttv_apiv2/public/post_stories_follow`
- `/ttv/ttv_apiv2/public/post_story_filter`

### Buoc tiep theo de hoan thien crawler

1. Trace payload + hash cho tung endpoint chua ro bang script `hook_trace_formbody.js`.
2. Bo sung ham hash theo endpoint vao `haskmaker.py` neu cong thuc khac nhau.
3. Them method vao `crawler_ttv.py` va test tung endpoint theo nhom `get_*` va `post_*`.
