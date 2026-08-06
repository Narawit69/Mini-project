from datetime import datetime
import os
import streamlit as st
from pymongo import MongoClient

# 1. เชื่อมต่อกับ MongoDB
mongo_uri = st.secrets["MONGO_URI"]
client = MongoClient(mongo_uri)
db = client["worklog_db"]  # ชื่อฐานข้อมูล
collection = db["logs"]  # ชื่อ Collection

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

# --- ส่วนที่ A: ฟอร์มกรอกข้อมูลบันทึกงาน ---
with st.form("worklog_form"):
  st.subheader("📝 เพิ่มบันทึกงานใหม่")
  
  # เพิ่มช่องกรอกชื่อผู้บันทึก
  author = st.text_input("👤 ชื่อผู้บันทึกงาน (ระบุชื่อของคุณ เพื่อแยกข้อมูล)")
  
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
    if author and title and content:
      # ป้องกันการบันทึกซ้ำด้วยการเช็กสถานะการกดใน session_state
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

        # เพิ่ม field author เข้าไปในข้อมูลที่จะบันทึก
        log_data = {
            "author": author.strip(),
            "date": str(log_date),
            "title": title,
            "category": category,
            "content": content,
            "attachment": filename,
            "created_at": datetime.now(),
        }
        collection.insert_one(log_data)
        
        st.success("บันทึกข้อมูลสำเร็จเรียบร้อยแล้ว! 🎉")
        
        # รีเซ็ตสถานะแล้วสั่งรันใหม่
        st.session_state.form_submitted = False
        st.rerun()
    else:
      st.warning("กรุณากรอก **ชื่อผู้บันทึก**, หัวข้อ และรายละเอียดให้ครบถ้วนครับ")

st.divider()

# --- ส่วนที่ B: แสดงรายการบันทึกการทำงานทั้งหมด (พร้อมระบบกรองตามชื่อ) ---
st.subheader("📚 ประวัติบันทึกการทำงาน")

# ช่องค้นหา/กรองข้อมูลตามชื่อ
search_author = st.text_input("🔍 พิมพ์ชื่อของคุณเพื่อดูประวัติงานเฉพาะบุคคล:")

if search_author:
  # ดึงข้อมูลเฉพาะของชื่อที่ระบุ เรียงจากล่าสุดไปเก่าสุด
  logs = list(collection.find({"author": {"$regex": search_author.strip(), "$options": "i"}}).sort("created_at", -1))
  
  if len(logs) == 0:
    st.info(f"ยังไม่พบข้อมูลบันทึกของชื่อ '{search_author}' ครับ")
  else:
    st.write(f"ผลการค้นหาของ: **{search_author}** (พบ {len(logs)} รายการ)")
    for log in logs:
      with st.expander(f"📌 [{log['category']}] {log['title']} ({log['date']}) — โดย: {log.get('author', 'ไม่ระบุชื่อ')}"):
        st.write(f"**รายละเอียด:** {log['content']}")
        if log.get("attachment"):
          st.write(f"📎 **ไฟล์แนบ:** {log['attachment']}")
          file_path = os.path.join(UPLOAD_DIR, log["attachment"])
          if os.path.exists(file_path) and log["attachment"].lower().endswith(
              ("png", "jpg", "jpeg")
          ):
            st.image(file_path, width=400)

        # --- ปุ่มสำหรับลบข้อมูล ---
        if st.button("🗑️ ลบบันทึกนี้", key=str(log["_id"])):
          collection.delete_one({"_id": log["_id"]})
          if log.get("attachment"):
            target_file = os.path.join(UPLOAD_DIR, log["attachment"])
            if os.path.exists(target_file):
              os.remove(target_file)
          st.success("ลบข้อมูลสำเร็จแล้ว!")
          st.rerun()
else:
  st.info("💡 โปรดพิมพ์ชื่อของคุณในช่องค้นหาด้านบน เพื่อเรียกดูประวัติบันทึกงานส่วนตัวครับ")