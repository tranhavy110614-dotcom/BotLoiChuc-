import os
import requests
import firebase_admin
from firebase_admin import credentials, db
import google.generativeai as genai
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ==========================================
# 1. CẤU HÌNH CÁC BIẾN MÔI TRƯỜNG (ENVIRONMENT VARIABLES)
# ==========================================
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "my_secret_key")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL")

# ==========================================
# 2. KHỞI TẠO GEMINI AI & FIREBASE
# ==========================================
# Khởi tạo Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Khởi tạo Firebase từ file firebase_key.json
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': FIREBASE_DB_URL
})

# ==========================================
# 3. HÀM TƯƠNG TÁC VỚI CƠ SỞ DỮ LIỆU FIREBASE
# ==========================================
def save_role(role, sender_id):
    """Lưu ID người dùng vào Firebase theo vai trò"""
    ref = db.reference('users')
    if role == 'banbe':
        friends = ref.child('banbe').get() or []
        if sender_id not in friends:
            friends.append(sender_id)
            ref.child('banbe').set(friends)
    else:
        ref.child(role).set(sender_id)

def get_users():
    """Lấy danh sách ID đã đăng ký từ Firebase"""
    ref = db.reference('users')
    return ref.get() or {}

# ==========================================
# 4. HÀM GỬI TIN NHẮN MESSENGER & TẠO LỜI CHÚC
# ==========================================
def send_msg(user_id, text):
    """Gửi tin nhắn phản hồi qua Messenger Graph API"""
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": user_id},
        "message": {"text": text}
    }
    requests.post(url, json=payload)

def tao_loi_chuc(doi_tuong, thoi_gian):
    """Gọi Gemini AI tạo lời chúc tự nhiên"""
    prompt = f"Viết 1 lời chúc buổi {thoi_gian} ngắn gọn, tự nhiên, tràn đầy tình cảm gửi cho {doi_tuong} (kèm 1-2 icon phù hợp). Tuyệt đối không để lời chúc trong dấu ngoặc kép."
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Lỗi gọi Gemini AI: {e}")
        return f"Chúc {doi_tuong} một buổi {thoi_gian} luôn ngập tràn niềm vui và bình an nhé! ❤️"

# ==========================================
# 5. TỰ ĐỘNG GỬI TIN NHẮN THEO KHUNG GIỜ
# ==========================================
def gui_tin_nhan_theo_khung_gio(thoi_gian):
    """Lấy ID từ Firebase và tự động gửi tin nhắn cho từng đối tượng"""
    data = get_users()
    
    # 1. Gửi cho Mẹ
    if "me" in data and data["me"]:
        send_msg(data["me"], tao_loi_chuc("Mẹ", thoi_gian))
        
    # 2. Gửi cho Bà
    if "ba" in data and data["ba"]:
        send_msg(data["ba"], tao_loi_chuc("Bà", thoi_gian))
        
    # 3. Gửi cho Danh sách Bạn bè
    if "banbe" in data and isinstance(data["banbe"], list):
        for user_id in data["banbe"]:
            send_msg(user_id, tao_loi_chuc("bạn thân", thoi_gian))

# Lập lịch tự động chạy theo giờ Việt Nam (Asia/Ho_Chi_Minh)
scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
scheduler.add_job(lambda: gui_tin_nhan_theo_khung_gio("sáng"), 'cron', hour=7, minute=0)
scheduler.add_job(lambda: gui_tin_nhan_theo_khung_gio("trưa"), 'cron', hour=11, minute=30)
scheduler.add_job(lambda: gui_tin_nhan_theo_khung_gio("chiều"), 'cron', hour=17, minute=0)
scheduler.add_job(lambda: gui_tin_nhan_theo_khung_gio("tối"), 'cron', hour=21, minute=0)
scheduler.start()

# ==========================================
# 6. MÃ NGUỒN WEBHOOK KẾT NỐI MESSENGER
# ==========================================
@app.route('/webhook', methods=['GET'])
def verify():
    """Xác thực Webhook với Facebook Developer"""
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Wrong token", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    """Xử lý tin nhắn đến từ người dùng"""
    req_data = request.get_json()
    for entry in req_data.get("entry", []):
        for msg_event in entry.get("messaging", []):
            sender_id = msg_event["sender"]["id"]
            if "message" in msg_event and "text" in msg_event["message"]:
                text = msg_event["message"]["text"].upper().strip()
                users = get_users()
                
                # Cú pháp 1: Đăng ký Mẹ
                if text == "DK ME":
                    if "me" in users and users["me"]:
                        send_msg(sender_id, "Tài khoản Mẹ đã có người đăng ký rồi ạ!")
                    else:
                        save_role("me", sender_id)
                        send_msg(sender_id, "Chào Mẹ! Bot đã kích hoạt thành công. Hàng ngày bot sẽ tự động nhắn tin chúc Mẹ! ❤️")
                
                # Cú pháp 2: Đăng ký Bà
                elif text in ["DK BA", "DK3"]:
                    if "ba" in users and users["ba"]:
                        send_msg(sender_id, "Tài khoản Bà đã có người đăng ký rồi ạ!")
                    else:
                        save_role("ba", sender_id)
                        send_msg(sender_id, "Cháu chào Bà! Bot đã kích hoạt thành công để tự động gửi lời chúc cho Bà rồi ạ! ❤️")
                
                # Cú pháp 3: Đăng ký Bạn
                elif text == "DK BAN":
                    save_role("banbe", sender_id)
                    send_msg(sender_id, "Alo bạn! Đã đăng ký nhận lời chúc tự động thành công!")
                    
    return "OK", 200

# ==========================================
# 7. KHỞI CHẠY FLASK SERVER
# ==========================================
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))