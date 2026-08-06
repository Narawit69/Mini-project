from datetime import datetime
import os
import streamlit as st
from pymongo import MongoClient

# 1. เชื่อมต่อกับ MongoDB
mongo_uri = st.secrets["MONGO_URI"]
client = MongoClient(mongo_uri)
db = client["worklog_db"]
collection = db["logs"]

# 2. กำหนด Path สำหรับเก็บไฟล์
UPLOAD_DIR = "./data_volumes"
if not os.path.exists(UPLOAD_DIR):
  os.makedirs(UPLOAD_DIR)

# 3. ออกแบบหน้าตาเว็บแอปด้วย Streamlit
st.title("💻 My Daily Work Log")
st.write(
    "ระบบบันทึกรายงานการทำงานประจำวัน (เก็บ Text ลง MongoDB และเก็บไฟล์ลง"
    " Storage)"
)

# --- ระบบระบุตัวตน (Session User) เพื่อความปลอดภัย ---
st.sidebar.header("🔐 ตั้งค่าผู้ใช้งาน")
current_user = st.sidebar.text_input("ระบุชื่อของคุณเพื่อเข้าใช้งาน:", value="")

if not current_user.strip():
  st.warning("⚠️ กรุณากรอกชื่อของคุณที่แถบด้านข้าง (Sidebar) ซ้ายมือ เพื่อเริ่มต้นใช้งานระบบครับ")
  st.stop() # หยุดการทำงานหน้าเว็บส่วนที่เหลือไว้ก่อน จนกว่าจะใส่ชื่อ
else:
  st.sidebar.success(f"กำลังใช้งานในนาม: **{current_user.strip()}**")

# --- ส่วนที่ A: ฟอร์มกรอกข้อมูลบันทึกงาน ---
with st.form("worklog_form"):
  st.subheader(f"📝 เพิ่มบันทึกงานใหม่ (ผู้บันทึก: {current_user.strip()})")
  
  log_date = st.date_input("วันที่ปฏิบัติงาน", datetime.today())
  title = st.text_input("หัวข้อเรื่อง / งานที่ทำ")
  category = st.selectbox(
      "หมวดหมู่งาน", ["Coding", "Meeting", "Debugging", "Learning", "Other"]
  )
  content = st.text_area("รายละเอียดการทำงาน")

  uploaded_file = st.file_uploader(
      "แนบไฟล์หลักฐาน (รูปภาพ/เอกสาร/วิดีโอ)", 
      type=["png", "jpg", "jpeg", "pdf", "mp4", "mov", "avi"]
  )

  submitted = st.form_submit_button("บันทึกข้อมูล")

  if submitted:
    if title and content:
      if "form_submitted" not in st.session_state:
        st.session_state.form_submitted = False

      if not st.session_state.form_submitted:
        st.session_state.form_submitted = True

        filename = ""
        if uploaded_file is not None:
          filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
          file_path = os.path.join(UPLOAD_DIR, filename)
          with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # บันทึกโดยอิงจากชื่อใน Sidebar อัตโนมัติ (ปลอมแปลงไม่ได้)
        log_data = {
            "author": current_user.strip(),
            "date": str(log_date),
            "title": title,
            "category": category,
            "content": content,
            "attachment": filename,
            "created_at": datetime.now(),
        }
        collection.insert_one(log_data)
        
        st.success("บันทึกข้อมูลสำเร็จเรียบร้อยแล้ว! 🎉")
        st.session_state.form_submitted = False
        st.rerun()
    else:
      st.warning("กรุณากรอกหัวข้อและรายละเอียดให้ครบถ้วนครับ")

st.divider()

# --- ส่วนที่ B: แสดงเฉพาะประวัติ "ของฉันเอง" เท่านั้น ---
st.subheader(f"📚 ประวัติบันทึกการทำงานของ: {current_user.strip()}")

# ดึงข้อมูลเฉพาะของ "ชื่อที่กำลัง Login อยู่ตอนนี้" เท่านั้น 
# ตัดช่องค้นหาทิ้งไปเลย ป้องกันการแอบดูและแอบลบของคนอื่น
user_logs = list(collection.find({"author": {"$regex": f"^{current_user.strip()}$", "$options": "i"}}).sort("created_at", -1))

if len(user_logs) == 0:
  st.info(f"ยังไม่มีประวัติบันทึกงานของคุณ ({current_user.strip()}) เริ่มเพิ่มข้อมูลกันเลย!")
else:
  st.write(f"พบข้อมูลทั้งหมด {len(user_logs)} รายการ")
  for log in user_logs:
    with st.expander(f"📌 [{log['category']}] {log['title']} ({log['date']})"):
      st.write(f"**รายละเอียด:** {log['content']}")
      
      if log.get("attachment"):
        st.write(f"📎 **ไฟล์แนบ:** {log['attachment']}")
        file_path = os.path.join(UPLOAD_DIR, log["attachment"])
        
        if os.path.exists(file_path):
          if log["attachment"].lower().endswith(("png", "jpg", "jpeg")):
            st.image(file_path, width=400)
          elif log["attachment"].lower().endswith(("mp4", "mov", "avi")):
            st.video(file_path)

      # เนื่องจากหน้านี้แสดงเฉพาะข้อมูลของเจ้าของชื่ออยู่แล้ว ปุ่มลบนี้จึงปลอดภัย 100%
      if st.button("🗑️ ลบบันทึกนี้", key=str(log["_id"])):
        collection.delete_one({"_id": log["_id"]})
        if log.get("attachment"):
          target_file = os.path.join(UPLOAD_DIR, log["attachment"])
          if os.path.exists(target_file):
            os.remove(target_file)
        st.success("ลบข้อมูลสำเร็จแล้ว!")
        st.rerun()