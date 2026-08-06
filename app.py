from datetime import datetime
import os
import streamlit as st
from pymongo import MongoClient

# 1. เชื่อมต่อกับ MongoDB (ที่รันอยู่บน Docker พอร์ต 27017)
mongo_uri = st.secrets["MONGO_URI"]
client = MongoClient(mongo_uri)
db = client["worklog_db"]  # ชื่อฐานข้อมูล
collection = db["logs"]  # ชื่อ Collection

# 2. กำหนด Path สำหรับเก็บไฟล์ (จำลองการเก็บลง Docker Volume / โฟลเดอร์ในเครื่อง)
UPLOAD_DIR = "./data_volumes"
if not os.path.exists(UPLOAD_DIR):
  os.makedirs(UPLOAD_DIR)

# 3. ออกแบบหน้าตาเว็บแอปด้วย Streamlit
st.title("💻 My Daily Work Log App")
st.write(
    "ระบบบันทึกรายงานการทำงานประจำวัน (เก็บ Text ลง MongoDB และเก็บไฟล์ลง"
    " Storage)"
)

# --- ส่วนที่ A: ฟอร์มกรอกข้อมูลบันทึกงาน ---
with st.form("worklog_form"):
  st.subheader("📝 เพิ่มบันทึกงานใหม่")
  log_date = st.date_input("วันที่ปฏิบัติงาน", datetime.today())
  title = st.text_input("หัวข้อเรื่อง / งานที่ทำ")
  category = st.selectbox(
      "หมวดหมู่งาน", ["Coding", "Meeting", "Debugging", "Other"]
  )
  content = st.text_area("รายละเอียดการทำงาน")

  # ช่องอัปโหลดไฟล์ (เช่น ภาพ Screenshot หรือโค้ด)
  uploaded_file = st.file_uploader(
      "แนบไฟล์หลักฐาน (รูปภาพ/เอกสาร)", type=["png", "jpg", "jpeg", "pdf"]
  )

  submitted = st.form_submit_button("บันทึกข้อมูล")

  if submitted:
    if title and content:
      filename = ""
      # ถ้ามีการอัปโหลดไฟล์ ให้บันทึกไฟล์เก็บไว้ใน Volume Directory
      if uploaded_file is not None:
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
          f.write(uploaded_file.getbuffer())

      # บันทึกข้อมูล Text ลง MongoDB
      log_data = {
          "date": str(log_date),
          "title": title,
          "category": category,
          "content": content,
          "attachment": filename,
          "created_at": datetime.now(),
      }
      collection.insert_one(log_data)
      st.success("บันทึกข้อมูลสำเร็จเรียบร้อยแล้ว! 🎉")
    else:
      st.warning("กรุณากรอกหัวข้อและรายละเอียดให้ครบถ้วนครับ")

st.divider()

# --- ส่วนที่ B: แสดงรายการบันทึกย้อนหลังทั้งหมดจาก MongoDB ---
st.subheader("📚 ประวัติบันทึกการทำงานทั้งหมด")

# ดึงข้อมูลจาก MongoDB เรียงจากล่าสุดไปเก่าสุด
logs = list(collection.find().sort("created_at", -1))

if len(logs) == 0:
  st.info("ยังไม่มีข้อมูลบันทึกการทำงาน เริ่มเพิ่มข้อมูลกันเลย!")
else:
  for log in logs:
    with st.expander(f"📌 [{log['category']}] {log['title']} ({log['date']})"):
      st.write(f"**รายละเอียด:** {log['content']}")
      if log.get("attachment"):
        st.write(f"📎 **ไฟล์แนบ:** {log['attachment']}")
        # หากต้องการแสดงรูปภาพที่อัปโหลด (ถ้าเป็นไฟล์รูป)
        file_path = os.path.join(UPLOAD_DIR, log["attachment"])
        if os.path.exists(file_path) and log["attachment"].lower().endswith(
            ("png", "jpg", "jpeg")
        ):
          st.image(file_path, width=400)